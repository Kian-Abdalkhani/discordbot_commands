import json
import os
import logging
import aiofiles
import asyncio
import yfinance as yf
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import concurrent.futures

logger = logging.getLogger(__name__)

class DividendManager:
    """Manages dividend tracking and payouts for the stock market simulator"""
    
    def __init__(self, currency_manager):
        self.currency_manager = currency_manager
        self.dividend_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "dividends.json"
        )
        self.dividend_data = {}
        self.cache = {}
        self.cache_expiry = {}
        self.cache_duration = timedelta(hours=1)  # Cache dividend data for 1 hour
        
    async def initialize(self):
        """Initialize the dividend manager by loading data"""
        await self.load_dividend_data()
        logger.info("DividendManager initialized")
    
    async def load_dividend_data(self):
        """Load dividend data from JSON file"""
        try:
            if os.path.exists(self.dividend_file):
                async with aiofiles.open(self.dividend_file, 'r') as f:
                    content = await f.read()
                    self.dividend_data = json.loads(content)
                logger.info(f"Loaded dividend data from {self.dividend_file}")
            else:
                logger.info(f"No dividend file found at {self.dividend_file}, starting with empty data")
                self.dividend_data = {
                    "dividend_history": {},
                    "user_dividend_earnings": {},
                    "processed_dividends": {}  # Track which dividends have been processed
                }
        except Exception as e:
            logger.error(f"Error loading dividend data: {e}")
            self.dividend_data = {
                "dividend_history": {},
                "user_dividend_earnings": {},
                "processed_dividends": {}
            }
    
    async def save_dividend_data(self):
        """Save dividend data to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.dividend_file), exist_ok=True)
            
            async with aiofiles.open(self.dividend_file, 'w') as f:
                await f.write(json.dumps(self.dividend_data, indent=4, default=str))
            logger.info(f"Saved dividend data to {self.dividend_file}")
        except Exception as e:
            logger.error(f"Error saving dividend data: {e}")
    
    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cached dividend data is still valid"""
        if symbol not in self.cache or symbol not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[symbol]
    
    async def get_dividend_info(self, symbol: str) -> Optional[Dict]:
        """Get dividend information for a stock symbol"""
        try:
            # Check cache first
            if self._is_cache_valid(symbol):
                return self.cache[symbol]
            
            # Fetch from yfinance API in thread pool
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                ticker = await loop.run_in_executor(executor, yf.Ticker, symbol.upper())
                
                # Get stock info for dividend yield and ex-dividend date
                info = await loop.run_in_executor(executor, lambda: ticker.info)
                
                # Get historical dividends
                dividends = await loop.run_in_executor(executor, lambda: ticker.dividends)
                
                dividend_info = {
                    "symbol": symbol.upper(),
                    "dividend_yield": info.get('dividendYield', 0.0),
                    "forward_dividend_rate": info.get('dividendRate', 0.0),
                    "ex_dividend_date": None,
                    "last_dividend_value": 0.0,
                    "historical_dividends": [],
                    "pays_dividends": False
                }
                
                # Process ex-dividend date
                if 'exDividendDate' in info and info['exDividendDate']:
                    try:
                        # Convert timestamp to date
                        ex_div_timestamp = info['exDividendDate']
                        ex_div_date = datetime.fromtimestamp(ex_div_timestamp).date()
                        dividend_info["ex_dividend_date"] = ex_div_date.isoformat()
                    except Exception as e:
                        logger.warning(f"Could not parse ex-dividend date for {symbol}: {e}")
                
                # Process historical dividends
                if not dividends.empty:
                    dividend_info["pays_dividends"] = True
                    
                    # Get last 12 months of dividends
                    recent_dividends = dividends.tail(4)  # Usually quarterly
                    
                    for div_date, amount in recent_dividends.items():
                        dividend_info["historical_dividends"].append({
                            "date": div_date.date().isoformat(),
                            "amount": float(amount)
                        })
                    
                    if len(dividend_info["historical_dividends"]) > 0:
                        dividend_info["last_dividend_value"] = dividend_info["historical_dividends"][-1]["amount"]
                
                # Cache the result
                self.cache[symbol] = dividend_info
                self.cache_expiry[symbol] = datetime.now() + self.cache_duration
                
                logger.info(f"Fetched dividend info for {symbol}: pays_dividends={dividend_info['pays_dividends']}")
                return dividend_info
                
        except Exception as e:
            logger.error(f"Error fetching dividend info for {symbol}: {e}")
            return None
    
    async def get_upcoming_dividends_for_portfolio(self, user_id: str) -> List[Dict]:
        """Get upcoming dividend information for user's portfolio"""
        try:
            portfolio = await self.currency_manager.get_portfolio(user_id)
            if not portfolio:
                return []
            
            upcoming_dividends = []
            symbols = list(portfolio.keys())
            
            # Fetch dividend info for all symbols in parallel
            tasks = [self.get_dividend_info(symbol) for symbol in symbols]
            dividend_infos = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, dividend_info in zip(symbols, dividend_infos):
                if isinstance(dividend_info, Exception) or not dividend_info:
                    continue
                
                if (dividend_info["pays_dividends"] and 
                    dividend_info["ex_dividend_date"] and 
                    dividend_info["last_dividend_value"] > 0):
                    
                    position = portfolio[symbol]
                    shares = position["shares"]
                    estimated_payout = shares * dividend_info["last_dividend_value"]
                    
                    upcoming_dividends.append({
                        "symbol": symbol,
                        "ex_dividend_date": dividend_info["ex_dividend_date"],
                        "dividend_amount": dividend_info["last_dividend_value"],
                        "shares_owned": shares,
                        "estimated_payout": estimated_payout,
                        "dividend_yield": dividend_info["dividend_yield"]
                    })
            
            # Sort by ex-dividend date
            upcoming_dividends.sort(key=lambda x: x["ex_dividend_date"])
            return upcoming_dividends
            
        except Exception as e:
            logger.error(f"Error getting upcoming dividends for user {user_id}: {e}")
            return []
    
    async def calculate_dividend_payout(self, symbol: str, dividend_amount: float, ex_dividend_date: str) -> Dict[str, Dict]:
        """Calculate dividend payouts for all users holding a stock on ex-dividend date"""
        try:
            eligible_users = {}
            
            # Get all users from currency manager
            await self.currency_manager.load_currency_data()
            all_users = self.currency_manager.currency_data
            
            for user_id, user_data in all_users.items():
                portfolio = user_data.get("portfolio", {})
                
                if symbol in portfolio:
                    position = portfolio[symbol]
                    shares = position["shares"]
                    
                    # Check if user owned the stock on ex-dividend date
                    purchase_date = datetime.fromisoformat(position["purchase_date"]).date()
                    ex_div_date = date.fromisoformat(ex_dividend_date)
                    
                    if purchase_date <= ex_div_date:
                        payout = shares * dividend_amount
                        eligible_users[user_id] = {
                            "shares": shares,
                            "payout": payout
                        }
            
            logger.info(f"Calculated dividend payouts for {symbol}: {len(eligible_users)} eligible users")
            return eligible_users
            
        except Exception as e:
            logger.error(f"Error calculating dividend payout for {symbol}: {e}")
            return {}
    
    async def process_dividend_payment(self, symbol: str, dividend_amount: float, ex_dividend_date: str) -> bool:
        """Process dividend payment for a stock"""
        try:
            # Check if this dividend has already been processed
            dividend_key = f"{symbol}_{ex_dividend_date}_{dividend_amount}"
            
            if dividend_key in self.dividend_data.get("processed_dividends", {}):
                logger.info(f"Dividend already processed: {dividend_key}")
                return True
            
            # Calculate eligible users and payouts
            eligible_users = await self.calculate_dividend_payout(symbol, dividend_amount, ex_dividend_date)
            
            if not eligible_users:
                logger.info(f"No eligible users for dividend {symbol} on {ex_dividend_date}")
                return True
            
            total_paid = 0.0
            successful_payments = 0
            
            # Pay dividends to eligible users
            for user_id, payout_info in eligible_users.items():
                try:
                    payout = payout_info["payout"]
                    shares = payout_info["shares"]
                    
                    # Add dividend to user balance
                    await self.currency_manager.add_currency(user_id, payout)
                    
                    # Track dividend earnings in currency manager
                    await self.currency_manager.record_dividend_payment(
                        user_id, symbol, payout, shares, ex_dividend_date
                    )
                    
                    # Track dividend earnings in dividend manager
                    await self._record_dividend_earning(user_id, symbol, payout)
                    
                    total_paid += payout
                    successful_payments += 1
                    
                    logger.info(f"Paid dividend ${payout:.2f} to user {user_id} for {shares} shares of {symbol}")
                    
                except Exception as e:
                    logger.error(f"Error paying dividend to user {user_id}: {e}")
            
            # Record the dividend in history
            if symbol not in self.dividend_data["dividend_history"]:
                self.dividend_data["dividend_history"][symbol] = []
            
            self.dividend_data["dividend_history"][symbol].append({
                "ex_dividend_date": ex_dividend_date,
                "amount": dividend_amount,
                "processed": True,
                "eligible_users": eligible_users,
                "total_paid": total_paid,
                "users_paid": successful_payments,
                "processed_date": datetime.now().isoformat()
            })
            
            # Mark as processed
            if "processed_dividends" not in self.dividend_data:
                self.dividend_data["processed_dividends"] = {}
            self.dividend_data["processed_dividends"][dividend_key] = True
            
            await self.save_dividend_data()
            
            logger.info(f"Successfully processed dividend for {symbol}: ${total_paid:.2f} paid to {successful_payments} users")
            return True
            
        except Exception as e:
            logger.error(f"Error processing dividend payment for {symbol}: {e}")
            return False
    
    async def _record_dividend_earning(self, user_id: str, symbol: str, amount: float):
        """Record dividend earning for a user"""
        try:
            if "user_dividend_earnings" not in self.dividend_data:
                self.dividend_data["user_dividend_earnings"] = {}
            
            if user_id not in self.dividend_data["user_dividend_earnings"]:
                self.dividend_data["user_dividend_earnings"][user_id] = {
                    "total_earned": 0.0,
                    "last_updated": datetime.now().isoformat(),
                    "by_stock": {}
                }
            
            user_earnings = self.dividend_data["user_dividend_earnings"][user_id]
            
            # Update totals
            user_earnings["total_earned"] += amount
            user_earnings["last_updated"] = datetime.now().isoformat()
            
            # Update by stock
            if symbol not in user_earnings["by_stock"]:
                user_earnings["by_stock"][symbol] = 0.0
            user_earnings["by_stock"][symbol] += amount
            
        except Exception as e:
            logger.error(f"Error recording dividend earning for user {user_id}: {e}")
    
    async def get_user_dividend_history(self, user_id: str) -> Dict:
        """Get dividend earning history for a user"""
        try:
            user_earnings = self.dividend_data.get("user_dividend_earnings", {}).get(user_id)
            
            if not user_earnings:
                return {
                    "total_earned": 0.0,
                    "by_stock": {},
                    "recent_payments": []
                }
            
            # Get recent dividend payments from history
            recent_payments = []
            for symbol, dividend_history in self.dividend_data.get("dividend_history", {}).items():
                for dividend in dividend_history:
                    eligible_users = dividend.get("eligible_users", {})
                    if user_id in eligible_users:
                        recent_payments.append({
                            "symbol": symbol,
                            "date": dividend["ex_dividend_date"],
                            "amount_per_share": dividend["amount"],
                            "shares": eligible_users[user_id]["shares"],
                            "payout": eligible_users[user_id]["payout"],
                            "processed_date": dividend.get("processed_date")
                        })
            
            # Sort recent payments by date
            recent_payments.sort(key=lambda x: x["date"], reverse=True)
            
            return {
                "total_earned": user_earnings["total_earned"],
                "by_stock": user_earnings["by_stock"],
                "recent_payments": recent_payments[:10]  # Last 10 payments
            }
            
        except Exception as e:
            logger.error(f"Error getting dividend history for user {user_id}: {e}")
            return {"total_earned": 0.0, "by_stock": {}, "recent_payments": []}
    
    async def check_for_new_dividends(self) -> List[Dict]:
        """Check for new dividend announcements across all held stocks"""
        try:
            # Get all unique symbols from all user portfolios
            held_symbols = set()
            
            await self.currency_manager.load_currency_data()
            all_users = self.currency_manager.currency_data
            
            for user_data in all_users.values():
                portfolio = user_data.get("portfolio", {})
                held_symbols.update(portfolio.keys())
            
            if not held_symbols:
                return []
            
            logger.info(f"Checking for dividends on {len(held_symbols)} held stocks")
            
            new_dividends = []
            
            # Check each symbol for new dividends
            for symbol in held_symbols:
                try:
                    dividend_info = await self.get_dividend_info(symbol)
                    
                    if (dividend_info and dividend_info["pays_dividends"] and 
                        dividend_info["ex_dividend_date"] and dividend_info["last_dividend_value"] > 0):
                        
                        ex_div_date = dividend_info["ex_dividend_date"]
                        dividend_amount = dividend_info["last_dividend_value"]
                        
                        # Check if this is a new dividend we haven't processed
                        dividend_key = f"{symbol}_{ex_div_date}_{dividend_amount}"
                        
                        if dividend_key not in self.dividend_data.get("processed_dividends", {}):
                            # Check if ex-dividend date has passed
                            ex_div_date_obj = date.fromisoformat(ex_div_date)
                            if ex_div_date_obj <= date.today():
                                new_dividends.append({
                                    "symbol": symbol,
                                    "ex_dividend_date": ex_div_date,
                                    "amount": dividend_amount,
                                    "key": dividend_key
                                })
                
                except Exception as e:
                    logger.error(f"Error checking dividends for {symbol}: {e}")
                    continue
            
            logger.info(f"Found {len(new_dividends)} new dividends to process")
            return new_dividends
            
        except Exception as e:
            logger.error(f"Error checking for new dividends: {e}")
            return []