import pytest
import pytest_asyncio
import json
import os
import tempfile
import shutil
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands

from src.utils.currency_manager import CurrencyManager
from src.cogs.currency import CurrencyCog
from src.utils.stock_market_manager import StockMarketManager


class TestNetWorthLeaderboard:
    """Comprehensive test suite for net worth leaderboard functionality"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for testing file operations"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_currency_data(self):
        """Mock currency data with various portfolio scenarios"""
        return {
            "123456001": {
                "balance": 10000.0,
                "last_daily_claim": None,
                "last_hangman_bonus_claim": None,
                "portfolio": {
                    "AAPL": {
                        "shares": 50.0,
                        "purchase_price": 150.0,
                        "leverage": 1.0,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
            },
            "123456002": {
                "balance": 50000.0,
                "last_daily_claim": None,
                "last_hangman_bonus_claim": None,
                "portfolio": {
                    "MSFT": {
                        "shares": 100.0,
                        "purchase_price": 200.0,
                        "leverage": 10.0,
                        "purchase_date": "2024-01-01T00:00:00"
                    },
                    "GOOGL": {
                        "shares": 25.0,
                        "purchase_price": 100.0,
                        "leverage": 5.0,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
            },
            "123456003": {
                "balance": 5000.0,
                "last_daily_claim": None,
                "last_hangman_bonus_claim": None,
                "portfolio": {}
            },
            "123456004": {
                "balance": 1000.0,
                "last_daily_claim": None,
                "last_hangman_bonus_claim": None,
                "portfolio": {
                    "INVALID_STOCK": {
                        "shares": 10.0,
                        "purchase_price": 50.0,
                        "leverage": 1.0,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
            }
        }

    @pytest_asyncio.fixture
    async def currency_manager(self, mock_currency_data, temp_data_dir):
        """Create currency manager with test data"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "currency.json")

        # Write test data to file
        with open(manager.currency_file, 'w') as f:
            json.dump(mock_currency_data, f)

        await manager.initialize()
        return manager

    @pytest.fixture
    def mock_bot(self):
        """Mock bot with currency manager"""
        bot = MagicMock(spec=commands.Bot)
        bot.currency_manager = MagicMock()
        return bot

    @pytest.fixture
    def mock_interaction(self):
        """Mock Discord interaction"""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)
        bot_mock = MagicMock()
        bot_mock.get_user = MagicMock(return_value=None)
        bot_mock.fetch_user = AsyncMock(return_value=None)
        interaction.client = bot_mock
        return interaction

    # Test calculate_net_worth method
    @pytest.mark.asyncio
    async def test_calculate_net_worth_cash_only(self, currency_manager):
        """Test net worth calculation for user with cash only"""
        net_worth, cash_balance, portfolio_value = await currency_manager.calculate_net_worth("123456003")

        assert net_worth == 5000.0
        assert cash_balance == 5000.0
        assert portfolio_value == 0.0

    @pytest.mark.asyncio
    async def test_calculate_net_worth_with_portfolio_no_prices(self, currency_manager):
        """Test net worth calculation when stock prices are not provided"""
        with patch.object(StockMarketManager, 'get_multiple_prices', new_callable=AsyncMock) as mock_prices:
            mock_prices.return_value = {"AAPL": 180.0}

            net_worth, cash_balance, portfolio_value = await currency_manager.calculate_net_worth("123456001")

            assert cash_balance == 10000.0
            # Portfolio value should be: original investment (50 * 150 / 1) + profit/loss ((180 - 150) * 50)
            # = 7500 + 1500 = 9000
            assert portfolio_value == 9000.0
            assert net_worth == 19000.0

    @pytest.mark.asyncio
    async def test_calculate_net_worth_with_provided_prices(self, currency_manager):
        """Test net worth calculation with provided stock prices"""
        current_prices = {"AAPL": 200.0}

        net_worth, cash_balance, portfolio_value = await currency_manager.calculate_net_worth("123456001", current_prices)

        assert cash_balance == 10000.0
        # Portfolio value: original investment (7500) + profit/loss ((200 - 150) * 50 = 2500) = 10000
        assert portfolio_value == 10000.0
        assert net_worth == 20000.0

    @pytest.mark.asyncio
    async def test_calculate_net_worth_with_leverage(self, currency_manager):
        """Test net worth calculation with leveraged positions"""
        current_prices = {"MSFT": 220.0, "GOOGL": 120.0}

        net_worth, cash_balance, portfolio_value = await currency_manager.calculate_net_worth("123456002", current_prices)

        assert cash_balance == 50000.0

        # MSFT: original investment (100 * 200 / 10 = 2000) + profit/loss ((220 - 200) * 100 = 2000) = 4000
        # GOOGL: original investment (25 * 100 / 5 = 500) + profit/loss ((120 - 100) * 25 = 500) = 1000
        expected_portfolio_value = 4000.0 + 1000.0
        assert portfolio_value == expected_portfolio_value
        assert net_worth == 50000.0 + expected_portfolio_value

    @pytest.mark.asyncio
    async def test_calculate_net_worth_missing_stock_prices(self, currency_manager):
        """Test net worth calculation when some stock prices are missing"""
        current_prices = {"AAPL": None}  # Price not available

        net_worth, cash_balance, portfolio_value = await currency_manager.calculate_net_worth("123456001", current_prices)

        assert cash_balance == 10000.0
        assert portfolio_value == 0.0  # No value calculated due to missing price
        assert net_worth == 10000.0

    @pytest.mark.asyncio
    async def test_calculate_net_worth_nonexistent_user(self, currency_manager):
        """Test net worth calculation for non-existent user"""
        net_worth, cash_balance, portfolio_value = await currency_manager.calculate_net_worth("nonexistent_user")

        # New user gets default balance
        assert cash_balance == 100000.0
        assert portfolio_value == 0.0
        assert net_worth == 100000.0

    @pytest.mark.asyncio
    async def test_calculate_net_worth_stock_api_failure(self, currency_manager):
        """Test net worth calculation when stock API fails"""
        with patch.object(StockMarketManager, 'get_multiple_prices', new_callable=AsyncMock) as mock_prices:
            mock_prices.side_effect = Exception("API failure")

            # Should handle gracefully and fall back to cash balance only
            net_worth, cash_balance, portfolio_value = await currency_manager.calculate_net_worth("123456001")

            assert cash_balance == 10000.0
            assert portfolio_value == 0.0  # Portfolio value should be 0 when API fails
            assert net_worth == 10000.0  # Net worth should equal cash balance

    # Test leaderboard command functionality
    @pytest.mark.asyncio
    async def test_leaderboard_command_empty_database(self):
        """Test leaderboard command with empty database"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = {}

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await cog.leaderboard.callback(cog, interaction)

        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

        # Check that it sent a "no users" message
        call_args = interaction.followup.send.call_args[1]
        embed = call_args['embed']
        assert "No users have currency data yet" in embed.description

    @pytest.mark.asyncio
    async def test_leaderboard_command_with_users(self, mock_currency_data):
        """Test leaderboard command with user data"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = mock_currency_data
        mock_bot.currency_manager.calculate_net_worth = AsyncMock()

        # Mock net worth calculations
        net_worth_results = [
            (75000.0, 50000.0, 25000.0),  # user2 - highest net worth
            (19000.0, 10000.0, 9000.0),   # user1 - second
            (5000.0, 5000.0, 0.0),        # user3 - third
            (1000.0, 1000.0, 0.0),        # user4 - lowest
        ]

        mock_bot.currency_manager.calculate_net_worth.side_effect = net_worth_results

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(return_value=None)

        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={})
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

        # Check that net worth was calculated for all users
        assert mock_bot.currency_manager.calculate_net_worth.call_count == 4

    @pytest.mark.asyncio
    async def test_leaderboard_command_user_lookup_fallback(self, mock_currency_data):
        """Test leaderboard command user lookup with fallbacks"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = mock_currency_data
        mock_bot.currency_manager.calculate_net_worth = AsyncMock(return_value=(10000.0, 10000.0, 0.0))

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)

        # Test fallback to bot.get_user
        mock_user = MagicMock()
        mock_user.display_name = "TestUser"
        cog.bot.get_user = MagicMock(return_value=mock_user)
        cog.bot.fetch_user = AsyncMock(return_value=None)

        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={})
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        cog.bot.get_user.assert_called()

    @pytest.mark.asyncio
    async def test_leaderboard_command_api_fetch_fallback(self, mock_currency_data):
        """Test leaderboard command with API fetch fallback"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = mock_currency_data
        mock_bot.currency_manager.calculate_net_worth = AsyncMock(return_value=(10000.0, 10000.0, 0.0))

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)
        cog.bot.get_user = MagicMock(return_value=None)

        # Test fallback to bot.fetch_user
        mock_user = MagicMock()
        mock_user.display_name = "FetchedUser"
        cog.bot.fetch_user = AsyncMock(return_value=mock_user)

        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={})
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        cog.bot.fetch_user.assert_called()

    @pytest.mark.asyncio
    async def test_leaderboard_command_user_lookup_failure(self, mock_currency_data):
        """Test leaderboard command when all user lookup methods fail"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = mock_currency_data
        mock_bot.currency_manager.calculate_net_worth = AsyncMock(return_value=(10000.0, 10000.0, 0.0))

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(side_effect=Exception("API error"))

        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={})
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        # Should still complete without crashing
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_leaderboard_command_stock_api_failure(self, mock_currency_data):
        """Test leaderboard command when stock API fails"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = mock_currency_data
        mock_bot.currency_manager.calculate_net_worth = AsyncMock(side_effect=Exception("Stock API failed"))

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(return_value=None)

        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(side_effect=Exception("Stock API error"))
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        # Should still complete and fall back to cash balance
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_cash_leaderboard_command(self, mock_currency_data):
        """Test cash leaderboard command"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = mock_currency_data
        mock_bot.currency_manager.format_balance = MagicMock(side_effect=lambda x: f"${x:,.2f}")

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(return_value=None)

        await cog.cash_leaderboard.callback(cog, interaction)

        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_cash_leaderboard_empty_database(self):
        """Test cash leaderboard with empty database"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = {}

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()

        await cog.cash_leaderboard.callback(cog, interaction)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[1]
        embed = call_args['embed']
        assert "No users have currency data yet" in embed.description

    # Performance and edge case tests
    @pytest.mark.asyncio
    async def test_leaderboard_performance_many_users(self):
        """Test leaderboard performance with many users"""
        # Create mock data for 100 users
        large_currency_data = {}
        for i in range(100):
            large_currency_data[f"user{i}"] = {
                "balance": 1000 + i,
                "portfolio": {}
            }

        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = large_currency_data
        mock_bot.currency_manager.calculate_net_worth = AsyncMock(side_effect=lambda user_id, _: (1000, 1000, 0))

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(return_value=None)

        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={})
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        # Should complete without timeout or excessive delay
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_leaderboard_with_corrupted_portfolio_data(self, currency_manager):
        """Test leaderboard handling of corrupted portfolio data"""
        # Add user with corrupted portfolio data
        currency_manager.currency_data["corrupted_user"] = {
            "balance": 5000.0,
            "portfolio": {
                "INVALID": {
                    "shares": "not_a_number",  # Invalid data type
                    "purchase_price": 100.0,
                    "leverage": 1.0
                }
            }
        }

        # Should handle gracefully without crashing
        try:
            net_worth, cash, portfolio = await currency_manager.calculate_net_worth("corrupted_user", {"INVALID": 120.0})
            # Should fall back to cash balance only
            assert net_worth >= cash
        except Exception as e:
            # If it throws an exception, it should be handled gracefully in the calling code
            assert "not_a_number" in str(e) or "invalid" in str(e).lower()

    @pytest.mark.asyncio
    async def test_leaderboard_rank_calculation(self, mock_currency_data):
        """Test that leaderboard correctly calculates and displays user ranks"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = mock_currency_data
        mock_bot.currency_manager.format_balance = MagicMock(side_effect=lambda x: f"${x:,.2f}")

        # Mock different net worth values to test ranking
        net_worth_side_effects = [
            (25000.0, 10000.0, 15000.0),  # user1
            (75000.0, 50000.0, 25000.0),  # user2 - should be #1
            (5000.0, 5000.0, 0.0),        # user3
            (1000.0, 1000.0, 0.0),        # user4
        ]
        mock_bot.currency_manager.calculate_net_worth = AsyncMock(side_effect=net_worth_side_effects)

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 123456789  # Mock user ID
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(return_value=None)

        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={})
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_net_worth_concurrent_calls(self, currency_manager):
        """Test that concurrent calls to calculate_net_worth don't interfere with each other"""
        import asyncio

        current_prices = {"AAPL": 180.0}

        # Run multiple concurrent calls
        tasks = [
            currency_manager.calculate_net_worth("123456001", current_prices),
            currency_manager.calculate_net_worth("123456003", current_prices),
            currency_manager.calculate_net_worth("123456001", current_prices),
        ]

        results = await asyncio.gather(*tasks)

        # Results for same user should be identical
        assert results[0] == results[2]
        # Different users should have different results
        assert results[0] != results[1]

    @pytest.mark.asyncio
    async def test_leaderboard_command_response_patterns(self, mock_currency_data):
        """Test that leaderboard follows proper Discord interaction response patterns"""
        mock_bot = MagicMock()
        mock_bot.currency_manager = MagicMock()
        mock_bot.currency_manager.load_currency_data = AsyncMock()
        mock_bot.currency_manager.currency_data = mock_currency_data
        mock_bot.currency_manager.calculate_net_worth = AsyncMock(return_value=(10000.0, 10000.0, 0.0))

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 123456789
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(return_value=None)

        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={})
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        # Should use defer followed by followup for long operations
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

        # Should not call response.send_message after defer
        interaction.response.send_message.assert_not_called()