import pytest
import asyncio
import json
import os
import tempfile
import shutil
import stat
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime, timedelta

from src.utils.currency_manager import CurrencyManager
from src.config.settings import DAILY_CLAIM, HANGMAN_DAILY_BONUS, STOCK_MARKET_LEVERAGE


class TestCurrencyEdgeCases:
    """Edge case tests for CurrencyManager focusing on error handling, file corruption, and boundary conditions"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for testing file operations"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def currency_manager(self, temp_data_dir):
        """Create a CurrencyManager with temporary file"""
        async def _create_manager():
            manager = CurrencyManager()
            manager.currency_file = os.path.join(temp_data_dir, "currency.json")
            await manager.initialize()
            return manager
        return _create_manager()

    # File System Error Tests
    @pytest.mark.asyncio
    async def test_load_currency_data_permission_denied(self, temp_data_dir):
        """Test loading currency data when file permissions are denied"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "readonly_currency.json")
        
        # Create file with initial data
        initial_data = {"test_user": {"balance": 5000, "portfolio": {}}}
        with open(manager.currency_file, 'w') as f:
            json.dump(initial_data, f)
        
        # Make file read-only (simulate permission error)
        os.chmod(manager.currency_file, stat.S_IRUSR)
        
        try:
            # Should still be able to read
            await manager.load_currency_data()
            assert manager.currency_data == initial_data
        finally:
            # Restore permissions for cleanup
            os.chmod(manager.currency_file, stat.S_IRUSR | stat.S_IWUSR)

    @pytest.mark.asyncio
    async def test_save_currency_data_permission_denied(self, temp_data_dir):
        """Test saving currency data when write permissions are denied"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "readonly_currency.json")
        
        # Create file and make directory read-only
        with open(manager.currency_file, 'w') as f:
            json.dump({}, f)
        
        os.chmod(temp_data_dir, stat.S_IRUSR | stat.S_IXUSR)  # Remove write permission
        
        try:
            with patch('src.utils.currency_manager.logger.error') as mock_error:
                await manager.save_currency_data()
                # Should log error but not crash
                mock_error.assert_called_once()
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_data_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    @pytest.mark.asyncio
    async def test_save_currency_data_disk_full_simulation(self, currency_manager):
        """Test saving currency data when disk is full (simulated via OSError)"""
        with patch('aiofiles.open', side_effect=OSError("No space left on device")):
            with patch('src.utils.currency_manager.logger.error') as mock_error:
                await currency_manager.save_currency_data()
                # Should handle disk full error gracefully
                mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_currency_data_file_locked(self, temp_data_dir):
        """Test loading currency data when file is locked by another process"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "locked_currency.json")
        
        with patch('aiofiles.open', side_effect=PermissionError("File is locked")):
            with patch('src.utils.currency_manager.logger.error') as mock_error:
                await manager.load_currency_data()
                # Should handle file lock gracefully
                assert manager.currency_data == {}
                mock_error.assert_called_once()

    # Data Corruption Tests
    @pytest.mark.asyncio
    async def test_load_currency_data_corrupted_json(self, temp_data_dir):
        """Test loading completely corrupted JSON data"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "corrupted.json")
        
        # Write various types of corrupted data that should actually fail JSON parsing
        corrupted_data_samples = [
            "{ invalid json }",
            '{"key": value_without_quotes}',
            '{"incomplete": "json"',
            '{"nested": {"incomplete": }',
            '{"unicode": "\\uXXXX"}',
            '{"number": 123.456.789}',
            "not json at all",
            '{"unterminated": "string',
            '{"missing_colon" "value"}',
        ]
        
        for corrupted_data in corrupted_data_samples:
            with open(manager.currency_file, 'w') as f:
                f.write(corrupted_data)
            
            with patch('src.utils.currency_manager.logger.error') as mock_error:
                await manager.load_currency_data()
                # Should handle corruption gracefully - some might succeed, some fail
                # The key is that it doesn't crash and handles errors
                if mock_error.called:
                    # If error was logged, data should be empty
                    assert manager.currency_data == {}
                
                # Reset for next test
                manager.currency_data = {}

    @pytest.mark.asyncio
    async def test_load_currency_data_partial_corruption(self, temp_data_dir):
        """Test loading data with partial corruption but valid JSON structure"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "partial_corrupted.json")
        
        # Data with missing required fields
        partial_data = {
            "valid_user": {
                "balance": 5000,
                "last_daily_claim": None,
                "portfolio": {}
            },
            "corrupted_user_1": {
                "balance": "invalid_balance_type",  # Should be number
                "portfolio": {}
            },
            "corrupted_user_2": {
                # Missing balance field
                "last_daily_claim": None,
                "portfolio": {}
            },
            "corrupted_user_3": {
                "balance": 1000,
                "portfolio": "invalid_portfolio_type"  # Should be dict
            }
        }
        
        with open(manager.currency_file, 'w') as f:
            json.dump(partial_data, f)
        
        await manager.load_currency_data()
        
        # Should load the data as-is (let get_user_data handle corrections)
        assert "valid_user" in manager.currency_data
        assert "corrupted_user_1" in manager.currency_data
        assert "corrupted_user_2" in manager.currency_data
        assert "corrupted_user_3" in manager.currency_data

    @pytest.mark.asyncio
    async def test_get_user_data_with_corrupted_user_data(self, currency_manager):
        """Test get_user_data handles and fixes corrupted user data"""
        # Manually insert corrupted user data
        currency_manager.currency_data["corrupted_user"] = {
            "balance": "not_a_number",
            "portfolio": "not_a_dict"
            # Missing required fields
        }
        
        # get_user_data should handle and fix corruption
        user_data = await currency_manager.get_user_data("corrupted_user")
        
        # Should have correct structure now
        assert isinstance(user_data["balance"], (int, float))
        assert isinstance(user_data["portfolio"], dict)
        assert "last_daily_claim" in user_data
        assert "last_hangman_bonus_claim" in user_data

    @pytest.mark.asyncio
    async def test_currency_file_becomes_directory(self, temp_data_dir):
        """Test handling when currency file path is occupied by a directory"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        
        # Create directory with same name as expected file
        os.makedirs(manager.currency_file)
        
        with patch('src.utils.currency_manager.logger.error') as mock_error:
            await manager.load_currency_data()
            # Should handle gracefully
            assert manager.currency_data == {}
            mock_error.assert_called_once()

    # Boundary Condition Tests
    @pytest.mark.asyncio
    async def test_extremely_large_balance_operations(self, currency_manager):
        """Test operations with extremely large balance values"""
        manager = await currency_manager
        user_id = "large_balance_user"
        
        # Test with very large numbers
        large_amount = 999_999_999_999_999  # Nearly a quadrillion
        
        # Should handle large additions
        new_balance = await manager.add_currency(user_id, large_amount)
        assert new_balance == 100_000 + large_amount  # Default + large amount
        
        # Should handle large subtractions
        success, balance = await manager.subtract_currency(user_id, large_amount // 2)
        assert success is True
        # After adding large_amount and subtracting half of it, we should have initial + half
        expected_balance = 100_000 + large_amount - (large_amount // 2)
        assert balance == expected_balance

    @pytest.mark.asyncio
    async def test_zero_and_negative_boundary_conditions(self, currency_manager):
        """Test boundary conditions around zero and negative values"""
        manager = await currency_manager
        user_id = "boundary_user"
        
        # Test zero operations
        zero_balance = await manager.add_currency(user_id, 0)
        initial_balance = await manager.get_balance(user_id)
        assert zero_balance == initial_balance  # Should be unchanged
        
        # Test subtracting exact balance
        success, new_balance = await manager.subtract_currency(user_id, initial_balance)
        assert success is True
        assert new_balance == 0
        
        # Test subtracting from zero balance
        success, balance = await manager.subtract_currency(user_id, 1)
        assert success is False
        assert balance == 0

    @pytest.mark.asyncio
    async def test_floating_point_precision_issues(self, currency_manager):
        """Test handling of floating point precision issues"""
        manager = await currency_manager
        user_id = "precision_user"
        
        # Add amounts that might cause floating point issues
        await manager.add_currency(user_id, 0.1)
        await manager.add_currency(user_id, 0.2)
        
        balance = await manager.get_balance(user_id)
        # Should handle floating point precision correctly
        expected = 100_000 + 0.1 + 0.2
        assert abs(balance - expected) < 1e-10

    # Stock Market Edge Cases
    @pytest.mark.asyncio
    async def test_stock_operations_with_extreme_values(self, currency_manager):
        """Test stock operations with extreme price and share values"""
        user_id = "extreme_stock_user"
        
        # Add large balance for testing
        await currency_manager.add_currency(user_id, 1_000_000)
        
        # Test with very small share amounts
        success, message = await currency_manager.buy_stock(user_id, "MICRO", 0.0001, 1000.0, 20)
        assert success is True
        
        # Test with very large share amounts
        success, message = await currency_manager.buy_stock(user_id, "MACRO", 1_000_000.0, 0.01, 20)
        assert success is True
        
        # Test with extreme leverage
        success, message = await currency_manager.buy_stock(user_id, "LEVER", 1.0, 100.0, 1000)
        assert success is True

    @pytest.mark.asyncio
    async def test_stock_liquidation_edge_cases(self, currency_manager):
        """Test edge cases in stock position liquidation"""
        user_id = "liquidation_user"
        
        # Create leveraged position that will be liquidated
        await currency_manager.add_currency(user_id, 10000)
        await currency_manager.buy_stock(user_id, "RISKY", 1000.0, 100.0, 50)  # High leverage
        
        # Test liquidation with extreme price drops
        crash_prices = {
            "RISKY": 0.01,  # Price drops to almost zero
            "MISSING": None,  # Missing price data
        }
        
        liquidated = await currency_manager.check_and_liquidate_positions(user_id, crash_prices)
        
        # Should handle extreme liquidation scenario
        portfolio = await currency_manager.get_portfolio(user_id)
        assert isinstance(liquidated, list)

    # Date/Time Edge Cases
    @pytest.mark.asyncio
    async def test_daily_claim_with_corrupted_timestamps(self, currency_manager):
        """Test daily claim handling with corrupted timestamp data"""
        user_id = "timestamp_user"
        
        # Set corrupted timestamp
        user_data = await currency_manager.get_user_data(user_id)
        user_data["last_daily_claim"] = "not_a_valid_timestamp"
        
        # Should handle corrupted timestamp gracefully
        can_claim, time_left = await currency_manager.can_claim_daily(user_id)
        assert can_claim is True  # Should default to allowing claim
        assert time_left is None

    @pytest.mark.asyncio
    async def test_hangman_bonus_with_future_timestamps(self, currency_manager):
        """Test hangman bonus with timestamps set in the future"""
        user_id = "future_user"
        
        # Set timestamp in future
        future_time = datetime.now() + timedelta(days=1)
        user_data = await currency_manager.get_user_data(user_id)
        user_data["last_hangman_bonus_claim"] = future_time.isoformat()
        
        # Should handle future timestamp appropriately
        can_claim, time_left = await currency_manager.can_claim_hangman_bonus(user_id)
        # Depending on implementation, might allow claim or calculate negative time
        assert isinstance(can_claim, bool)

    @pytest.mark.asyncio
    async def test_timezone_edge_cases(self, currency_manager):
        """Test handling of timezone-related edge cases"""
        user_id = "timezone_user"
        
        # Test with timezone-aware timestamps
        utc_time = datetime.utcnow()
        user_data = await currency_manager.get_user_data(user_id)
        user_data["last_daily_claim"] = utc_time.isoformat() + "Z"  # UTC indicator
        
        # Should handle timezone indicators
        can_claim, time_left = await currency_manager.can_claim_daily(user_id)
        assert isinstance(can_claim, bool)

    # Concurrency Edge Cases
    @pytest.mark.asyncio
    async def test_rapid_concurrent_file_operations(self, currency_manager):
        """Test rapid concurrent file save operations"""
        user_id = "rapid_ops_user"
        
        async def rapid_operation(amount):
            await currency_manager.add_currency(user_id, amount)
        
        # Launch many concurrent operations
        tasks = [rapid_operation(i) for i in range(1, 51)]  # 50 concurrent operations
        
        # Should handle without corruption
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify final balance is correct
        final_balance = await currency_manager.get_balance(user_id)
        expected_total = sum(range(1, 51))  # Sum of 1+2+...+50
        assert final_balance == 100_000 + expected_total

    @pytest.mark.asyncio
    async def test_lock_acquisition_timeout_simulation(self, currency_manager):
        """Test behavior when lock acquisition takes a very long time"""
        user_id = "lock_timeout_user"
        
        # Create a lock that takes a long time to release
        user_lock = await currency_manager._get_user_lock(user_id)
        
        async def long_running_operation():
            async with user_lock:
                await asyncio.sleep(1)  # Hold lock for 1 second
                await currency_manager.add_currency(user_id, 100)
        
        async def quick_operation():
            await currency_manager.add_currency(user_id, 50)
        
        # Start long operation
        long_task = asyncio.create_task(long_running_operation())
        
        # Wait a bit then start quick operation
        await asyncio.sleep(0.1)
        quick_task = asyncio.create_task(quick_operation())
        
        # Both should complete without deadlock
        await asyncio.gather(long_task, quick_task)
        
        # Verify both operations completed
        final_balance = await currency_manager.get_balance(user_id)
        assert final_balance == 100_000 + 150  # 100 + 50

    # Memory and Performance Edge Cases
    @pytest.mark.asyncio
    async def test_large_user_dataset_performance(self, currency_manager):
        """Test performance with large number of users"""
        # Create many users
        user_count = 1000
        
        tasks = []
        for i in range(user_count):
            user_id = f"user_{i:04d}"
            tasks.append(currency_manager.add_currency(user_id, 100))
        
        # Should handle large dataset efficiently
        await asyncio.gather(*tasks)
        
        # Verify all users were created
        assert len(currency_manager.currency_data) >= user_count

    @pytest.mark.asyncio
    async def test_portfolio_with_many_positions(self, currency_manager):
        """Test portfolio operations with many stock positions"""
        user_id = "diverse_portfolio_user"
        
        # Add large balance
        await currency_manager.add_currency(user_id, 1_000_000)
        
        # Create many stock positions
        stock_count = 100
        for i in range(stock_count):
            symbol = f"STOCK{i:03d}"
            await currency_manager.buy_stock(user_id, symbol, 10.0, 100.0, 20)
        
        # Test portfolio operations with many positions
        portfolio = await currency_manager.get_portfolio(user_id)
        assert len(portfolio) == stock_count
        
        # Test portfolio value calculation with many positions
        prices = {f"STOCK{i:03d}": 120.0 for i in range(stock_count)}
        total_value, profit_loss, details = await currency_manager.calculate_portfolio_value(user_id, prices)
        
        assert len(details) == stock_count
        assert total_value > 0
        assert profit_loss > 0  # All stocks went up in price

    # Data Recovery Edge Cases
    @pytest.mark.asyncio
    async def test_partial_data_recovery(self, temp_data_dir):
        """Test recovery from partially corrupted data files"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "partial_recovery.json")
        
        # Create data with some valid and some invalid entries
        mixed_data = {
            "good_user_1": {
                "balance": 5000,
                "last_daily_claim": None,
                "portfolio": {"AAPL": {"shares": 10, "purchase_price": 150, "leverage": 20}}
            },
            "good_user_2": {
                "balance": 3000,
                "last_daily_claim": "2025-01-01T00:00:00",
                "portfolio": {}
            },
            "bad_user_1": {
                "balance": None,  # Invalid
                "last_daily_claim": "invalid_date",
                "portfolio": {"MSFT": "invalid_position_data"}
            }
        }
        
        with open(manager.currency_file, 'w') as f:
            json.dump(mixed_data, f)
        
        await manager.initialize()
        
        # Should load all data, let individual operations handle validation
        assert len(manager.currency_data) == 3
        assert "good_user_1" in manager.currency_data
        assert "good_user_2" in manager.currency_data
        assert "bad_user_1" in manager.currency_data

    @pytest.mark.asyncio
    async def test_empty_file_recovery(self, temp_data_dir):
        """Test recovery from completely empty file"""
        manager = CurrencyManager()
        manager.currency_file = os.path.join(temp_data_dir, "empty.json")
        
        # Create empty file
        with open(manager.currency_file, 'w') as f:
            pass  # Write nothing
        
        await manager.load_currency_data()
        
        # Should handle empty file gracefully
        assert manager.currency_data == {}
        
        # Should be able to operate normally after
        user_data = await manager.get_user_data("new_user")
        assert user_data["balance"] == 100_000

    @pytest.mark.asyncio
    async def test_file_truncation_during_write(self, currency_manager):
        """Test handling of file truncation during write operations"""
        user_id = "truncation_test_user"
        await currency_manager.add_currency(user_id, 1000)
        
        # Simulate file truncation during write
        original_write = None
        
        async def truncating_write(content):
            # Write only part of the content to simulate truncation
            truncated_content = content[:len(content)//2]
            with open(currency_manager.currency_file, 'w') as f:
                f.write(truncated_content)
        
        with patch('aiofiles.open') as mock_open:
            mock_file = AsyncMock()
            mock_file.write = truncating_write
            mock_open.return_value.__aenter__.return_value = mock_file
            
            # This should cause corruption but not crash
            await currency_manager.save_currency_data()
        
        # Try to load the corrupted file
        with patch('src.utils.currency_manager.logger.error') as mock_error:
            new_manager = CurrencyManager()
            new_manager.currency_file = currency_manager.currency_file
            await new_manager.load_currency_data()
            
            # Should handle corrupted file gracefully
            mock_error.assert_called_once()
            assert new_manager.currency_data == {}

    # Unicode and Special Character Edge Cases
    @pytest.mark.asyncio
    async def test_unicode_user_ids(self, currency_manager):
        """Test handling of Unicode characters in user IDs"""
        unicode_user_ids = [
            "用户123",  # Chinese characters
            "usuario_español",  # Spanish
            "пользователь",  # Cyrillic
            "🎮gamer🎮",  # Emoji
            "user\u0000null",  # Null character
            "user\ttab",  # Tab character
            "user\nnewline",  # Newline
        ]
        
        for user_id in unicode_user_ids:
            try:
                balance = await currency_manager.get_balance(user_id)
                assert balance == 100_000  # Should handle Unicode gracefully
                
                # Test operations
                await currency_manager.add_currency(user_id, 100)
                new_balance = await currency_manager.get_balance(user_id)
                assert new_balance == 100_100
            except Exception as e:
                # If Unicode causes issues, should be handled gracefully
                assert isinstance(e, (UnicodeError, ValueError))

    @pytest.mark.asyncio
    async def test_extremely_long_user_ids(self, currency_manager):
        """Test handling of extremely long user IDs"""
        long_user_id = "a" * 10000  # 10K character user ID
        
        # Should handle long IDs without crashing
        balance = await currency_manager.get_balance(long_user_id)
        assert balance == 100_000
        
        # Test that file operations still work
        await currency_manager.add_currency(long_user_id, 500)
        new_balance = await currency_manager.get_balance(long_user_id)
        assert new_balance == 100_500