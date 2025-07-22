import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class CurrencyManager:
    """Manages virtual currency for Discord bot users"""
    
    def __init__(self):
        self.currency_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "currency.json"
        )
        self.currency_data = {}
        self.load_currency_data()
    
    def load_currency_data(self):
        """Load currency data from JSON file"""
        try:
            if os.path.exists(self.currency_file):
                with open(self.currency_file, 'r') as f:
                    self.currency_data = json.load(f)
                logger.info(f"Loaded currency data from {self.currency_file}")
            else:
                logger.info(f"No currency file found at {self.currency_file}, starting with empty data")
                self.currency_data = {}
        except Exception as e:
            logger.error(f"Error loading currency data: {e}")
            self.currency_data = {}
    
    def save_currency_data(self):
        """Save currency data to JSON file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.currency_file), exist_ok=True)
            
            with open(self.currency_file, 'w') as f:
                json.dump(self.currency_data, f, indent=4)
            logger.info(f"Saved currency data to {self.currency_file}")
        except Exception as e:
            logger.error(f"Error saving currency data: {e}")
    
    def get_user_data(self, user_id: str) -> Dict:
        """Get user currency data, creating default if doesn't exist"""
        if user_id not in self.currency_data:
            # New users start with $100,000
            self.currency_data[user_id] = {
                "balance": 100000,
                "last_daily_claim": None
            }
            self.save_currency_data()
            logger.info(f"Created new currency account for user {user_id} with $100,000")
        
        return self.currency_data[user_id]
    
    def get_balance(self, user_id: str) -> int:
        """Get user's current balance"""
        user_data = self.get_user_data(user_id)
        return user_data["balance"]
    
    def add_currency(self, user_id: str, amount: int) -> int:
        """Add currency to user's balance. Returns new balance."""
        user_data = self.get_user_data(user_id)
        user_data["balance"] += amount
        self.save_currency_data()
        logger.info(f"Added ${amount} to user {user_id}. New balance: ${user_data['balance']}")
        return user_data["balance"]
    
    def subtract_currency(self, user_id: str, amount: int) -> Tuple[bool, int]:
        """
        Subtract currency from user's balance.
        Returns (success, new_balance).
        """
        user_data = self.get_user_data(user_id)
        
        if user_data["balance"] < amount:
            logger.warning(f"User {user_id} attempted to spend ${amount} but only has ${user_data['balance']}")
            return False, user_data["balance"]
        
        user_data["balance"] -= amount
        self.save_currency_data()
        logger.info(f"Subtracted ${amount} from user {user_id}. New balance: ${user_data['balance']}")
        return True, user_data["balance"]
    
    def transfer_currency(self, from_user_id: str, to_user_id: str, amount: int) -> Tuple[bool, str]:
        """
        Transfer currency between users.
        Returns (success, message).
        """
        if amount <= 0:
            return False, "Transfer amount must be positive."
        
        from_user_data = self.get_user_data(from_user_id)
        to_user_data = self.get_user_data(to_user_id)
        
        if from_user_data["balance"] < amount:
            return False, f"Insufficient funds. You have ${from_user_data['balance']:,} but tried to send ${amount:,}."
        
        # Perform the transfer
        from_user_data["balance"] -= amount
        to_user_data["balance"] += amount
        self.save_currency_data()
        
        logger.info(f"Transferred ${amount} from user {from_user_id} to user {to_user_id}")
        return True, f"Successfully transferred ${amount:,}!"
    
    def can_claim_daily(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user can claim daily bonus.
        Returns (can_claim, time_until_next_claim).
        """
        user_data = self.get_user_data(user_id)
        last_claim = user_data["last_daily_claim"]
        
        if last_claim is None:
            return True, None
        
        try:
            last_claim_date = datetime.fromisoformat(last_claim)
            now = datetime.now()
            
            # Check if 24 hours have passed
            if now - last_claim_date >= timedelta(hours=24):
                return True, None
            else:
                next_claim = last_claim_date + timedelta(hours=24)
                time_left = next_claim - now
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                return False, f"{hours}h {minutes}m"
        
        except Exception as e:
            logger.error(f"Error parsing last claim date for user {user_id}: {e}")
            return True, None
    
    def claim_daily_bonus(self, user_id: str) -> Tuple[bool, str, int]:
        """
        Claim daily bonus for user.
        Returns (success, message, new_balance).
        """
        can_claim, time_left = self.can_claim_daily(user_id)
        
        if not can_claim:
            user_data = self.get_user_data(user_id)
            return False, f"You already claimed your daily bonus! Next claim in {time_left}.", user_data["balance"]
        
        # Give daily bonus
        daily_amount = 1000
        new_balance = self.add_currency(user_id, daily_amount)
        
        # Update last claim time
        user_data = self.get_user_data(user_id)
        user_data["last_daily_claim"] = datetime.now().isoformat()
        self.save_currency_data()
        
        logger.info(f"User {user_id} claimed daily bonus of ${daily_amount}")
        return True, f"You claimed your daily bonus of ${daily_amount:,}!", new_balance
    
    def format_balance(self, balance: int) -> str:
        """Format balance with commas and dollar sign"""
        return f"${balance:,}"