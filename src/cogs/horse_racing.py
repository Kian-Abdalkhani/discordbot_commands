import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime, timedelta

from src.config.settings import GUILD_ID, HORSE_RACE_UPDATE_INTERVAL, HORSE_RACE_DURATION, HORSE_RACE_ALLOW_ADMIN_START, HORSE_RACE_SCHEDULE,HORSE_RACE_CHANNEL_ID
from src.utils.horse_race_manager import HorseRaceManager

logger = logging.getLogger(__name__)

class HorseRacingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.horse_race_manager = HorseRaceManager()
        self.currency_manager = bot.currency_manager
        
        # Race state
        self.current_race_message = None
        self.race_start_time = None
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        await self.horse_race_manager.initialize()
        self.check_race_schedule.start()
        logger.info("Horse Racing Cog loaded successfully")

    async def cog_unload(self):
        """Called when the cog is unloaded"""
        self.check_race_schedule.cancel()
        if hasattr(self, 'race_animation_task') and not self.race_animation_task.done():
            self.race_animation_task.cancel()
        
    @tasks.loop(minutes=5)  # Check every 5 minutes for scheduled races
    async def check_race_schedule(self):
        """Check if it's time to start a scheduled race"""
        try:
            if self.horse_race_manager.race_in_progress:
                return  # Skip check if race already in progress
                
            now = datetime.now()
            
            # Check all scheduled race times
            for race_config in HORSE_RACE_SCHEDULE:
                race_day = race_config["day"]
                race_hour = race_config["hour"]
                race_minute = race_config["minute"]
                
                # Calculate the race time for today
                today_race_time = now.replace(hour=race_hour, minute=race_minute, second=0, microsecond=0)
                
                # Check if today matches the race day and it's time for the race
                if (now.weekday() == race_day and 
                    abs((now - today_race_time).total_seconds()) <= 300):  # Within 5 minutes
                    
                    # Find the general channel to announce the race
                    guild = self.bot.get_guild(GUILD_ID)
                    if guild:
                        # Set the channel that the horse race starts in
                        channel = HORSE_RACE_CHANNEL_ID
                        
                        if channel:
                            await self.start_scheduled_race(channel)
                            return  # Start only one race at a time
                        
        except Exception as e:
            logger.error(f"Error in race schedule check: {e}")
            
    @check_race_schedule.before_loop
    async def before_check_race_schedule(self):
        """Wait for bot to be ready before starting the schedule loop"""
        await self.bot.wait_until_ready()

    @app_commands.command(name="horserace_info", description="Show horse race information and current bets")
    async def horserace_info(self, interaction: discord.Interaction):
        await self.show_race_info(interaction)
        
    @app_commands.command(name="horserace_bet", description="Place a bet on a horse")
    @app_commands.describe(
        horse_id="Horse ID to bet on (1-8)",
        amount="Amount to bet"
    )
    async def horserace_bet(self, interaction: discord.Interaction, horse_id: int, amount: int):
        await self.place_bet(interaction, horse_id, amount)
        
    @app_commands.command(name="horserace_start", description="Start a horse race manually (admin only, if enabled)")
    async def horserace_start(self, interaction: discord.Interaction):
        await self.manual_start_race(interaction)
        
    @app_commands.command(name="horserace_schedule", description="Show the schedule for the next 3 horse races")
    async def horserace_schedule(self, interaction: discord.Interaction):
        await self.show_race_schedule(interaction)
            
    async def show_race_info(self, interaction: discord.Interaction):
        """Show current race information, betting odds, and all open bets"""
        try:
            horses = await self.horse_race_manager.get_current_horses()
            embed = self.horse_race_manager.create_betting_embed(horses, self.bot)
            
            if self.horse_race_manager.race_in_progress:
                # Create new embed for race in progress
                embed = discord.Embed(
                    title="🏇 Horse Racing - Race in Progress! 🏇",
                    description="🏁 Race in progress! Betting is closed.",
                    color=0xff9900,
                    timestamp=embed.timestamp
                )
                # Copy original embed fields
                original_embed = self.horse_race_manager.create_betting_embed(horses, self.bot)
                for field in original_embed.fields:
                    embed.add_field(name=field.name, value=field.value, inline=field.inline)
            elif not self.horse_race_manager.is_betting_time():
                # Create new embed for betting closed
                embed = discord.Embed(
                    title="🏇 Horse Racing - Betting Closed 🏇",
                    description="❌ Betting is currently closed.",
                    color=0xff0000,
                    timestamp=embed.timestamp
                )
                # Copy original embed fields
                original_embed = self.horse_race_manager.create_betting_embed(horses, self.bot)
                for field in original_embed.fields:
                    embed.add_field(name=field.name, value=field.value, inline=field.inline)
                
            # Bets are now shown directly under each horse in the embed
                
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing race info: {e}")
            await interaction.response.send_message(
                "❌ Error retrieving race information!", ephemeral=True
            )
            
    async def place_bet(self, interaction: discord.Interaction, horse_id: int, amount: int):
        """Place a bet on a horse"""
            
        user_id = str(interaction.user.id)
        
        try:
            # Check if user has enough currency
            user_balance = await self.currency_manager.get_balance(user_id)
            if user_balance < amount:
                await interaction.response.send_message(
                    f"❌ Insufficient funds! You have ${user_balance:,.2f}, need {amount:,.2f}.",
                    ephemeral=True
                )
                return
                
            # Place the bet
            success, message = await self.horse_race_manager.place_bet(user_id, horse_id, amount)
            
            if success:
                # Subtract bet amount from user's balance
                await self.currency_manager.subtract_currency(user_id, amount)
                
                embed = discord.Embed(
                    title="✅ Bet Placed Successfully!",
                    description=message,
                    color=0x00ff00
                )
                
                # Show updated balance
                new_balance = await self.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="Balance",
                    value=f"${new_balance:,.2f} remaining",
                    inline=True
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error placing bet: {e}")
            await interaction.response.send_message(
                "❌ Error placing bet. Please try again!", ephemeral=True
            )
            
    async def show_user_bets(self, interaction: discord.Interaction):
        """Show user's current bets"""
        user_id = str(interaction.user.id)
        
        try:
            bets = await self.horse_race_manager.get_user_bets(user_id)
            
            if not bets:
                embed = discord.Embed(
                    title="No Bets Placed",
                    description="You haven't placed any bets for the upcoming race.",
                    color=0xff9900
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            embed = discord.Embed(
                title="🎰 Your Current Bets",
                color=0x0099ff
            )
            
            total_bet = 0
            bet_details = []
            
            for bet in bets:
                from src.config.settings import HORSE_STATS
                horse_name = HORSE_STATS[bet["horse_id"] - 1]["name"]
                bet_details.append(f"🐎 **{horse_name}** - {bet['amount']:,.2f}")
                total_bet += bet['amount']
                
            embed.add_field(
                name="Bets Placed",
                value="\n".join(bet_details),
                inline=False
            )
            
            embed.add_field(
                name="Total Bet Amount",
                value=f"{total_bet:,.2f}",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error showing user bets: {e}")
            await interaction.response.send_message(
                "❌ Error retrieving your bets!", ephemeral=True
            )
            
    async def show_race_schedule(self, interaction: discord.Interaction):
        """Show the schedule for the next 3 horse races"""
        try:
            next_race_times = self.horse_race_manager.get_next_race_times(3)
            
            embed = discord.Embed(
                title="📅 Upcoming Horse Race Schedule 📅",
                description="Here are the dates and times for the next 3 horse races:",
                color=0x00ff00
            )
            
            for i, race_time in enumerate(next_race_times, 1):
                # Format the race time with Discord timestamp
                timestamp = int(race_time.timestamp())
                embed.add_field(
                    name=f"Race #{i}",
                    value=f"<t:{timestamp}:F>\n<t:{timestamp}:R>",
                    inline=False
                )
            
            embed.add_field(
                name="ℹ️ Information",
                value="Betting opens 1 week before each race!\nUse `/horserace_info` to see current betting status.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing race schedule: {e}")
            await interaction.response.send_message(
                "❌ Error retrieving race schedule!", ephemeral=True
            )
            
    async def manual_start_race(self, interaction: discord.Interaction):
        """Manually start a race (admin only)"""
        # Check if admin race starting is enabled
        if not HORSE_RACE_ALLOW_ADMIN_START:
            await interaction.response.send_message(
                "❌ Manual race starting has been disabled. Races now run on a scheduled basis only."
                "\nCheck `/horserace_info` for the next scheduled race time.", 
                ephemeral=True
            )
            return
            
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can manually start races!", ephemeral=True
            )
            return
            
        if self.horse_race_manager.race_in_progress:
            await interaction.response.send_message(
                "❌ A race is already in progress!", ephemeral=True
            )
            return
            
        try:
            await interaction.response.send_message("🏁 Starting race manually...")
            await self.start_race_in_channel(interaction.channel)
            
        except Exception as e:
            logger.error(f"Error starting manual race: {e}")
            await interaction.followup.send("❌ Error starting race!")
            
    async def start_scheduled_race(self, channel):
        """Start a scheduled race in the specified channel"""
        try:
            embed = discord.Embed(
                title="🏇 Horse Race Starting! 🏇",
                description="A scheduled horse race is about to begin!",
                color=0x00ff00
            )
            
            await channel.send("@here", embed=embed)
            await asyncio.sleep(3)  # Give people time to see the announcement
            
            await self.start_race_in_channel(channel)
            
        except Exception as e:
            logger.error(f"Error starting scheduled race: {e}")
            
    async def start_race_in_channel(self, channel = HORSE_RACE_CHANNEL_ID):
        """Start a race in the specified channel with animation"""
        try:
            # Start the race
            horses = await self.horse_race_manager.start_race()
            
            # Create initial race embed
            embed = self.horse_race_manager.create_race_embed(horses, 0.0)
            self.current_race_message = await channel.send(embed=embed)
            self.race_start_time = datetime.now()
            
            # Start race animation
            self.race_animation_task = asyncio.create_task(
                self.animate_race(channel, horses)
            )
            
        except Exception as e:
            logger.error(f"Error starting race: {e}")
            await channel.send("❌ Error starting race!")
            
    async def animate_race(self, channel, horses):
        """Animate the race with regular updates"""
        try:
            race_finished = False
            
            while not race_finished:
                await asyncio.sleep(HORSE_RACE_UPDATE_INTERVAL)
                
                # Calculate elapsed time
                time_elapsed = (datetime.now() - self.race_start_time).total_seconds()
                
                # Update race
                horses, race_finished = await self.horse_race_manager.update_race(time_elapsed)
                
                # Update embed
                if self.current_race_message:
                    embed = self.horse_race_manager.create_race_embed(horses, time_elapsed)
                    if race_finished:
                        # Create new finished embed
                        finished_embed = discord.Embed(
                            title="🏁 Race Finished! 🏁",
                            color=0xff0000,
                            timestamp=embed.timestamp
                        )
                        # Copy fields from race embed
                        for field in embed.fields:
                            finished_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                        embed = finished_embed
                        
                    try:
                        await self.current_race_message.edit(embed=embed)
                    except discord.NotFound:
                        # Message was deleted, continue anyway
                        pass
                        
                # Check for timeout (allow extra time since horses can take 60-120s to finish)
                if time_elapsed >= HORSE_RACE_DURATION:
                    race_finished = True
                    
            # Show final results
            await self.show_race_results(channel)
            
        except asyncio.CancelledError:
            logger.info("Race animation cancelled")
        except Exception as e:
            logger.error(f"Error in race animation: {e}")
            
    async def show_race_results(self, channel):
        """Show race results and handle payouts"""
        try:
            results = await self.horse_race_manager.get_race_results()
            if not results:
                await channel.send("❌ Error retrieving race results!")
                return
                
            # Create results embed
            embed = discord.Embed(
                title="🏆 Race Results 🏆",
                color=0xffd700
            )
            
            # Show top 3 finishers
            result_text = ""
            for i, result in enumerate(results[:3]):
                medal = ["🥇", "🥈", "🥉"][i]
                from src.config.settings import HORSE_STATS
                horse_color = next(h["color"] for h in HORSE_STATS if h["name"] == result["horse_name"])
                result_text += f"{medal} **{result['horse_name']}** {horse_color}\n"
                
            embed.add_field(
                name="Final Standings",
                value=result_text,
                inline=False
            )
            
            # Calculate and distribute payouts
            payouts = await self.horse_race_manager.calculate_payouts()
            
            if payouts:
                payout_text = ""
                total_winnings = 0
                
                for user_id, payout_info in payouts.items():
                    if payout_info["total_winnings"] > 0:
                        # Add winnings to user's balance
                        await self.currency_manager.add_currency(user_id, payout_info["total_winnings"])
                        
                        user = self.bot.get_user(int(user_id))
                        username = user.display_name if user else f"User {user_id}"
                        
                        payout_text += f"💰 **{username}**: {payout_info['total_winnings']:,.2f}\n"
                        total_winnings += payout_info["total_winnings"]
                        
                if payout_text:
                    embed.add_field(
                        name="🎉 Winners!",
                        value=payout_text,
                        inline=False
                    )
                    embed.add_field(
                        name="Total Paid Out",
                        value=f"{total_winnings:,.2f}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="No Winners",
                        value="No one bet on the winning horse! 🐎",
                        inline=False
                    )
                    
            await channel.send(embed=embed)
            
            # Reset race state
            await self.horse_race_manager.reset_race()
            self.current_race_message = None
            self.race_start_time = None
            
        except Exception as e:
            logger.error(f"Error showing race results: {e}")
            await channel.send("❌ Error processing race results!")

async def setup(bot):
    """Setup function to load the cog"""
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(HorseRacingCog(bot), guild=guild_id)