import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
import logging
from typing import Optional

from src.config.settings import GUILD_ID, STOCK_MARKET_LEVERAGE
from src.utils.stock_market_manager import StockMarketManager
from src.utils.dividend_manager import DividendManager

logger = logging.getLogger(__name__)

class StockMarketCog(commands.Cog):
    """Stock Market Simulator commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.currency_manager = bot.currency_manager
        self.stock_manager = StockMarketManager()
        self.dividend_manager = bot.dividend_manager
        logger.info("StockMarketCog initialized")
    
    @app_commands.command(name="buy_stock", description="Buy stocks with leverage")
    @app_commands.describe(
        symbol="Stock symbol (e.g., AAPL, MSFT, TSLA)",
        amount="Dollar amount to invest in the stock"
    )
    @app_commands.guild_only()
    async def buy_stock(self, interaction: discord.Interaction, symbol: str, amount: float):
        """Buy stocks with leverage"""
        await interaction.response.defer()
        
        try:
            symbol = symbol.upper().strip()
            user_id = str(interaction.user.id)
            leverage = STOCK_MARKET_LEVERAGE
            
            # Validate inputs
            if amount <= 0:
                await interaction.followup.send("❌ Investment amount must be positive!", ephemeral=True)
                return
            
            # Validate stock symbol and get current price
            current_price = await self.stock_manager.get_stock_price(symbol)
            if current_price is None:
                await interaction.followup.send(f"❌ Could not find stock symbol '{symbol}'. Please check the symbol and try again.", ephemeral=True)
                return
            
            # Calculate number of shares from dollar amount
            # With leverage, the total position value is amount * leverage
            total_position_value = amount * leverage
            shares = total_position_value / current_price
            
            # The investment amount is what the user wants to invest
            investment_amount = amount
            
            # Attempt to buy the stock
            success, message = await self.currency_manager.buy_stock(user_id, symbol, shares, current_price, leverage)
            
            if success:
                # Create success embed
                embed = discord.Embed(
                    title="📈 Stock Purchase Successful!",
                    description=message,
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="📊 Transaction Details",
                    value=f"**Symbol:** {symbol}\n"
                          f"**Investment Amount:** ${amount:,.2f}\n"
                          f"**Shares Purchased:** {shares:,.4f}\n"
                          f"**Price per Share:** ${current_price:.2f}\n"
                          f"**Leverage:** {leverage}x\n"
                          f"**Total Position Value:** ${total_position_value:,.2f}",
                    inline=False
                )
                
                # Show remaining balance
                remaining_balance = await self.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="💰 Remaining Balance",
                    value=f"${remaining_balance:,.2f}",
                    inline=True
                )
                
                if leverage > 1.0:
                    embed.add_field(
                        name="⚠️ Leverage Warning",
                        value=f"You're using {leverage}x leverage. This amplifies both gains and losses!",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"User {user_id} invested ${amount} in {symbol} ({shares:.4f} shares) with {leverage}x leverage")
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in buy_stock command: {e}")
            await interaction.followup.send("❌ An error occurred while processing your stock purchase. Please try again later.", ephemeral=True)
    
    @app_commands.command(name="sell_stock", description="Sell stocks from your portfolio")
    @app_commands.describe(
        symbol="Stock symbol to sell",
        amount="Dollar amount to sell (optional if using sell_all)",
        sell_all="Sell all shares of this stock"
    )
    @app_commands.choices(sell_all=[
        Choice(name="Yes", value="yes"),
        Choice(name="No", value="no")
    ])
    @app_commands.guild_only()
    async def sell_stock(self, interaction: discord.Interaction, symbol: str, amount: Optional[str] = None, sell_all: Optional[str] = None):
        """Sell stocks from portfolio"""
        await interaction.response.defer()
        
        try:
            symbol = symbol.upper().strip()
            user_id = str(interaction.user.id)
            
            # Validate that at least one parameter is provided
            if not amount and not sell_all:
                await interaction.followup.send("❌ Please specify either an amount to sell or choose 'Yes' for sell_all.", ephemeral=True)
                return
            
            # Get user's portfolio
            portfolio = await self.currency_manager.get_portfolio(user_id)
            
            if symbol not in portfolio:
                await interaction.followup.send(f"❌ You don't own any shares of {symbol}.", ephemeral=True)
                return
            
            # Get current stock price first
            current_price = await self.stock_manager.get_stock_price(symbol)
            if current_price is None:
                await interaction.followup.send(f"❌ Could not get current price for {symbol}. Please try again later.", ephemeral=True)
                return
            
            position = portfolio[symbol]
            owned_shares = position["shares"]
            leverage = position["leverage"]
            
            # Determine shares to sell based on parameters
            if sell_all == "yes":
                # Sell all shares regardless of amount parameter
                shares_to_sell = owned_shares
                sell_amount = owned_shares * current_price / leverage  # This is the investment value
            elif amount:
                # Use amount parameter (either dollar amount or 'all')
                if amount.lower() == 'all':
                    shares_to_sell = owned_shares
                    sell_amount = owned_shares * current_price / leverage  # This is the investment value
                else:
                    try:
                        sell_amount = float(amount)
                        if sell_amount <= 0:
                            await interaction.followup.send("❌ Sell amount must be positive!", ephemeral=True)
                            return
                        
                        # Calculate shares to sell based on dollar amount
                        # The sell amount represents the investment value, so we need to account for leverage
                        shares_to_sell = (sell_amount * leverage) / current_price
                        
                        if shares_to_sell > owned_shares:
                            max_sell_amount = (owned_shares * current_price) / leverage
                            await interaction.followup.send(f"❌ You can only sell up to ${max_sell_amount:,.2f} worth of {symbol}. You own {owned_shares:.4f} shares.", ephemeral=True)
                            return
                            
                    except ValueError:
                        await interaction.followup.send("❌ Invalid amount. Use a dollar amount or 'all'.", ephemeral=True)
                        return
            else:
                # This shouldn't happen due to validation, but just in case
                await interaction.followup.send("❌ Please specify either an amount to sell or choose 'Yes' for sell_all.", ephemeral=True)
                return
            
            # Attempt to sell the stock
            success, message, profit_loss = await self.currency_manager.sell_stock(user_id, symbol, shares_to_sell, current_price)
            
            if success:
                # Create success embed
                color = discord.Color.green() if profit_loss >= 0 else discord.Color.red()
                embed = discord.Embed(
                    title="📉 Stock Sale Successful!",
                    description=message,
                    color=color
                )
                
                embed.add_field(
                    name="📊 Transaction Details",
                    value=f"**Symbol:** {symbol}\n"
                          f"**Sell Amount:** ${sell_amount:,.2f}\n"
                          f"**Shares Sold:** {shares_to_sell:,.4f}\n"
                          f"**Sale Price:** ${current_price:.2f}\n"
                          f"**Purchase Price:** ${position['purchase_price']:.2f}\n"
                          f"**Leverage:** {position['leverage']}x",
                    inline=False
                )
                
                # Show remaining balance
                remaining_balance = await self.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="💰 New Balance",
                    value=f"${remaining_balance:,.2f}",
                    inline=True
                )
                
                profit_emoji = "📈" if profit_loss >= 0 else "📉"
                embed.add_field(
                    name=f"{profit_emoji} Profit/Loss",
                    value=f"${profit_loss:,.2f}",
                    inline=True
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"User {user_id} sold ${sell_amount} worth of {symbol} ({shares_to_sell:.4f} shares)")
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in sell_stock command: {e}")
            await interaction.followup.send("❌ An error occurred while processing your stock sale. Please try again later.", ephemeral=True)
    
    @app_commands.command(name="portfolio", description="View your stock portfolio")
    @app_commands.describe(user="User to view portfolio for (optional)")
    @app_commands.guild_only()
    async def portfolio(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """View stock portfolio"""
        await interaction.response.defer()
        
        try:
            target_user = user or interaction.user
            user_id = str(target_user.id)
            
            # Get portfolio
            portfolio = await self.currency_manager.get_portfolio(user_id)
            
            if not portfolio:
                embed = discord.Embed(
                    title=f"📊 {target_user.display_name}'s Portfolio",
                    description="No stocks owned yet. Use `/buy_stock` to start investing!",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Get current prices for all owned stocks
            symbols = list(portfolio.keys())
            current_prices = await self.stock_manager.get_multiple_prices(symbols)
            
            # Calculate portfolio value (this will also trigger automatic liquidation if needed)
            total_value, total_profit_loss, position_details = await self.currency_manager.calculate_portfolio_value(user_id, current_prices)
            
            # Check if any positions were liquidated and notify users
            updated_portfolio = await self.currency_manager.get_portfolio(user_id)
            liquidated_symbols = []
            for symbol in symbols:
                if symbol not in updated_portfolio and symbol not in position_details:
                    liquidated_symbols.append(symbol)
            
            # Create portfolio embed
            embed = discord.Embed(
                title=f"📊 {target_user.display_name}'s Stock Portfolio",
                color=discord.Color.green() if total_profit_loss >= 0 else discord.Color.red()
            )
            
            # Add liquidation notification if any positions were liquidated
            if liquidated_symbols:
                liquidation_text = f"⚠️ **Auto-Liquidated Positions**: {', '.join(liquidated_symbols)}\n"
                liquidation_text += "These positions lost 100% or more of their value and were automatically sold for $0 to prevent further losses."
                embed.add_field(
                    name="🚨 Automatic Liquidation Alert",
                    value=liquidation_text,
                    inline=False
                )
            
            # Add portfolio summary
            cash_balance = await self.currency_manager.get_balance(user_id)
            
            # Calculate non-leveraged portfolio value (sum of original investments)
            non_leveraged_portfolio_value = 0.0
            for symbol, details in position_details.items():
                non_leveraged_portfolio_value += details["original_investment"] + total_profit_loss
            
            # Total Account Value should be Portfolio Value + Cash Balance
            total_account_value = cash_balance + non_leveraged_portfolio_value
            
            embed.add_field(
                name="💰 Account Summary",
                value=f"**Cash Balance:** ${cash_balance:,.2f}\n"
                      f"**Portfolio Value:** ${non_leveraged_portfolio_value:,.2f}\n"
                      f"**Total Account Value:** ${total_account_value:,.2f}\n"
                      f"**Total P&L:** ${total_profit_loss:,.2f}",
                inline=False
            )
            
            # Add individual positions with dividend info
            positions_text = ""
            total_estimated_dividends = 0.0
            
            for symbol, details in position_details.items():
                if current_prices.get(symbol) is None:
                    continue

                current_position_value =  details['original_investment'] + details['profit_loss']
                
                profit_emoji = "📈" if details["profit_loss"] >= 0 else "📉"
                positions_text += f"**{symbol}** {profit_emoji}\n"
                positions_text += f"Shares: {details['shares']:,.2f} | "
                positions_text += f"Leverage: {details['leverage']}x\n"
                positions_text += f"Buy: ${details['purchase_price']:.2f} | "
                positions_text += f"Current: ${details['current_price']:.2f}\n"
                positions_text += f"Original Investment: ${details['original_investment']:,.2f}\n "
                positions_text += f"Total Investment: ${current_position_value:,.2f}\n "
                positions_text += f"Net P&L: ${details['profit_loss']:,.2f} ({details['profit_loss_percentage']:+.1f}%)\n"
                
                # Add dividend information
                try:
                    dividend_yield = await self.stock_manager.get_dividend_yield(symbol)

                    if dividend_yield and dividend_yield > 0:
                        estimated_annual_dividend = current_position_value * (dividend_yield/100)
                        total_estimated_dividends += estimated_annual_dividend
                        positions_text += f"💰 Div Yield: {dividend_yield:,.2f}% | Est Annual: ${estimated_annual_dividend:,.2f}\n"
                    else:
                        positions_text += f"💰 No dividends\n"
                except Exception as e:
                    logger.warning(f"Could not fetch dividend info for {symbol}: {e}")
                    positions_text += f"💰 Dividend info unavailable\n"
                
                positions_text += "\n"
            
            if positions_text:
                # Split into multiple fields if too long
                if len(positions_text) > 1024:
                    # Split positions into chunks
                    chunks = []
                    current_chunk = ""
                    for line in positions_text.split('\n\n'):
                        if len(current_chunk + line) > 1000:
                            chunks.append(current_chunk)
                            current_chunk = line + '\n\n'
                        else:
                            current_chunk += line + '\n\n'
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    for i, chunk in enumerate(chunks):
                        field_name = "📈 Positions" if i == 0 else f"📈 Positions (cont. {i+1})"
                        embed.add_field(name=field_name, value=chunk.strip(), inline=False)
                else:
                    embed.add_field(name="📈 Positions", value=positions_text.strip(), inline=False)
                
                # Add dividend summary if there are dividend-paying positions
                if total_estimated_dividends > 0:
                    embed.add_field(
                        name="💰 Estimated Annual Dividends",
                        value=f"${total_estimated_dividends:.2f}",
                        inline=True
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Displayed portfolio for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in portfolio command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching your portfolio. Please try again later.", ephemeral=True)
    
    @app_commands.command(name="stock_price", description="Get current stock price and info")
    @app_commands.describe(symbol="Stock symbol to look up")
    @app_commands.guild_only()
    async def stock_price(self, interaction: discord.Interaction, symbol: str):
        """Get current stock price and information"""
        await interaction.response.defer()
        
        try:
            symbol = symbol.upper().strip()
            
            # Get stock price and info
            current_price = await self.stock_manager.get_stock_price(symbol)
            stock_info = await self.stock_manager.get_stock_info(symbol)
            
            if current_price is None:
                await interaction.followup.send(f"❌ Could not find stock symbol '{symbol}'. Please check the symbol and try again.", ephemeral=True)
                return
            
            # Create stock info embed
            embed = discord.Embed(
                title=f"📊 {symbol} Stock Information",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="💰 Current Price",
                value=f"${current_price:.2f}",
                inline=True
            )
            
            if stock_info:
                # Add additional info if available
                if 'longName' in stock_info:
                    embed.add_field(
                        name="🏢 Company",
                        value=stock_info['longName'],
                        inline=True
                    )
                
                if 'marketCap' in stock_info:
                    market_cap = stock_info['marketCap']
                    if market_cap:
                        embed.add_field(
                            name="📈 Market Cap",
                            value=f"${market_cap:,.0f}",
                            inline=True
                        )
                
                if 'previousClose' in stock_info:
                    prev_close = stock_info['previousClose']
                    if prev_close:
                        change = current_price - prev_close
                        change_percent = (change / prev_close)
                        change_emoji = "📈" if change >= 0 else "📉"
                        embed.add_field(
                            name=f"{change_emoji} Daily Change",
                            value=f"${change:+.2f} ({change_percent:+.2f}%)",
                            inline=True
                        )
            
            # Add current leverage setting
            current_leverage = self.stock_manager.get_current_leverage()
            embed.add_field(
                name="⚡ Current Leverage",
                value=f"{current_leverage}x",
                inline=False
            )
            
            embed.set_footer(text="Use /buy_stock to invest with leverage!")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Displayed stock price for {symbol}")
            
        except Exception as e:
            logger.error(f"Error in stock_price command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching stock information. Please try again later.", ephemeral=True)
    
    @app_commands.command(name="popular_stocks", description="View popular stock symbols")
    @app_commands.guild_only()
    async def popular_stocks(self, interaction: discord.Interaction):
        """Show popular stock symbols"""
        await interaction.response.defer()
        
        try:
            popular_stocks = self.stock_manager.get_popular_stocks()
            
            embed = discord.Embed(
                title="📊 Popular Stock Symbols",
                description="Here are some popular stocks you can trade:",
                color=discord.Color.blue()
            )
            
            # Split into chunks for better display
            chunk_size = 8
            for i in range(0, len(popular_stocks), chunk_size):
                chunk = popular_stocks[i:i + chunk_size]
                field_name = f"Stocks {i+1}-{min(i+chunk_size, len(popular_stocks))}"
                field_value = " • ".join(chunk)
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            embed.add_field(
                name="💡 How to Use",
                value="Use `/stock_price SYMBOL` to check prices\nUse `/buy_stock SYMBOL AMOUNT` to invest in stocks",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            logger.info("Displayed popular stocks list")
            
        except Exception as e:
            logger.error(f"Error in popular_stocks command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching popular stocks. Please try again later.", ephemeral=True)
    
    @app_commands.command(name="dividend_info", description="Get dividend information for a stock")
    @app_commands.describe(symbol="Stock symbol to get dividend info for")
    @app_commands.guild_only()
    async def dividend_info(self, interaction: discord.Interaction, symbol: str):
        """Get dividend information for a stock"""
        await interaction.response.defer()
        
        try:
            symbol = symbol.upper().strip()
            
            # Get dividend information
            dividend_info = await self.dividend_manager.get_dividend_info(symbol)
            
            if not dividend_info:
                await interaction.followup.send(f"❌ Could not find dividend information for '{symbol}'. Please check the symbol and try again.", ephemeral=True)
                return
            
            # Create dividend info embed
            embed = discord.Embed(
                title=f"💰 {symbol} Dividend Information",
                color=discord.Color.green() if dividend_info["pays_dividends"] else discord.Color.orange()
            )
            
            if dividend_info["pays_dividends"]:
                # Add dividend yield
                if dividend_info["dividend_yield"]:
                    yield_percent = dividend_info["dividend_yield"]
                    embed.add_field(
                        name="📊 Dividend Yield",
                        value=f"{yield_percent:.2f}%",
                        inline=True
                    )
                
                # Add forward dividend rate
                if dividend_info["forward_dividend_rate"]:
                    embed.add_field(
                        name="💵 Annual Dividend Rate",
                        value=f"${dividend_info['forward_dividend_rate']:.2f}",
                        inline=True
                    )
                
                # Add ex-dividend date
                if dividend_info["ex_dividend_date"]:
                    embed.add_field(
                        name="📅 Last Ex-Dividend Date",
                        value=dividend_info["ex_dividend_date"],
                        inline=True
                    )
                
                # Add last dividend amount
                if dividend_info["last_dividend_value"] > 0:
                    embed.add_field(
                        name="💳 Last Dividend Amount",
                        value=f"${dividend_info['last_dividend_value']:.4f}",
                        inline=True
                    )
                
                # Add recent dividend history
                if dividend_info["historical_dividends"]:
                    history_text = ""
                    for i, dividend in enumerate(dividend_info["historical_dividends"][:5]):  # Show last 5
                        history_text += f"**{dividend['date']}:** ${dividend['amount']:.4f}\n"
                    
                    embed.add_field(
                        name="📈 Recent Dividend History",
                        value=history_text,
                        inline=False
                    )
                
                embed.set_footer(text="💡 Dividends are paid automatically to shareholders on ex-dividend dates")
            else:
                embed.description = f"**{symbol}** does not currently pay dividends."
                embed.add_field(
                    name="ℹ️ Note",
                    value="This stock may still be a good investment for capital appreciation!",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Displayed dividend info for {symbol}")
            
        except Exception as e:
            logger.error(f"Error in dividend_info command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching dividend information. Please try again later.", ephemeral=True)
    
    @app_commands.command(name="dividend_history", description="View your dividend earnings history")
    @app_commands.describe(user="User to view dividend history for (optional)")
    @app_commands.guild_only()
    async def dividend_history(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """View dividend earnings history"""
        await interaction.response.defer()
        
        try:
            target_user = user or interaction.user
            user_id = str(target_user.id)
            
            # Get dividend summary from currency manager
            dividend_summary = await self.currency_manager.get_dividend_summary(user_id)
            
            embed = discord.Embed(
                title=f"💰 {target_user.display_name}'s Dividend History",
                color=discord.Color.green()
            )
            
            if dividend_summary["total_all_time"] == 0:
                embed.description = "No dividend earnings yet. Invest in dividend-paying stocks to start earning!"
                embed.add_field(
                    name="💡 Getting Started",
                    value="Use `/dividend_info SYMBOL` to check if a stock pays dividends\nUse `/buy_stock` to invest in dividend-paying stocks",
                    inline=False
                )
            else:
                # Add summary stats
                embed.add_field(
                    name="📊 Total Earnings",
                    value=f"**All Time:** ${dividend_summary['total_all_time']:,.2f}\n"
                          f"**Last 30 Days:** ${dividend_summary['total_last_30_days']:,.2f}",
                    inline=True
                )
                
                embed.add_field(
                    name="📈 Payment Count",
                    value=f"{dividend_summary['payment_count']} payments",
                    inline=True
                )
                
                # Add by-stock breakdown
                if dividend_summary["by_stock"]:
                    stock_breakdown = ""
                    sorted_stocks = sorted(dividend_summary["by_stock"].items(), key=lambda x: x[1], reverse=True)
                    
                    for symbol, amount in sorted_stocks[:8]:  # Top 8 stocks
                        stock_breakdown += f"**{symbol}:** ${amount:.2f}\n"
                    
                    embed.add_field(
                        name="💼 Earnings by Stock",
                        value=stock_breakdown,
                        inline=False
                    )
                
                # Add recent payments
                if dividend_summary["recent_payments"]:
                    recent_text = ""
                    for payment in dividend_summary["recent_payments"][:5]:  # Last 5 payments
                        recent_text += f"**{payment['symbol']}** - ${payment['amount']:.2f} ({payment['shares']:.2f} shares)\n"
                        recent_text += f"└ Ex-div: {payment['ex_dividend_date']}\n\n"
                    
                    embed.add_field(
                        name="🕐 Recent Payments",
                        value=recent_text.strip(),
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Displayed dividend history for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in dividend_history command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching dividend history. Please try again later.", ephemeral=True)
    
    @app_commands.command(name="dividend_calendar", description="View upcoming dividend dates for your portfolio")
    @app_commands.describe(days="Number of days ahead to look (default: 30)")
    @app_commands.guild_only()
    async def dividend_calendar(self, interaction: discord.Interaction, days: Optional[int] = 30):
        """View upcoming dividend calendar for portfolio"""
        await interaction.response.defer()
        
        try:
            user_id = str(interaction.user.id)
            
            if days is None or days <= 0:
                days = 30
            elif days > 365:
                days = 365
            
            # Get upcoming dividends for user's portfolio
            upcoming_dividends = await self.dividend_manager.get_upcoming_dividends_for_portfolio(user_id)
            
            embed = discord.Embed(
                title=f"📅 Dividend Calendar - Next {days} Days",
                color=discord.Color.blue()
            )
            
            if not upcoming_dividends:
                embed.description = "No upcoming dividends found for your portfolio."
                embed.add_field(
                    name="💡 Tips",
                    value="• Invest in dividend-paying stocks to see them here\n"
                          "• Use `/dividend_info SYMBOL` to check dividend information\n"
                          "• Popular dividend stocks: AAPL, MSFT, JNJ, KO, PEP",
                    inline=False
                )
            else:
                total_estimated = 0.0
                calendar_text = ""
                
                # Filter by date range and sort
                from datetime import date, timedelta
                end_date = date.today() + timedelta(days=days)
                
                filtered_dividends = []
                for dividend in upcoming_dividends:
                    try:
                        ex_div_date = date.fromisoformat(dividend["ex_dividend_date"])
                        if ex_div_date <= end_date:
                            filtered_dividends.append({
                                **dividend,
                                "ex_div_date_obj": ex_div_date
                            })
                    except:
                        continue
                
                filtered_dividends.sort(key=lambda x: x["ex_div_date_obj"])
                
                for dividend in filtered_dividends[:10]:  # Show up to 10 upcoming
                    symbol = dividend["symbol"]
                    ex_date = dividend["ex_dividend_date"]
                    amount_per_share = dividend["dividend_amount"]
                    shares = dividend["shares_owned"]
                    estimated_payout = dividend["estimated_payout"]
                    
                    total_estimated += estimated_payout
                    
                    calendar_text += f"**{symbol}** - {ex_date}\n"
                    calendar_text += f"└ ${amount_per_share:.4f}/share × {shares:.2f} shares = ${estimated_payout:.2f}\n\n"
                
                if calendar_text:
                    embed.add_field(
                        name="📊 Upcoming Dividends",
                        value=calendar_text.strip(),
                        inline=False
                    )
                    
                    embed.add_field(
                        name="💰 Estimated Total",
                        value=f"${total_estimated:.2f}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="📈 Count",
                        value=f"{len(filtered_dividends)} dividend{'s' if len(filtered_dividends) != 1 else ''}",
                        inline=True
                    )
                else:
                    embed.description = f"No upcoming dividends in the next {days} days."
            
            embed.set_footer(text="💡 Dividend amounts are estimates based on last payments. Actual amounts may vary.")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Displayed dividend calendar for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in dividend_calendar command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching dividend calendar. Please try again later.", ephemeral=True)

async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(StockMarketCog(bot), guild=guild_id)