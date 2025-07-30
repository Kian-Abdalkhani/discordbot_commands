import pytest
import asyncio
import json
import os
import tempfile
import shutil
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.utils.currency_manager import CurrencyManager
from src.cogs.blackjack import BlackjackCog
from src.cogs.hangman import HangmanCog
from src.config.settings import DAILY_CLAIM, HANGMAN_DAILY_BONUS, BLACKJACK_PAYOUT_MULTIPLIER


class TestCurrencyIntegration:
    """Integration tests to ensure shared CurrencyManager usage across cogs and prevent data corruption"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for testing file operations"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    async def create_shared_test_setup(self, temp_data_dir):
        """Create shared test setup with bot and cogs"""
        # Create mock bot
        mock_bot = MagicMock()
        
        # Create shared currency manager
        currency_manager = CurrencyManager()
        currency_manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        await currency_manager.initialize()
        
        # Attach to bot
        mock_bot.currency_manager = currency_manager
        
        # Create cogs
        blackjack_cog = BlackjackCog(mock_bot)
        hangman_cog = HangmanCog(mock_bot)
        
        # Mock stats files
        blackjack_cog.stats_file = os.path.join(temp_data_dir, "blackjack_stats.json")
        hangman_cog.stats_file = os.path.join(temp_data_dir, "hangman_stats.json")
        
        await blackjack_cog.load_blackjack_stats()
        await hangman_cog.load_hangman_stats()
        
        return mock_bot, blackjack_cog, hangman_cog

    @pytest.mark.asyncio
    async def test_shared_currency_manager_instance(self, temp_data_dir):
        """Test that both cogs use the same currency manager instance"""
        bot, bj_cog, hm_cog = await self.create_shared_test_setup(temp_data_dir)
        
        # Verify both cogs reference the same currency manager instance
        assert bj_cog.currency_manager is hm_cog.currency_manager
        assert bj_cog.bot.currency_manager is hm_cog.bot.currency_manager
        
        # Verify it's the same object in memory
        assert id(bj_cog.currency_manager) == id(hm_cog.currency_manager)

    @pytest.mark.asyncio
    async def test_cogs_do_not_create_new_currency_manager(self, temp_data_dir):
        """Test that cogs use bot.currency_manager instead of creating new instances"""
        bot, bj_cog, hm_cog = await self.create_shared_test_setup(temp_data_dir)
        original_manager = bot.currency_manager
        
        # Verify they use the shared instance, not new ones
        assert bj_cog.currency_manager is original_manager
        assert hm_cog.currency_manager is original_manager
        
        # Ensure no new CurrencyManager instances were created
        with patch('src.utils.currency_manager.CurrencyManager') as mock_currency_class:
            # Creating new cogs should not instantiate new CurrencyManager
            new_blackjack = BlackjackCog(bot)
            new_hangman = HangmanCog(bot)
            
            # CurrencyManager constructor should not be called
            mock_currency_class.assert_not_called()
            
            # But they should still reference the shared instance
            assert new_blackjack.currency_manager is original_manager
            assert new_hangman.currency_manager is original_manager

    @pytest.mark.asyncio
    async def test_cross_cog_currency_consistency(self, temp_data_dir):
        """Test that currency operations from different cogs maintain consistency"""
        bot, bj_cog, hm_cog = await self.create_shared_test_setup(temp_data_dir)
        user_id = "test_user_123"
        
        # Start with fresh user
        initial_balance = await bj_cog.currency_manager.get_balance(user_id)
        
        # Blackjack adds currency
        await bj_cog.currency_manager.add_currency(user_id, 1000)
        balance_after_blackjack = await bj_cog.currency_manager.get_balance(user_id)
        
        # Hangman should see the same balance
        balance_from_hangman = await hm_cog.currency_manager.get_balance(user_id)
        assert balance_from_hangman == balance_after_blackjack
        assert balance_from_hangman == initial_balance + 1000
        
        # Hangman subtracts currency
        success, new_balance = await hm_cog.currency_manager.subtract_currency(user_id, 500)
        assert success is True
        
        # Blackjack should see the updated balance
        balance_from_blackjack = await bj_cog.currency_manager.get_balance(user_id)
        assert balance_from_blackjack == new_balance
        assert balance_from_blackjack == initial_balance + 500

    @pytest.mark.asyncio
    async def test_concurrent_operations_across_cogs(self, blackjack_cog, hangman_cog):
        """Test concurrent currency operations from different cogs maintain data integrity"""
        user_id = "concurrent_test_user"
        
        # Get initial balance
        initial_balance = await blackjack_cog.currency_manager.get_balance(user_id)
        
        async def blackjack_operations():
            """Simulate blackjack game operations"""
            await blackjack_cog.currency_manager.add_currency(user_id, 500)  # Win
            await blackjack_cog.currency_manager.subtract_currency(user_id, 100)  # Bet
            await blackjack_cog.currency_manager.add_currency(user_id, 200)  # Another win
        
        async def hangman_operations():
            """Simulate hangman game operations"""
            await hangman_cog.currency_manager.add_currency(user_id, 300)  # Win bonus
            await hangman_cog.currency_manager.subtract_currency(user_id, 50)  # Some cost
            await hangman_cog.currency_manager.add_currency(user_id, 100)  # Another bonus
        
        # Run operations concurrently
        await asyncio.gather(
            blackjack_operations(),
            hangman_operations()
        )
        
        # Calculate expected final balance
        # Blackjack: +500 -100 +200 = +600
        # Hangman: +300 -50 +100 = +350
        # Total: +950
        expected_balance = initial_balance + 950
        
        # Verify final balance from both cogs
        final_balance_blackjack = await blackjack_cog.currency_manager.get_balance(user_id)
        final_balance_hangman = await hangman_cog.currency_manager.get_balance(user_id)
        
        assert final_balance_blackjack == final_balance_hangman
        assert final_balance_blackjack == expected_balance

    @pytest.mark.asyncio
    async def test_hangman_bonus_integration(self, hangman_cog):
        """Test hangman bonus claim integration with shared currency manager"""
        user_id = "hangman_bonus_user"
        
        # Get initial balance
        initial_balance = await hangman_cog.currency_manager.get_balance(user_id)
        
        # Mock hangman game completion and bonus claim
        success, message, new_balance = await hangman_cog.currency_manager.claim_hangman_bonus(user_id)
        
        assert success is True
        assert new_balance == initial_balance + HANGMAN_DAILY_BONUS
        assert f"${HANGMAN_DAILY_BONUS:,}" in message
        
        # Verify the bonus is reflected in the shared currency manager
        current_balance = await hangman_cog.currency_manager.get_balance(user_id)
        assert current_balance == initial_balance + HANGMAN_DAILY_BONUS

    @pytest.mark.asyncio
    async def test_blackjack_payout_integration(self, blackjack_cog):
        """Test blackjack payout calculation with shared currency manager"""
        user_id = "blackjack_payout_user"
        bet_amount = 1000
        
        # Ensure user has enough balance
        await blackjack_cog.currency_manager.add_currency(user_id, 5000)
        initial_balance = await blackjack_cog.currency_manager.get_balance(user_id)
        
        # Simulate blackjack bet
        success, balance_after_bet = await blackjack_cog.currency_manager.subtract_currency(user_id, bet_amount)
        assert success is True
        assert balance_after_bet == initial_balance - bet_amount
        
        # Simulate blackjack win (true blackjack with multiplier)
        payout = int(bet_amount * BLACKJACK_PAYOUT_MULTIPLIER)
        final_balance = await blackjack_cog.currency_manager.add_currency(user_id, payout)
        
        # Verify final balance
        expected_final = initial_balance - bet_amount + payout
        assert final_balance == expected_final

    @pytest.mark.asyncio
    async def test_file_operations_consistency_across_cogs(self, blackjack_cog, hangman_cog, temp_data_dir):
        """Test that file operations from different cogs maintain data consistency"""
        user_id = "file_ops_user"
        
        # Perform operations from blackjack cog
        await blackjack_cog.currency_manager.add_currency(user_id, 1000)
        
        # Verify data is written to file
        currency_file = os.path.join(temp_data_dir, "currency.json")
        with open(currency_file, 'r') as f:
            data = json.load(f)
        
        assert user_id in data
        assert data[user_id]["balance"] == 101000  # 100000 default + 1000 added
        
        # Perform operations from hangman cog
        await hangman_cog.currency_manager.add_currency(user_id, 500)
        
        # Verify updated data in file
        with open(currency_file, 'r') as f:
            updated_data = json.load(f)
        
        assert updated_data[user_id]["balance"] == 101500  # Previous + 500

    @pytest.mark.asyncio
    async def test_prevent_duplicate_manager_creation_bug(self, temp_data_dir):
        """Test that prevents the bug where cogs created their own CurrencyManager instances"""
        # Create bot with shared currency manager
        mock_bot = MagicMock()
        shared_manager = CurrencyManager()
        shared_manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        await shared_manager.initialize()
        mock_bot.currency_manager = shared_manager
        
        # Create user data with shared manager
        user_id = "duplicate_prevention_user"
        await shared_manager.add_currency(user_id, 5000)
        initial_balance = await shared_manager.get_balance(user_id)
        
        # Create cogs that should use shared manager
        blackjack_cog = BlackjackCog(mock_bot)
        hangman_cog = HangmanCog(mock_bot)
        
        # Verify cogs use shared manager
        assert blackjack_cog.currency_manager is shared_manager
        assert hangman_cog.currency_manager is shared_manager
        
        # Perform operations from cogs
        await blackjack_cog.currency_manager.add_currency(user_id, 1000)
        await hangman_cog.currency_manager.subtract_currency(user_id, 500)
        
        # Verify operations affected the same data
        final_balance_shared = await shared_manager.get_balance(user_id)
        final_balance_blackjack = await blackjack_cog.currency_manager.get_balance(user_id)
        final_balance_hangman = await hangman_cog.currency_manager.get_balance(user_id)
        
        expected_balance = initial_balance + 1000 - 500
        assert final_balance_shared == expected_balance
        assert final_balance_blackjack == expected_balance
        assert final_balance_hangman == expected_balance
        
        # Verify all balances are identical (same data source)
        assert final_balance_shared == final_balance_blackjack == final_balance_hangman

    @pytest.mark.asyncio
    async def test_daily_bonus_across_cogs_consistency(self, blackjack_cog, hangman_cog):
        """Test that daily bonus claims are consistent across cogs"""
        user_id = "daily_bonus_user"
        
        # Get initial balance from blackjack cog
        initial_balance_bj = await blackjack_cog.currency_manager.get_balance(user_id)
        
        # Claim daily bonus through hangman cog
        success, message, new_balance = await hangman_cog.currency_manager.claim_daily_bonus(user_id)
        assert success is True
        
        # Verify balance is updated and consistent across both cogs
        balance_from_blackjack = await blackjack_cog.currency_manager.get_balance(user_id)
        balance_from_hangman = await hangman_cog.currency_manager.get_balance(user_id)
        
        assert balance_from_blackjack == balance_from_hangman
        assert balance_from_blackjack == initial_balance_bj + DAILY_CLAIM
        assert balance_from_blackjack == new_balance

    @pytest.mark.asyncio
    async def test_portfolio_operations_consistency(self, blackjack_cog, hangman_cog):
        """Test that stock portfolio operations are consistent across cogs"""
        user_id = "portfolio_user"
        
        # Add balance for stock trading
        await blackjack_cog.currency_manager.add_currency(user_id, 10000)
        
        # Buy stock through blackjack cog
        success, message = await blackjack_cog.currency_manager.buy_stock(user_id, "AAPL", 10.0, 150.0, 20)
        assert success is True
        
        # Check portfolio from hangman cog
        portfolio_from_hangman = await hangman_cog.currency_manager.get_portfolio(user_id)
        portfolio_from_blackjack = await blackjack_cog.currency_manager.get_portfolio(user_id)
        
        # Portfolios should be identical
        assert portfolio_from_hangman == portfolio_from_blackjack
        assert "AAPL" in portfolio_from_hangman
        assert portfolio_from_hangman["AAPL"]["shares"] == 10.0
        assert portfolio_from_hangman["AAPL"]["purchase_price"] == 150.0
        assert portfolio_from_hangman["AAPL"]["leverage"] == 20

    @pytest.mark.asyncio
    async def test_error_handling_consistency_across_cogs(self, blackjack_cog, hangman_cog):
        """Test that error handling is consistent when using shared currency manager"""
        user_id = "error_test_user"
        
        # Attempt insufficient balance operation from blackjack cog
        success_bj, balance_bj = await blackjack_cog.currency_manager.subtract_currency(user_id, 999999)
        assert success_bj is False
        
        # Same operation from hangman cog should have same result
        success_hm, balance_hm = await hangman_cog.currency_manager.subtract_currency(user_id, 999999)
        assert success_hm is False
        
        # Balances should be identical
        assert balance_bj == balance_hm
        
        # Both should show the same user balance
        balance_check_bj = await blackjack_cog.currency_manager.get_balance(user_id)
        balance_check_hm = await hangman_cog.currency_manager.get_balance(user_id)
        
        assert balance_check_bj == balance_check_hm == balance_bj == balance_hm

    @pytest.mark.asyncio
    async def test_user_lock_consistency_across_cogs(self, blackjack_cog, hangman_cog):
        """Test that user locks work consistently across different cogs"""
        user_id = "lock_test_user"
        
        # Get user locks from both cogs' currency managers (should be same instance)
        lock_from_bj = await blackjack_cog.currency_manager._get_user_lock(user_id)
        lock_from_hm = await hangman_cog.currency_manager._get_user_lock(user_id)
        
        # Should be the same lock object
        assert lock_from_bj is lock_from_hm
        
        # Test that lock prevents race conditions across cogs
        initial_balance = await blackjack_cog.currency_manager.get_balance(user_id)
        
        async def blackjack_operation():
            async with lock_from_bj:
                balance = await blackjack_cog.currency_manager.get_balance(user_id)
                await asyncio.sleep(0.01)  # Simulate processing time
                await blackjack_cog.currency_manager.add_currency(user_id, 100)
        
        async def hangman_operation():
            async with lock_from_hm:
                balance = await hangman_cog.currency_manager.get_balance(user_id)
                await asyncio.sleep(0.01)  # Simulate processing time
                await hangman_cog.currency_manager.add_currency(user_id, 200)
        
        # Run operations concurrently
        await asyncio.gather(
            blackjack_operation(),
            hangman_operation()
        )
        
        # Final balance should be initial + 100 + 200
        final_balance = await blackjack_cog.currency_manager.get_balance(user_id)
        assert final_balance == initial_balance + 300

    @pytest.mark.asyncio
    async def test_cog_initialization_with_shared_manager(self, mock_bot_with_shared_currency_manager):
        """Test that cogs initialize correctly with shared currency manager"""
        bot = mock_bot_with_shared_currency_manager
        
        # Ensure currency manager is already initialized
        assert hasattr(bot, 'currency_manager')
        assert bot.currency_manager is not None
        
        # Create cogs
        blackjack_cog = BlackjackCog(bot)
        hangman_cog = HangmanCog(bot)
        
        # Verify cogs reference the bot's currency manager
        assert blackjack_cog.currency_manager is bot.currency_manager
        assert hangman_cog.currency_manager is bot.currency_manager
        
        # Verify currency manager is functional
        test_user = "init_test_user"
        balance = await blackjack_cog.currency_manager.get_balance(test_user)
        assert balance == 100000  # Default balance for new user

    @pytest.mark.asyncio
    async def test_multiple_cogs_same_file_operations(self, temp_data_dir):
        """Test multiple cogs operating on the same currency file without conflicts"""
        # Create multiple bots with shared currency managers pointing to same file
        currency_file = os.path.join(temp_data_dir, "shared_currency.json")
        
        # Bot 1 with blackjack cog
        bot1 = MagicMock()
        manager1 = CurrencyManager()
        manager1.currency_file = currency_file
        await manager1.initialize()
        bot1.currency_manager = manager1
        blackjack_cog = BlackjackCog(bot1)
        
        # Bot 2 with hangman cog
        bot2 = MagicMock()
        manager2 = CurrencyManager()
        manager2.currency_file = currency_file
        await manager2.initialize()
        bot2.currency_manager = manager2
        hangman_cog = HangmanCog(bot2)
        
        user_id = "multi_cog_user"
        
        # Operations from cog 1
        await blackjack_cog.currency_manager.add_currency(user_id, 1000)
        
        # Reload manager 2 to get latest data
        await hangman_cog.currency_manager.load_currency_data()
        balance_from_cog2 = await hangman_cog.currency_manager.get_balance(user_id)
        
        # Should see the update from cog 1
        assert balance_from_cog2 == 101000  # 100000 default + 1000
        
        # Operations from cog 2
        await hangman_cog.currency_manager.add_currency(user_id, 500)
        
        # Reload manager 1 to get latest data
        await blackjack_cog.currency_manager.load_currency_data()
        balance_from_cog1 = await blackjack_cog.currency_manager.get_balance(user_id)
        
        # Should see both updates
        assert balance_from_cog1 == 101500  # Previous + 500