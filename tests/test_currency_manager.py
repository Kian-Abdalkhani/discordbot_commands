import pytest
import json
import os
import asyncio
import tempfile
import shutil
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
from datetime import datetime, timedelta
from src.utils.currency_manager import CurrencyManager
from src.config.settings import DAILY_CLAIM, HANGMAN_DAILY_BONUS, STOCK_MARKET_LEVERAGE


class TestCurrencyManager:
    """Comprehensive test suite for CurrencyManager with focus on thread-safety and async operations"""
    @pytest.fixture
    def mock_currency_data(self):
        return {
                "773346702257291264": {
                    "balance": 20000,
                    "last_daily_claim": "2025-07-24T04:26:01.650715",
                    "last_hangman_bonus_claim": None,
                    "portfolio": {}
                },
                "1184766650638155877": {
                    "balance": 35125.58309037901,
                    "last_daily_claim": "2025-07-24T04:26:01.679162",
                    "last_hangman_bonus_claim": "2025-07-23T04:26:01.679162",
                    "portfolio": {
                        "AAPL": {
                            "shares": 466.4179104477612,
                            "purchase_price": 214.4,
                            "leverage": 20,
                            "purchase_date": "2025-07-23T05:04:59.806372"
                        }
                    }
                },
                "1046197048313126962": {
                    "balance": 19600,
                    "last_daily_claim": "2025-07-24T04:26:01.681611",
                    "last_hangman_bonus_claim": None,
                    "portfolio": {}
                }
        }

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for testing file operations"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def currency_manager(self, mock_currency_data, temp_data_dir):
        """Sync fixture for legacy sync tests (deprecated)"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        manager.currency_data = mock_currency_data.copy()
        return manager

    @pytest.fixture
    def async_currency_manager(self, mock_currency_data, temp_data_dir):
        """Async fixture for testing async functionality with real file operations"""
        async def _create_manager():
            manager = CurrencyManager()
            manager.currency_file = os.path.join(temp_data_dir, "currency.json")
            
            # Write initial test data to file
            with open(manager.currency_file, 'w') as f:
                json.dump(mock_currency_data, f)
            
            await manager.initialize()
            return manager
        return _create_manager()
    
    @pytest.fixture
    def clean_currency_manager(self, temp_data_dir):
        """Clean async fixture without pre-existing data"""
        async def _create_clean_manager():
            manager = CurrencyManager()
            manager.currency_file = os.path.join(temp_data_dir, "currency.json")
            await manager.initialize()
            return manager
        return _create_clean_manager()

    @pytest.mark.asyncio
    async def test_initialization(self, clean_currency_manager):
        """Test CurrencyManager initialization"""
        manager = await clean_currency_manager
        assert manager.currency_file.endswith("currency.json")
        assert isinstance(manager.currency_data, dict)
        assert isinstance(manager._locks, dict)
        assert manager._global_lock is not None

    @pytest.mark.asyncio
    async def test_load_currency_data_file_exists(self, mock_currency_data, temp_data_dir):
        """Test loading currency data when file exists"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        
        # Write test data to file
        with open(manager.currency_file, 'w') as f:
            json.dump(mock_currency_data, f)
        
        await manager.load_currency_data()
        assert manager.currency_data == mock_currency_data

    @pytest.mark.asyncio
    async def test_load_currency_data_file_not_exists(self, temp_data_dir):
        """Test loading currency data when file doesn't exist"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "nonexistent.json")
        await manager.load_currency_data()
        assert manager.currency_data == {}

    @pytest.mark.asyncio
    async def test_load_currency_data_json_error(self, temp_data_dir):
        """Test loading currency data with JSON decode error"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "corrupted.json")
        
        # Write invalid JSON
        with open(manager.currency_file, 'w') as f:
            f.write("invalid json content")
        
        with patch('src.utils.currency_manager.logger.error') as mock_error:
            await manager.load_currency_data()
            assert manager.currency_data == {}
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_currency_data(self, async_currency_manager):
        """Test saving currency data to file"""
        manager = await async_currency_manager
        original_data = manager.currency_data.copy()
        
        # Modify data and save
        manager.currency_data["test_user"] = {"balance": 1000, "portfolio": {}}
        await manager.save_currency_data()
        
        # Verify file was written correctly
        with open(manager.currency_file, 'r') as f:
            saved_data = json.load(f)
        
        assert "test_user" in saved_data
        assert saved_data["test_user"]["balance"] == 1000

    @pytest.mark.asyncio
    async def test_save_currency_data_error(self, temp_data_dir):
        """Test saving currency data with error"""
        manager = CurrencyManager()
        manager.currency_file = "/invalid/path/currency.json"  # Invalid path
        
        with patch('src.utils.currency_manager.logger.error') as mock_error:
            await manager.save_currency_data()
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_data_existing_user(self, async_currency_manager):
        """Test getting data for existing user"""
        manager = await async_currency_manager
        user_data = await manager.get_user_data("1184766650638155877")
        assert user_data["balance"] == 35125.58309037901
        assert "portfolio" in user_data
        assert "last_hangman_bonus_claim" in user_data

    @pytest.mark.asyncio
    async def test_get_user_data_new_user(self, async_currency_manager):
        """Test getting data for new user with correct default balance"""
        manager = await async_currency_manager
        user_data = await manager.get_user_data("99999")
        assert user_data["balance"] == 100000  # New users start with $100,000
        assert user_data["portfolio"] == {}
        assert user_data["last_daily_claim"] is None
        assert user_data["last_hangman_bonus_claim"] is None

    @pytest.mark.asyncio
    async def test_get_balance(self, async_currency_manager):
        """Test getting user balance"""
        manager = await async_currency_manager
        balance = await manager.get_balance("1184766650638155877")
        assert balance == 35125.58309037901
        
        # Test new user gets default balance
        balance = await manager.get_balance("99999")
        assert balance == 100000

    @pytest.mark.asyncio
    async def test_add_currency(self, async_currency_manager):
        """Test adding currency to user"""
        manager = await async_currency_manager
        initial_balance = await manager.get_balance("1184766650638155877")
        
        new_balance = await manager.add_currency("1184766650638155877", 1000)
        assert new_balance == initial_balance + 1000
        
        # Verify balance was updated
        current_balance = await manager.get_balance("1184766650638155877")
        assert current_balance == initial_balance + 1000

    @pytest.mark.asyncio
    async def test_subtract_currency_sufficient_balance(self, async_currency_manager):
        """Test subtracting currency with sufficient balance"""
        manager = await async_currency_manager
        initial_balance = await manager.get_balance("1184766650638155877")
        
        success, new_balance = await manager.subtract_currency("1184766650638155877", 1000)
        assert success is True
        assert new_balance == initial_balance - 1000
        
        # Verify balance was updated
        current_balance = await manager.get_balance("1184766650638155877")
        assert current_balance == initial_balance - 1000

    @pytest.mark.asyncio
    async def test_subtract_currency_insufficient_balance(self, async_currency_manager):
        """Test subtracting currency with insufficient balance"""
        manager = await async_currency_manager
        initial_balance = await manager.get_balance("1184766650638155877")
        
        success, balance = await manager.subtract_currency("1184766650638155877", 50000)
        assert success is False
        assert balance == initial_balance  # Unchanged
        
        # Verify balance was not changed
        current_balance = await manager.get_balance("1184766650638155877")
        assert current_balance == initial_balance

    @pytest.mark.asyncio
    async def test_transfer_currency_success(self, async_currency_manager):
        """Test successful currency transfer"""
        manager = await async_currency_manager
        from_initial = await manager.get_balance("1184766650638155877")
        to_initial = await manager.get_balance("1046197048313126962")
        
        success, message = await manager.transfer_currency("1184766650638155877", "1046197048313126962", 1000)
        assert success is True
        assert "Successfully transferred" in message
        
        # Verify balances updated correctly
        from_final = await manager.get_balance("1184766650638155877")
        to_final = await manager.get_balance("1046197048313126962")
        
        assert from_final == from_initial - 1000
        assert to_final == to_initial + 1000

    @pytest.mark.asyncio
    async def test_transfer_currency_insufficient_balance(self, async_currency_manager):
        """Test currency transfer with insufficient balance"""
        manager = await async_currency_manager
        from_initial = await manager.get_balance("1184766650638155877")
        to_initial = await manager.get_balance("1046197048313126962")
        
        success, message = await manager.transfer_currency("1184766650638155877", "1046197048313126962", 50000)
        assert success is False
        assert "Insufficient funds" in message
        
        # Verify balances unchanged
        from_final = await manager.get_balance("1184766650638155877")
        to_final = await manager.get_balance("1046197048313126962")
        
        assert from_final == from_initial
        assert to_final == to_initial

    @pytest.mark.asyncio
    async def test_can_claim_daily_never_claimed(self, async_currency_manager):
        """Test daily claim check for user who never claimed"""
        manager = await async_currency_manager
        can_claim, time_left = await manager.can_claim_daily("99999")
        assert can_claim is True
        assert time_left is None

    @pytest.mark.asyncio
    async def test_can_claim_daily_can_claim(self, async_currency_manager):
        """Test daily claim check when user can claim"""
        manager = await async_currency_manager
        # Set last claim to more than 24 hours ago
        old_time = datetime.now() - timedelta(hours=25)
        manager.currency_data["1184766650638155877"]["last_daily_claim"] = old_time.isoformat()
        
        can_claim, time_left = await manager.can_claim_daily("1184766650638155877")
        assert can_claim is True
        assert time_left is None

    @pytest.mark.asyncio
    async def test_can_claim_daily_cannot_claim(self, async_currency_manager):
        """Test daily claim check when user cannot claim"""
        manager = await async_currency_manager
        # Set last claim to recent time
        recent_time = datetime.now() - timedelta(hours=1)
        manager.currency_data["1184766650638155877"]["last_daily_claim"] = recent_time.isoformat()
        
        can_claim, time_left = await manager.can_claim_daily("1184766650638155877")
        assert can_claim is False
        assert time_left is not None
        assert isinstance(time_left, str)  # Returns formatted string like "23h 5m"

    @pytest.mark.asyncio
    async def test_claim_daily_bonus(self, async_currency_manager):
        """Test claiming daily bonus"""
        manager = await async_currency_manager
        # Set user to be able to claim (no recent claim)
        manager.currency_data["1184766650638155877"]["last_daily_claim"] = None
        
        old_balance = await manager.get_balance("1184766650638155877")
        success, message, new_balance = await manager.claim_daily_bonus("1184766650638155877")
        
        assert success is True
        assert f"${DAILY_CLAIM:,}" in message
        assert new_balance == old_balance + DAILY_CLAIM
        
        # Verify claim timestamp was set
        user_data = await manager.get_user_data("1184766650638155877")
        assert user_data["last_daily_claim"] is not None

    def test_format_balance(self, currency_manager):
        """Test balance formatting"""
        assert currency_manager.format_balance(1000) == "$1,000.00"
        assert currency_manager.format_balance(1000000) == "$1,000,000.00"
        assert currency_manager.format_balance(1000.5) == "$1,000.50"

    @pytest.mark.asyncio
    async def test_buy_stock_success(self, async_currency_manager):
        """Test successful stock purchase"""
        manager = await async_currency_manager
        initial_balance = await manager.get_balance("1184766650638155877")
        
        success, message = await manager.buy_stock("1184766650638155877", "MSFT", 5.0, 200.0, 20)
        assert success is True
        assert "Successfully bought" in message
        
        # Check balance was deducted (investment amount = (5 * 200) / 20 = 50)
        expected_balance = initial_balance - 50
        current_balance = await manager.get_balance("1184766650638155877")
        assert abs(current_balance - expected_balance) < 0.01
        
        # Check portfolio was updated
        portfolio = await manager.get_portfolio("1184766650638155877")
        assert "MSFT" in portfolio
        assert portfolio["MSFT"]["shares"] == 5.0
        assert portfolio["MSFT"]["purchase_price"] == 200.0
        assert portfolio["MSFT"]["leverage"] == 20

    @pytest.mark.asyncio
    async def test_buy_stock_insufficient_funds(self, async_currency_manager):
        """Test stock purchase with insufficient funds"""
        manager = await async_currency_manager
        initial_balance = await manager.get_balance("1184766650638155877")
        
        success, message = await manager.buy_stock("1184766650638155877", "MSFT", 2000.0, 200.0, 20)
        assert success is False
        assert "Insufficient funds" in message
        
        # Check balance unchanged
        current_balance = await manager.get_balance("1184766650638155877")
        assert current_balance == initial_balance

    @pytest.mark.asyncio
    async def test_buy_stock_existing_position(self, async_currency_manager):
        """Test buying more of an existing stock"""
        manager = await async_currency_manager
        # Buy more AAPL (user already has 466.4179104477612 shares at $214.4)
        success, message = await manager.buy_stock("1184766650638155877", "AAPL", 5.0, 200.0, 20)
        assert success is True
        assert "Successfully bought" in message
        
        portfolio = await manager.get_portfolio("1184766650638155877")
        assert abs(portfolio["AAPL"]["shares"] - 471.4179104477612) < 0.01  # 466.4179104477612 + 5
        # Average price should be calculated: (466.4179104477612*214.4 + 5*200) / 471.4179104477612
        expected_avg_price = ((466.4179104477612 * 214.4) + (5 * 200)) / 471.4179104477612
        assert abs(portfolio["AAPL"]["purchase_price"] - expected_avg_price) < 0.01

    @pytest.mark.asyncio
    async def test_sell_stock_success(self, async_currency_manager):
        """Test successful stock sale"""
        manager = await async_currency_manager
        initial_balance = await manager.get_balance("1184766650638155877")
        
        # Sell 5 shares of AAPL at current price of $180
        success, message, profit_loss = await manager.sell_stock("1184766650638155877", "AAPL", 5.0, 180.0)
        assert success is True
        assert "Successfully sold" in message
        
        # Check portfolio updated
        portfolio = await manager.get_portfolio("1184766650638155877")
        expected_remaining_shares = 466.4179104477612 - 5.0
        assert abs(portfolio["AAPL"]["shares"] - expected_remaining_shares) < 0.01
        
        # Check balance increased (should get proceeds)
        final_balance = await manager.get_balance("1184766650638155877")
        assert final_balance > initial_balance

    @pytest.mark.asyncio
    async def test_sell_stock_insufficient_shares(self, async_currency_manager):
        """Test selling more shares than owned"""
        manager = await async_currency_manager
        initial_balance = await manager.get_balance("1184766650638155877")
        
        success, message, profit_loss = await manager.sell_stock("1184766650638155877", "AAPL", 500.0, 180.0)
        assert success is False
        assert "You only own" in message
        assert profit_loss == 0.0
        
        # Check balance unchanged
        final_balance = await manager.get_balance("1184766650638155877")
        assert final_balance == initial_balance

    @pytest.mark.asyncio
    async def test_sell_stock_not_owned(self, async_currency_manager):
        """Test selling stock not owned"""
        manager = await async_currency_manager
        initial_balance = await manager.get_balance("1184766650638155877")
        
        success, message, profit_loss = await manager.sell_stock("1184766650638155877", "MSFT", 5.0, 180.0)
        assert success is False
        assert "You don't own any shares" in message
        assert profit_loss == 0.0
        
        # Check balance unchanged
        final_balance = await manager.get_balance("1184766650638155877")
        assert final_balance == initial_balance

    @pytest.mark.asyncio
    async def test_sell_all_shares(self, async_currency_manager):
        """Test selling all shares of a stock"""
        manager = await async_currency_manager
        portfolio = await manager.get_portfolio("1184766650638155877")
        aapl_shares = portfolio["AAPL"]["shares"]
        
        success, message, profit_loss = await manager.sell_stock("1184766650638155877", "AAPL", aapl_shares, 180.0)
        assert success is True
        assert "Successfully sold" in message
        
        # Check stock removed from portfolio
        updated_portfolio = await manager.get_portfolio("1184766650638155877")
        assert "AAPL" not in updated_portfolio

    @pytest.mark.asyncio
    async def test_get_portfolio(self, async_currency_manager):
        """Test getting user portfolio"""
        manager = await async_currency_manager
        portfolio = await manager.get_portfolio("1184766650638155877")
        assert "AAPL" in portfolio
        assert abs(portfolio["AAPL"]["shares"] - 466.4179104477612) < 0.01
        
        # Test empty portfolio
        portfolio = await manager.get_portfolio("773346702257291264")
        assert portfolio == {}

    @pytest.mark.asyncio
    async def test_calculate_portfolio_value(self, async_currency_manager):
        """Test calculating portfolio value"""
        manager = await async_currency_manager
        current_prices = {"AAPL": 180.0}
        total_value, total_profit_loss, details = await manager.calculate_portfolio_value("1184766650638155877", current_prices)
        
        # 466.4179104477612 shares * $180
        expected_value = 466.4179104477612 * 180.0
        assert abs(total_value - expected_value) < 0.01
        assert "AAPL" in details
        assert abs(details["AAPL"]["position_value"] - expected_value) < 0.01
        
        # Profit/loss: (180 - 214.4) * 466.4179104477612
        expected_profit_loss = (180.0 - 214.4) * 466.4179104477612
        assert abs(total_profit_loss - expected_profit_loss) < 0.01
        assert abs(details["AAPL"]["profit_loss"] - expected_profit_loss) < 0.01

    @pytest.mark.asyncio
    async def test_check_and_liquidate_positions(self, async_currency_manager):
        """Test position liquidation logic"""
        manager = await async_currency_manager
        # This would test leveraged positions that need liquidation
        # For now, test that it doesn't crash with normal positions
        current_prices = {"AAPL": 180.0}
        liquidated = await manager.check_and_liquidate_positions("1184766650638155877", current_prices)
        assert isinstance(liquidated, list)

    @pytest.mark.asyncio
    async def test_async_initialization(self, mock_currency_data, temp_data_dir):
        """Test async initialization of CurrencyManager"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        
        # Write test data to file
        with open(manager.currency_file, 'w') as f:
            json.dump(mock_currency_data, f)
        
        await manager.initialize()
        assert manager.currency_data == mock_currency_data

    @pytest.mark.asyncio
    async def test_get_user_lock(self, async_currency_manager):
        """Test user-specific lock creation and retrieval"""
        manager = await async_currency_manager
        user_id = "12345"
        
        # Get lock for first time
        lock1 = await manager._get_user_lock(user_id)
        assert isinstance(lock1, asyncio.Lock)
        
        # Get same lock again
        lock2 = await manager._get_user_lock(user_id)
        assert lock1 is lock2
        
        # Get lock for different user
        lock3 = await manager._get_user_lock("67890")
        assert lock3 is not lock1

    @pytest.mark.asyncio
    async def test_concurrent_currency_operations(self, async_currency_manager):
        """Test that concurrent operations on same user are properly serialized"""
        manager = await async_currency_manager
        user_id = "1184766650638155877"
        initial_balance = await manager.get_balance(user_id)
        
        operation_results = []
        
        async def add_currency_operation():
            result = await manager.add_currency(user_id, 100)
            operation_results.append(("add", result))
        
        async def subtract_currency_operation():
            result = await manager.subtract_currency(user_id, 50)
            operation_results.append(("subtract", result))
        
        # Run operations concurrently - they should be serialized by user locks
        await asyncio.gather(
            add_currency_operation(),
            subtract_currency_operation(),
            add_currency_operation(),
        )
        
        # Final balance should be initial + 100 - 50 + 100 = initial + 150
        final_balance = await manager.get_balance(user_id)
        expected_balance = initial_balance + 150
        
        assert abs(final_balance - expected_balance) < 0.01
        assert len(operation_results) == 3

    @pytest.mark.asyncio
    async def test_async_add_currency(self, async_currency_manager):
        """Test async add_currency with proper locking"""
        manager = await async_currency_manager
        user_id = "12345"
        initial_balance = await manager.get_balance(user_id)  # New user gets 100000
        
        new_balance = await manager.add_currency(user_id, 500)
        assert new_balance == initial_balance + 500
        
        final_balance = await manager.get_balance(user_id)
        assert final_balance == initial_balance + 500

    @pytest.mark.asyncio
    async def test_async_subtract_currency_success(self, async_currency_manager):
        """Test async subtract_currency with sufficient balance"""
        manager = await async_currency_manager
        user_id = "1184766650638155877"
        initial_balance = await manager.get_balance(user_id)
        
        success, new_balance = await manager.subtract_currency(user_id, 1000)
        
        assert success is True
        assert new_balance == initial_balance - 1000
        
        final_balance = await manager.get_balance(user_id)
        assert final_balance == initial_balance - 1000

    @pytest.mark.asyncio
    async def test_async_subtract_currency_insufficient(self, async_currency_manager):
        """Test async subtract_currency with insufficient balance"""
        manager = await async_currency_manager
        user_id = "1184766650638155877"
        initial_balance = await manager.get_balance(user_id)
        
        success, balance = await manager.subtract_currency(user_id, initial_balance + 1000)
        
        assert success is False
        assert balance == initial_balance  # Unchanged
        
        final_balance = await manager.get_balance(user_id)
        assert final_balance == initial_balance

    @pytest.mark.asyncio 
    async def test_race_condition_prevention(self, async_currency_manager):
        """Test that race conditions are prevented with user locks"""
        manager = await async_currency_manager
        user_id = "1184766650638155877"
        initial_balance = await manager.get_balance(user_id)
        
        # Simulate race condition where multiple operations try to subtract from same balance
        async def subtract_operation(amount):
            return await manager.subtract_currency(user_id, amount)
        
        # Try to subtract amounts that together exceed balance
        amount_to_subtract = int(initial_balance * 0.8)
        results = await asyncio.gather(
            subtract_operation(amount_to_subtract),  # 80% of balance
            subtract_operation(amount_to_subtract),  # Another 80% of balance
            return_exceptions=True
        )
        
        # Only one operation should succeed
        successes = sum(1 for success, _ in results if success)
        assert successes == 1
        
        # Balance should only be reduced once
        final_balance = await manager.get_balance(user_id)
        expected_balance = initial_balance - amount_to_subtract
        assert abs(final_balance - expected_balance) < 0.01

    # Hangman Bonus Tests
    @pytest.mark.asyncio
    async def test_can_claim_hangman_bonus_never_claimed(self, async_currency_manager):
        """Test hangman bonus claim check for user who never claimed"""
        manager = await async_currency_manager
        can_claim, time_left = await manager.can_claim_hangman_bonus("99999")
        assert can_claim is True
        assert time_left is None

    @pytest.mark.asyncio
    async def test_can_claim_hangman_bonus_can_claim(self, async_currency_manager):
        """Test hangman bonus claim check when user can claim"""
        manager = await async_currency_manager
        # Set last claim to more than 24 hours ago
        old_time = datetime.now() - timedelta(hours=25)
        user_data = await manager.get_user_data("1184766650638155877")
        user_data["last_hangman_bonus_claim"] = old_time.isoformat()
        
        can_claim, time_left = await manager.can_claim_hangman_bonus("1184766650638155877")
        assert can_claim is True
        assert time_left is None

    @pytest.mark.asyncio
    async def test_can_claim_hangman_bonus_cannot_claim(self, async_currency_manager):
        """Test hangman bonus claim check when user cannot claim"""
        manager = await async_currency_manager
        # Set last claim to recent time (already claimed today)
        recent_time = datetime.now() - timedelta(hours=1)
        user_data = await manager.get_user_data("1184766650638155877")
        user_data["last_hangman_bonus_claim"] = recent_time.isoformat()
        
        can_claim, time_left = await manager.can_claim_hangman_bonus("1184766650638155877")
        assert can_claim is False
        assert time_left is not None
        assert isinstance(time_left, str)  # Returns formatted string like "23h 5m"

    @pytest.mark.asyncio
    async def test_claim_hangman_bonus_success(self, async_currency_manager):
        """Test successful hangman bonus claim with user locks"""
        manager = await async_currency_manager
        # Set user to be able to claim (no recent claim)
        user_data = await manager.get_user_data("1184766650638155877")
        user_data["last_hangman_bonus_claim"] = None
        
        old_balance = await manager.get_balance("1184766650638155877")
        success, message, new_balance = await manager.claim_hangman_bonus("1184766650638155877")
        
        assert success is True
        assert f"${HANGMAN_DAILY_BONUS:,}" in message
        assert new_balance == old_balance + HANGMAN_DAILY_BONUS
        
        # Verify claim timestamp was set
        updated_user_data = await manager.get_user_data("1184766650638155877")
        assert updated_user_data["last_hangman_bonus_claim"] is not None

    @pytest.mark.asyncio
    async def test_claim_hangman_bonus_already_claimed(self, async_currency_manager):
        """Test hangman bonus claim when already claimed"""
        manager = await async_currency_manager
        # Set recent claim
        recent_time = datetime.now() - timedelta(hours=1)
        user_data = await manager.get_user_data("1184766650638155877")
        user_data["last_hangman_bonus_claim"] = recent_time.isoformat()
        
        old_balance = await manager.get_balance("1184766650638155877")
        success, message, balance = await manager.claim_hangman_bonus("1184766650638155877")
        
        assert success is False
        assert "already claimed" in message
        assert balance == old_balance  # Unchanged

    # Parametrized Tests for Edge Cases
    @pytest.mark.parametrize("amount", [0, -100, -1])
    @pytest.mark.asyncio
    async def test_transfer_currency_invalid_amounts(self, async_currency_manager, amount):
        """Test transfer with invalid amounts"""
        manager = await async_currency_manager
        success, message = await manager.transfer_currency("1184766650638155877", "1046197048313126962", amount)
        assert success is False
        assert "must be positive" in message

    @pytest.mark.parametrize("shares", [0, -5, -1])
    @pytest.mark.asyncio
    async def test_buy_stock_invalid_shares(self, async_currency_manager, shares):
        """Test stock purchase with invalid share amounts"""
        manager = await async_currency_manager
        success, message = await manager.buy_stock("1184766650638155877", "MSFT", shares, 200.0, 20)
        assert success is False
        assert "must be positive" in message

    @pytest.mark.parametrize("leverage", [0, -1, -20])
    @pytest.mark.asyncio
    async def test_buy_stock_invalid_leverage(self, async_currency_manager, leverage):
        """Test stock purchase with invalid leverage"""
        manager = await async_currency_manager
        success, message = await manager.buy_stock("1184766650638155877", "MSFT", 5.0, 200.0, leverage)
        assert success is False
        assert "must be positive" in message

    @pytest.mark.parametrize("shares", [0, -5, -1])
    @pytest.mark.asyncio
    async def test_sell_stock_invalid_shares(self, async_currency_manager, shares):
        """Test stock sale with invalid share amounts"""
        manager = await async_currency_manager
        success, message, profit_loss = await manager.sell_stock("1184766650638155877", "AAPL", shares, 180.0)
        assert success is False
        assert "must be positive" in message
        assert profit_loss == 0.0

    # Thread Safety and Concurrency Tests
    @pytest.mark.asyncio
    async def test_concurrent_user_operations_different_users(self, async_currency_manager):
        """Test that operations on different users can run concurrently"""
        manager = await async_currency_manager
        
        user1_id = "1184766650638155877"
        user2_id = "1046197048313126962"
        
        user1_initial = await manager.get_balance(user1_id)
        user2_initial = await manager.get_balance(user2_id)
        
        async def user1_operations():
            await manager.add_currency(user1_id, 100)
            await manager.subtract_currency(user1_id, 50)
        
        async def user2_operations():
            await manager.add_currency(user2_id, 200)
            await manager.subtract_currency(user2_id, 25)
        
        # Run operations concurrently for different users
        await asyncio.gather(
            user1_operations(),
            user2_operations()
        )
        
        # Check final balances
        user1_final = await manager.get_balance(user1_id)
        user2_final = await manager.get_balance(user2_id)
        
        assert user1_final == user1_initial + 50
        assert user2_final == user2_initial + 175

    @pytest.mark.asyncio
    async def test_concurrent_hangman_bonus_claims(self, async_currency_manager):
        """Test that concurrent hangman bonus claims are properly serialized"""
        manager = await async_currency_manager
        user_id = "1184766650638155877"
        
        # Set user to be able to claim
        user_data = await manager.get_user_data(user_id)
        user_data["last_hangman_bonus_claim"] = None
        
        initial_balance = await manager.get_balance(user_id)
        
        # Try to claim bonus concurrently (should only succeed once due to user locks)
        results = await asyncio.gather(
            manager.claim_hangman_bonus(user_id),
            manager.claim_hangman_bonus(user_id),
            manager.claim_hangman_bonus(user_id),
            return_exceptions=True
        )
        
        # Only one claim should succeed
        successes = sum(1 for success, _, _ in results if success)
        assert successes == 1
        
        # Balance should only increase by one bonus amount
        final_balance = await manager.get_balance(user_id)
        assert final_balance == initial_balance + HANGMAN_DAILY_BONUS

    @pytest.mark.asyncio
    async def test_stock_trading_with_mixed_leverage(self, async_currency_manager):
        """Test that mixed leverage positions are handled correctly"""
        manager = await async_currency_manager
        user_id = "1184766650638155877"
        
        # Try to buy more AAPL with different leverage (should fail)
        success, message = await manager.buy_stock(user_id, "AAPL", 1.0, 200.0, 10)
        assert success is False
        assert "Cannot mix leverage levels" in message

    @pytest.mark.asyncio
    async def test_liquidation_with_leverage_losses(self, async_currency_manager):
        """Test automatic liquidation of leveraged positions with 100%+ loss"""
        manager = await async_currency_manager
        user_id = "test_user_liquidation"
        
        # Create user with enough balance
        user_data = await manager.get_user_data(user_id)
        user_data["balance"] = 10000
        
        # Buy leveraged position
        await manager.buy_stock(user_id, "TEST", 100.0, 100.0, 20)  # $500 investment for $10,000 position
        
        # Simulate price crash that would cause 100%+ loss
        crash_prices = {"TEST": 75.0}  # Price drops to $75, causing massive leveraged loss
        
        liquidated = await manager.check_and_liquidate_positions(user_id, crash_prices)
        
        # Position should be liquidated if proceeds <= 0
        portfolio = await manager.get_portfolio(user_id)
        
        # Calculate if position should be liquidated
        purchase_price = 100.0
        current_price = 75.0
        leverage = 20
        shares = 100.0
        
        price_change = current_price - purchase_price
        total_profit = price_change * shares
        original_investment_per_share = purchase_price / leverage
        proceeds = (original_investment_per_share * shares) + total_profit
        
        if proceeds <= 0:
            assert "TEST" not in portfolio
            assert "TEST" in liquidated
        else:
            assert "TEST" in portfolio

    # Integration Tests with Configuration
    @pytest.mark.asyncio
    async def test_daily_claim_amount_from_settings(self, async_currency_manager):
        """Test that daily claim uses amount from settings"""
        manager = await async_currency_manager
        user_id = "test_user"
        
        # Set user to be able to claim
        user_data = await manager.get_user_data(user_id)
        user_data["last_daily_claim"] = None
        
        initial_balance = await manager.get_balance(user_id)
        success, message, new_balance = await manager.claim_daily_bonus(user_id)
        
        assert success is True
        assert new_balance == initial_balance + DAILY_CLAIM
        assert f"${DAILY_CLAIM:,}" in message

    @pytest.mark.asyncio
    async def test_hangman_bonus_amount_from_settings(self, async_currency_manager):
        """Test that hangman bonus uses amount from settings"""
        manager = await async_currency_manager
        user_id = "test_user"
        
        # Set user to be able to claim
        user_data = await manager.get_user_data(user_id)
        user_data["last_hangman_bonus_claim"] = None
        
        initial_balance = await manager.get_balance(user_id)
        success, message, new_balance = await manager.claim_hangman_bonus(user_id)
        
        assert success is True
        assert new_balance == initial_balance + HANGMAN_DAILY_BONUS
        assert f"${HANGMAN_DAILY_BONUS:,}" in message

    @pytest.mark.asyncio
    async def test_stock_leverage_from_settings(self, async_currency_manager):
        """Test that default stock leverage uses value from settings"""
        manager = await async_currency_manager
        user_id = "test_user"
        
        # Buy stock with default leverage (should be STOCK_MARKET_LEVERAGE)
        success, message = await manager.buy_stock(user_id, "MSFT", 1.0, 100.0, STOCK_MARKET_LEVERAGE)
        assert success is True
        
        portfolio = await manager.get_portfolio(user_id)
        assert portfolio["MSFT"]["leverage"] == STOCK_MARKET_LEVERAGE

    # Edge Cases for Data Consistency
    @pytest.mark.asyncio
    async def test_backwards_compatibility_missing_fields(self, temp_data_dir):
        """Test that missing fields in existing user data are handled correctly"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        
        # Create data without hangman bonus field (simulating old data)
        old_data = {
            "123456": {
                "balance": 5000,
                "last_daily_claim": None,
                "portfolio": {}
                # Missing "last_hangman_bonus_claim"
            }
        }
        
        with open(manager.currency_file, 'w') as f:
            json.dump(old_data, f)
        
        await manager.initialize()
        
        # Getting user data should add missing fields
        user_data = await manager.get_user_data("123456")
        assert "last_hangman_bonus_claim" in user_data
        assert user_data["last_hangman_bonus_claim"] is None
        assert "portfolio" in user_data

    @pytest.mark.asyncio
    async def test_new_user_default_values(self, clean_currency_manager):
        """Test that new users get correct default values"""
        manager = await clean_currency_manager
        user_id = "brand_new_user"
        
        user_data = await manager.get_user_data(user_id)
        
        assert user_data["balance"] == 100000  # Default starting balance
        assert user_data["last_daily_claim"] is None
        assert user_data["last_hangman_bonus_claim"] is None
        assert user_data["portfolio"] == {}

    @pytest.mark.asyncio
    async def test_portfolio_value_with_missing_prices(self, async_currency_manager):
        """Test portfolio calculation when some stock prices are missing"""
        manager = await async_currency_manager
        user_id = "1184766650638155877"
        
        # Calculate with partial price data
        partial_prices = {}  # No AAPL price available
        total_value, total_profit_loss, details = await manager.calculate_portfolio_value(user_id, partial_prices)
        
        # Should handle missing prices gracefully
        assert total_value == 0.0
        assert total_profit_loss == 0.0
        assert details == {}

    @pytest.mark.asyncio
    async def test_portfolio_value_with_none_prices(self, async_currency_manager):
        """Test portfolio calculation when stock prices are None"""
        manager = await async_currency_manager
        user_id = "1184766650638155877"
        
        # Calculate with None price
        none_prices = {"AAPL": None}
        total_value, total_profit_loss, details = await manager.calculate_portfolio_value(user_id, none_prices)
        
        # Should handle None prices gracefully
        assert total_value == 0.0
        assert total_profit_loss == 0.0
        assert details == {}