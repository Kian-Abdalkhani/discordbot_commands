import json
import os
import logging
import aiofiles
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, Optional, Tuple, List

from src.config.settings import DAILY_CLAIM, STOCK_MARKET_LEVERAGE, HANGMAN_DAILY_BONUS, TRANSACTION_TYPES
from src.utils.transaction_logger import TransactionLogger

logger = logging.getLogger(__name__)

class CurrencyManager:
    """Manages virtual currency for Discord bot users"""
    
    def __init__(self):
        self.currency_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "currency.json"
        )
        self.currency_data = {}
        self._locks = {}  # Per-user locks for atomic operations
        self._global_lock = asyncio.Lock()  # Global lock for managing user locks
        self.transaction_logger = TransactionLogger()
    
    async def initialize(self):
        """Initialize the currency manager by loading data"""
        await self.load_currency_data()
        await self.transaction_logger.initialize()
    
    async def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific user"""
        async with self._global_lock:
            if user_id not in self._locks:
                self._locks[user_id] = asyncio.Lock()
            return self._locks[user_id]
    
    async def load_currency_data(self):
        """Load currency data from JSON file"""
        try:
            if os.path.exists(self.currency_file):
                async with aiofiles.open(self.currency_file, 'r') as f:
                    content = await f.read()
                    self.currency_data = json.loads(content)
                logger.info(f"Loaded currency data from {self.currency_file}")
            else:
                logger.info(f"No currency file found at {self.currency_file}, starting with empty data")
                self.currency_data = {}
        except Exception as e:
            logger.error(f"Error loading currency data: {e}")
            self.currency_data = {}
    
    async def save_currency_data(self):
        """Save currency data to JSON file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.currency_file), exist_ok=True)
            
            async with aiofiles.open(self.currency_file, 'w') as f:
                await f.write(json.dumps(self.currency_data, indent=4))
            logger.info(f"Saved currency data to {self.currency_file}")
        except Exception as e:
            logger.error(f"Error saving currency data: {e}")
    
    async def get_user_data(self, user_id: str) -> Dict:
        """Get user currency data, creating default if doesn't exist"""
        if user_id not in self.currency_data:
            # New users start with $100,000
            self.currency_data[user_id] = {
                "balance": 100000,
                "last_daily_claim": None,
                "last_hangman_bonus_claim": None,
                "portfolio": {}  # Stock positions: {symbol: {shares, purchase_price, leverage, purchase_date}}
            }
            await self.save_currency_data()
            logger.info(f"Created new currency account for user {user_id} with $100,000")
        
        # Ensure portfolio exists for existing users
        if "portfolio" not in self.currency_data[user_id]:
            self.currency_data[user_id]["portfolio"] = {}
            await self.save_currency_data()
        
        # Ensure hangman bonus claim tracking exists for existing users
        if "last_hangman_bonus_claim" not in self.currency_data[user_id]:
            self.currency_data[user_id]["last_hangman_bonus_claim"] = None
            await self.save_currency_data()
        
        return self.currency_data[user_id]
    
    async def get_balance(self, user_id: str) -> float:
        """Get user's current balance"""
        user_data = await self.get_user_data(user_id)
        return user_data["balance"]
    
    async def add_currency(self, user_id: str, amount: int, command: str = "add_currency", 
                          metadata: Optional[Dict] = None, profit_loss: float = 0.0,
                          transaction_type: str = "currency", display_name: Optional[str] = None,
                          mention: Optional[str] = None, skip_logging: bool = False) -> float:
        """Add currency to user's balance. Returns new balance."""
        await self.load_currency_data()
        user_data = await self.get_user_data(user_id)
        balance_before = user_data["balance"]
        user_data["balance"] += amount
        balance_after = user_data["balance"]
        await self.save_currency_data()
        
        # Log the transaction with enhanced data (unless skipping logging)
        if not skip_logging:
            await self.transaction_logger.log_transaction(
                user_id=user_id,
                command=command,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                profit_loss=profit_loss,
                transaction_type=transaction_type,
                metadata=metadata,
                display_name=display_name,
                mention=mention
            )
        
        logger.info(f"Added ${amount} to user {user_id}. New balance: ${user_data['balance']}")
        return user_data["balance"]
    
    async def subtract_currency(self, user_id: str, amount: int, command: str = "subtract_currency", 
                               metadata: Optional[Dict] = None, profit_loss: float = 0.0,
                               transaction_type: str = "currency", display_name: Optional[str] = None,
                               mention: Optional[str] = None, skip_logging: bool = False) -> Tuple[bool, float]:
        """
        Subtract currency from user's balance.
        Returns (success, new_balance).
        """
        user_data = await self.get_user_data(user_id)
        balance_before = user_data["balance"]
        
        if user_data["balance"] < amount:
            logger.warning(f"User {user_id} attempted to spend ${amount} but only has ${user_data['balance']}")
            return False, user_data["balance"]
        
        user_data["balance"] -= amount
        balance_after = user_data["balance"]
        await self.save_currency_data()
        
        # Log the transaction with enhanced data (unless skipping logging)
        if not skip_logging:
            await self.transaction_logger.log_transaction(
                user_id=user_id,
                command=command,
                amount=-amount,  # Negative amount for subtractions
                balance_before=balance_before,
                balance_after=balance_after,
                profit_loss=profit_loss,
                transaction_type=transaction_type,
                metadata=metadata,
                display_name=display_name,
                mention=mention
            )
        
        logger.info(f"Subtracted ${amount} from user {user_id}. New balance: ${user_data['balance']}")
        return True, user_data["balance"]
    
    async def transfer_currency(self, from_user_id: str, to_user_id: str, amount: int) -> Tuple[bool, str]:
        """
        Transfer currency between users.
        Returns (success, message).
        """
        if amount <= 0:
            return False, "Transfer amount must be positive."
        
        from_user_data = await self.get_user_data(from_user_id)
        to_user_data = await self.get_user_data(to_user_id)
        
        from_balance_before = from_user_data["balance"]
        to_balance_before = to_user_data["balance"]
        
        if from_user_data["balance"] < amount:
            return False, f"Insufficient funds. You have ${from_user_data['balance']:,} but tried to send ${amount:,}."
        
        # Perform the transfer
        from_user_data["balance"] -= amount
        to_user_data["balance"] += amount
        
        from_balance_after = from_user_data["balance"]
        to_balance_after = to_user_data["balance"]
        
        await self.save_currency_data()
        
        # Log both sides of the transfer
        transfer_metadata = {"recipient": to_user_id, "transfer_type": "send"}
        await self.transaction_logger.log_transaction(
            user_id=from_user_id,
            command="transfer_send",
            amount=-amount,
            balance_before=from_balance_before,
            balance_after=from_balance_after,
            metadata=transfer_metadata
        )
        
        receive_metadata = {"sender": from_user_id, "transfer_type": "receive"}
        await self.transaction_logger.log_transaction(
            user_id=to_user_id,
            command="transfer_receive",
            amount=amount,
            balance_before=to_balance_before,
            balance_after=to_balance_after,
            metadata=receive_metadata
        )
        
        logger.info(f"Transferred ${amount} from user {from_user_id} to user {to_user_id}")
        return True, f"Successfully transferred ${amount:,}!"
    
    async def can_claim_daily(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user can claim daily bonus.
        Returns (can_claim, message_if_cannot_claim).
        """
        user_data = await self.get_user_data(user_id)
        last_claim = user_data["last_daily_claim"]
        
        if last_claim is None:
            return True, None
        
        try:
            # Parse the stored date (could be old timestamp or new date format)
            if 'T' in last_claim:  # Old timestamp format
                last_claim_date = datetime.fromisoformat(last_claim).date()
            else:  # New date format
                last_claim_date = date.fromisoformat(last_claim)
            
            today = date.today()
            
            # Check if it's a new day
            if today > last_claim_date:
                return True, None
            else:
                return False, "You already claimed your daily bonus today!"
        
        except Exception as e:
            logger.error(f"Error parsing last claim date for user {user_id}: {e}")
            return True, None
    
    async def claim_daily_bonus(self, user_id: str) -> Tuple[bool, str, float]:
        """
        Claim daily bonus for user.
        Returns (success, message, new_balance).
        """
        can_claim, time_left = await self.can_claim_daily(user_id)
        
        if not can_claim:
            user_data = await self.get_user_data(user_id)
            return False, time_left, user_data["balance"]
        
        # Give daily bonus
        new_balance = await self.add_currency(user_id, DAILY_CLAIM, command="daily_bonus", 
                                           transaction_type=TRANSACTION_TYPES["currency"])
        
        # Update last claim date
        user_data = await self.get_user_data(user_id)
        user_data["last_daily_claim"] = date.today().isoformat()
        await self.save_currency_data()
        
        logger.info(f"User {user_id} claimed daily bonus of ${DAILY_CLAIM}")
        return True, f"You claimed your daily bonus of ${DAILY_CLAIM:,}!", new_balance
    
    async def can_claim_hangman_bonus(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user can claim hangman daily bonus.
        Returns (can_claim, message_if_cannot_claim).
        """
        user_data = await self.get_user_data(user_id)
        last_claim = user_data["last_hangman_bonus_claim"]
        
        if last_claim is None:
            return True, None
        
        try:
            # Parse the stored date (could be old timestamp or new date format)
            if 'T' in last_claim:  # Old timestamp format
                last_claim_date = datetime.fromisoformat(last_claim).date()
            else:  # New date format
                last_claim_date = date.fromisoformat(last_claim)
            
            today = date.today()
            
            # Check if it's a new day
            if today > last_claim_date:
                return True, None
            else:
                return False, "You already claimed your hangman bonus today!"
        
        except Exception as e:
            logger.error(f"Error parsing last hangman bonus claim date for user {user_id}: {e}")
            return True, None
    
    async def claim_hangman_bonus(self, user_id: str) -> Tuple[bool, str, float]:
        """
        Claim hangman daily bonus for user.
        Returns (success, message, new_balance).
        """
        # Use user-specific lock to prevent race conditions
        user_lock = await self._get_user_lock(user_id)
        async with user_lock:
            can_claim, time_left = await self.can_claim_hangman_bonus(user_id)
            
            if not can_claim:
                user_data = await self.get_user_data(user_id)
                return False, time_left, user_data["balance"]
            
            # Give hangman bonus
            new_balance = await self.add_currency(user_id, HANGMAN_DAILY_BONUS, command="hangman_bonus",
                                                transaction_type=TRANSACTION_TYPES["currency"])
            
            # Update last claim date
            user_data = await self.get_user_data(user_id)
            user_data["last_hangman_bonus_claim"] = date.today().isoformat()
            await self.save_currency_data()
            
            logger.info(f"User {user_id} claimed hangman bonus of ${HANGMAN_DAILY_BONUS}")
            return True, f"🎯 Hangman Hard Mode Bonus: ${HANGMAN_DAILY_BONUS:,}!", new_balance
    
    def format_balance(self, balance: float) -> str:
        """Format balance with commas and dollar sign, limited to 2 decimal places"""
        return f"${balance:,.2f}"
    
    async def buy_stock(self, user_id: str, symbol: str, shares: float, price: float, leverage: float = 1.0) -> Tuple[bool, str]:
        """
        Buy stock for user with optional leverage.
        Returns (success, message).
        """
        if shares <= 0:
            return False, "Number of shares must be positive."
        
        if leverage <= 0:
            return False, "Leverage must be positive."
        
        # Calculate investment amount required for leveraged positions
        investment_amount = (shares * price) / leverage
        
        user_data = await self.get_user_data(user_id)
        balance_before = user_data["balance"]
        
        if user_data["balance"] < investment_amount:
            return False, f"Insufficient funds. You need ${investment_amount:,.2f} but have ${user_data['balance']:,.2f}."
        
        # Deduct investment amount from balance
        user_data["balance"] -= investment_amount
        balance_after = user_data["balance"]
        
        # Add to portfolio
        portfolio = user_data["portfolio"]
        if symbol in portfolio:
            # Average the purchase price if buying more of the same stock
            existing_shares = portfolio[symbol]["shares"]
            existing_price = portfolio[symbol]["purchase_price"]
            existing_leverage = portfolio[symbol].get("leverage", STOCK_MARKET_LEVERAGE)
            
            # Only allow same leverage for additional purchases
            if existing_leverage != leverage:
                user_data["balance"] += investment_amount  # Refund
                return False, f"You already own {symbol} with {existing_leverage}x leverage. Cannot mix leverage levels."
            
            total_shares = existing_shares + shares
            weighted_price = ((existing_shares * existing_price) + (shares * price)) / total_shares
            
            portfolio[symbol]["shares"] = total_shares
            portfolio[symbol]["purchase_price"] = weighted_price
            portfolio[symbol]["leverage"] = leverage  # Ensure leverage is set correctly
        else:
            portfolio[symbol] = {
                "shares": shares,
                "purchase_price": price,
                "leverage": leverage,
                "purchase_date": datetime.now().isoformat()
            }
        
        await self.save_currency_data()
        
        # Log the stock purchase transaction
        stock_metadata = {
            "symbol": symbol,
            "shares": shares,
            "price_per_share": price,
            "leverage": leverage,
            "total_value": shares * price,
            "investment_amount": investment_amount
        }
        await self.transaction_logger.log_transaction(
            user_id=user_id,
            command="buy_stock",
            amount=-investment_amount,
            balance_before=balance_before,
            balance_after=balance_after,
            profit_loss=0.0,  # Stock purchases are investments, not profit/loss events
            transaction_type=TRANSACTION_TYPES["investment"],
            metadata=stock_metadata
        )
        
        total_value = shares * price
        logger.info(f"User {user_id} bought {shares:,.2f} shares of {symbol} at ${price:.2f} with {leverage}x leverage")
        return True, f"Successfully bought {shares:,.2f} shares of {symbol} at ${price:.2f} each (${total_value:,.2f} total value) with {leverage}x leverage!"
    
    async def sell_stock(self, user_id: str, symbol: str, shares: float, current_price: float) -> Tuple[bool, str, float]:
        """
        Sell stock for user.
        Returns (success, message, profit_loss).
        """
        if shares <= 0:
            return False, "Number of shares must be positive.", 0.0
        
        user_data = await self.get_user_data(user_id)
        portfolio = user_data["portfolio"]
        balance_before = user_data["balance"]
        
        if symbol not in portfolio:
            return False, f"You don't own any shares of {symbol}.", 0.0
        
        position = portfolio[symbol]
        owned_shares = position["shares"]
        
        if shares > owned_shares:
            return False, f"You only own {owned_shares:,.2f} shares of {symbol}, cannot sell {shares:.2f}.", 0.0
        
        purchase_price = position["purchase_price"]
        leverage = position["leverage"]
        
        # Calculate profit/loss with leverage
        price_change = current_price - purchase_price
        total_profit = price_change * shares
        
        # Calculate proceeds (original investment + profit/loss)
        original_investment_per_share = purchase_price / leverage
        proceeds = (original_investment_per_share * shares) + total_profit
        investment_amount = (shares * purchase_price) / leverage
        
        # Add proceeds to balance
        user_data["balance"] += proceeds
        balance_after = user_data["balance"]
        
        # Update portfolio
        if shares == owned_shares:
            # Selling all shares, remove from portfolio
            del portfolio[symbol]
        else:
            # Partial sale, update remaining shares
            portfolio[symbol]["shares"] = owned_shares - shares
        
        await self.save_currency_data()
        
        # Log the stock sale transaction
        sell_metadata = {
            "symbol": symbol,
            "shares": shares,
            "sale_price_per_share": current_price,
            "purchase_price_per_share": purchase_price,
            "leverage": leverage,
            "proceeds": proceeds,
            "total_profit": total_profit,
            "investment_amount": investment_amount
        }
        await self.transaction_logger.log_transaction(
            user_id=user_id,
            command="sell_stock",
            amount=proceeds,
            balance_before=balance_before,
            balance_after=balance_after,
            profit_loss=total_profit,  # Actual profit/loss from the sale
            transaction_type=TRANSACTION_TYPES["investment"],
            metadata=sell_metadata
        )
        
        profit_percentage = (total_profit / investment_amount) * 100
        logger.info(f"User {user_id} sold {shares:,.2f} shares of {symbol} at ${current_price:.2f} for ${proceeds:.2f} profit/loss")
        
        profit_status = "profit" if total_profit >= 0 else "loss"
        return True, f"Successfully sold {shares:,.2f} shares of {symbol} at ${current_price:.2f} each for a {profit_status} of ${abs(total_profit):,.2f} ({profit_percentage:+.2f}%)!", total_profit
    
    async def get_portfolio(self, user_id: str) -> Dict:
        """Get user's stock portfolio"""
        user_data = await self.get_user_data(user_id)
        return user_data["portfolio"]
    
    async def check_and_liquidate_positions(self, user_id: str, current_prices: Dict[str, float]) -> List[str]:
        """
        Check for positions that have lost 100% or more and automatically liquidate them.
        Returns list of liquidated symbols.
        """
        portfolio = await self.get_portfolio(user_id)
        liquidated_symbols = []
        
        if not portfolio:
            return liquidated_symbols
        
        # Create a copy of portfolio items to avoid modifying dict during iteration
        portfolio_items = list(portfolio.items())
        
        for symbol, position in portfolio_items:
            if symbol not in current_prices or current_prices[symbol] is None:
                continue
            
            shares = position["shares"]
            purchase_price = position["purchase_price"]
            leverage = position["leverage"]
            current_price = current_prices[symbol]
            
            # Calculate proceeds using the same logic as the sell_stock method
            price_change = current_price - purchase_price
            total_profit = price_change * shares
            
            # Calculate proceeds (original investment + profit/loss)
            original_investment_per_share = purchase_price / leverage
            proceeds = (original_investment_per_share * shares) + total_profit
            
            # Check if position has lost 100% or more (proceeds <= 0)
            if proceeds <= 0:
                # Automatically liquidate the position for $0
                user_data = await self.get_user_data(user_id)
                
                # Remove the position from portfolio (user gets $0 back)
                del user_data["portfolio"][symbol]
                
                # Calculate loss percentage for logging
                original_investment = original_investment_per_share * shares
                profit_loss_percentage = (total_profit / original_investment) * 100 if original_investment > 0 else 0
                
                # Log the liquidation
                logger.warning(f"Auto-liquidated position for user {user_id}: {symbol} - {shares:.4f} shares at {profit_loss_percentage:.2f}% loss (proceeds: ${proceeds:.2f})")
                
                liquidated_symbols.append(symbol)
        
        # Save changes if any liquidations occurred
        if liquidated_symbols:
            await self.save_currency_data()
        
        return liquidated_symbols

    async def calculate_portfolio_value(self, user_id: str, current_prices: Dict[str, float]) -> Tuple[float, float, Dict]:
        """
        Calculate total portfolio value and profit/loss.
        Automatically liquidates positions that have lost 100% or more.
        Returns (total_value, total_profit_loss, position_details).
        """
        # First, check and liquidate any positions that have lost 100% or more
        liquidated_symbols = await self.check_and_liquidate_positions(user_id, current_prices)
        
        # Get updated portfolio after potential liquidations
        portfolio = await self.get_portfolio(user_id)
        
        if not portfolio:
            return 0.0, 0.0, {}
        
        total_value = 0.0
        total_profit_loss = 0.0
        position_details = {}
        
        for symbol, position in portfolio.items():
            if symbol not in current_prices or current_prices[symbol] is None:
                continue
            
            shares = position["shares"]
            purchase_price = position["purchase_price"]
            leverage = position.get("leverage", STOCK_MARKET_LEVERAGE)
            current_price = current_prices[symbol]
            
            # Calculate the position value with leverage
            price_change = current_price - purchase_price
            position_value = current_price * shares
            
            # Calculate original investment amount
            original_investment = (purchase_price * shares) / leverage
            profit_loss = price_change * shares
            
            total_value += position_value
            total_profit_loss += profit_loss
            
            position_details[symbol] = {
                "shares": shares,
                "purchase_price": purchase_price,
                "current_price": current_price,
                "leverage": leverage,
                "position_value": position_value,
                "original_investment": original_investment,
                "profit_loss": profit_loss,
                "profit_loss_percentage": (profit_loss / original_investment) * 100 if original_investment > 0 else 0
            }
        
        return total_value, total_profit_loss, position_details
    
    async def record_dividend_payment(self, user_id: str, symbol: str, amount: float, shares: float, ex_dividend_date: str) -> bool:
        """Record a dividend payment for a user"""
        try:
            user_data = await self.get_user_data(user_id)
            
            # Initialize dividend tracking if it doesn't exist
            if "dividend_earnings" not in user_data:
                user_data["dividend_earnings"] = {
                    "total": 0.0,
                    "by_stock": {},
                    "payments": []
                }
            
            dividend_earnings = user_data["dividend_earnings"]
            
            # Update totals
            dividend_earnings["total"] += amount
            
            if symbol not in dividend_earnings["by_stock"]:
                dividend_earnings["by_stock"][symbol] = 0.0
            dividend_earnings["by_stock"][symbol] += amount
            
            # Record the payment
            payment_record = {
                "symbol": symbol,
                "amount": amount,
                "shares": shares,
                "amount_per_share": amount / shares if shares > 0 else 0,
                "ex_dividend_date": ex_dividend_date,
                "payment_date": datetime.now().isoformat()
            }
            
            dividend_earnings["payments"].append(payment_record)
            
            # Keep only last 50 payments to prevent file bloat
            if len(dividend_earnings["payments"]) > 50:
                dividend_earnings["payments"] = dividend_earnings["payments"][-50:]
            
            await self.save_currency_data()
            
            logger.info(f"Recorded dividend payment for user {user_id}: ${amount:.2f} from {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording dividend payment for user {user_id}: {e}")
            return False
    
    async def get_dividend_summary(self, user_id: str) -> Dict:
        """Get dividend earnings summary for a user"""
        try:
            user_data = await self.get_user_data(user_id)
            dividend_earnings = user_data.get("dividend_earnings", {
                "total": 0.0,
                "by_stock": {},
                "payments": []
            })
            
            # Calculate additional stats
            recent_payments = dividend_earnings.get("payments", [])
            
            # Get payments from last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_total = 0.0
            
            for payment in recent_payments:
                try:
                    payment_date = datetime.fromisoformat(payment["payment_date"])
                    if payment_date >= thirty_days_ago:
                        recent_total += payment["amount"]
                except:
                    continue
            
            return {
                "total_all_time": dividend_earnings.get("total", 0.0),
                "total_last_30_days": recent_total,
                "by_stock": dividend_earnings.get("by_stock", {}),
                "recent_payments": recent_payments[-10:],  # Last 10 payments
                "payment_count": len(recent_payments)
            }
            
        except Exception as e:
            logger.error(f"Error getting dividend summary for user {user_id}: {e}")
            return {
                "total_all_time": 0.0,
                "total_last_30_days": 0.0,
                "by_stock": {},
                "recent_payments": [],
                "payment_count": 0
            }