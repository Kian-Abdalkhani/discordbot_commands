import pytest
import json
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, date, timedelta
from src.utils.dividend_manager import DividendManager
from src.utils.currency_manager import CurrencyManager


class TestDividendManager:
    """Test suite for DividendManager focusing on core dividend functionality"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for testing file operations"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_currency_manager(self):
        """Mock currency manager for testing"""
        mock_manager = AsyncMock(spec=CurrencyManager)
        mock_manager.currency_data = {
            "user1": {
                "balance": 10000.0,
                "portfolio": {
                    "AAPL": {
                        "shares": 100.0,
                        "purchase_price": 150.0,
                        "leverage": 1,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
            },
            "user2": {
                "balance": 5000.0,
                "portfolio": {
                    "AAPL": {
                        "shares": 50.0,
                        "purchase_price": 150.0,
                        "leverage": 1,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
            }
        }
        mock_manager.get_portfolio.return_value = {
            "AAPL": {
                "shares": 100.0,
                "purchase_price": 150.0,
                "leverage": 1,
                "purchase_date": "2024-01-01T00:00:00"
            }
        }
        mock_manager.add_currency.return_value = None
        mock_manager.record_dividend_payment.return_value = True
        mock_manager.load_currency_data.return_value = None
        return mock_manager

    # Test Core Dividend Manager Functionality
    @pytest.mark.asyncio
    async def test_dividend_manager_initialization(self, temp_data_dir, mock_currency_manager):
        """Test DividendManager initialization"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        assert manager.currency_manager is not None
        assert manager.dividend_file.endswith("dividends.json")
        assert isinstance(manager.dividend_data, dict)
        assert "dividend_history" in manager.dividend_data
        assert "user_dividend_earnings" in manager.dividend_data
        assert "processed_dividends" in manager.dividend_data
        assert manager.cache_duration == timedelta(hours=1)

    @pytest.mark.asyncio
    async def test_load_dividend_data_file_exists(self, temp_data_dir, mock_currency_manager):
        """Test loading dividend data when file exists"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        
        # Write test data to file
        test_data = {
            "dividend_history": {"AAPL": []},
            "user_dividend_earnings": {"user1": {"total_earned": 24.0}},
            "processed_dividends": {"AAPL_2024-02-01_0.24": True}
        }
        with open(manager.dividend_file, 'w') as f:
            json.dump(test_data, f)
        
        await manager.load_dividend_data()
        assert manager.dividend_data == test_data

    @pytest.mark.asyncio
    async def test_load_dividend_data_file_not_exists(self, temp_data_dir, mock_currency_manager):
        """Test loading dividend data when file doesn't exist"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "nonexistent.json")
        
        await manager.load_dividend_data()
        
        assert manager.dividend_data["dividend_history"] == {}
        assert manager.dividend_data["user_dividend_earnings"] == {}
        assert manager.dividend_data["processed_dividends"] == {}

    @pytest.mark.asyncio
    async def test_calculate_dividend_payout_success(self, temp_data_dir, mock_currency_manager):
        """Test successful dividend payout calculation"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        await manager.currency_manager.load_currency_data()
        result = await manager.calculate_dividend_payout("AAPL", 0.25, "2024-08-09")
        
        assert len(result) == 2  # Both users should be eligible
        assert "user1" in result
        assert "user2" in result
        assert result["user1"]["shares"] == 100.0
        assert result["user1"]["payout"] == 25.0  # 100 shares * 0.25
        assert result["user2"]["shares"] == 50.0
        assert result["user2"]["payout"] == 12.5  # 50 shares * 0.25

    @pytest.mark.asyncio
    async def test_calculate_dividend_payout_purchase_after_ex_date(self, temp_data_dir, mock_currency_manager):
        """Test dividend calculation when stock was purchased after ex-dividend date"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        # Modify the mock data to have a purchase date after ex-dividend date
        manager.currency_manager.currency_data["user1"]["portfolio"]["AAPL"]["purchase_date"] = "2024-08-15T00:00:00"
        
        result = await manager.calculate_dividend_payout("AAPL", 0.25, "2024-08-09")
        
        # user1 should not be eligible (purchased after ex-date), user2 should be
        assert "user1" not in result
        assert "user2" in result
        assert result["user2"]["payout"] == 12.5

    @pytest.mark.asyncio
    async def test_process_dividend_payment_success(self, temp_data_dir, mock_currency_manager):
        """Test successful dividend payment processing"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        eligible_users = {
            "user1": {"shares": 100.0, "payout": 25.0},
            "user2": {"shares": 50.0, "payout": 12.5}
        }
        
        with patch.object(manager, 'calculate_dividend_payout', return_value=eligible_users):
            result = await manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
            
            assert result is True
            assert manager.currency_manager.add_currency.call_count == 2
            assert manager.currency_manager.record_dividend_payment.call_count == 2
            
            # Verify dividend history was recorded
            assert "AAPL" in manager.dividend_data["dividend_history"]
            history_entry = manager.dividend_data["dividend_history"]["AAPL"][0]
            assert history_entry["ex_dividend_date"] == "2024-08-09"
            assert history_entry["amount"] == 0.25
            assert history_entry["total_paid"] == 37.5
            assert history_entry["users_paid"] == 2

    @pytest.mark.asyncio
    async def test_get_dividend_info_no_dividends(self, temp_data_dir, mock_currency_manager):
        """Test getting dividend info for non-dividend paying stock"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        mock_ticker = MagicMock()
        mock_ticker.info = {
            'dividendYield': None,
            'dividendRate': None,
            'exDividendDate': None
        }
        
        import pandas as pd
        mock_ticker.dividends = pd.Series([], dtype=float)
        
        with patch('yfinance.Ticker', return_value=mock_ticker):
            result = await manager.get_dividend_info("TSLA")
            
            assert result is not None
            assert result["symbol"] == "TSLA"
            assert result["pays_dividends"] is False
            assert result["dividend_yield"] == 0.0 or result["dividend_yield"] is None

    @pytest.mark.asyncio
    async def test_get_dividend_info_api_error(self, temp_data_dir, mock_currency_manager):
        """Test handling API errors when fetching dividend info"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        with patch('yfinance.Ticker', side_effect=Exception("API Error")):
            result = await manager.get_dividend_info("INVALID")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_validation(self, temp_data_dir, mock_currency_manager):
        """Test dividend info cache validation"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        # Test no cache
        assert manager._is_cache_valid("AAPL") is False
        
        # Test expired cache
        manager.cache["AAPL"] = {"test": "data"}
        manager.cache_expiry["AAPL"] = datetime.now() - timedelta(minutes=2)
        assert manager._is_cache_valid("AAPL") is False
        
        # Test valid cache
        manager.cache_expiry["AAPL"] = datetime.now() + timedelta(minutes=30)
        assert manager._is_cache_valid("AAPL") is True

    @pytest.mark.asyncio
    async def test_get_upcoming_dividends_for_portfolio(self, temp_data_dir, mock_currency_manager):
        """Test getting upcoming dividends for user portfolio"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        mock_dividend_info = {
            "symbol": "AAPL",
            "pays_dividends": True,
            "ex_dividend_date": "2024-11-08",
            "last_dividend_value": 0.25,
            "dividend_yield": 0.0045
        }
        
        with patch.object(manager, 'get_dividend_info', return_value=mock_dividend_info):
            result = await manager.get_upcoming_dividends_for_portfolio("user1")
            
            assert len(result) == 1
            dividend = result[0]
            assert dividend["symbol"] == "AAPL"
            assert dividend["ex_dividend_date"] == "2024-11-08"
            assert dividend["estimated_payout"] == 25.0

    @pytest.mark.asyncio
    async def test_get_upcoming_dividends_empty_portfolio(self, temp_data_dir, mock_currency_manager):
        """Test getting upcoming dividends with empty portfolio"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        manager.currency_manager.get_portfolio.return_value = {}
        result = await manager.get_upcoming_dividends_for_portfolio("user1")
        assert result == []

    @pytest.mark.asyncio
    async def test_record_dividend_earning(self, temp_data_dir, mock_currency_manager):
        """Test recording dividend earning for user"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        await manager._record_dividend_earning("user1", "AAPL", 25.0)
        
        user_earnings = manager.dividend_data["user_dividend_earnings"]["user1"]
        assert user_earnings["total_earned"] == 25.0
        assert user_earnings["by_stock"]["AAPL"] == 25.0
        assert "last_updated" in user_earnings

    @pytest.mark.asyncio
    async def test_check_for_new_dividends(self, temp_data_dir, mock_currency_manager):
        """Test checking for new dividends"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()

        # Use yesterday's date since ex-dividend date must have fully passed
        yesterday = date.today() - timedelta(days=1)
        mock_dividend_info = {
            "symbol": "AAPL",
            "pays_dividends": True,
            "ex_dividend_date": yesterday.isoformat(),
            "last_dividend_value": 0.25
        }
        
        await manager.currency_manager.load_currency_data()
        
        with patch.object(manager, 'get_dividend_info', return_value=mock_dividend_info):
            result = await manager.check_for_new_dividends()
            
            assert len(result) == 1
            dividend = result[0]
            assert dividend["symbol"] == "AAPL"
            assert dividend["amount"] == 0.25

    @pytest.mark.asyncio
    async def test_save_and_load_data(self, temp_data_dir, mock_currency_manager):
        """Test saving and loading dividend data"""
        manager = DividendManager(mock_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        
        # Add test data and save
        manager.dividend_data["test_key"] = "test_value"
        await manager.save_dividend_data()
        
        # Create new manager and load data
        manager2 = DividendManager(mock_currency_manager)
        manager2.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager2.load_dividend_data()
        
        assert manager2.dividend_data["test_key"] == "test_value"