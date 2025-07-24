import yfinance as yf
import logging
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import asyncio
import concurrent.futures

from src.config.settings import STOCK_MARKET_LEVERAGE

logger = logging.getLogger(__name__)

class StockMarketManager:
    """Manages stock market data and operations for the simulator"""
    
    def __init__(self):
        self.cache = {}
        self.cache_expiry = {}
        self.cache_duration = timedelta(minutes=1)  # Cache for 1 minute
        
    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cached data is still valid"""
        if symbol not in self.cache or symbol not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[symbol]
    
    async def get_stock_price(self, symbol: str) -> Optional[float]:
        """Get current stock price for a symbol"""
        try:
            # Check cache first
            if self._is_cache_valid(symbol):
                return self.cache[symbol]['price']
            
            # Fetch from API in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                stock = await loop.run_in_executor(executor, yf.Ticker, symbol.upper())
                info = await loop.run_in_executor(executor, lambda: stock.info)
                
                if 'currentPrice' in info:
                    price = float(info['currentPrice'])
                elif 'regularMarketPrice' in info:
                    price = float(info['regularMarketPrice'])
                else:
                    # Try to get from history if current price not available
                    hist = await loop.run_in_executor(executor, lambda: stock.history(period="1d"))
                    if not hist.empty:
                        price = float(hist['Close'].iloc[-1])
                    else:
                        return None
                
                # Cache the result
                self.cache[symbol] = {
                    'price': price,
                    'info': info
                }
                self.cache_expiry[symbol] = datetime.now() + self.cache_duration
                
                logger.info(f"Fetched price for {symbol}: ${price:.2f}")
                return price
                
        except Exception as e:
            logger.error(f"Error fetching stock price for {symbol}: {e}")
            return None
    
    async def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """Get detailed stock information"""
        try:
            # Check cache first
            if self._is_cache_valid(symbol):
                return self.cache[symbol]['info']
            
            # Fetch price first to populate cache
            await self.get_stock_price(symbol)
            
            if symbol in self.cache:
                return self.cache[symbol]['info']
            return None
            
        except Exception as e:
            logger.error(f"Error fetching stock info for {symbol}: {e}")
            return None
    
    async def validate_stock_symbol(self, symbol: str) -> bool:
        """Validate if a stock symbol exists"""
        price = await self.get_stock_price(symbol)
        return price is not None
    
    async def get_multiple_prices(self, symbols: List[str]) -> Dict[str, Optional[float]]:
        """Get prices for multiple symbols efficiently"""
        tasks = [self.get_stock_price(symbol) for symbol in symbols]
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        
        result = {}
        for symbol, price in zip(symbols, prices):
            if isinstance(price, Exception):
                result[symbol] = None
            else:
                result[symbol] = price
        
        return result
    
    def calculate_leveraged_return(self, original_price: float, current_price: float, leverage: float) -> float:
        """Calculate return with leverage applied"""
        price_change_percent = (current_price - original_price) / original_price
        leveraged_return_percent = price_change_percent * leverage
        return leveraged_return_percent
    
    def calculate_position_value(self, shares: float, current_price: float, leverage: float = 1.0) -> float:
        """Calculate current value of a position"""
        return shares * current_price * leverage
    
    def get_popular_stocks(self) -> List[str]:
        """Get a list of popular stock symbols for suggestions"""
        return [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "NFLX",
            "AMD",  "PYPL", "ADBE", "CRM", "ORCL", "IBM", "UBER",
            "SPOT", "SNAP",  "ZOOM", "SHOP", "SQ", "ROKU", "PINS"
        ]
    
    def format_price(self, price: float) -> str:
        """Format price for display"""
        return f"${price:.2f}"
    
    def format_percentage(self, percentage: float) -> str:
        """Format percentage for display"""
        sign = "+" if percentage >= 0 else ""
        return f"{sign}{percentage:.2f}%"
    
    def get_current_leverage(self) -> float:
        """Get the current leverage setting"""
        return STOCK_MARKET_LEVERAGE
    
    def calculate_margin_requirement(self, investment_amount: float, leverage: float) -> float:
        """Calculate margin requirement for leveraged position"""
        return investment_amount / leverage