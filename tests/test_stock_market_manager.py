import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from src.utils.stock_market_manager import StockMarketManager


class TestStockMarketManager:
    @pytest.fixture
    def stock_manager(self):
        return StockMarketManager()

    @pytest.fixture
    def mock_stock_info(self):
        return {
            'currentPrice': 150.0,
            'regularMarketPrice': 150.0,
            'shortName': 'Apple Inc.',
            'symbol': 'AAPL'
        }

    def test_initialization(self, stock_manager):
        """Test StockMarketManager initialization"""
        assert stock_manager.cache == {}
        assert stock_manager.cache_expiry == {}
        assert isinstance(stock_manager.cache_duration, timedelta)
        assert stock_manager.cache_duration.total_seconds() == 60  # 1 minute

    def test_is_cache_valid_no_cache(self, stock_manager):
        """Test cache validation when no cache exists"""
        assert stock_manager._is_cache_valid("AAPL") is False

    def test_is_cache_valid_expired_cache(self, stock_manager):
        """Test cache validation with expired cache"""
        # Set up expired cache
        stock_manager.cache["AAPL"] = {"price": 150.0}
        stock_manager.cache_expiry["AAPL"] = datetime.now() - timedelta(minutes=2)
        
        assert stock_manager._is_cache_valid("AAPL") is False

    def test_is_cache_valid_valid_cache(self, stock_manager):
        """Test cache validation with valid cache"""
        # Set up valid cache
        stock_manager.cache["AAPL"] = {"price": 150.0}
        stock_manager.cache_expiry["AAPL"] = datetime.now() + timedelta(minutes=2)
        
        assert stock_manager._is_cache_valid("AAPL") is True

    @pytest.mark.asyncio
    async def test_get_stock_price_from_cache(self, stock_manager):
        """Test getting stock price from cache"""
        # Set up valid cache
        stock_manager.cache["AAPL"] = {"price": 150.0}
        stock_manager.cache_expiry["AAPL"] = datetime.now() + timedelta(minutes=2)
        
        price = await stock_manager.get_stock_price("AAPL")
        assert price == 150.0

    @pytest.mark.asyncio
    async def test_get_stock_price_from_api_current_price(self, stock_manager, mock_stock_info):
        """Test getting stock price from API using currentPrice"""
        mock_ticker = MagicMock()
        mock_ticker.info = mock_stock_info
        
        with patch('src.utils.stock_market_manager.yf.Ticker', return_value=mock_ticker), \
             patch('src.utils.stock_market_manager.logger') as mock_logger:
            
            price = await stock_manager.get_stock_price("AAPL")
            assert price == 150.0
            
            # Verify cache was updated
            assert "AAPL" in stock_manager.cache
            assert stock_manager.cache["AAPL"]["price"] == 150.0
            
            # Verify logging
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stock_price_from_api_regular_market_price(self, stock_manager):
        """Test getting stock price from API using regularMarketPrice"""
        mock_info = {"regularMarketPrice": 155.0}
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        
        with patch('src.utils.stock_market_manager.yf.Ticker', return_value=mock_ticker), \
             patch('src.utils.stock_market_manager.logger'):
            
            price = await stock_manager.get_stock_price("AAPL")
            assert price == 155.0

    @pytest.mark.asyncio
    async def test_get_stock_price_from_history(self, stock_manager):
        """Test getting stock price from historical data"""
        import pandas as pd
        
        mock_info = {}  # No current price info
        mock_history = pd.DataFrame({'Close': [160.0, 165.0]})
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        mock_ticker.history.return_value = mock_history
        
        with patch('src.utils.stock_market_manager.yf.Ticker', return_value=mock_ticker), \
             patch('src.utils.stock_market_manager.logger'):
            
            price = await stock_manager.get_stock_price("AAPL")
            assert price == 165.0  # Last close price

    @pytest.mark.asyncio
    async def test_get_stock_price_api_error(self, stock_manager):
        """Test handling API errors"""
        with patch('src.utils.stock_market_manager.yf.Ticker', side_effect=Exception("API Error")), \
             patch('src.utils.stock_market_manager.logger') as mock_logger:
            
            price = await stock_manager.get_stock_price("INVALID")
            assert price is None
            
            # Verify error was logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stock_info_from_cache(self, stock_manager, mock_stock_info):
        """Test getting stock info from cache"""
        # Set up valid cache
        stock_manager.cache["AAPL"] = {"price": 150.0, "info": mock_stock_info}
        stock_manager.cache_expiry["AAPL"] = datetime.now() + timedelta(minutes=2)
        
        info = await stock_manager.get_stock_info("AAPL")
        assert info == mock_stock_info

    @pytest.mark.asyncio
    async def test_get_stock_info_fetch_price_first(self, stock_manager, mock_stock_info):
        """Test getting stock info by fetching price first"""
        mock_ticker = MagicMock()
        mock_ticker.info = mock_stock_info
        
        with patch('src.utils.stock_market_manager.yf.Ticker', return_value=mock_ticker), \
             patch('src.utils.stock_market_manager.logger'):
            
            info = await stock_manager.get_stock_info("AAPL")
            assert info == mock_stock_info

    @pytest.mark.asyncio
    async def test_validate_stock_symbol_valid(self, stock_manager, mock_stock_info):
        """Test validating a valid stock symbol"""
        mock_ticker = MagicMock()
        mock_ticker.info = mock_stock_info
        
        with patch('src.utils.stock_market_manager.yf.Ticker', return_value=mock_ticker), \
             patch('src.utils.stock_market_manager.logger'):
            
            is_valid = await stock_manager.validate_stock_symbol("AAPL")
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_stock_symbol_invalid(self, stock_manager):
        """Test validating an invalid stock symbol"""
        with patch('src.utils.stock_market_manager.yf.Ticker', side_effect=Exception("Invalid symbol")), \
             patch('src.utils.stock_market_manager.logger'):
            
            is_valid = await stock_manager.validate_stock_symbol("INVALID")
            assert is_valid is False

    @pytest.mark.asyncio
    async def test_get_multiple_prices_success(self, stock_manager):
        """Test getting multiple stock prices successfully"""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        # Mock get_stock_price to return different prices
        async def mock_get_price(symbol):
            prices = {"AAPL": 150.0, "MSFT": 200.0, "GOOGL": 2500.0}
            return prices.get(symbol)
        
        with patch.object(stock_manager, 'get_stock_price', side_effect=mock_get_price):
            result = await stock_manager.get_multiple_prices(symbols)
            
            assert result["AAPL"] == 150.0
            assert result["MSFT"] == 200.0
            assert result["GOOGL"] == 2500.0

    @pytest.mark.asyncio
    async def test_get_multiple_prices_with_errors(self, stock_manager):
        """Test getting multiple stock prices with some errors"""
        symbols = ["AAPL", "INVALID", "MSFT"]
        
        async def mock_get_price(symbol):
            if symbol == "INVALID":
                raise Exception("Invalid symbol")
            prices = {"AAPL": 150.0, "MSFT": 200.0}
            return prices.get(symbol)
        
        with patch.object(stock_manager, 'get_stock_price', side_effect=mock_get_price):
            result = await stock_manager.get_multiple_prices(symbols)
            
            assert result["AAPL"] == 150.0
            assert result["INVALID"] is None
            assert result["MSFT"] == 200.0

    def test_calculate_leveraged_return(self, stock_manager):
        """Test calculating leveraged returns"""
        # Test positive return with 2x leverage
        result = stock_manager.calculate_leveraged_return(100.0, 110.0, 2.0)
        assert result == 0.2  # 10% * 2 = 20%
        
        # Test negative return with 2x leverage
        result = stock_manager.calculate_leveraged_return(100.0, 90.0, 2.0)
        assert result == -0.2  # -10% * 2 = -20%
        
        # Test with 1x leverage (no leverage)
        result = stock_manager.calculate_leveraged_return(100.0, 105.0, 1.0)
        assert result == 0.05  # 5%

    def test_calculate_position_value(self, stock_manager):
        """Test calculating position value"""
        # Test without leverage
        value = stock_manager.calculate_position_value(10.0, 150.0, 1.0)
        assert value == 1500.0  # 10 * 150 * 1
        
        # Test with leverage
        value = stock_manager.calculate_position_value(10.0, 150.0, 2.0)
        assert value == 3000.0  # 10 * 150 * 2

    def test_get_popular_stocks(self, stock_manager):
        """Test getting popular stocks list"""
        popular_stocks = stock_manager.get_popular_stocks()
        
        assert isinstance(popular_stocks, list)
        assert len(popular_stocks) > 0
        assert "AAPL" in popular_stocks
        assert "MSFT" in popular_stocks
        assert "GOOGL" in popular_stocks

    def test_format_price(self, stock_manager):
        """Test price formatting"""
        assert stock_manager.format_price(150.0) == "$150.00"
        assert stock_manager.format_price(150.123) == "$150.12"
        assert stock_manager.format_price(0.99) == "$0.99"

    def test_format_percentage(self, stock_manager):
        """Test percentage formatting"""
        assert stock_manager.format_percentage(0.05) == "+5.00%"
        assert stock_manager.format_percentage(-0.03) == "-3.00%"
        assert stock_manager.format_percentage(0.0) == "+0.00%"

    def test_get_current_leverage(self, stock_manager):
        """Test getting current leverage setting"""
        with patch('src.utils.stock_market_manager.STOCK_MARKET_LEVERAGE', 20):
            leverage = stock_manager.get_current_leverage()
            assert leverage == 20

    def test_calculate_margin_requirement(self, stock_manager):
        """Test calculating margin requirement"""
        # Test with 2x leverage
        margin = stock_manager.calculate_margin_requirement(1000.0, 2.0)
        assert margin == 500.0  # 1000 / 2
        
        # Test with 10x leverage
        margin = stock_manager.calculate_margin_requirement(1000.0, 10.0)
        assert margin == 100.0  # 1000 / 10

    def test_cache_expiry_logic(self, stock_manager):
        """Test cache expiry logic"""
        # Test that cache expires after the duration
        stock_manager.cache["TEST"] = {"price": 100.0}
        stock_manager.cache_expiry["TEST"] = datetime.now() - timedelta(seconds=1)
        
        assert stock_manager._is_cache_valid("TEST") is False
        
        # Test that cache is valid within duration
        stock_manager.cache_expiry["TEST"] = datetime.now() + timedelta(seconds=30)
        assert stock_manager._is_cache_valid("TEST") is True

    @pytest.mark.asyncio
    async def test_symbol_case_handling(self, stock_manager, mock_stock_info):
        """Test that symbols are converted to uppercase"""
        mock_ticker = MagicMock()
        mock_ticker.info = mock_stock_info
        
        with patch('src.utils.stock_market_manager.yf.Ticker') as mock_yf, \
             patch('src.utils.stock_market_manager.logger'):
            mock_yf.return_value = mock_ticker
            
            # Test lowercase symbol
            await stock_manager.get_stock_price("aapl")
            
            # Verify yf.Ticker was called with uppercase symbol
            mock_yf.assert_called_with("AAPL")

    def test_cache_key_consistency(self, stock_manager):
        """Test that cache keys are consistent"""
        # Set cache with uppercase key
        stock_manager.cache["AAPL"] = {"price": 150.0}
        stock_manager.cache_expiry["AAPL"] = datetime.now() + timedelta(minutes=2)
        
        # Test that validation works with the same key
        assert stock_manager._is_cache_valid("AAPL") is True