import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging

from src.config.settings import GUILD_ID, DAILY_CLAIM

logger = logging.getLogger(__name__)

class CurrencyCog(commands.Cog):
    """Cog for managing virtual currency system"""
    
    def __init__(self, bot):
        self.bot = bot

        # Initialize currency manager
        self.currency_manager = bot.currency_manager
        logger.info("Currency system initialized")
        
        # # Start the daily currency distribution task
        # self.daily_distribution_task.start()
    
    @app_commands.command(name="balance", description="Check your current balance")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check balance for yourself or another user"""
        target_user = user if user else interaction.user
        user_id = str(target_user.id)
        
        # Reload currency data to ensure we have the most current balance
        await self.currency_manager.load_currency_data()
        
        balance = await self.currency_manager.get_balance(user_id)
        formatted_balance = self.currency_manager.format_balance(balance)
        
        embed = discord.Embed(
            title="💰 Balance",
            color=discord.Color.green()
        )
        
        if user:
            embed.description = f"{target_user.display_name} has {formatted_balance}"
        else:
            embed.description = f"You have {formatted_balance}"
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} checked balance for {target_user}: {formatted_balance}")
    
    @app_commands.command(name="daily", description=f"Claim your daily bonus of ${DAILY_CLAIM:,.2f}")
    async def daily(self, interaction: discord.Interaction):
        """Claim daily bonus"""
        user_id = str(interaction.user.id)
        
        success, message, new_balance = await self.currency_manager.claim_daily_bonus(user_id)
        
        embed = discord.Embed(
            title="🎁 Daily Bonus",
            description=message,
            color=discord.Color.gold() if success else discord.Color.red()
        )
        
        if success:
            embed.add_field(
                name="New Balance", 
                value=self.currency_manager.format_balance(new_balance), 
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} attempted daily claim: {message}")
    
    @app_commands.command(name="send", description="Send currency to another user")
    @app_commands.describe(
        user="The user to send currency to",
        amount="The amount to send"
    )
    async def send_currency(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Send currency to another user"""
        if user.id == interaction.user.id:
            embed = discord.Embed(
                title="❌ Transfer Failed",
                description="You cannot send currency to yourself!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if user.bot:
            embed = discord.Embed(
                title="❌ Transfer Failed",
                description="You cannot send currency to bots!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Reload currency data to ensure we have the most current balance
        await self.currency_manager.load_currency_data()
        
        from_user_id = str(interaction.user.id)
        to_user_id = str(user.id)
        
        success, message = await self.currency_manager.transfer_currency(from_user_id, to_user_id, amount)
        
        embed = discord.Embed(
            title="💸 Currency Transfer",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        if success:
            from_balance = await self.currency_manager.get_balance(from_user_id)
            to_balance = await self.currency_manager.get_balance(to_user_id)
            
            embed.add_field(
                name="Your New Balance",
                value=self.currency_manager.format_balance(from_balance),
                inline=True
            )
            embed.add_field(
                name=f"{user.display_name}'s New Balance",
                value=self.currency_manager.format_balance(to_balance),
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} attempted to send ${amount} to {user}: {message}")
    
    @app_commands.command(name="leaderboard", description="Show the net worth leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Show net worth leaderboard (cash + portfolio value)"""
        await interaction.response.defer()

        await self.currency_manager.load_currency_data()
        # Get all users with currency data
        currency_data = self.currency_manager.currency_data

        if not currency_data:
            embed = discord.Embed(
                title="💰 Net Worth Leaderboard",
                description="No users have currency data yet!",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed)
            return

        # Collect all unique stock symbols from all portfolios
        all_symbols = set()
        for user_data in currency_data.values():
            portfolio = user_data.get("portfolio", {})
            all_symbols.update(portfolio.keys())

        # Fetch current prices for all symbols
        current_prices = {}
        if all_symbols:
            try:
                from src.utils.stock_market_manager import StockMarketManager
                stock_manager = StockMarketManager()
                current_prices = await stock_manager.get_multiple_prices(list(all_symbols))
            except Exception as e:
                logger.error(f"Error fetching stock prices for leaderboard: {e}")
                # Continue with empty prices dict - individual calculations will handle fallbacks
                current_prices = {}

        # Calculate net worth for all users
        user_net_worths = []
        for user_id, user_data in currency_data.items():
            try:
                net_worth, cash_balance, portfolio_value = await self.currency_manager.calculate_net_worth(
                    user_id, current_prices
                )
                user_net_worths.append((user_id, net_worth, cash_balance, portfolio_value))
            except Exception as e:
                logger.error(f"Error calculating net worth for user {user_id}: {e}")
                # Fallback to cash balance only
                cash_balance = user_data.get("balance", 0)
                user_net_worths.append((user_id, cash_balance, cash_balance, 0.0))

        # Sort users by net worth (descending)
        sorted_users = sorted(user_net_worths, key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="💰 Net Worth Leaderboard",
            color=discord.Color.gold()
        )

        # Show top 10 users
        leaderboard_text = ""
        for i, (user_id, net_worth, cash_balance, portfolio_value) in enumerate(sorted_users[:10], 1):
            try:
                # Get member from the guild to get server-specific name
                member = interaction.guild.get_member(int(user_id))
                if member:
                    # Use display_name which shows server nickname or global display name
                    username = member.display_name
                else:
                    # Fallback if member not found in guild - try cached user first
                    user = self.bot.get_user(int(user_id))
                    if user:
                        username = user.display_name
                    else:
                        # Final fallback - fetch user from Discord API
                        try:
                            user = await self.bot.fetch_user(int(user_id))
                            username = user.display_name
                        except Exception as e:
                            logger.debug(f"Failed to fetch user {user_id} from Discord API: {e}")
                            username = f"User {user_id}"
            except Exception as e:
                logger.error(f"Error processing user {user_id} in leaderboard: {e}")
                username = f"User {user_id}"

            net_worth_formatted = self.currency_manager.format_balance(net_worth)

            # Add medal emojis for top 3
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."

            # Show only net worth total
            leaderboard_text += f"{medal} {username}: {net_worth_formatted}\n"

        embed.description = leaderboard_text

        # Show current user's rank if not in top 10
        user_id = str(interaction.user.id)
        user_rank = next((i for i, (uid, _, _, _) in enumerate(sorted_users, 1) if uid == user_id), None)
        if user_rank and user_rank > 10:
            user_net_worth = next((nw for uid, nw, _, _ in sorted_users if uid == user_id), 0)
            user_net_worth_formatted = self.currency_manager.format_balance(user_net_worth)
            embed.add_field(
                name="Your Rank",
                value=f"#{user_rank}: {user_net_worth_formatted}",
                inline=False
            )

        await interaction.followup.send(embed=embed)
        logger.info(f"{interaction.user} viewed net worth leaderboard")

    @app_commands.command(name="cash_leaderboard", description="Show the cash balance leaderboard")
    async def cash_leaderboard(self, interaction: discord.Interaction):
        """Show cash balance leaderboard (cash only, no portfolio)"""
        await self.currency_manager.load_currency_data()
        # Get all users with currency data
        currency_data = self.currency_manager.currency_data

        if not currency_data:
            embed = discord.Embed(
                title="💵 Cash Balance Leaderboard",
                description="No users have currency data yet!",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return

        # Sort users by balance (descending)
        sorted_users = sorted(
            currency_data.items(),
            key=lambda x: x[1]["balance"],
            reverse=True
        )

        embed = discord.Embed(
            title="💵 Cash Balance Leaderboard",
            color=discord.Color.green()
        )

        # Show top 10 users
        leaderboard_text = ""
        for i, (user_id, data) in enumerate(sorted_users[:10], 1):
            try:
                # Get member from the guild to get server-specific name
                member = interaction.guild.get_member(int(user_id))
                if member:
                    # Use display_name which shows server nickname or global display name
                    username = member.display_name
                else:
                    # Fallback if member not found in guild - try cached user first
                    user = self.bot.get_user(int(user_id))
                    if user:
                        username = user.display_name
                    else:
                        # Final fallback - fetch user from Discord API
                        try:
                            user = await self.bot.fetch_user(int(user_id))
                            username = user.display_name
                        except Exception as e:
                            logger.debug(f"Failed to fetch user {user_id} from Discord API: {e}")
                            username = f"User {user_id}"
            except Exception as e:
                logger.error(f"Error processing user {user_id} in cash leaderboard: {e}")
                username = f"User {user_id}"

            balance = self.currency_manager.format_balance(data["balance"])

            # Add medal emojis for top 3
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."

            leaderboard_text += f"{medal} {username}: {balance}\n"

        embed.description = leaderboard_text

        # Show current user's rank if not in top 10
        user_id = str(interaction.user.id)
        if user_id in currency_data:
            user_rank = next((i for i, (uid, _) in enumerate(sorted_users, 1) if uid == user_id), None)
            if user_rank and user_rank > 10:
                user_balance = self.currency_manager.format_balance(currency_data[user_id]["balance"])
                embed.add_field(
                    name="Your Rank",
                    value=f"#{user_rank}: {user_balance}",
                    inline=False
                )

        await interaction.response.send_message(embed=embed)
        logger.info(f"{interaction.user} viewed cash balance leaderboard")

    @app_commands.command(name="test_user_lookup", description="Test user lookup functionality (diagnostic)")
    async def test_user_lookup(self, interaction: discord.Interaction):
        """Diagnostic command to test user lookup functionality"""
        user_id = str(interaction.user.id)
        
        embed = discord.Embed(
            title="🔍 User Lookup Diagnostic",
            color=discord.Color.blue()
        )
        
        # Test all three lookup methods
        results = []
        
        # Method 1: Guild member lookup
        try:
            member = interaction.guild.get_member(int(user_id))
            if member:
                results.append(f"✅ Guild Member: {member.display_name}")
            else:
                results.append("❌ Guild Member: Not found")
        except Exception as e:
            results.append(f"❌ Guild Member: Error - {e}")
        
        # Method 2: Cached user lookup
        try:
            user = self.bot.get_user(int(user_id))
            if user:
                results.append(f"✅ Cached User: {user.display_name}")
            else:
                results.append("❌ Cached User: Not found")
        except Exception as e:
            results.append(f"❌ Cached User: Error - {e}")
        
        # Method 3: API fetch
        try:
            user = await self.bot.fetch_user(int(user_id))
            if user:
                results.append(f"✅ API Fetch: {user.display_name}")
            else:
                results.append("❌ API Fetch: Not found")
        except Exception as e:
            results.append(f"❌ API Fetch: Error - {e}")
        
        embed.description = "\n".join(results)
        embed.add_field(
            name="Your User ID",
            value=user_id,
            inline=False
        )
        embed.add_field(
            name="Bot Intents",
            value=f"Members: {self.bot.intents.members}\nUsers: {self.bot.intents.default()}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"{interaction.user} ran user lookup diagnostic")
    
    # @tasks.loop(hours=1)
    # async def daily_distribution_task(self):
    #     """Background task to automatically distribute daily bonuses"""
    #     try:
    #         # Get all users who have currency data
    #         currency_data = self.currency_manager.currency_data
    #         eligible_users = []
    #
    #         for user_id, data in currency_data.items():
    #             can_claim, _ = await self.currency_manager.can_claim_daily(user_id)
    #             if can_claim:
    #                 eligible_users.append(user_id)
    #
    #         if eligible_users:
    #             logger.info(f"Auto-distributing daily bonuses to {len(eligible_users)} eligible users")
    #
    #             for user_id in eligible_users:
    #                 success, message, new_balance = await self.currency_manager.claim_daily_bonus(user_id)
    #                 if success:
    #                     logger.info(f"Auto-distributed daily bonus to user {user_id}: {message}")
    #
    #             logger.info(f"Completed auto-distribution of daily bonuses")
    #         else:
    #             logger.debug("No users eligible for daily bonus auto-distribution")
    #
    #     except Exception as e:
    #         logger.error(f"Error in daily distribution task: {e}")
    #
    # @daily_distribution_task.before_loop
    # async def before_daily_distribution_task(self):
    #     """Wait until the bot is ready before starting the task"""
    #     await self.bot.wait_until_ready()
    #     logger.info("Daily currency distribution task started")
    #
    # def cog_unload(self):
    #     """Clean up when the cog is unloaded"""
    #     self.daily_distribution_task.cancel()
    #     logger.info("Daily currency distribution task stopped")

async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(CurrencyCog(bot),guild=guild_id)