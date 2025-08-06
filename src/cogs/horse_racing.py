import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime, timedelta

from src.config.settings import GUILD_ID, HORSE_RACE_UPDATE_INTERVAL, HORSE_RACE_DURATION, HORSE_RACE_ALLOW_ADMIN_START, HORSE_RACE_SCHEDULE,HORSE_RACE_CHANNEL_ID, BET_TYPES, HORSE_STATS
from src.utils.horse_race_manager import HorseRaceManager

logger = logging.getLogger(__name__)

class HorseSelect(discord.ui.Select):
    """Dropdown for selecting horse"""
    def __init__(self, amount: int, cog):
        self.amount = amount
        self.cog = cog
        
        options = []
        for i, horse in enumerate(HORSE_STATS, 1):
            options.append(discord.SelectOption(
                label=f"Horse {i}: {horse['name']}",
                description=f"{horse['color']} - Speed: {horse['speed']}, Stamina: {horse['stamina']}",
                value=str(i)
            ))
        
        super().__init__(placeholder="Choose your horse...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        try:
            logger.info(f"Horse selection callback triggered - User: {interaction.user.id}, Amount: {self.amount}")
            horse_id = int(self.values[0])
            logger.info(f"Selected horse: {horse_id}")
            await self.cog.show_bet_type_selection_after_horse(interaction, horse_id, self.amount)
            logger.info(f"Bet type selection displayed for user {interaction.user.id}")
        except Exception as e:
            logger.error(f"Error in horse selection callback: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error processing your horse selection!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error processing your horse selection!", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"Failed to send error message to user: {followup_error}")

class BetTypeSelect(discord.ui.Select):
    """Dropdown for selecting bet type"""
    def __init__(self, horse_id: int, amount: int, cog):
        self.horse_id = horse_id
        self.amount = amount
        self.cog = cog
        
        options = []
        for bet_type, config in BET_TYPES.items():
            options.append(discord.SelectOption(
                label=config["name"],
                description=config["description"],
                value=bet_type
            ))
        
        super().__init__(placeholder="Choose your bet type...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        try:
            logger.info(f"Bet type selection callback triggered - User: {interaction.user.id}, Horse: {self.horse_id}, Amount: {self.amount}")
            bet_type = self.values[0]
            logger.info(f"Selected bet type: {bet_type}")
            await self.cog.place_bet_with_type(interaction, self.horse_id, self.amount, bet_type)
            logger.info(f"Bet placed successfully for user {interaction.user.id}")
        except Exception as e:
            logger.error(f"Error in bet type selection callback: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error processing your bet selection!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error processing your bet selection!", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"Failed to send error message to user: {followup_error}")

class BetAmountView(discord.ui.View):
    """View containing the horse selection dropdown"""
    def __init__(self, amount: int, cog):
        super().__init__(timeout=60)
        self.amount = amount
        self.cog = cog
        self.add_item(HorseSelect(amount, cog))
    
    async def on_timeout(self):
        """Handle view timeout"""
        try:
            logger.info(f"Horse selection timed out for amount {self.amount}")
            # Disable all items
            for item in self.children:
                item.disabled = True
        except Exception as e:
            logger.error(f"Error in BetAmountView timeout handler: {e}")

class BetView(discord.ui.View):
    """View containing the bet type dropdown"""
    def __init__(self, horse_id: int, amount: int, cog):
        super().__init__(timeout=60)
        self.horse_id = horse_id
        self.amount = amount
        self.cog = cog
        self.add_item(BetTypeSelect(horse_id, amount, cog))
    
    async def on_timeout(self):
        """Handle view timeout"""
        try:
            logger.info(f"Bet selection timed out for horse {self.horse_id}, amount {self.amount}")
            # Disable all items
            for item in self.children:
                item.disabled = True
        except Exception as e:
            logger.error(f"Error in BetView timeout handler: {e}")

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
        amount="Amount to bet"
    )
    async def horserace_bet(self, interaction: discord.Interaction, amount: int):
        await self.show_horse_selection(interaction, amount)
        
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
            
    async def show_horse_selection(self, interaction: discord.Interaction, amount: int):
        """Show horse selection dropdown"""
        user_id = str(interaction.user.id)
        
        try:
            logger.info(f"Showing horse selection - User: {user_id}, Amount: {amount}")
            
            # Check if user has enough currency
            user_balance = await self.currency_manager.get_balance(user_id)
            logger.debug(f"User {user_id} balance: ${user_balance:,.2f}")
            
            if user_balance < amount:
                error_msg = f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${amount:,.2f}."
                logger.warning(f"User {user_id} insufficient funds: has {user_balance}, needs {amount}")
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            # Check betting conditions
            betting_open = self.horse_race_manager.is_betting_time()
            race_in_progress = self.horse_race_manager.race_in_progress
            logger.debug(f"Betting conditions - betting_open: {betting_open}, race_in_progress: {race_in_progress}")
            
            if not betting_open:
                logger.warning(f"User {user_id} attempted to bet when betting is closed")
                await interaction.response.send_message("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if race_in_progress:
                logger.warning(f"User {user_id} attempted to bet during race")
                await interaction.response.send_message("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Show horse selection dropdown
            embed = discord.Embed(
                title="🐎 Select Your Horse",
                description=f"Choose a horse to place your ${amount:,.2f} bet on:",
                color=0x0099ff
            )
            
            # Show horse stats
            horses_info = ""
            horses = await self.horse_race_manager.get_current_horses()
            
            for i, horse_stat in enumerate(HORSE_STATS, 1):
                horses_info += f"**Horse {i}: {horse_stat['name']}** {horse_stat['color']}\n"
                horses_info += f"Speed: {horse_stat['speed']} | Stamina: {horse_stat['stamina']}\n\n"
            
            embed.add_field(
                name="🏇 Available Horses",
                value=horses_info,
                inline=False
            )
            
            # Create the view with dropdown
            logger.debug("Creating horse selection view with dropdown")
            view = BetAmountView(amount, self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"Horse selection displayed successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error showing horse selection for user {user_id}: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Error showing horse selection. Please try again!", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Error showing horse selection. Please try again!", ephemeral=True
                    )
            except Exception as error_response_error:
                logger.error(f"Failed to send error response to user {user_id}: {error_response_error}")

    async def show_bet_type_selection_after_horse(self, interaction: discord.Interaction, horse_id: int, amount: int):
        """Show bet type selection dropdown after horse is selected"""
        user_id = str(interaction.user.id)
        
        try:
            logger.info(f"Showing bet type selection after horse - User: {user_id}, Horse: {horse_id}, Amount: {amount}")
            
            # Validate horse_id range
            if horse_id < 1 or horse_id > len(HORSE_STATS):
                error_msg = f"❌ Invalid horse ID! Choose 1-{len(HORSE_STATS)}"
                logger.warning(f"Invalid horse ID {horse_id} for user {user_id}")
                await interaction.response.edit_message(content=error_msg, embed=None, view=None)
                return
            
            # Double-check currency again in case balance changed
            user_balance = await self.currency_manager.get_balance(user_id)
            logger.debug(f"User {user_id} balance: ${user_balance:,.2f}")
            
            if user_balance < amount:
                error_msg = f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${amount:,.2f}."
                logger.warning(f"User {user_id} insufficient funds: has {user_balance}, needs {amount}")
                await interaction.response.edit_message(content=error_msg, embed=None, view=None)
                return
            
            # Show horse info and bet type dropdown
            horse_name = HORSE_STATS[horse_id - 1]["name"]
            horse_color = HORSE_STATS[horse_id - 1]["color"]
            logger.debug(f"Selected horse: {horse_name} ({horse_color})")
            
            embed = discord.Embed(
                title="🎰 Select Bet Type",
                description=f"Placing ${amount:,.2f} bet on {horse_color} **{horse_name}**",
                color=0x0099ff
            )
            
            # Show odds for each bet type
            logger.debug("Calculating odds for all bet types")
            horses = await self.horse_race_manager.get_current_horses()
            odds_info = ""
            
            for bet_type, config in BET_TYPES.items():
                try:
                    odds = self.horse_race_manager.calculate_payout_odds(horses, bet_type)
                    payout_multiplier = odds[horse_id]
                    potential_winnings = int(amount * payout_multiplier)
                    odds_info += f"**{config['name']}**: {payout_multiplier:.1f}:1 (Win: ${potential_winnings:,.2f})\n"
                    odds_info += f"*{config['description']}*\n\n"
                    logger.debug(f"{bet_type} odds for horse {horse_id}: {payout_multiplier:.1f}:1")
                except Exception as odds_error:
                    logger.error(f"Error calculating {bet_type} odds: {odds_error}")
                    odds_info += f"**{config['name']}**: Error calculating odds\n"
            
            embed.add_field(
                name="🎯 Odds & Potential Winnings",
                value=odds_info,
                inline=False
            )
            
            # Create the view with dropdown
            logger.debug("Creating bet view with dropdown")
            view = BetView(horse_id, amount, self)
            await interaction.response.edit_message(content=None, embed=embed, view=view)
            logger.info(f"Bet type selection displayed successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error showing bet type selection after horse for user {user_id}: {e}", exc_info=True)
            try:
                await interaction.response.edit_message(
                    content="❌ Error showing bet options. Please try again!",
                    embed=None,
                    view=None
                )
            except Exception as error_response_error:
                logger.error(f"Failed to send error response to user {user_id}: {error_response_error}")

    async def show_bet_type_selection(self, interaction: discord.Interaction, horse_id: int, amount: int):
        """Show bet type selection dropdown"""
        user_id = str(interaction.user.id)
        
        try:
            logger.info(f"Showing bet type selection - User: {user_id}, Horse: {horse_id}, Amount: {amount}")
            
            # Validate horse_id range
            if horse_id < 1 or horse_id > len(HORSE_STATS):
                error_msg = f"❌ Invalid horse ID! Choose 1-{len(HORSE_STATS)}"
                logger.warning(f"Invalid horse ID {horse_id} for user {user_id}")
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            # Check if user has enough currency
            user_balance = await self.currency_manager.get_balance(user_id)
            logger.debug(f"User {user_id} balance: ${user_balance:,.2f}")
            
            if user_balance < amount:
                error_msg = f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${amount:,.2f}."
                logger.warning(f"User {user_id} insufficient funds: has {user_balance}, needs {amount}")
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            # Check betting conditions
            betting_open = self.horse_race_manager.is_betting_time()
            race_in_progress = self.horse_race_manager.race_in_progress
            logger.debug(f"Betting conditions - betting_open: {betting_open}, race_in_progress: {race_in_progress}")
            
            if not betting_open:
                logger.warning(f"User {user_id} attempted to bet when betting is closed")
                await interaction.response.send_message("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if race_in_progress:
                logger.warning(f"User {user_id} attempted to bet during race")
                await interaction.response.send_message("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Show horse info and bet type dropdown
            horse_name = HORSE_STATS[horse_id - 1]["name"]
            horse_color = HORSE_STATS[horse_id - 1]["color"]
            logger.debug(f"Selected horse: {horse_name} ({horse_color})")
            
            embed = discord.Embed(
                title="🎰 Select Bet Type",
                description=f"Placing ${amount:,.2f} bet on {horse_color} **{horse_name}**",
                color=0x0099ff
            )
            
            # Show odds for each bet type
            logger.debug("Calculating odds for all bet types")
            horses = await self.horse_race_manager.get_current_horses()
            odds_info = ""
            
            for bet_type, config in BET_TYPES.items():
                try:
                    odds = self.horse_race_manager.calculate_payout_odds(horses, bet_type)
                    payout_multiplier = odds[horse_id]
                    potential_winnings = int(amount * payout_multiplier)
                    odds_info += f"**{config['name']}**: {payout_multiplier:.1f}:1 (Win: ${potential_winnings:,.2f})\n"
                    odds_info += f"*{config['description']}*\n\n"
                    logger.debug(f"{bet_type} odds for horse {horse_id}: {payout_multiplier:.1f}:1")
                except Exception as odds_error:
                    logger.error(f"Error calculating {bet_type} odds: {odds_error}")
                    odds_info += f"**{config['name']}**: Error calculating odds\n"
            
            embed.add_field(
                name="🎯 Odds & Potential Winnings",
                value=odds_info,
                inline=False
            )
            
            # Create the view with dropdown
            logger.debug("Creating bet view with dropdown")
            view = BetView(horse_id, amount, self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"Bet type selection displayed successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error showing bet type selection for user {user_id}: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Error showing bet options. Please try again!", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Error showing bet options. Please try again!", ephemeral=True
                    )
            except Exception as error_response_error:
                logger.error(f"Failed to send error response to user {user_id}: {error_response_error}")
    
    async def place_bet_with_type(self, interaction: discord.Interaction, horse_id: int, amount: int, bet_type: str):
        """Place a bet with the selected type"""
        user_id = str(interaction.user.id)
        
        try:
            logger.info(f"Placing bet - User: {user_id}, Horse: {horse_id}, Amount: {amount}, Type: {bet_type}")
            
            # Double-check currency again in case balance changed
            user_balance = await self.currency_manager.get_balance(user_id)
            logger.debug(f"User balance: ${user_balance:,.2f}")
            
            if user_balance < amount:
                error_msg = f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${amount:,.2f}."
                logger.warning(f"Insufficient funds for user {user_id}: has {user_balance}, needs {amount}")
                
                # Use edit_message since the interaction was already responded to in the dropdown display
                await interaction.response.edit_message(
                    content=error_msg,
                    embed=None,
                    view=None
                )
                return
                
            # Place the bet with the selected type
            logger.debug(f"Calling horse_race_manager.place_bet for user {user_id}")
            success, message = await self.horse_race_manager.place_bet(user_id, horse_id, amount, bet_type)
            logger.debug(f"Bet placement result: success={success}, message={message}")
            
            if success:
                # Subtract bet amount from user's balance
                logger.debug(f"Subtracting {amount} from user {user_id} balance")
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
                
                logger.info(f"Bet successfully placed for user {user_id}, new balance: ${new_balance:,.2f}")
                
                # Use edit_message since the interaction was already responded to in the dropdown display
                await interaction.response.edit_message(
                    content=None,
                    embed=embed,
                    view=None
                )
            else:
                logger.warning(f"Bet placement failed for user {user_id}: {message}")
                await interaction.response.edit_message(
                    content=f"❌ {message}",
                    embed=None,
                    view=None
                )
                
        except Exception as e:
            logger.error(f"Error placing bet with type for user {user_id}: {e}", exc_info=True)
            try:
                await interaction.response.edit_message(
                    content="❌ Error placing bet. Please try again!",
                    embed=None,
                    view=None
                )
            except Exception as edit_error:
                logger.error(f"Failed to edit message with error for user {user_id}: {edit_error}")
                try:
                    await interaction.followup.send(
                        "❌ Error placing bet. Please try again!", ephemeral=True
                    )
                except Exception as followup_error:
                    logger.error(f"Failed to send followup message to user {user_id}: {followup_error}")
            
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
                horse_name = HORSE_STATS[bet["horse_id"] - 1]["name"]
                bet_type = bet.get("bet_type", "win")
                bet_type_name = BET_TYPES[bet_type]["name"]
                bet_details.append(f"🐎 **{horse_name}** - ${bet['amount']:,.2f} ({bet_type_name})")
                total_bet += bet['amount']
                
            embed.add_field(
                name="Bets Placed",
                value="\n".join(bet_details),
                inline=False
            )
            
            embed.add_field(
                name="Total Bet Amount",
                value=f"${total_bet:,.2f}",
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