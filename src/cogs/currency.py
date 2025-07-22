import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime, timedelta

from src.config.settings import GUILD_ID
from src.utils.currency_manager import CurrencyManager

logger = logging.getLogger(__name__)

class CurrencyCog(commands.Cog):
    """Cog for managing virtual currency system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.currency_manager = CurrencyManager()
        logger.info("Currency system initialized")
        
        # Start the daily currency distribution task
        self.daily_distribution_task.start()
    
    @app_commands.command(name="balance", description="Check your current balance")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check balance for yourself or another user"""
        target_user = user if user else interaction.user
        user_id = str(target_user.id)
        
        # Reload currency data to ensure we have the most current balance
        self.currency_manager.load_currency_data()
        
        balance = self.currency_manager.get_balance(user_id)
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
    
    @app_commands.command(name="daily", description="Claim your daily bonus of $1,000")
    async def daily(self, interaction: discord.Interaction):
        """Claim daily bonus"""
        user_id = str(interaction.user.id)
        
        success, message, new_balance = self.currency_manager.claim_daily_bonus(user_id)
        
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
        self.currency_manager.load_currency_data()
        
        from_user_id = str(interaction.user.id)
        to_user_id = str(user.id)
        
        success, message = self.currency_manager.transfer_currency(from_user_id, to_user_id, amount)
        
        embed = discord.Embed(
            title="💸 Currency Transfer",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        if success:
            from_balance = self.currency_manager.get_balance(from_user_id)
            to_balance = self.currency_manager.get_balance(to_user_id)
            
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
    
    @app_commands.command(name="leaderboard", description="Show the currency leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        """Show currency leaderboard"""
        # Get all users with currency data
        currency_data = self.currency_manager.currency_data
        
        if not currency_data:
            embed = discord.Embed(
                title="📊 Currency Leaderboard",
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
            title="📊 Currency Leaderboard",
            color=discord.Color.gold()
        )
        
        # Show top 10 users
        leaderboard_text = ""
        for i, (user_id, data) in enumerate(sorted_users[:10], 1):
            try:
                user = self.bot.get_user(int(user_id))
                username = user.display_name if user else f"User {user_id}"
            except:
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
        logger.info(f"{interaction.user} viewed currency leaderboard")
    
    @tasks.loop(hours=1)
    async def daily_distribution_task(self):
        """Background task to automatically distribute daily bonuses"""
        try:
            # Get all users who have currency data
            currency_data = self.currency_manager.currency_data
            eligible_users = []
            
            for user_id, data in currency_data.items():
                can_claim, _ = self.currency_manager.can_claim_daily(user_id)
                if can_claim:
                    eligible_users.append(user_id)
            
            if eligible_users:
                logger.info(f"Auto-distributing daily bonuses to {len(eligible_users)} eligible users")
                
                for user_id in eligible_users:
                    success, message, new_balance = self.currency_manager.claim_daily_bonus(user_id)
                    if success:
                        logger.info(f"Auto-distributed daily bonus to user {user_id}: {message}")
                
                logger.info(f"Completed auto-distribution of daily bonuses")
            else:
                logger.debug("No users eligible for daily bonus auto-distribution")
                
        except Exception as e:
            logger.error(f"Error in daily distribution task: {e}")
    
    @daily_distribution_task.before_loop
    async def before_daily_distribution_task(self):
        """Wait until the bot is ready before starting the task"""
        await self.bot.wait_until_ready()
        logger.info("Daily currency distribution task started")
    
    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        self.daily_distribution_task.cancel()
        logger.info("Daily currency distribution task stopped")

async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(CurrencyCog(bot),guild=guild_id)