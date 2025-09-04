import pytest
import discord
from discord.ext import commands
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date, timedelta
from src.cogs.stock_market import StockMarketCog


class TestDividendCommands:
    """Test dividend-related Discord commands in StockMarketCog"""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot with required managers"""
        bot = MagicMock()
        
        # Mock currency manager
        bot.currency_manager = AsyncMock()
        bot.currency_manager.get_dividend_summary.return_value = {
            "total_all_time": 125.50,
            "total_last_30_days": 45.75,
            "by_stock": {"AAPL": 75.25, "MSFT": 50.25},
            "recent_payments": [
                {
                    "symbol": "AAPL",
                    "amount": 25.0,
                    "amount_per_share": 0.25,
                    "shares": 100.0,
                    "payout": 25.0,
                    "ex_dividend_date": "2024-08-09",
                    "payment_date": "2024-08-09T10:00:00"
                }
            ],
            "payment_count": 8
        }
        
        # Mock dividend manager
        bot.dividend_manager = AsyncMock()
        bot.dividend_manager.get_dividend_info.return_value = {
            "symbol": "AAPL",
            "dividend_yield": 0.0045,
            "forward_dividend_rate": 0.96,
            "ex_dividend_date": "2024-11-08",
            "last_dividend_value": 0.25,
            "historical_dividends": [
                {"date": "2024-02-09", "amount": 0.24},
                {"date": "2024-05-10", "amount": 0.24},
                {"date": "2024-08-09", "amount": 0.24},
                {"date": "2024-11-08", "amount": 0.25}
            ],
            "pays_dividends": True
        }
        
        bot.dividend_manager.get_upcoming_dividends_for_portfolio.return_value = [
            {
                "symbol": "AAPL",
                "ex_dividend_date": "2024-11-08",
                "dividend_amount": 0.25,
                "shares_owned": 100.0,
                "estimated_payout": 25.0,
                "dividend_yield": 0.0045
            }
        ]
        
        return bot
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction"""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # Mock user
        interaction.user = MagicMock()
        interaction.user.id = 123456789
        interaction.user.mention = "<@123456789>"
        interaction.user.display_name = "TestUser"
        
        return interaction
    
    @pytest.fixture
    def stock_market_cog(self, mock_bot):
        """Create StockMarketCog instance with mocked dependencies"""
        cog = StockMarketCog(mock_bot)
        # Mock the managers directly
        cog.dividend_manager = mock_bot.dividend_manager
        cog.bot = mock_bot
        return cog

    # Test /dividend_info command
    @pytest.mark.asyncio
    async def test_dividend_info_command_success(self, stock_market_cog, mock_interaction):
        """Test successful dividend_info command"""
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "AAPL")
        
        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()
        
        # Verify dividend manager was called
        stock_market_cog.dividend_manager.get_dividend_info.assert_called_once_with("AAPL")
        
        # Verify followup was sent with embed
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        
        assert 'embed' in kwargs
        embed = kwargs['embed']
        assert isinstance(embed, discord.Embed)
        assert "AAPL" in embed.title
        assert embed.color == discord.Color.green()  # Green for dividend-paying stock

    @pytest.mark.asyncio
    async def test_dividend_info_command_no_dividends(self, stock_market_cog, mock_interaction):
        """Test dividend_info command for non-dividend paying stock"""
        # Mock non-dividend paying stock
        stock_market_cog.dividend_manager.get_dividend_info.return_value = {
            "symbol": "TSLA",
            "dividend_yield": 0.0,
            "forward_dividend_rate": 0.0,
            "ex_dividend_date": None,
            "last_dividend_value": 0.0,
            "historical_dividends": [],
            "pays_dividends": False
        }
        
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "TSLA")
        
        # Verify followup was sent
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        
        embed = kwargs['embed']
        assert embed.color == discord.Color.orange()  # Orange for non-dividend stock
        assert "does not currently pay dividends" in embed.description

    @pytest.mark.asyncio
    async def test_dividend_info_command_invalid_symbol(self, stock_market_cog, mock_interaction):
        """Test dividend_info command with invalid stock symbol"""
        # Mock API returning None for invalid symbol
        stock_market_cog.dividend_manager.get_dividend_info.return_value = None
        
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "INVALID")
        
        # Verify error message was sent
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        
        assert kwargs['ephemeral'] is True
        assert "Could not find dividend information" in args[0]

    @pytest.mark.asyncio
    async def test_dividend_info_command_api_error(self, stock_market_cog, mock_interaction):
        """Test dividend_info command when API throws error"""
        # Mock API error
        stock_market_cog.dividend_manager.get_dividend_info.side_effect = Exception("API Error")
        
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "AAPL")
        
        # Verify error message was sent
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        
        assert kwargs['ephemeral'] is True
        assert "An error occurred while fetching dividend information" in args[0]

    @pytest.mark.asyncio
    async def test_dividend_info_command_case_insensitive(self, stock_market_cog, mock_interaction):
        """Test that dividend_info command handles case-insensitive symbols"""
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "aapl")
        
        # Verify symbol was converted to uppercase
        stock_market_cog.dividend_manager.get_dividend_info.assert_called_once_with("AAPL")

    # Test /dividend_history command
    @pytest.mark.asyncio
    async def test_dividend_history_command_self(self, stock_market_cog, mock_interaction):
        """Test dividend_history command for self"""
        await stock_market_cog.dividend_history.callback(stock_market_cog, mock_interaction, None)
        
        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()
        
        # Verify currency manager was called with user's ID
        stock_market_cog.bot.currency_manager.get_dividend_summary.assert_called_once_with("123456789")
        
        # Verify embed was sent
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        
        assert 'embed' in kwargs
        embed = kwargs['embed']
        assert "TestUser's Dividend Earnings" in embed.title

    @pytest.mark.asyncio
    async def test_dividend_history_command_other_user(self, stock_market_cog, mock_interaction):
        """Test dividend_history command for another user"""
        # Mock other user
        other_user = MagicMock()
        other_user.id = 987654321
        other_user.display_name = "OtherUser"
        
        await stock_market_cog.dividend_history.callback(stock_market_cog, mock_interaction, other_user)
        
        # Verify currency manager was called with other user's ID
        stock_market_cog.bot.currency_manager.get_dividend_summary.assert_called_once_with("987654321")
        
        # Verify embed mentions other user
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        assert "OtherUser's Dividend Earnings" in embed.title

    @pytest.mark.asyncio
    async def test_dividend_history_command_no_earnings(self, stock_market_cog, mock_interaction):
        """Test dividend_history command for user with no earnings"""
        # Mock no earnings
        stock_market_cog.bot.currency_manager.get_dividend_summary.return_value = {
            "total_all_time": 0.0,
            "total_last_30_days": 0.0,
            "by_stock": {},
            "recent_payments": [],
            "payment_count": 0
        }
        
        await stock_market_cog.dividend_history.callback(stock_market_cog, mock_interaction, None)
        
        # Verify appropriate message for no earnings
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        assert "No dividend earnings yet" in embed.description

    @pytest.mark.asyncio
    async def test_dividend_history_command_error(self, stock_market_cog, mock_interaction):
        """Test dividend_history command when error occurs"""
        # Mock error
        stock_market_cog.bot.currency_manager.get_dividend_summary.side_effect = Exception("Database error")
        
        await stock_market_cog.dividend_history.callback(stock_market_cog, mock_interaction, None)
        
        # Verify error message was sent
        args, kwargs = mock_interaction.followup.send.call_args
        assert kwargs['ephemeral'] is True
        assert "An error occurred while fetching dividend history" in args[0]

    # Test /dividend_calendar command
    @pytest.mark.asyncio
    async def test_dividend_calendar_command_default_days(self, stock_market_cog, mock_interaction):
        """Test dividend_calendar command with default 30 days"""
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, None)
        
        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()
        
        # Verify dividend manager was called
        stock_market_cog.dividend_manager.get_upcoming_dividends_for_portfolio.assert_called_once_with("123456789")
        
        # Verify embed was sent
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        
        assert 'embed' in kwargs
        embed = kwargs['embed']
        assert "Dividend Calendar" in embed.title
        assert "Next 30 Days" in embed.title

    @pytest.mark.asyncio
    async def test_dividend_calendar_command_custom_days(self, stock_market_cog, mock_interaction):
        """Test dividend_calendar command with custom day range"""
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 60)
        
        # Verify embed reflects custom range
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        assert "Next 60 Days" in embed.title

    @pytest.mark.asyncio
    async def test_dividend_calendar_command_no_upcoming(self, stock_market_cog, mock_interaction):
        """Test dividend_calendar command with no upcoming dividends"""
        # Mock no upcoming dividends
        stock_market_cog.dividend_manager.get_upcoming_dividends_for_portfolio.return_value = []
        
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 30)
        
        # Verify appropriate message for no dividends
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        assert "No upcoming dividends found" in embed.description

    @pytest.mark.asyncio
    async def test_dividend_calendar_command_filters_by_date_range(self, stock_market_cog, mock_interaction):
        """Test that dividend_calendar correctly filters by date range"""
        # Mock dividends with varying dates
        today = date.today()
        near_future = today + timedelta(days=10)
        far_future = today + timedelta(days=50)
        
        stock_market_cog.dividend_manager.get_upcoming_dividends_for_portfolio.return_value = [
            {
                "symbol": "AAPL",
                "ex_dividend_date": near_future.isoformat(),
                "dividend_amount": 0.25,
                "shares_owned": 100.0,
                "estimated_payout": 25.0,
                "dividend_yield": 0.0045
            },
            {
                "symbol": "MSFT",
                "ex_dividend_date": far_future.isoformat(),
                "dividend_amount": 0.75,
                "shares_owned": 50.0,
                "estimated_payout": 37.5,
                "dividend_yield": 0.0275
            }
        ]
        
        # Test with 30 day filter
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 30)
        
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        
        # Should only show AAPL (within 30 days), not MSFT (50 days out)
        embed_str = str(embed.to_dict())
        assert "AAPL" in embed_str
        assert "MSFT" not in embed_str

    @pytest.mark.asyncio
    async def test_dividend_calendar_command_sorts_by_date(self, stock_market_cog, mock_interaction):
        """Test that dividend_calendar sorts dividends by date"""
        # Mock dividends in random order
        today = date.today()
        
        stock_market_cog.dividend_manager.get_upcoming_dividends_for_portfolio.return_value = [
            {
                "symbol": "MSFT",
                "ex_dividend_date": (today + timedelta(days=20)).isoformat(),
                "dividend_amount": 0.75,
                "shares_owned": 50.0,
                "estimated_payout": 37.5,
                "dividend_yield": 0.0275
            },
            {
                "symbol": "AAPL", 
                "ex_dividend_date": (today + timedelta(days=5)).isoformat(),
                "dividend_amount": 0.25,
                "shares_owned": 100.0,
                "estimated_payout": 25.0,
                "dividend_yield": 0.0045
            }
        ]
        
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 30)
        
        # Verify both dividends are shown and sorted
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        embed_str = str(embed.to_dict())
        
        # AAPL should appear before MSFT (earlier date)
        aapl_pos = embed_str.find("AAPL")
        msft_pos = embed_str.find("MSFT")
        assert aapl_pos < msft_pos

    @pytest.mark.asyncio
    async def test_dividend_calendar_command_limits_to_10(self, stock_market_cog, mock_interaction):
        """Test that dividend_calendar limits display to 10 upcoming dividends"""
        # Mock 15 upcoming dividends
        today = date.today()
        upcoming_dividends = []
        for i in range(15):
            upcoming_dividends.append({
                "symbol": f"STOCK{i}",
                "ex_dividend_date": (today + timedelta(days=i+1)).isoformat(),
                "dividend_amount": 0.25,
                "shares_owned": 10.0,
                "estimated_payout": 2.5,
                "dividend_yield": 0.02
            })
        
        stock_market_cog.dividend_manager.get_upcoming_dividends_for_portfolio.return_value = upcoming_dividends
        
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 30)
        
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        embed_str = str(embed.to_dict())
        
        # Should contain first 10 stocks but not the last 5
        assert "STOCK0" in embed_str
        assert "STOCK9" in embed_str
        assert "STOCK10" not in embed_str

    @pytest.mark.asyncio
    async def test_dividend_calendar_command_error(self, stock_market_cog, mock_interaction):
        """Test dividend_calendar command when error occurs"""
        # Mock error
        stock_market_cog.dividend_manager.get_upcoming_dividends_for_portfolio.side_effect = Exception("API Error")
        
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 30)
        
        # Verify error message was sent
        args, kwargs = mock_interaction.followup.send.call_args
        assert kwargs['ephemeral'] is True
        assert "An error occurred while fetching dividend calendar" in args[0]

    @pytest.mark.asyncio
    async def test_dividend_calendar_command_invalid_days(self, stock_market_cog, mock_interaction):
        """Test dividend_calendar command with invalid days parameter"""
        # Test with negative days
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, -5)
        
        # Should handle gracefully (likely default to 30 or show no results)
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        assert embed is not None

    # Test Integration with Portfolio Display
    @pytest.mark.asyncio
    async def test_portfolio_command_includes_dividend_info(self, stock_market_cog, mock_interaction):
        """Test that portfolio command includes dividend information"""
        # This tests the integration where portfolio shows dividend yields
        # We need to mock the stock manager for this
        stock_market_cog.stock_manager.get_portfolio_value = AsyncMock(return_value=(25000.0, [
            {
                "symbol": "AAPL",
                "shares": 100.0,
                "current_price": 180.0,
                "purchase_price": 150.0,
                "current_value": 18000.0,
                "profit_loss": 3000.0,
                "profit_loss_percentage": 20.0
            }
        ]))
        
        stock_market_cog.stock_manager.get_dividend_yield = AsyncMock(return_value=0.45)  # 0.45%
        
        # Mock currency manager portfolio
        stock_market_cog.currency_manager.get_portfolio.return_value = {
            "AAPL": {
                "shares": 100.0,
                "purchase_price": 150.0,
                "leverage": 1,
                "purchase_date": "2024-01-01T00:00:00"
            }
        }
        
        # Test portfolio command (if it exists in the cog)
        if hasattr(stock_market_cog, 'portfolio'):
            await stock_market_cog.portfolio(mock_interaction)
            
            # Verify dividend yield was fetched
            stock_market_cog.stock_manager.get_dividend_yield.assert_called_with("AAPL")

    # Test Edge Cases and Error Handling
    @pytest.mark.asyncio
    async def test_dividend_commands_with_empty_symbol(self, stock_market_cog, mock_interaction):
        """Test dividend commands with empty or whitespace-only symbols"""
        # Test empty string
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "")
        
        # Should handle gracefully
        mock_interaction.followup.send.assert_called_once()
        
        # Reset mock for second test
        mock_interaction.followup.send.reset_mock()
        
        # Test whitespace
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "   ")
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dividend_history_embed_formatting(self, stock_market_cog, mock_interaction):
        """Test that dividend_history command formats embed correctly"""
        await stock_market_cog.dividend_history.callback(stock_market_cog, mock_interaction, None)
        
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        
        # Verify embed structure
        assert embed.title == "TestUser's Dividend Earnings"
        assert embed.color == discord.Color.green()
        
        # Check for expected fields
        field_names = [field.name for field in embed.fields]
        assert "Total Earnings" in field_names
        assert "Payment History" in field_names
        assert "Top Dividend Stocks" in field_names

    @pytest.mark.asyncio
    async def test_dividend_info_embed_formatting_with_dividends(self, stock_market_cog, mock_interaction):
        """Test dividend_info embed formatting for dividend-paying stock"""
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "AAPL")
        
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        
        # Verify embed structure for dividend-paying stock
        assert "AAPL" in embed.title
        assert "Dividend Information" in embed.title
        assert embed.color == discord.Color.green()
        
        # Check for expected fields
        field_names = [field.name for field in embed.fields]
        assert any("Dividend Yield" in name for name in field_names)
        assert any("Ex-Dividend Date" in name for name in field_names)
        assert any("Last Dividend" in name for name in field_names)
        
        # Check footer
        assert "Dividends are paid automatically" in embed.footer.text

    @pytest.mark.asyncio
    async def test_dividend_calendar_embed_formatting(self, stock_market_cog, mock_interaction):
        """Test dividend_calendar embed formatting"""
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 30)
        
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        
        # Verify embed structure
        assert "Dividend Calendar" in embed.title
        assert "Next 30 Days" in embed.title
        assert embed.color == discord.Color.blue()
        
        # Should contain dividend information
        embed_str = str(embed.to_dict())
        assert "AAPL" in embed_str
        assert "MSFT" in embed_str
        assert "$25.00" in embed_str  # AAPL payout
        assert "$37.50" in embed_str  # MSFT payout

    # Test Command Parameter Validation
    @pytest.mark.asyncio
    async def test_dividend_calendar_extreme_day_values(self, stock_market_cog, mock_interaction):
        """Test dividend_calendar with extreme day values"""
        # Test very large number of days
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 10000)
        
        # Should handle gracefully
        mock_interaction.followup.send.assert_called_once()
        
        # Reset for zero days test
        mock_interaction.followup.send.reset_mock()
        
        # Test zero days
        await stock_market_cog.dividend_calendar.callback(stock_market_cog, mock_interaction, 0)
        
        # Should show no results or handle gracefully
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        assert embed is not None

    # Test Performance and Responsiveness
    @pytest.mark.asyncio
    async def test_dividend_commands_responsiveness(self, stock_market_cog, mock_interaction):
        """Test that dividend commands respond within reasonable time"""
        # Mock slow API response
        async def slow_api_call(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate 100ms delay
            return {
                "symbol": "AAPL",
                "pays_dividends": True,
                "dividend_yield": 0.0045
            }
        
        stock_market_cog.dividend_manager.get_dividend_info = slow_api_call
        
        start_time = datetime.now()
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "AAPL")
        end_time = datetime.now()
        
        response_time = (end_time - start_time).total_seconds()
        
        # Should respond quickly even with API delays
        assert response_time < 1.0
        
        # Verify interaction was deferred to show loading state
        mock_interaction.response.defer.assert_called_once()

    # Test Error Recovery
    @pytest.mark.asyncio
    async def test_dividend_commands_graceful_degradation(self, stock_market_cog, mock_interaction):
        """Test graceful degradation when services are partially unavailable"""
        # Mock dividend manager available but currency manager failing
        stock_market_cog.bot.currency_manager.get_dividend_summary.side_effect = Exception("Currency service down")
        
        # dividend_history should fail gracefully
        await stock_market_cog.dividend_history.callback(stock_market_cog, mock_interaction, None)
        
        args, kwargs = mock_interaction.followup.send.call_args
        assert kwargs['ephemeral'] is True
        assert "error occurred" in args[0].lower()

    @pytest.mark.asyncio
    async def test_dividend_info_handles_partial_data(self, stock_market_cog, mock_interaction):
        """Test dividend_info handles partial/missing data gracefully"""
        # Mock dividend info with missing fields
        stock_market_cog.dividend_manager.get_dividend_info.return_value = {
            "symbol": "AAPL",
            "dividend_yield": None,  # Missing yield
            "forward_dividend_rate": 0.96,
            "ex_dividend_date": None,  # Missing ex-date
            "last_dividend_value": 0.0,  # No recent dividend
            "historical_dividends": [],  # No history
            "pays_dividends": True
        }
        
        await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, "AAPL")
        
        # Should handle gracefully without crashing
        args, kwargs = mock_interaction.followup.send.call_args
        embed = kwargs['embed']
        assert embed is not None
        assert embed.color == discord.Color.green()  # Still shows as dividend stock

    # Test Symbol Processing
    @pytest.mark.asyncio
    async def test_dividend_commands_symbol_normalization(self, stock_market_cog, mock_interaction):
        """Test that dividend commands normalize stock symbols"""
        test_symbols = ["aapl", "AAPL", " aapl ", "Aapl"]
        
        for symbol in test_symbols:
            # Reset mock
            stock_market_cog.dividend_manager.get_dividend_info.reset_mock()
            
            await stock_market_cog.dividend_info.callback(stock_market_cog, mock_interaction, symbol)
            
            # All should be normalized to "AAPL"
            stock_market_cog.dividend_manager.get_dividend_info.assert_called_once_with("AAPL")