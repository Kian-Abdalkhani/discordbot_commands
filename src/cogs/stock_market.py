import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
import logging
from typing import Optional

from src.config.settings import GUILD_ID, STOCK_MARKET_LEVERAGE
from src.utils.stock_market_manager import StockMarketManager

logger = logging.getLogger(__name__)

class StockMarketCog(commands.Cog):
    """Stock Market Simulator commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.currency_manager = bot.currency_manager
        self.stock_manager = StockMarketManager()
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
                non_leveraged_portfolio_value += details["original_investment"]
            
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
            
            # Add individual positions
            positions_text = ""
            for symbol, details in position_details.items():
                if current_prices.get(symbol) is None:
                    continue
                
                profit_emoji = "📈" if details["profit_loss"] >= 0 else "📉"
                positions_text += f"**{symbol}** {profit_emoji}\n"
                positions_text += f"Shares: {details['shares']:,.2f} | "
                positions_text += f"Leverage: {details['leverage']}x\n"
                positions_text += f"Buy: ${details['purchase_price']:.2f} | "
                positions_text += f"Current: ${details['current_price']:.2f}\n"
                positions_text += f"Investment: ${details['original_investment']:,.2f} | "
                positions_text += f"Net P&L: ${details['profit_loss']:,.2f} ({details['profit_loss_percentage']:+.1f}%)\n\n"
            
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
                        change_percent = (change / prev_close) * 100
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

async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(StockMarketCog(bot), guild=guild_id)