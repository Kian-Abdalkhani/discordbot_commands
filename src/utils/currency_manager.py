import json
import os
import logging
import aiofiles
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List

from src.config.settings import DAILY_CLAIM, STOCK_MARKET_LEVERAGE

logger = logging.getLogger(__name__)

class CurrencyManager:
    """Manages virtual currency for Discord bot users"""
    
    def __init__(self):
        self.currency_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "currency.json"
        )
        self.currency_data = {}
    
    async def initialize(self):
        """Initialize the currency manager by loading data"""
        await self.load_currency_data()
    
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
                "portfolio": {}  # Stock positions: {symbol: {shares, purchase_price, leverage, purchase_date}}
            }
            await self.save_currency_data()
            logger.info(f"Created new currency account for user {user_id} with $100,000")
        
        # Ensure portfolio exists for existing users
        if "portfolio" not in self.currency_data[user_id]:
            self.currency_data[user_id]["portfolio"] = {}
            await self.save_currency_data()
        
        return self.currency_data[user_id]
    
    async def get_balance(self, user_id: str) -> float:
        """Get user's current balance"""
        user_data = await self.get_user_data(user_id)
        return user_data["balance"]
    
    async def add_currency(self, user_id: str, amount: int) -> float:
        """Add currency to user's balance. Returns new balance."""
        user_data = await self.get_user_data(user_id)
        user_data["balance"] += amount
        await self.save_currency_data()
        logger.info(f"Added ${amount} to user {user_id}. New balance: ${user_data['balance']}")
        return user_data["balance"]
    
    async def subtract_currency(self, user_id: str, amount: int) -> Tuple[bool, float]:
        """
        Subtract currency from user's balance.
        Returns (success, new_balance).
        """
        user_data = await self.get_user_data(user_id)
        
        if user_data["balance"] < amount:
            logger.warning(f"User {user_id} attempted to spend ${amount} but only has ${user_data['balance']}")
            return False, user_data["balance"]
        
        user_data["balance"] -= amount
        await self.save_currency_data()
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
        
        if from_user_data["balance"] < amount:
            return False, f"Insufficient funds. You have ${from_user_data['balance']:,} but tried to send ${amount:,}."
        
        # Perform the transfer
        from_user_data["balance"] -= amount
        to_user_data["balance"] += amount
        await self.save_currency_data()
        
        logger.info(f"Transferred ${amount} from user {from_user_id} to user {to_user_id}")
        return True, f"Successfully transferred ${amount:,}!"
    
    async def can_claim_daily(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user can claim daily bonus.
        Returns (can_claim, time_until_next_claim).
        """
        user_data = await self.get_user_data(user_id)
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
    
    async def claim_daily_bonus(self, user_id: str) -> Tuple[bool, str, float]:
        """
        Claim daily bonus for user.
        Returns (success, message, new_balance).
        """
        can_claim, time_left = await self.can_claim_daily(user_id)
        
        if not can_claim:
            user_data = await self.get_user_data(user_id)
            return False, f"You already claimed your daily bonus! Next claim in {time_left}.", user_data["balance"]
        
        # Give daily bonus
        new_balance = await self.add_currency(user_id, DAILY_CLAIM)
        
        # Update last claim time
        user_data = await self.get_user_data(user_id)
        user_data["last_daily_claim"] = datetime.now().isoformat()
        await self.save_currency_data()
        
        logger.info(f"User {user_id} claimed daily bonus of ${DAILY_CLAIM}")
        return True, f"You claimed your daily bonus of ${DAILY_CLAIM:,}!", new_balance
    
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
        
        if user_data["balance"] < investment_amount:
            return False, f"Insufficient funds. You need ${investment_amount:,.2f} but have ${user_data['balance']:,.2f}."
        
        # Deduct investment amount from balance
        user_data["balance"] -= investment_amount
        
        # Add to portfolio
        portfolio = user_data["portfolio"]
        if symbol in portfolio:
            # Average the purchase price if buying more of the same stock
            existing_shares = portfolio[symbol]["shares"]
            existing_price = portfolio[symbol]["purchase_price"]
            existing_leverage = portfolio[symbol]["leverage"]
            
            # Only allow same leverage for additional purchases
            if existing_leverage != leverage:
                user_data["balance"] += investment_amount  # Refund
                return False, f"You already own {symbol} with {existing_leverage}x leverage. Cannot mix leverage levels."
            
            total_shares = existing_shares + shares
            weighted_price = ((existing_shares * existing_price) + (shares * price)) / total_shares
            
            portfolio[symbol]["shares"] = total_shares
            portfolio[symbol]["purchase_price"] = weighted_price
        else:
            portfolio[symbol] = {
                "shares": shares,
                "purchase_price": price,
                "leverage": leverage,
                "purchase_date": datetime.now().isoformat()
            }
        
        await self.save_currency_data()
        
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
        
        # Update portfolio
        if shares == owned_shares:
            # Selling all shares, remove from portfolio
            del portfolio[symbol]
        else:
            # Partial sale, update remaining shares
            portfolio[symbol]["shares"] = owned_shares - shares
        
        await self.save_currency_data()
        
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
            leverage = position["leverage"]
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