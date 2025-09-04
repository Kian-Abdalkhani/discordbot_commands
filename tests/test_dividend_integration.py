import pytest
import pytest_asyncio
import json
import os
import asyncio
import tempfile
import shutil
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, date, timedelta
from src.utils.dividend_manager import DividendManager
from src.utils.currency_manager import CurrencyManager


class TestDividendIntegration:
    """Test integration between DividendManager and CurrencyManager"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for testing file operations"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def real_currency_manager_factory(self, temp_data_dir):
        """Factory to create a real currency manager for integration testing"""
        async def _create():
            manager = CurrencyManager()
            manager.currency_file = os.path.join(temp_data_dir, "currency.json")
            
            # Initialize with test data
            test_data = {
                "user1": {
                    "balance": 10000.0,
                    "last_daily_claim": "2024-01-01T00:00:00",
                    "last_hangman_bonus_claim": None,
                    "portfolio": {
                        "AAPL": {
                            "shares": 100.0,
                            "purchase_price": 150.0,
                            "leverage": 1,
                            "purchase_date": "2024-01-01T00:00:00"
                        },
                        "MSFT": {
                            "shares": 50.0,
                            "purchase_price": 300.0,
                            "leverage": 1,
                            "purchase_date": "2024-01-15T00:00:00"
                        }
                    },
                    "dividend_earnings": {
                        "total": 0.0,
                        "by_stock": {},
                        "payments": []
                    }
                },
                "user2": {
                    "balance": 5000.0,
                    "last_daily_claim": "2024-01-01T00:00:00",
                    "last_hangman_bonus_claim": None,
                    "portfolio": {
                        "AAPL": {
                            "shares": 75.0,
                            "purchase_price": 155.0,
                            "leverage": 1,
                            "purchase_date": "2024-01-05T00:00:00"
                        }
                    },
                    "dividend_earnings": {
                        "total": 25.0,
                        "by_stock": {"AAPL": 25.0},
                        "payments": [
                            {
                                "symbol": "AAPL",
                                "amount": 25.0,
                                "shares": 75.0,
                                "amount_per_share": 0.333,
                                "ex_dividend_date": "2024-01-15",
                                "payment_date": "2024-01-16T10:00:00"
                            }
                        ]
                    }
                }
            }
            
            with open(manager.currency_file, 'w') as f:
                json.dump(test_data, f)
            
            await manager.initialize()
            return manager
        
        return _create
    
    @pytest_asyncio.fixture
    async def real_currency_manager(self, real_currency_manager_factory):
        """Create a real currency manager instance for testing"""
        return await real_currency_manager_factory()
    
    @pytest_asyncio.fixture
    async def real_dividend_manager(self, temp_data_dir, real_currency_manager):
        """Create a real dividend manager for integration testing"""
        manager = DividendManager(real_currency_manager)
        manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await manager.initialize()
        return manager

    # Test Currency Manager Dividend Methods
    @pytest.mark.asyncio
    async def test_record_dividend_payment_new_user(self, real_currency_manager):
        """Test recording dividend payment for user with no previous dividend earnings"""
        manager = real_currency_manager
        
        # Record dividend for user1 (who has no previous dividend earnings)
        result = await manager.record_dividend_payment("user1", "AAPL", 24.0, 100.0, "2024-08-09")
        
        assert result is True
        
        # Verify dividend earnings were recorded
        user_data = await manager.get_user_data("user1")
        dividend_earnings = user_data["dividend_earnings"]
        
        assert dividend_earnings["total"] == 24.0
        assert dividend_earnings["by_stock"]["AAPL"] == 24.0
        assert len(dividend_earnings["payments"]) == 1
        
        payment = dividend_earnings["payments"][0]
        assert payment["symbol"] == "AAPL"
        assert payment["amount"] == 24.0
        assert payment["shares"] == 100.0
        assert payment["amount_per_share"] == 0.24
        assert payment["ex_dividend_date"] == "2024-08-09"

    @pytest.mark.asyncio
    async def test_record_dividend_payment_existing_user(self, real_currency_manager):
        """Test recording dividend payment for user with existing earnings"""
        manager = real_currency_manager
        
        # Record dividend for user2 (who already has dividend earnings)
        result = await manager.record_dividend_payment("user2", "MSFT", 15.0, 50.0, "2024-08-15")
        
        assert result is True
        
        user_data = await manager.get_user_data("user2")
        dividend_earnings = user_data["dividend_earnings"]
        
        assert dividend_earnings["total"] == 40.0  # 25.0 + 15.0
        assert dividend_earnings["by_stock"]["AAPL"] == 25.0  # Unchanged
        assert dividend_earnings["by_stock"]["MSFT"] == 15.0  # New
        assert len(dividend_earnings["payments"]) == 2

    @pytest.mark.asyncio
    async def test_record_dividend_payment_payment_limit(self, real_currency_manager):
        """Test that payment history is limited to 50 entries"""
        manager = real_currency_manager
        
        # Add 52 payments to exceed the limit
        for i in range(52):
            await manager.record_dividend_payment("user1", "TEST", 1.0, 1.0, f"2024-{i+1:02d}-01")
        
        user_data = await manager.get_user_data("user1")
        payments = user_data["dividend_earnings"]["payments"]
        
        # Should be limited to 50 payments
        assert len(payments) == 50
        
        # Should keep the most recent payments
        assert payments[0]["ex_dividend_date"] == "2024-03-01"  # Should start from 3rd entry
        assert payments[-1]["ex_dividend_date"] == "2024-52-01"

    @pytest.mark.asyncio
    async def test_record_dividend_payment_zero_shares(self, real_currency_manager):
        """Test recording dividend payment with zero shares"""
        manager = real_currency_manager
        
        result = await manager.record_dividend_payment("user1", "AAPL", 0.0, 0.0, "2024-08-09")
        
        assert result is True
        
        user_data = await manager.get_user_data("user1")
        payment = user_data["dividend_earnings"]["payments"][0]
        assert payment["amount_per_share"] == 0.0  # Should handle division by zero

    @pytest.mark.asyncio
    async def test_get_dividend_summary_no_earnings(self, real_currency_manager):
        """Test getting dividend summary for user with no earnings"""
        manager = real_currency_manager
        
        # Clear existing dividend earnings for user1
        user_data = await manager.get_user_data("user1")
        if "dividend_earnings" in user_data:
            del user_data["dividend_earnings"]
        await manager.save_currency_data()
        
        result = await manager.get_dividend_summary("user1")
        
        assert result["total_all_time"] == 0.0
        assert result["total_last_30_days"] == 0.0
        assert result["by_stock"] == {}
        assert result["recent_payments"] == []
        assert result["payment_count"] == 0

    @pytest.mark.asyncio
    async def test_get_dividend_summary_with_earnings(self, real_currency_manager):
        """Test getting dividend summary for user with earnings"""
        manager = real_currency_manager
        
        result = await manager.get_dividend_summary("user2")
        
        assert result["total_all_time"] == 25.0
        assert result["by_stock"]["AAPL"] == 25.0
        assert result["payment_count"] == 1
        assert len(result["recent_payments"]) == 1

    @pytest.mark.asyncio
    async def test_get_dividend_summary_30_day_filter(self, real_currency_manager):
        """Test that dividend summary correctly filters last 30 days"""
        manager = real_currency_manager
        
        # Add old payment (more than 30 days ago)
        old_payment_date = datetime.now() - timedelta(days=45)
        await manager.record_dividend_payment("user1", "OLD", 10.0, 10.0, "2024-01-01")
        
        # Manually set the payment date to be old
        user_data = await manager.get_user_data("user1")
        user_data["dividend_earnings"]["payments"][0]["payment_date"] = old_payment_date.isoformat()
        await manager.save_currency_data()
        
        # Add recent payment
        await manager.record_dividend_payment("user1", "NEW", 5.0, 5.0, "2024-08-01")
        
        result = await manager.get_dividend_summary("user1")
        
        assert result["total_all_time"] == 15.0  # Both payments
        assert result["total_last_30_days"] == 5.0  # Only recent payment

    # Test Full End-to-End Integration
    @pytest.mark.asyncio
    async def test_end_to_end_dividend_processing(self, real_dividend_manager):
        """Test complete end-to-end dividend processing"""
        dividend_manager = real_dividend_manager
        currency_manager = dividend_manager.currency_manager
        
        # Test data
        symbol = "AAPL"
        dividend_amount = 0.30
        ex_dividend_date = "2024-08-15"
        
        # Get initial balances
        user1_initial_balance = await currency_manager.get_balance("user1")
        user2_initial_balance = await currency_manager.get_balance("user2")
        
        # Process dividend payment
        result = await dividend_manager.process_dividend_payment(symbol, dividend_amount, ex_dividend_date)
        assert result is True
        
        # Verify balances increased
        user1_final_balance = await currency_manager.get_balance("user1")
        user2_final_balance = await currency_manager.get_balance("user2")
        
        assert user1_final_balance == user1_initial_balance + 30.0  # 100 shares * 0.30
        assert user2_final_balance == user2_initial_balance + 22.5  # 75 shares * 0.30
        
        # Verify dividend earnings were recorded in currency manager
        user1_summary = await currency_manager.get_dividend_summary("user1")
        user2_summary = await currency_manager.get_dividend_summary("user2")
        
        assert user1_summary["total_all_time"] == 30.0
        assert user2_summary["total_all_time"] == 47.5  # 25.0 (existing) + 22.5 (new)
        
        # Verify dividend history was recorded in dividend manager
        user1_history = await dividend_manager.get_user_dividend_history("user1")
        assert user1_history["total_earned"] == 30.0
        assert user1_history["by_stock"]["AAPL"] == 30.0

    @pytest.mark.asyncio
    async def test_dividend_processing_with_partial_portfolio(self, real_dividend_manager):
        """Test dividend processing when only some users hold the stock"""
        dividend_manager = real_dividend_manager
        currency_manager = dividend_manager.currency_manager
        
        # Add user3 without AAPL position
        user3_data = {
            "balance": 3000.0,
            "last_daily_claim": "2024-01-01T00:00:00",
            "last_hangman_bonus_claim": None,
            "portfolio": {
                "TSLA": {  # Different stock
                    "shares": 10.0,
                    "purchase_price": 800.0,
                    "leverage": 1,
                    "purchase_date": "2024-01-01T00:00:00"
                }
            }
        }
        currency_manager.currency_data["user3"] = user3_data
        await currency_manager.save_currency_data()
        
        # Process AAPL dividend
        result = await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
        assert result is True
        
        # Verify only AAPL holders received dividends
        user3_summary = await currency_manager.get_dividend_summary("user3")
        assert user3_summary["total_all_time"] == 0.0  # Should not have received AAPL dividend

    @pytest.mark.asyncio
    async def test_dividend_processing_with_leverage_positions(self, real_dividend_manager):
        """Test dividend processing with leveraged positions"""
        dividend_manager = real_dividend_manager
        currency_manager = dividend_manager.currency_manager
        
        # Modify user1 to have leveraged position
        user_data = await currency_manager.get_user_data("user1")
        user_data["portfolio"]["AAPL"]["leverage"] = 10  # 10x leverage
        await currency_manager.save_currency_data()
        
        # Process dividend - dividends should be based on share count, not leverage
        result = await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
        assert result is True
        
        # Verify dividend is still calculated based on actual shares (100), not leveraged amount
        user1_summary = await currency_manager.get_dividend_summary("user1")
        assert user1_summary["total_all_time"] == 25.0  # 100 shares * 0.25

    @pytest.mark.asyncio
    async def test_dividend_error_resilience(self, real_dividend_manager):
        """Test system resilience when individual operations fail"""
        dividend_manager = real_dividend_manager
        currency_manager = dividend_manager.currency_manager
        
        original_add_currency = currency_manager.add_currency
        
        # Mock add_currency to fail for user1 but succeed for user2
        async def failing_add_currency(user_id, amount):
            if user_id == "user1":
                raise Exception("Payment system down")
            return await original_add_currency(user_id, amount)
        
        currency_manager.add_currency = failing_add_currency
        
        # Process dividend
        result = await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
        assert result is True  # Should still succeed overall
        
        # Verify user2 still received dividend
        user2_balance = await currency_manager.get_balance("user2")
        assert user2_balance >= 5000.0 + 18.75  # Original balance + dividend
        
        # Verify history records partial success
        history = dividend_manager.dividend_data["dividend_history"]["AAPL"][0]
        assert history["users_paid"] == 1  # Only one user paid successfully

    # Test Cross-Manager Data Consistency
    @pytest.mark.asyncio
    async def test_dividend_data_consistency_across_managers(self, real_dividend_manager):
        """Test that dividend data is consistent between managers"""
        dividend_manager = real_dividend_manager
        currency_manager = dividend_manager.currency_manager
        
        # Process a dividend
        await dividend_manager.process_dividend_payment("AAPL", 0.40, "2024-08-20")
        
        # Get data from both managers
        currency_summary = await currency_manager.get_dividend_summary("user1")
        dividend_history = await dividend_manager.get_user_dividend_history("user1")
        
        # Data should be consistent
        assert currency_summary["total_all_time"] == dividend_history["total_earned"]
        assert currency_summary["by_stock"]["AAPL"] == dividend_history["by_stock"]["AAPL"]

    @pytest.mark.asyncio
    async def test_portfolio_retrieval_integration(self, real_dividend_manager):
        """Test portfolio retrieval integration for dividend calculations"""
        dividend_manager = real_dividend_manager
        
        # Test getting upcoming dividends uses real portfolio data
        with patch.object(dividend_manager, 'get_dividend_info') as mock_get_info:
            # Mock to return dividend info for both AAPL and MSFT
            def side_effect(symbol):
                if symbol == "AAPL":
                    return {
                        "symbol": "AAPL",
                        "pays_dividends": True,
                        "ex_dividend_date": "2024-09-15",
                        "last_dividend_value": 0.25,
                        "dividend_yield": 0.005
                    }
                elif symbol == "MSFT":
                    return {
                        "symbol": "MSFT",
                        "pays_dividends": True,
                        "ex_dividend_date": "2024-09-15", 
                        "last_dividend_value": 0.25,
                        "dividend_yield": 0.005
                    }
                return None
                
            mock_get_info.side_effect = side_effect
            
            result = await dividend_manager.get_upcoming_dividends_for_portfolio("user1")
            
            assert len(result) == 2  # Both AAPL and MSFT
            
            # Find AAPL dividend in results
            aapl_dividend = next((d for d in result if d["symbol"] == "AAPL"), None)
            assert aapl_dividend is not None
            assert aapl_dividend["shares_owned"] == 100.0  # From real portfolio
            assert aapl_dividend["estimated_payout"] == 25.0

    @pytest.mark.asyncio
    async def test_multiple_stock_dividend_processing(self, real_dividend_manager):
        """Test processing dividends for multiple stocks simultaneously"""
        dividend_manager = real_dividend_manager
        currency_manager = dividend_manager.currency_manager
        
        # Get initial balance
        user1_initial = await currency_manager.get_balance("user1")
        
        # Process dividends for both stocks user1 holds
        await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
        await dividend_manager.process_dividend_payment("MSFT", 0.75, "2024-08-10")
        
        # Verify total balance increase
        user1_final = await currency_manager.get_balance("user1")
        expected_increase = (100.0 * 0.25) + (50.0 * 0.75)  # AAPL + MSFT dividends
        assert abs(user1_final - user1_initial - expected_increase) < 0.01
        
        # Verify dividend tracking
        summary = await currency_manager.get_dividend_summary("user1")
        assert summary["by_stock"]["AAPL"] == 25.0
        assert summary["by_stock"]["MSFT"] == 37.5
        assert summary["total_all_time"] == 62.5

    @pytest.mark.asyncio
    async def test_dividend_processing_preserves_other_data(self, real_dividend_manager):
        """Test that dividend processing doesn't affect other user data"""
        dividend_manager = real_dividend_manager
        currency_manager = dividend_manager.currency_manager
        
        # Get initial state
        user1_data_before = await currency_manager.get_user_data("user1")
        initial_portfolio = user1_data_before["portfolio"].copy()
        initial_daily_claim = user1_data_before["last_daily_claim"]
        
        # Process dividend
        await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
        
        # Verify other data preserved
        user1_data_after = await currency_manager.get_user_data("user1")
        assert user1_data_after["portfolio"] == initial_portfolio
        assert user1_data_after["last_daily_claim"] == initial_daily_claim

    # Test Performance and Scalability
    @pytest.mark.asyncio
    async def test_dividend_processing_performance(self, temp_data_dir):
        """Test dividend processing performance with many users"""
        # Create currency manager with many users
        currency_manager = CurrencyManager()
        currency_manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        
        # Create 200 users with AAPL positions
        large_data = {}
        for i in range(200):
            large_data[f"user{i}"] = {
                "balance": 5000.0,
                "portfolio": {
                    "AAPL": {
                        "shares": float(i + 1),  # 1 to 200 shares
                        "purchase_price": 150.0,
                        "leverage": 1,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
            }
        
        with open(currency_manager.currency_file, 'w') as f:
            json.dump(large_data, f)
        
        await currency_manager.initialize()
        
        dividend_manager = DividendManager(currency_manager)
        dividend_manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await dividend_manager.initialize()
        
        # Measure processing time
        start_time = datetime.now()
        result = await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        assert result is True
        assert processing_time < 5.0  # Should complete within 5 seconds
        
        # Verify all users were processed
        history = dividend_manager.dividend_data["dividend_history"]["AAPL"][0]
        assert history["users_paid"] == 200

    # Test Error Recovery and Data Integrity
    @pytest.mark.asyncio
    async def test_dividend_processing_file_corruption_recovery(self, real_dividend_manager):
        """Test recovery from file corruption during dividend processing"""
        dividend_manager = real_dividend_manager
        
        # Simulate file corruption during save
        original_save = dividend_manager.save_dividend_data
        
        async def failing_save():
            # Fail the first save attempt
            if not hasattr(failing_save, 'called'):
                failing_save.called = True
                raise Exception("Disk full")
            else:
                return await original_save()
        
        dividend_manager.save_dividend_data = failing_save
        
        # Process dividend - should handle save failure gracefully
        with patch('src.utils.dividend_manager.logger.error') as mock_error:
            result = await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
            
            # Method returns False when save fails, but currency payments might still have succeeded
            assert result is False
            
            # Verify users still received their dividend payments despite save failure
            user1_balance = await dividend_manager.currency_manager.get_balance("user1")
            user2_balance = await dividend_manager.currency_manager.get_balance("user2")
            
            # Balances should have increased despite save failure
            assert user1_balance >= 10025.0  # Should have received 25.0 dividend
            assert user2_balance >= 5018.75  # Should have received 18.75 dividend
            
            # Verify error was logged
            mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_dividend_and_trading_operations(self, real_dividend_manager):
        """Test dividend processing concurrent with trading operations"""
        dividend_manager = real_dividend_manager
        currency_manager = dividend_manager.currency_manager
        
        async def buy_stock_operation():
            """Simulate concurrent stock buying"""
            await currency_manager.buy_stock("user1", "NVDA", 10.0, 500.0, 1)
        
        async def dividend_operation():
            """Simulate dividend processing"""
            await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
        
        # Run operations concurrently
        results = await asyncio.gather(
            buy_stock_operation(),
            dividend_operation(),
            return_exceptions=True
        )
        
        # Both operations should complete successfully
        # (Note: buy_stock might fail due to insufficient funds, but that's expected)
        # The important thing is that dividend processing works
        dividend_result = results[1]
        assert dividend_result is True or isinstance(dividend_result, Exception) is False

    # Test Data Migration and Backward Compatibility
    @pytest.mark.asyncio
    async def test_dividend_system_with_legacy_users(self, temp_data_dir):
        """Test dividend system with users who don't have dividend_earnings structure"""
        # Create currency manager with legacy user data (no dividend_earnings)
        currency_manager = CurrencyManager()
        currency_manager.currency_file = os.path.join(temp_data_dir, "currency.json")
        
        legacy_data = {
            "legacy_user": {
                "balance": 10000.0,
                "portfolio": {
                    "AAPL": {
                        "shares": 100.0,
                        "purchase_price": 150.0,
                        "leverage": 1,
                        "purchase_date": "2024-01-01T00:00:00"
                    }
                }
                # No dividend_earnings key
            }
        }
        
        with open(currency_manager.currency_file, 'w') as f:
            json.dump(legacy_data, f)
        
        await currency_manager.initialize()
        
        # Create dividend manager
        dividend_manager = DividendManager(currency_manager)
        dividend_manager.dividend_file = os.path.join(temp_data_dir, "dividends.json")
        await dividend_manager.initialize()
        
        # Process dividend for legacy user
        result = await dividend_manager.process_dividend_payment("AAPL", 0.25, "2024-08-09")
        assert result is True
        
        # Verify dividend earnings structure was created
        user_data = await currency_manager.get_user_data("legacy_user")
        assert "dividend_earnings" in user_data
        assert user_data["dividend_earnings"]["total"] == 25.0

    @pytest.mark.asyncio
    async def test_dividend_summary_date_parsing_resilience(self, real_currency_manager):
        """Test dividend summary handles corrupted date data gracefully"""
        manager = real_currency_manager
        
        # Add payment with invalid date format
        user_data = await manager.get_user_data("user2")
        user_data["dividend_earnings"]["payments"].append({
            "symbol": "TEST",
            "amount": 10.0,
            "shares": 10.0,
            "amount_per_share": 1.0,
            "ex_dividend_date": "2024-08-09",
            "payment_date": "invalid_date_format"
        })
        await manager.save_currency_data()
        
        # Should handle gracefully and not crash
        result = await manager.get_dividend_summary("user2")
        
        assert isinstance(result, dict)
        # Should include the manually added payment even with corrupted date
        assert result["total_all_time"] >= 25.0  # At least the original amount
        # total_last_30_days might not include the corrupted entry, but should not crash
        assert "total_last_30_days" in result
        assert isinstance(result["total_last_30_days"], (int, float))