#!/usr/bin/env python3
"""
Test script for the virtual currency system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.currency_manager import CurrencyManager
import json

def test_currency_system():
    """Test all currency system functionality"""
    print("🧪 Testing Virtual Currency System")
    print("=" * 50)
    
    # Initialize currency manager
    cm = CurrencyManager()
    
    # Test user IDs (fake Discord user IDs)
    user1 = "123456789012345678"
    user2 = "987654321098765432"
    
    print("\n1. Testing new user creation...")
    balance1 = cm.get_balance(user1)
    print(f"   User1 initial balance: {cm.format_balance(balance1)}")
    assert balance1 == 100000, f"Expected $100,000, got ${balance1}"
    print("   ✅ New user starts with $100,000")
    
    print("\n2. Testing currency addition...")
    new_balance = cm.add_currency(user1, 5000)
    print(f"   Added $5,000. New balance: {cm.format_balance(new_balance)}")
    assert new_balance == 105000, f"Expected $105,000, got ${new_balance}"
    print("   ✅ Currency addition works correctly")
    
    print("\n3. Testing currency subtraction...")
    success, new_balance = cm.subtract_currency(user1, 10000)
    print(f"   Subtracted $10,000. Success: {success}, New balance: {cm.format_balance(new_balance)}")
    assert success and new_balance == 95000, f"Expected success=True and $95,000, got success={success} and ${new_balance}"
    print("   ✅ Currency subtraction works correctly")
    
    print("\n4. Testing insufficient funds...")
    success, balance = cm.subtract_currency(user1, 200000)
    print(f"   Tried to subtract $200,000. Success: {success}, Balance: {cm.format_balance(balance)}")
    assert not success and balance == 95000, f"Expected success=False and $95,000, got success={success} and ${balance}"
    print("   ✅ Insufficient funds handling works correctly")
    
    print("\n5. Testing currency transfer...")
    # Create second user
    balance2 = cm.get_balance(user2)
    print(f"   User2 initial balance: {cm.format_balance(balance2)}")
    
    success, message = cm.transfer_currency(user1, user2, 15000)
    print(f"   Transfer result: {success}, Message: {message}")
    
    balance1_after = cm.get_balance(user1)
    balance2_after = cm.get_balance(user2)
    print(f"   User1 balance after transfer: {cm.format_balance(balance1_after)}")
    print(f"   User2 balance after transfer: {cm.format_balance(balance2_after)}")
    
    assert success, f"Transfer should succeed"
    assert balance1_after == 80000, f"User1 should have $80,000, got ${balance1_after}"
    assert balance2_after == 115000, f"User2 should have $115,000, got ${balance2_after}"
    print("   ✅ Currency transfer works correctly")
    
    print("\n6. Testing daily bonus...")
    can_claim, time_left = cm.can_claim_daily(user1)
    print(f"   Can claim daily: {can_claim}, Time left: {time_left}")
    assert can_claim, "Should be able to claim daily bonus for new user"
    
    success, message, new_balance = cm.claim_daily_bonus(user1)
    print(f"   Daily bonus result: {success}, Message: {message}")
    print(f"   New balance: {cm.format_balance(new_balance)}")
    assert success and new_balance == 81000, f"Expected success and $81,000, got success={success} and ${new_balance}"
    print("   ✅ Daily bonus works correctly")
    
    print("\n7. Testing daily bonus cooldown...")
    can_claim, time_left = cm.can_claim_daily(user1)
    print(f"   Can claim daily again: {can_claim}, Time left: {time_left}")
    assert not can_claim, "Should not be able to claim daily bonus again immediately"
    print("   ✅ Daily bonus cooldown works correctly")
    
    print("\n8. Testing data persistence...")
    # Save and reload
    cm.save_currency_data()
    cm2 = CurrencyManager()
    
    balance1_reloaded = cm2.get_balance(user1)
    balance2_reloaded = cm2.get_balance(user2)
    print(f"   User1 balance after reload: {cm2.format_balance(balance1_reloaded)}")
    print(f"   User2 balance after reload: {cm2.format_balance(balance2_reloaded)}")
    
    assert balance1_reloaded == 81000, f"User1 balance should persist as $81,000, got ${balance1_reloaded}"
    assert balance2_reloaded == 115000, f"User2 balance should persist as $115,000, got ${balance2_reloaded}"
    print("   ✅ Data persistence works correctly")
    
    print("\n" + "=" * 50)
    print("🎉 All currency system tests passed!")
    print("=" * 50)
    
    # Display final currency data
    print("\nFinal currency data:")
    with open(cm.currency_file, 'r') as f:
        data = json.load(f)
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    test_currency_system()