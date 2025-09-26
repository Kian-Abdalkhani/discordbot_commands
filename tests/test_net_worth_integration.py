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


class TestNetWorthIntegration:
    """Integration tests for net worth functionality with real components"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for testing file operations"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def real_currency_data(self):
        """Real currency data for integration testing"""
        return {
            "100001": {
                "balance": 50000.0,
                "last_daily_claim": None,
                "last_hangman_bonus_claim": None,
                "portfolio": {
                    "AAPL": {
                        "shares": 100.0,
                        "purchase_price": 150.0,
                        "leverage": 1.0,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
            },
            "100002": {
                "balance": 25000.0,
                "last_daily_claim": None,
                "last_hangman_bonus_claim": None,
                "portfolio": {
                    "MSFT": {
                        "shares": 50.0,
                        "purchase_price": 200.0,
                        "leverage": 10.0,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
            },
            "100003": {
                "balance": 75000.0,
                "last_daily_claim": None,
                "last_hangman_bonus_claim": None,
                "portfolio": {}
            }
        }

    @pytest_asyncio.fixture
    async def real_currency_manager(self, real_currency_data, temp_data_dir):
        """Create a real currency manager with test data"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "currency.json")

        # Write test data to file
        with open(manager.currency_file, 'w') as f:
            json.dump(real_currency_data, f)

        await manager.initialize()
        return manager

    @pytest.mark.asyncio
    async def test_end_to_end_net_worth_calculation(self, real_currency_manager):
        """Test end-to-end net worth calculation with realistic data"""
        # Mock stock prices
        stock_prices = {
            "AAPL": 180.0,  # User gained $30 per share
            "MSFT": 250.0   # User gained $50 per share with 10x leverage
        }

        # Test user with simple portfolio (100003)
        net_worth, cash, portfolio = await real_currency_manager.calculate_net_worth("100003", stock_prices)
        assert net_worth == 75000.0
        assert cash == 75000.0
        assert portfolio == 0.0

        # Test user with AAPL (100001)
        net_worth, cash, portfolio = await real_currency_manager.calculate_net_worth("100001", stock_prices)
        assert cash == 50000.0
        # Portfolio: original investment (100 * 150 / 1 = 15000) + profit ((180-150) * 100 = 3000) = 18000
        assert portfolio == 18000.0
        assert net_worth == 68000.0

        # Test user with leveraged MSFT (100002)
        net_worth, cash, portfolio = await real_currency_manager.calculate_net_worth("100002", stock_prices)
        assert cash == 25000.0
        # Portfolio: original investment (50 * 200 / 10 = 1000) + profit ((250-200) * 50 = 2500) = 3500
        assert portfolio == 3500.0
        assert net_worth == 28500.0

    @pytest.mark.asyncio
    async def test_end_to_end_leaderboard_ranking(self, real_currency_manager):
        """Test end-to-end leaderboard ranking"""
        # Mock bot and interaction
        mock_bot = MagicMock()
        mock_bot.currency_manager = real_currency_manager

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 100001
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(return_value=None)

        # Mock stock manager to return predictable prices
        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={
                "AAPL": 180.0,
                "MSFT": 250.0
            })
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        # Verify command completed successfully
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

        # Check that the embed was created properly
        call_args = interaction.followup.send.call_args[1]
        embed = call_args['embed']
        assert "Net Worth Leaderboard" in embed.title

    @pytest.mark.asyncio
    async def test_performance_characteristics(self, real_currency_manager):
        """Test that leaderboard performs reasonably well"""
        import time

        # Add more users to test performance
        for i in range(50):
            user_id = f"200{i:03d}"
            real_currency_manager.currency_data[user_id] = {
                "balance": 10000.0 + i * 1000,
                "portfolio": {
                    "AAPL": {
                        "shares": 10.0 + i,
                        "purchase_price": 150.0,
                        "leverage": 1.0,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                } if i % 2 == 0 else {}
            }

        start_time = time.time()

        # Mock bot and interaction
        mock_bot = MagicMock()
        mock_bot.currency_manager = real_currency_manager

        cog = CurrencyCog(mock_bot)
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user.id = 100001
        interaction.guild.get_member = MagicMock(return_value=None)
        interaction.client.get_user = MagicMock(return_value=None)
        interaction.client.fetch_user = AsyncMock(return_value=None)

        # Mock stock manager
        with patch('src.utils.stock_market_manager.StockMarketManager') as mock_stock_manager:
            mock_instance = MagicMock()
            mock_instance.get_multiple_prices = AsyncMock(return_value={"AAPL": 180.0})
            mock_stock_manager.return_value = mock_instance

            await cog.leaderboard.callback(cog, interaction)

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete within reasonable time (less than 1 second for 53 users)
        assert execution_time < 1.0

        # Verify command completed successfully
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_net_worth_calculations(self, real_currency_manager):
        """Test that concurrent net worth calculations work correctly"""
        import asyncio

        stock_prices = {"AAPL": 180.0, "MSFT": 250.0}

        # Run multiple concurrent net worth calculations
        tasks = [
            real_currency_manager.calculate_net_worth("100001", stock_prices),
            real_currency_manager.calculate_net_worth("100002", stock_prices),
            real_currency_manager.calculate_net_worth("100003", stock_prices),
            real_currency_manager.calculate_net_worth("100001", stock_prices),  # Duplicate
        ]

        results = await asyncio.gather(*tasks)

        # Results should be consistent
        assert len(results) == 4
        assert results[0] == results[3]  # Duplicate calls should return same result

        # Verify specific calculations
        # User 100001: 50000 cash + 18000 portfolio = 68000
        assert results[0] == (68000.0, 50000.0, 18000.0)

        # User 100002: 25000 cash + 3500 portfolio = 28500
        assert results[1] == (28500.0, 25000.0, 3500.0)

        # User 100003: 75000 cash + 0 portfolio = 75000
        assert results[2] == (75000.0, 75000.0, 0.0)

    @pytest.mark.asyncio
    async def test_edge_cases_and_error_recovery(self, real_currency_manager):
        """Test various edge cases and error recovery scenarios"""
        # Test with completely invalid stock prices
        invalid_prices = {}
        net_worth, cash, portfolio = await real_currency_manager.calculate_net_worth("100001", invalid_prices)
        assert cash == 50000.0
        assert portfolio == 0.0  # Should be 0 when no valid prices
        assert net_worth == 50000.0

        # Test with None stock prices
        none_prices = {"AAPL": None}
        net_worth, cash, portfolio = await real_currency_manager.calculate_net_worth("100001", none_prices)
        assert cash == 50000.0
        assert portfolio == 0.0
        assert net_worth == 50000.0

        # Test with non-existent user
        net_worth, cash, portfolio = await real_currency_manager.calculate_net_worth("999999")
        assert cash == 100000.0  # Default new user balance
        assert portfolio == 0.0
        assert net_worth == 100000.0

        # Test with malformed portfolio data
        real_currency_manager.currency_data["malformed"] = {
            "balance": 5000.0,
            "portfolio": {
                "BROKEN": {
                    "shares": "not_a_number",
                    "purchase_price": 100.0,
                    "leverage": 1.0
                }
            }
        }

        # Should handle gracefully
        net_worth, cash, portfolio = await real_currency_manager.calculate_net_worth("malformed", {"BROKEN": 120.0})
        assert cash == 5000.0
        # Portfolio value might be 0 or some fallback value depending on error handling
        assert net_worth >= cash