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
        super().__init__(timeout=300)
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
        super().__init__(timeout=300)
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

class MultiBetModal(discord.ui.Modal):
    """Modal for comprehensive multi-betting interface"""
    def __init__(self, cog):
        super().__init__(title="🏇 Multi-Horse Betting", timeout=600)
        self.cog = cog
        self.configured_bets = {}  # {horse_id: {bet_type: amount}}
        
        # Add text inputs for horse betting amounts
        self.horse_inputs = []
        # Discord modals are limited to 5 components, so show top 5 horses
        max_horses = min(5, len(HORSE_STATS))
        for i, horse_stat in enumerate(HORSE_STATS[:max_horses], 1):
            input_field = discord.ui.TextInput(
                label=f"{horse_stat['name']} {horse_stat['color']} - Win Bet",
                placeholder="Enter amount (e.g., 1000) or leave blank",
                required=False,
                max_length=10
            )
            self.add_item(input_field)
            self.horse_inputs.append(input_field)
            
    async def on_submit(self, interaction: discord.Interaction):
        """Process the multi-bet submission"""
        try:
            user_id = str(interaction.user.id)
            logger.info(f"Processing multi-bet submission for user {user_id}")
            
            # Parse bet inputs
            parsed_bets = []
            total_bet_amount = 0
            
            for i, input_field in enumerate(self.horse_inputs):
                if input_field.value.strip():
                    try:
                        amount = int(input_field.value.strip())
                        if amount > 0:
                            horse_id = i + 1
                            parsed_bets.append({
                                'horse_id': horse_id,
                                'amount': amount,
                                'bet_type': 'win'  # Default to win bets for now
                            })
                            total_bet_amount += amount
                    except ValueError:
                        await interaction.response.send_message(
                            f"❌ Invalid amount for {await self.bot.horse_nickname_manager.get_horse_display_name(i)}: '{input_field.value}'. Please enter a valid number.",
                            ephemeral=True
                        )
                        return
            
            if not parsed_bets:
                await interaction.response.send_message(
                    "❌ No bets were configured. Please enter at least one bet amount.",
                    ephemeral=True
                )
                return
            
            # Check if user has enough currency for total bet
            user_balance = await self.cog.currency_manager.get_balance(user_id)
            if user_balance < total_bet_amount:
                await interaction.response.send_message(
                    f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${total_bet_amount:,.2f}.",
                    ephemeral=True
                )
                return
            
            # Check betting conditions
            if not self.cog.horse_race_manager.is_betting_time():
                await interaction.response.send_message("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if self.cog.horse_race_manager.race_in_progress:
                await interaction.response.send_message("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Process all bets
            successful_bets = []
            failed_bets = []
            total_deducted = 0
            
            for bet in parsed_bets:
                success, message = await self.cog.horse_race_manager.place_bet(
                    user_id, bet['horse_id'], bet['amount'], bet['bet_type']
                )
                
                if success:
                    successful_bets.append(bet)
                    total_deducted += bet['amount']
                else:
                    failed_bets.append({'bet': bet, 'error': message})
            
            if successful_bets:
                # Deduct currency for successful bets
                await self.cog.currency_manager.subtract_currency(user_id, total_deducted)
                
                # Create success response
                embed = discord.Embed(
                    title="✅ Multi-Bet Placed Successfully!",
                    color=0x00ff00
                )
                
                bet_summary = ""
                for bet in successful_bets:
                    horse_name = HORSE_STATS[bet['horse_id'] - 1]['name']
                    bet_type_name = BET_TYPES[bet['bet_type']]['name']
                    bet_summary += f"• {horse_name}: ${bet['amount']:,.2f} ({bet_type_name})\n"
                
                embed.add_field(
                    name="Successful Bets",
                    value=bet_summary,
                    inline=False
                )
                
                embed.add_field(
                    name="Total Bet Amount",
                    value=f"${total_deducted:,.2f}",
                    inline=True
                )
                
                new_balance = await self.cog.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="Remaining Balance",
                    value=f"${new_balance:,.2f}",
                    inline=True
                )
                
                if failed_bets:
                    failed_summary = ""
                    for failed in failed_bets:
                        horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                        failed_summary += f"• {horse_name}: {failed['error']}\n"
                    
                    embed.add_field(
                        name="❌ Failed Bets",
                        value=failed_summary,
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"Multi-bet successfully processed for user {user_id}: {len(successful_bets)} successful, {len(failed_bets)} failed")
            else:
                # All bets failed
                error_summary = ""
                for failed in failed_bets:
                    horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                    error_summary += f"• {horse_name}: {failed['error']}\n"
                
                await interaction.response.send_message(
                    f"❌ All bets failed:\n{error_summary}",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error processing multi-bet submission: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Error processing your bets. Please try again!",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Error processing your bets. Please try again!",
                        ephemeral=True
                    )
            except Exception as error_response_error:
                logger.error(f"Failed to send error response: {error_response_error}")

class CleanMultiBetView(discord.ui.View):
    """Clean interface for selecting bet type and placing multiple bets"""
    def __init__(self, cog):
        super().__init__(timeout=600)
        self.cog = cog
        
    @discord.ui.button(label="🏆 Win", style=discord.ButtonStyle.primary, row=0)
    async def win_bets(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Win betting modal for all horses"""
        modal = BetTypeModal(self.cog, "win")
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="🥈 Place", style=discord.ButtonStyle.primary, row=0) 
    async def place_bets(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Place betting modal for all horses"""
        modal = BetTypeModal(self.cog, "place")
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="🥉 Show", style=discord.ButtonStyle.primary, row=1)
    async def show_bets(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Show betting modal for all horses"""
        modal = BetTypeModal(self.cog, "show")
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="🎯 Last", style=discord.ButtonStyle.primary, row=1)
    async def last_bets(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open Last Place betting modal for all horses"""
        modal = BetTypeModal(self.cog, "last")
        await interaction.response.send_modal(modal)

class BetTypeModal(discord.ui.Modal):
    """Modal for placing bets on all horses for a specific bet type"""
    def __init__(self, cog, bet_type):
        bet_config = BET_TYPES[bet_type]
        super().__init__(title=f"🏇 {bet_config['name']} Bets - All Horses", timeout=600)
        self.cog = cog
        self.bet_type = bet_type
        
        # Add text inputs for all 8 horses (Discord modal limit is 5, so show first 5)
        self.horse_inputs = []
        max_horses = min(5, len(HORSE_STATS))  # Discord modal limitation
        
        for i in range(max_horses):
            horse_stat = HORSE_STATS[i]
            horse_num = i + 1
            
            input_field = discord.ui.TextInput(
                label=f"{horse_num}. {horse_stat['name']} {horse_stat['color']}",
                placeholder="Enter bet amount (e.g., 1000) or leave blank",
                required=False,
                max_length=10,
                style=discord.TextStyle.short
            )
            self.add_item(input_field)
            self.horse_inputs.append(input_field)
            
        # Add note about remaining horses if there are more than 5
        if len(HORSE_STATS) > 5:
            note_field = discord.ui.TextInput(
                label="⚠️ More horses available after submission",
                placeholder="This modal shows first 5 horses. Submit to continue with remaining horses.",
                required=False,
                max_length=1,
                style=discord.TextStyle.short
            )
            # Remove one horse input to make room for the note
            self.remove_item(self.horse_inputs[-1])
            self.horse_inputs.pop()
            self.add_item(note_field)
            
    async def on_submit(self, interaction: discord.Interaction):
        """Process bet submission for this bet type"""
        try:
            user_id = str(interaction.user.id)
            logger.info(f"Processing {self.bet_type} bets for user {user_id}")
            
            # Parse bet inputs
            parsed_bets = []
            total_bet_amount = 0
            parse_errors = []
            
            for i, input_field in enumerate(self.horse_inputs):
                if input_field.value.strip():
                    horse_id = i + 1
                    
                    try:
                        amount = int(input_field.value.strip())
                        if amount > 0:
                            parsed_bets.append({
                                'horse_id': horse_id,
                                'amount': amount,
                                'bet_type': self.bet_type
                            })
                            total_bet_amount += amount
                    except ValueError:
                        horse_name = HORSE_STATS[i]['name']
                        parse_errors.append(f"{horse_name}: Invalid amount '{input_field.value}'. Please enter a valid number.")
            
            # Show parse errors if any
            if parse_errors:
                error_msg = "❌ **Input Errors:**\n" + "\n".join([f"• {error}" for error in parse_errors])
                if parsed_bets:
                    error_msg += f"\n\n✅ {len(parsed_bets)} valid bets found."
                
                # If there are more horses and some valid bets, offer to continue
                if len(HORSE_STATS) > len(self.horse_inputs) and parsed_bets:
                    error_msg += f"\n\n⏭️ **Continue with remaining horses?**"
                    view = ContinueBettingView(self.cog, self.bet_type, parsed_bets, total_bet_amount)
                    await interaction.response.send_message(error_msg, view=view, ephemeral=True)
                else:
                    await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            if not parsed_bets:
                # No bets for this set, but check if there are more horses
                if len(HORSE_STATS) > len(self.horse_inputs):
                    embed = discord.Embed(
                        title=f"Continue with {BET_TYPES[self.bet_type]['name']} Bets?",
                        description=f"No bets entered for horses 1-{len(self.horse_inputs)}.\nContinue with horses {len(self.horse_inputs)+1}-{len(HORSE_STATS)}?",
                        color=0x0099ff
                    )
                    view = ContinueBettingView(self.cog, self.bet_type, [], 0)
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                else:
                    await interaction.response.send_message(
                        f"❌ No {BET_TYPES[self.bet_type]['name']} bets entered. Please enter at least one bet amount.",
                        ephemeral=True
                    )
                return
            
            # If there are more horses, show continue option
            if len(HORSE_STATS) > len(self.horse_inputs):
                embed = discord.Embed(
                    title=f"✅ {len(parsed_bets)} {BET_TYPES[self.bet_type]['name']} Bets Configured",
                    description=(
                        f"**Current Bets:** ${total_bet_amount:,.2f} total\n\n"
                        f"Continue with horses {len(self.horse_inputs)+1}-{len(HORSE_STATS)} or submit current bets?"
                    ),
                    color=0x0099ff
                )
                
                bet_summary = ""
                for bet in parsed_bets:
                    horse_name = HORSE_STATS[bet['horse_id'] - 1]['name']
                    horse_color = HORSE_STATS[bet['horse_id'] - 1]['color']
                    bet_summary += f"• {horse_color} {horse_name}: ${bet['amount']:,.2f}\n"
                
                embed.add_field(
                    name="Current Bets",
                    value=bet_summary,
                    inline=False
                )
                
                view = ContinueBettingView(self.cog, self.bet_type, parsed_bets, total_bet_amount)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                # Process all bets (all horses covered)
                await self._process_final_bets(interaction, parsed_bets, total_bet_amount)
                
        except Exception as e:
            logger.error(f"Error in {self.bet_type} bet modal: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ Error processing {BET_TYPES[self.bet_type]['name']} bets. Please try again!",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Error processing {BET_TYPES[self.bet_type]['name']} bets. Please try again!",
                        ephemeral=True
                    )
            except Exception as error_response_error:
                logger.error(f"Failed to send error response: {error_response_error}")
                
    async def _process_final_bets(self, interaction: discord.Interaction, parsed_bets: list, total_bet_amount: int):
        """Process the final bet submission"""
        user_id = str(interaction.user.id)
        
        try:
            # Check balance
            user_balance = await self.cog.currency_manager.get_balance(user_id)
            if user_balance < total_bet_amount:
                await interaction.response.send_message(
                    f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${total_bet_amount:,.2f}.",
                    ephemeral=True
                )
                return
            
            # Check betting conditions
            if not self.cog.horse_race_manager.is_betting_time():
                await interaction.response.send_message("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if self.cog.horse_race_manager.race_in_progress:
                await interaction.response.send_message("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Use batch betting functionality
            successful_bets, failed_bets = await self.cog.horse_race_manager.place_multiple_bets(user_id, parsed_bets)
            
            if successful_bets:
                # Deduct currency for successful bets
                total_deducted = sum(bet['amount'] for bet in successful_bets)
                await self.cog.currency_manager.subtract_currency(user_id, total_deducted)
                
                # Create detailed response
                embed = discord.Embed(
                    title=f"✅ {BET_TYPES[self.bet_type]['name']} Bets Placed Successfully!",
                    color=0x00ff00
                )
                
                bet_summary = ""
                total_potential_winnings = 0
                horses = await self.cog.horse_race_manager.get_current_horses()
                
                for bet in successful_bets:
                    horse_name = HORSE_STATS[bet['horse_id'] - 1]['name']
                    horse_color = HORSE_STATS[bet['horse_id'] - 1]['color']
                    
                    # Calculate potential winnings
                    potential_winnings = self.cog.horse_race_manager.calculate_potential_winnings(
                        horses, bet['horse_id'], bet['amount'], bet['bet_type']
                    )
                    total_potential_winnings += potential_winnings
                    
                    bet_summary += f"• {horse_color} {horse_name}: ${bet['amount']:,.2f} → ${potential_winnings:,.2f}\n"
                
                embed.add_field(
                    name=f"🎯 {BET_TYPES[self.bet_type]['name']} Bets & Potential Winnings",
                    value=bet_summary,
                    inline=False
                )
                
                embed.add_field(
                    name="💰 Summary",
                    value=(
                        f"**Total Bet:** ${total_deducted:,.2f}\n"
                        f"**Max Potential:** ${total_potential_winnings:,.2f}\n"
                        f"**Bet Type:** {BET_TYPES[self.bet_type]['description']}"
                    ),
                    inline=True
                )
                
                new_balance = await self.cog.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="🏦 Balance",
                    value=f"${new_balance:,.2f} remaining",
                    inline=True
                )
                
                if failed_bets:
                    failed_summary = ""
                    for failed in failed_bets:
                        horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                        failed_summary += f"• {horse_name}: {failed['error']}\n"
                    
                    embed.add_field(
                        name="❌ Failed Bets",
                        value=failed_summary,
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # All bets failed
                error_summary = f"❌ **All {BET_TYPES[self.bet_type]['name']} bets failed:**\n"
                for failed in failed_bets:
                    horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                    error_summary += f"• {horse_name}: {failed['error']}\n"
                
                await interaction.response.send_message(error_summary, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error processing final {self.bet_type} bets: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error processing {BET_TYPES[self.bet_type]['name']} bets. Please try again!",
                ephemeral=True
            )

class ContinueBettingView(discord.ui.View):
    """View for continuing betting with remaining horses or submitting current bets"""
    def __init__(self, cog, bet_type, current_bets, current_total):
        super().__init__(timeout=300)
        self.cog = cog
        self.bet_type = bet_type
        self.current_bets = current_bets
        self.current_total = current_total
        
    def disable_all_items(self):
        """Disable all buttons in the view"""
        for item in self.children:
            item.disabled = True
        
    @discord.ui.button(label="⏭️ Continue Betting", style=discord.ButtonStyle.primary)
    async def continue_betting(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Continue betting with remaining horses"""
        # Calculate how many horses we've already covered
        horses_covered = min(5, len(HORSE_STATS)) if len(HORSE_STATS) > 5 else len(HORSE_STATS)
        if len(HORSE_STATS) > 5 and len(self.current_bets) < 4:  # Account for note field taking space
            horses_covered = 4
            
        remaining_horses = len(HORSE_STATS) - horses_covered
        if remaining_horses > 0:
            # Send modal directly as response (this is the fix!)
            modal = RemainingHorsesModal(self.cog, self.bet_type, self.current_bets, self.current_total, horses_covered)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("❌ All horses have been covered!", ephemeral=True)
            
    @discord.ui.button(label="✅ Submit Current Bets", style=discord.ButtonStyle.green)
    async def submit_current(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Submit the current bets without continuing"""
        # Disable view and clear message
        self.disable_all_items()
        await interaction.response.edit_message(content="✅ Processing your bets...", embed=None, view=self)
        
        if not self.current_bets:
            await interaction.followup.send(
                f"❌ No {BET_TYPES[self.bet_type]['name']} bets to submit!",
                ephemeral=True
            )
            return
            
        # Process the current bets
        await self._process_final_bets_followup(interaction, self.current_bets, self.current_total)
        
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_betting(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the betting process"""
        # Disable view and clear message
        self.disable_all_items()
        await interaction.response.edit_message(
            content=f"❌ {BET_TYPES[self.bet_type]['name']} betting cancelled.",
            embed=None, 
            view=self
        )
        
    async def _process_final_bets_followup(self, interaction: discord.Interaction, parsed_bets: list, total_bet_amount: int):
        """Process the final bet submission using followup (for buttons)"""
        user_id = str(interaction.user.id)
        
        try:
            # Check balance
            user_balance = await self.cog.currency_manager.get_balance(user_id)
            if user_balance < total_bet_amount:
                await interaction.followup.send(
                    f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${total_bet_amount:,.2f}.",
                    ephemeral=True
                )
                return
            
            # Check betting conditions
            if not self.cog.horse_race_manager.is_betting_time():
                await interaction.followup.send("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if self.cog.horse_race_manager.race_in_progress:
                await interaction.followup.send("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Use batch betting functionality
            successful_bets, failed_bets = await self.cog.horse_race_manager.place_multiple_bets(user_id, parsed_bets)
            
            if successful_bets:
                # Deduct currency for successful bets
                total_deducted = sum(bet['amount'] for bet in successful_bets)
                await self.cog.currency_manager.subtract_currency(user_id, total_deducted)
                
                # Create detailed response
                embed = discord.Embed(
                    title=f"✅ {BET_TYPES[self.bet_type]['name']} Bets Placed Successfully!",
                    color=0x00ff00
                )
                
                bet_summary = ""
                total_potential_winnings = 0
                horses = await self.cog.horse_race_manager.get_current_horses()
                
                for bet in successful_bets:
                    horse_name = HORSE_STATS[bet['horse_id'] - 1]['name']
                    horse_color = HORSE_STATS[bet['horse_id'] - 1]['color']
                    
                    # Calculate potential winnings
                    potential_winnings = self.cog.horse_race_manager.calculate_potential_winnings(
                        horses, bet['horse_id'], bet['amount'], bet['bet_type']
                    )
                    total_potential_winnings += potential_winnings
                    
                    bet_summary += f"• {horse_color} {horse_name}: ${bet['amount']:,.2f} → ${potential_winnings:,.2f}\n"
                
                embed.add_field(
                    name=f"🎯 {BET_TYPES[self.bet_type]['name']} Bets & Potential Winnings",
                    value=bet_summary,
                    inline=False
                )
                
                embed.add_field(
                    name="💰 Summary",
                    value=(
                        f"**Total Bet:** ${total_deducted:,.2f}\n"
                        f"**Max Potential:** ${total_potential_winnings:,.2f}\n"
                        f"**Bet Type:** {BET_TYPES[self.bet_type]['description']}"
                    ),
                    inline=True
                )
                
                new_balance = await self.cog.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="🏦 Balance",
                    value=f"${new_balance:,.2f} remaining",
                    inline=True
                )
                
                if failed_bets:
                    failed_summary = ""
                    for failed in failed_bets:
                        horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                        failed_summary += f"• {horse_name}: {failed['error']}\n"
                    
                    embed.add_field(
                        name="❌ Failed Bets",
                        value=failed_summary,
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                # All bets failed
                error_summary = f"❌ **All {BET_TYPES[self.bet_type]['name']} bets failed:**\n"
                for failed in failed_bets:
                    horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                    error_summary += f"• {horse_name}: {failed['error']}\n"
                
                await interaction.followup.send(error_summary, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error processing final {self.bet_type} bets: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error processing {BET_TYPES[self.bet_type]['name']} bets. Please try again!",
                ephemeral=True
            )
        
    async def _process_final_bets(self, interaction: discord.Interaction, parsed_bets: list, total_bet_amount: int):
        """Process the final bet submission"""
        user_id = str(interaction.user.id)
        
        try:
            # Check balance
            user_balance = await self.cog.currency_manager.get_balance(user_id)
            if user_balance < total_bet_amount:
                await interaction.response.send_message(
                    f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${total_bet_amount:,.2f}.",
                    ephemeral=True
                )
                return
            
            # Check betting conditions
            if not self.cog.horse_race_manager.is_betting_time():
                await interaction.response.send_message("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if self.cog.horse_race_manager.race_in_progress:
                await interaction.response.send_message("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Use batch betting functionality
            successful_bets, failed_bets = await self.cog.horse_race_manager.place_multiple_bets(user_id, parsed_bets)
            
            if successful_bets:
                # Deduct currency for successful bets
                total_deducted = sum(bet['amount'] for bet in successful_bets)
                await self.cog.currency_manager.subtract_currency(user_id, total_deducted)
                
                # Create detailed response
                embed = discord.Embed(
                    title=f"✅ {BET_TYPES[self.bet_type]['name']} Bets Placed Successfully!",
                    color=0x00ff00
                )
                
                bet_summary = ""
                total_potential_winnings = 0
                horses = await self.cog.horse_race_manager.get_current_horses()
                
                for bet in successful_bets:
                    horse_name = HORSE_STATS[bet['horse_id'] - 1]['name']
                    horse_color = HORSE_STATS[bet['horse_id'] - 1]['color']
                    
                    # Calculate potential winnings
                    potential_winnings = self.cog.horse_race_manager.calculate_potential_winnings(
                        horses, bet['horse_id'], bet['amount'], bet['bet_type']
                    )
                    total_potential_winnings += potential_winnings
                    
                    bet_summary += f"• {horse_color} {horse_name}: ${bet['amount']:,.2f} → ${potential_winnings:,.2f}\n"
                
                embed.add_field(
                    name=f"🎯 {BET_TYPES[self.bet_type]['name']} Bets & Potential Winnings",
                    value=bet_summary,
                    inline=False
                )
                
                embed.add_field(
                    name="💰 Summary",
                    value=(
                        f"**Total Bet:** ${total_deducted:,.2f}\n"
                        f"**Max Potential:** ${total_potential_winnings:,.2f}\n"
                        f"**Bet Type:** {BET_TYPES[self.bet_type]['description']}"
                    ),
                    inline=True
                )
                
                new_balance = await self.cog.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="🏦 Balance",
                    value=f"${new_balance:,.2f} remaining",
                    inline=True
                )
                
                if failed_bets:
                    failed_summary = ""
                    for failed in failed_bets:
                        horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                        failed_summary += f"• {horse_name}: {failed['error']}\n"
                    
                    embed.add_field(
                        name="❌ Failed Bets",
                        value=failed_summary,
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # All bets failed
                error_summary = f"❌ **All {BET_TYPES[self.bet_type]['name']} bets failed:**\n"
                for failed in failed_bets:
                    horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                    error_summary += f"• {horse_name}: {failed['error']}\n"
                
                await interaction.response.send_message(error_summary, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error processing final {self.bet_type} bets: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error processing {BET_TYPES[self.bet_type]['name']} bets. Please try again!",
                ephemeral=True
            )

class RemainingHorsesModal(discord.ui.Modal):
    """Modal for betting on remaining horses"""
    def __init__(self, cog, bet_type, existing_bets, existing_total, start_index):
        bet_config = BET_TYPES[bet_type]
        remaining_count = len(HORSE_STATS) - start_index
        super().__init__(title=f"🏇 {bet_config['name']} - Horses {start_index+1}-{len(HORSE_STATS)}", timeout=600)
        self.cog = cog
        self.bet_type = bet_type
        self.existing_bets = existing_bets
        self.existing_total = existing_total
        self.start_index = start_index
        
        # Add text inputs for remaining horses (up to 5)
        self.horse_inputs = []
        max_horses = min(5, remaining_count)
        
        for i in range(max_horses):
            horse_index = start_index + i
            horse_stat = HORSE_STATS[horse_index]
            horse_num = horse_index + 1
            
            input_field = discord.ui.TextInput(
                label=f"{horse_num}. {horse_stat['name']} {horse_stat['color']}",
                placeholder="Enter bet amount (e.g., 1000) or leave blank",
                required=False,
                max_length=10,
                style=discord.TextStyle.short
            )
            self.add_item(input_field)
            self.horse_inputs.append(input_field)
            
    async def on_submit(self, interaction: discord.Interaction):
        """Process remaining horses bet submission"""
        try:
            user_id = str(interaction.user.id)
            logger.info(f"Processing remaining {self.bet_type} bets for user {user_id}")
            
            # Parse new bet inputs
            new_bets = []
            new_total = 0
            parse_errors = []
            
            for i, input_field in enumerate(self.horse_inputs):
                if input_field.value.strip():
                    horse_index = self.start_index + i
                    horse_id = horse_index + 1
                    
                    try:
                        amount = int(input_field.value.strip())
                        if amount > 0:
                            new_bets.append({
                                'horse_id': horse_id,
                                'amount': amount,
                                'bet_type': self.bet_type
                            })
                            new_total += amount
                    except ValueError:
                        horse_name = HORSE_STATS[horse_index]['name']
                        parse_errors.append(f"{horse_name}: Invalid amount '{input_field.value}'. Please enter a valid number.")
            
            # Show parse errors if any
            if parse_errors:
                error_msg = "❌ **Input Errors:**\n" + "\n".join([f"• {error}" for error in parse_errors])
                if new_bets:
                    error_msg += f"\n\n✅ {len(new_bets)} valid new bets found."
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            # Combine with existing bets
            all_bets = self.existing_bets + new_bets
            total_amount = self.existing_total + new_total
            
            if not all_bets:
                await interaction.response.send_message(
                    f"❌ No {BET_TYPES[self.bet_type]['name']} bets configured!",
                    ephemeral=True
                )
                return
            
            # Process all bets
            await self._process_final_bets(interaction, all_bets, total_amount)
                
        except Exception as e:
            logger.error(f"Error in remaining horses {self.bet_type} modal: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error processing remaining {BET_TYPES[self.bet_type]['name']} bets. Please try again!",
                ephemeral=True
            )
            
    async def _process_final_bets(self, interaction: discord.Interaction, parsed_bets: list, total_bet_amount: int):
        """Process the final bet submission - same as in BetTypeModal"""
        user_id = str(interaction.user.id)
        
        try:
            # Check balance
            user_balance = await self.cog.currency_manager.get_balance(user_id)
            if user_balance < total_bet_amount:
                await interaction.response.send_message(
                    f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${total_bet_amount:,.2f}.",
                    ephemeral=True
                )
                return
            
            # Check betting conditions
            if not self.cog.horse_race_manager.is_betting_time():
                await interaction.response.send_message("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if self.cog.horse_race_manager.race_in_progress:
                await interaction.response.send_message("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Use batch betting functionality
            successful_bets, failed_bets = await self.cog.horse_race_manager.place_multiple_bets(user_id, parsed_bets)
            
            if successful_bets:
                # Deduct currency for successful bets
                total_deducted = sum(bet['amount'] for bet in successful_bets)
                await self.cog.currency_manager.subtract_currency(user_id, total_deducted)
                
                # Create detailed response
                embed = discord.Embed(
                    title=f"✅ {BET_TYPES[self.bet_type]['name']} Bets Placed Successfully!",
                    color=0x00ff00
                )
                
                bet_summary = ""
                total_potential_winnings = 0
                horses = await self.cog.horse_race_manager.get_current_horses()
                
                for bet in successful_bets:
                    horse_name = HORSE_STATS[bet['horse_id'] - 1]['name']
                    horse_color = HORSE_STATS[bet['horse_id'] - 1]['color']
                    
                    # Calculate potential winnings
                    potential_winnings = self.cog.horse_race_manager.calculate_potential_winnings(
                        horses, bet['horse_id'], bet['amount'], bet['bet_type']
                    )
                    total_potential_winnings += potential_winnings
                    
                    bet_summary += f"• {horse_color} {horse_name}: ${bet['amount']:,.2f} → ${potential_winnings:,.2f}\n"
                
                embed.add_field(
                    name=f"🎯 Complete {BET_TYPES[self.bet_type]['name']} Bets & Potential Winnings",
                    value=bet_summary,
                    inline=False
                )
                
                embed.add_field(
                    name="💰 Final Summary",
                    value=(
                        f"**Total Bet:** ${total_deducted:,.2f}\n"
                        f"**Max Potential:** ${total_potential_winnings:,.2f}\n"
                        f"**Bet Type:** {BET_TYPES[self.bet_type]['description']}"
                    ),
                    inline=True
                )
                
                new_balance = await self.cog.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="🏦 Balance",
                    value=f"${new_balance:,.2f} remaining",
                    inline=True
                )
                
                if failed_bets:
                    failed_summary = ""
                    for failed in failed_bets:
                        horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                        failed_summary += f"• {horse_name}: {failed['error']}\n"
                    
                    embed.add_field(
                        name="❌ Failed Bets",
                        value=failed_summary,
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # All bets failed
                error_summary = f"❌ **All {BET_TYPES[self.bet_type]['name']} bets failed:**\n"
                for failed in failed_bets:
                    horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                    error_summary += f"• {horse_name}: {failed['error']}\n"
                
                await interaction.response.send_message(error_summary, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error processing final {self.bet_type} bets: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error processing {BET_TYPES[self.bet_type]['name']} bets. Please try again!",
                ephemeral=True
            )

class ComprehensiveMultiBetModal(discord.ui.Modal):
    """Modal for betting on all horses with bet type selection"""
    def __init__(self, cog, start_index=0):
        super().__init__(title=f"🏇 Multi-Bet (Horses {start_index+1}-{min(start_index+5, len(HORSE_STATS))})", timeout=600)
        self.cog = cog
        self.start_index = start_index
        
        # Add inputs for up to 5 horses starting from start_index
        self.horse_inputs = []
        end_index = min(start_index + 5, len(HORSE_STATS))
        
        for i in range(start_index, end_index):
            horse_stat = HORSE_STATS[i]
            horse_num = i + 1
            
            input_field = discord.ui.TextInput(
                label=f"{horse_num}. {horse_stat['name']} {horse_stat['color']}",
                placeholder="Format: amount,bet_type (e.g., 1000,win or 500,place)",
                required=False,
                max_length=20,
                style=discord.TextStyle.short
            )
            self.add_item(input_field)
            self.horse_inputs.append(input_field)
            
    async def on_submit(self, interaction: discord.Interaction):
        """Process comprehensive multi-bet submission"""
        try:
            user_id = str(interaction.user.id)
            logger.info(f"Processing comprehensive multi-bet for user {user_id}")
            
            # Parse all bet inputs
            parsed_bets = []
            total_bet_amount = 0
            parse_errors = []
            
            for i, input_field in enumerate(self.horse_inputs):
                if input_field.value.strip():
                    horse_index = self.start_index + i
                    horse_id = horse_index + 1
                    
                    try:
                        # Parse input format: "amount,bet_type" or just "amount" (defaults to win)
                        parts = input_field.value.strip().split(',')
                        amount = int(parts[0].strip())
                        bet_type = parts[1].strip().lower() if len(parts) > 1 else 'win'
                        
                        # Validate bet type
                        if bet_type not in BET_TYPES:
                            parse_errors.append(f"{await self.bot.horse_nickname_manager.get_horse_display_name(horse_index)}: Invalid bet type '{bet_type}'. Use: win, place, show, last")
                            continue
                            
                        if amount > 0:
                            parsed_bets.append({
                                'horse_id': horse_id,
                                'amount': amount,
                                'bet_type': bet_type
                            })
                            total_bet_amount += amount
                            
                    except (ValueError, IndexError):
                        horse_name = HORSE_STATS[horse_index]['name']
                        parse_errors.append(f"{horse_name}: Invalid format. Use 'amount,bet_type' (e.g., 1000,win)")
            
            # Show parse errors if any
            if parse_errors:
                error_msg = "❌ **Input Format Errors:**\n" + "\n".join([f"• {error}" for error in parse_errors])
                if parsed_bets:
                    error_msg += f"\n\n✅ Successfully parsed {len(parsed_bets)} valid bets."
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            if not parsed_bets:
                await interaction.response.send_message(
                    "❌ No valid bets found. Format: `amount,bet_type` (e.g., `1000,win` or `500,place`)",
                    ephemeral=True
                )
                return
            
            # Check total balance
            user_balance = await self.cog.currency_manager.get_balance(user_id)
            if user_balance < total_bet_amount:
                await interaction.response.send_message(
                    f"❌ Insufficient funds! You have ${user_balance:,.2f}, need ${total_bet_amount:,.2f}.",
                    ephemeral=True
                )
                return
            
            # Check betting conditions
            if not self.cog.horse_race_manager.is_betting_time():
                await interaction.response.send_message("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if self.cog.horse_race_manager.race_in_progress:
                await interaction.response.send_message("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Use batch betting functionality
            successful_bets, failed_bets = await self.cog.horse_race_manager.place_multiple_bets(user_id, parsed_bets)
            
            if successful_bets:
                # Deduct currency for successful bets
                total_deducted = sum(bet['amount'] for bet in successful_bets)
                await self.cog.currency_manager.subtract_currency(user_id, total_deducted)
                
                # Create detailed response with potential winnings
                embed = discord.Embed(
                    title="✅ Comprehensive Multi-Bet Placed!",
                    color=0x00ff00
                )
                
                bet_summary = ""
                total_potential_winnings = 0
                horses = await self.cog.horse_race_manager.get_current_horses()
                
                for bet in successful_bets:
                    horse_name = HORSE_STATS[bet['horse_id'] - 1]['name']
                    horse_color = HORSE_STATS[bet['horse_id'] - 1]['color']
                    bet_type_name = BET_TYPES[bet['bet_type']]['name']
                    
                    # Calculate potential winnings
                    potential_winnings = self.cog.horse_race_manager.calculate_potential_winnings(
                        horses, bet['horse_id'], bet['amount'], bet['bet_type']
                    )
                    total_potential_winnings += potential_winnings
                    
                    bet_summary += f"• {horse_color} {horse_name}: ${bet['amount']:,.2f} ({bet_type_name}) → ${potential_winnings:,.2f}\n"
                
                embed.add_field(
                    name="🎯 Successful Bets & Potential Winnings",
                    value=bet_summary,
                    inline=False
                )
                
                embed.add_field(
                    name="💰 Bet Summary",
                    value=f"Total Bet: ${total_deducted:,.2f}\nMax Potential: ${total_potential_winnings:,.2f}",
                    inline=True
                )
                
                new_balance = await self.cog.currency_manager.get_balance(user_id)
                embed.add_field(
                    name="🏦 Balance",
                    value=f"${new_balance:,.2f} remaining",
                    inline=True
                )
                
                if failed_bets:
                    failed_summary = ""
                    for failed in failed_bets:
                        horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                        failed_summary += f"• {horse_name}: {failed['error']}\n"
                    
                    embed.add_field(
                        name="❌ Failed Bets",
                        value=failed_summary,
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # All bets failed
                error_summary = "❌ **All bets failed:**\n"
                for failed in failed_bets:
                    horse_name = HORSE_STATS[failed['bet']['horse_id'] - 1]['name']
                    error_summary += f"• {horse_name}: {failed['error']}\n"
                
                await interaction.response.send_message(error_summary, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in comprehensive multi-bet: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Error processing comprehensive multi-bet. Please try again!",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Error processing comprehensive multi-bet. Please try again!",
                        ephemeral=True
                    )
            except Exception as error_response_error:
                logger.error(f"Failed to send error response: {error_response_error}")

class HorseRacingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.horse_race_manager = HorseRaceManager(bot.horse_nickname_manager)
        self.currency_manager = bot.currency_manager
        
        # Race state
        self.current_race_message = None
        self.race_start_time = None
        self.race_starting = False  # Flag to prevent race condition during start
        
    async def _validate_channel_config(self):
        """Validate that the horse race channel is properly configured"""
        if not HORSE_RACE_CHANNEL_ID:
            logger.error("HORSE_RACE_CHANNEL_ID is not set in environment variables!")
            return
            
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            logger.error(f"Could not find guild with ID {GUILD_ID}")
            return
            
        channel = guild.get_channel(HORSE_RACE_CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {HORSE_RACE_CHANNEL_ID} in guild {guild.name}")
            return
            
        logger.info(f"Horse race channel validated: #{channel.name} ({channel.id}) in {guild.name}")
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        await self.horse_race_manager.initialize()
        await self._validate_channel_config()
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
            logger.debug("Running race schedule check...")
            
            if self.horse_race_manager.race_in_progress or self.race_starting:
                logger.debug("Race already in progress or starting, skipping schedule check")
                return  # Skip check if race already in progress or starting
                
            now = datetime.now()
            logger.debug(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} (weekday: {now.weekday()})")
            
            # Check all scheduled race times
            for race_config in HORSE_RACE_SCHEDULE:
                race_day = race_config["day"]
                race_hour = race_config["hour"]
                race_minute = race_config["minute"]
                
                # Calculate the race time for today
                today_race_time = now.replace(hour=race_hour, minute=race_minute, second=0, microsecond=0)
                time_diff = (now - today_race_time).total_seconds()
                
                logger.debug(f"Checking race config: day {race_day}, {race_hour:02d}:{race_minute:02d}")
                logger.debug(f"Today is weekday {now.weekday()}, race is on weekday {race_day}")
                logger.debug(f"Time difference: {time_diff:.1f} seconds")
                
                # Check if today matches the race day and it's time for the race
                # Allow a 5-minute window after scheduled time only to prevent multiple triggers
                if (now.weekday() == race_day and 
                    0 <= time_diff <= 300 and  # 0 to 5 minutes after scheduled time
                    self.horse_race_manager.should_start_race_now(today_race_time)):  # Check for duplicates
                    
                    # Find the general channel to announce the race
                    guild = self.bot.get_guild(GUILD_ID)
                    if guild and HORSE_RACE_CHANNEL_ID:
                        # Get the actual channel object from the channel ID
                        channel = guild.get_channel(HORSE_RACE_CHANNEL_ID)
                        
                        if channel:
                            logger.info(f"Starting scheduled race in channel: {channel.name} ({channel.id})")
                            self.race_starting = True  # Set flag immediately to prevent race condition
                            try:
                                await self.start_scheduled_race(channel)
                            finally:
                                self.race_starting = False  # Clear flag after race start attempt
                            return  # Start only one race at a time
                        else:
                            logger.error(f"Could not find channel with ID {HORSE_RACE_CHANNEL_ID}")
                    else:
                        logger.error("Guild not found or HORSE_RACE_CHANNEL_ID not set")
                        
        except Exception as e:
            logger.error(f"Error in race schedule check: {e}", exc_info=True)
            
    @check_race_schedule.before_loop
    async def before_check_race_schedule(self):
        """Wait for bot to be ready before starting the schedule loop"""
        await self.bot.wait_until_ready()

    @app_commands.command(name="horserace_info", description="Show horse race information and current bets")
    @app_commands.describe(
        display_type="Choose what to display"
    )
    @app_commands.choices(display_type=[
        app_commands.Choice(name="Horse Stats & Odds", value="stats"),
        app_commands.Choice(name="Current Bets", value="bets")
    ])
    async def horserace_info(self, interaction: discord.Interaction, display_type: str):
        await self.show_race_info(interaction, display_type)
        
    @app_commands.command(name="horserace_bet", description="Place a bet on a horse")
    @app_commands.describe(
        amount="Amount to bet"
    )
    async def horserace_bet(self, interaction: discord.Interaction, amount: int):
        await self.show_horse_selection(interaction, amount)
        
    @app_commands.command(name="horserace_multibet", description="Place multiple bets quickly with enhanced interface")
    async def horserace_multibet(self, interaction: discord.Interaction):
        await self.show_multibet_interface(interaction)
        
    @app_commands.command(name="horserace_start", description="Start a horse race manually (admin only, if enabled)")
    async def horserace_start(self, interaction: discord.Interaction):
        await self.manual_start_race(interaction)
        
    @app_commands.command(name="horserace_schedule", description="Show the schedule for the next 3 horse races")
    async def horserace_schedule(self, interaction: discord.Interaction):
        await self.show_race_schedule(interaction)
        
    @app_commands.command(name="horserace_debug", description="Show debug info for race scheduling (admin only)")
    async def horserace_debug(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can use this command!", ephemeral=True)
            return
            
        await self.show_debug_info(interaction)
    
    async def show_debug_info(self, interaction: discord.Interaction):
        """Show debug information about race scheduling"""
        try:
            now = datetime.now()
            next_race = self.horse_race_manager.get_next_race_time()
            time_until_race = (next_race - now).total_seconds()
            
            embed = discord.Embed(
                title="🔍 Horse Race Debug Info",
                description="Debug information for race scheduling",
                color=0xff9900
            )
            
            # Current time and status
            embed.add_field(
                name="Current Status",
                value=f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                      f"Current weekday: {now.weekday()} ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][now.weekday()]})\n"
                      f"Race in progress: {self.horse_race_manager.race_in_progress}\n"
                      f"Channel ID: {HORSE_RACE_CHANNEL_ID}",
                inline=False
            )
            
            # Next race info
            embed.add_field(
                name="Next Race",
                value=f"Scheduled: {next_race.strftime('%Y-%m-%d %H:%M:%S')}\n"
                      f"Time until: {time_until_race/3600:.1f} hours\n"
                      f"Betting open: {self.horse_race_manager.is_betting_time()}",
                inline=False
            )
            
            # Schedule configuration
            schedule_text = ""
            for i, race_config in enumerate(HORSE_RACE_SCHEDULE):
                day_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][race_config['day']]
                schedule_text += f"{i+1}. {day_name} {race_config['hour']:02d}:{race_config['minute']:02d}\n"
            
            embed.add_field(
                name="Race Schedule",
                value=schedule_text,
                inline=False
            )
            
            # Channel validation
            guild = self.bot.get_guild(GUILD_ID)
            if guild and HORSE_RACE_CHANNEL_ID:
                channel = guild.get_channel(HORSE_RACE_CHANNEL_ID)
                channel_status = f"✅ #{channel.name}" if channel else "❌ Channel not found"
            else:
                channel_status = "❌ Guild or channel ID not configured"
                
            embed.add_field(
                name="Channel Status",
                value=channel_status,
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error showing debug info: {e}")
            await interaction.response.send_message("❌ Error retrieving debug info!", ephemeral=True)
            
    async def show_race_info(self, interaction: discord.Interaction, display_type: str):
        """Show current race information, betting odds, and all open bets"""
        try:
            horses = await self.horse_race_manager.get_current_horses()
            embed = self.horse_race_manager.create_betting_embed(horses, self.bot, display_type)
            
            if self.horse_race_manager.race_in_progress:
                # Create new embed for race in progress
                embed = discord.Embed(
                    title="🏇 Horse Racing - Race in Progress! 🏇",
                    description="🏁 Race in progress! Betting is closed.",
                    color=0xff9900,
                    timestamp=embed.timestamp
                )
                # Copy original embed fields
                original_embed = self.horse_race_manager.create_betting_embed(horses, self.bot, display_type)
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
                original_embed = self.horse_race_manager.create_betting_embed(horses, self.bot, display_type)
                for field in original_embed.fields:
                    embed.add_field(name=field.name, value=field.value, inline=field.inline)
                
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
            horse_name = await self.bot.horse_nickname_manager.get_horse_display_name(horse_id - 1)
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
            horse_name = await self.bot.horse_nickname_manager.get_horse_display_name(horse_id - 1)
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
                horse_name = await self.bot.horse_nickname_manager.get_horse_display_name(bet["horse_id"] - 1)
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
            
    async def start_race_in_channel(self, channel):
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
                horse_color = HORSE_STATS[result["horse_id"] - 1]["color"]
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
            
    async def show_multibet_interface(self, interaction: discord.Interaction):
        """Show the clean multi-betting interface"""
        user_id = str(interaction.user.id)
        
        try:
            logger.info(f"Showing clean multi-bet interface for user {user_id}")
            
            # Check betting conditions first
            if not self.horse_race_manager.is_betting_time():
                await interaction.response.send_message("❌ Betting is not currently open!", ephemeral=True)
                return
                
            if self.horse_race_manager.race_in_progress:
                await interaction.response.send_message("❌ Race is in progress, betting is closed!", ephemeral=True)
                return
            
            # Get user balance for display
            user_balance = await self.currency_manager.get_balance(user_id)
            
            # Create main embed
            embed = discord.Embed(
                title="🏇 Multi-Bet Interface 🏇",
                description=(
                    "**Select a bet type to place multiple bets:**\n\n"
                    "Each bet type opens a form where you can enter amounts for all horses at once.\n"
                    "Simply click the bet type you want and fill in amounts for your chosen horses."
                ),
                color=0x0099ff
            )
            
            # Show current balance
            embed.add_field(
                name="💰 Your Balance",
                value=f"${user_balance:,.2f}",
                inline=True
            )
            
            # Show betting window info
            next_race = self.horse_race_manager.get_next_race_time()
            embed.add_field(
                name="⏰ Next Race",
                value=f"<t:{int(next_race.timestamp())}:R>",
                inline=True
            )
            
            # Show bet type descriptions with odds
            bet_info = ""
            horses = await self.horse_race_manager.get_current_horses()
            
            for bet_type, config in BET_TYPES.items():
                odds = self.horse_race_manager.calculate_payout_odds(horses, bet_type)
                avg_odds = sum(odds.values()) / len(odds)
                bet_info += f"**{config['name']}**: {config['description']} (Avg: {avg_odds:.1f}x)\n"
            
            embed.add_field(
                name="🎯 Available Bet Types",
                value=bet_info,
                inline=False
            )
            
            # Show all horses summary
            horses_summary = ""
            win_odds = self.horse_race_manager.calculate_payout_odds(horses, "win")
            
            for i, horse_stat in enumerate(HORSE_STATS, 1):
                horses_summary += f"{horse_stat['color']} **{i}. {horse_stat['name']}** ({win_odds[i]:.1f}x)\n"
            
            embed.add_field(
                name="🐎 All Horses & Win Odds",
                value=horses_summary,
                inline=False
            )
            
            # Add usage instructions
            embed.add_field(
                name="📝 How to Use",
                value=(
                    "1. Click a bet type button below\n"
                    "2. Enter bet amounts for desired horses\n"
                    "3. Submit or continue to more horses\n"
                    "4. Review and confirm your bets"
                ),
                inline=False
            )
            
            # Create the clean view with 4 bet type buttons
            view = CleanMultiBetView(self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"Clean multi-bet interface displayed successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error showing clean multi-bet interface for user {user_id}: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Error showing multi-bet interface. Please try again!", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Error showing multi-bet interface. Please try again!", ephemeral=True
                    )
            except Exception as error_response_error:
                logger.error(f"Failed to send error response to user {user_id}: {error_response_error}")

async def setup(bot):
    """Setup function to load the cog"""
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(HorseRacingCog(bot), guild=guild_id)