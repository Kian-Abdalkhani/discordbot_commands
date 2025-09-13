import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.config.settings import GUILD_ID, ADMIN_GIVE_MONEY_MAX_AMOUNT, ADMIN_GIVE_MONEY_REASON_MAX_LENGTH

logger = logging.getLogger(__name__)

class Permissions(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.pm = bot.pm

    @app_commands.command(name="timeout", description="Put a discord user in timeout")
    @app_commands.describe(
        member="The member to put in timeout",
        hours="Optional: Number of hours for timeout (leave empty for indefinite)"
    )
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, hours: float = None):
        # Load player permissions before running command
        await self.pm.load_permissions()
        if interaction.user.id not in self.pm.admins:
            await interaction.response.send_message("Only server administrators can use this command.")
            return
        
        # Check if user is already restricted using the new method
        if await self.pm.is_user_restricted(member.id):
            await interaction.response.send_message(f"{member.mention} is already in timeout.")
            return
        
        # Validate hours parameter
        if hours is not None and hours <= 0:
            await interaction.response.send_message("Hours must be a positive number.")
            return
        
        # Add timeout using the new method
        await self.pm.add_timeout(member.id, hours)
        
        if hours is None:
            await interaction.response.send_message(f"{member.mention} has been put in an indefinite timeout.")
        else:
            await interaction.response.send_message(f"{member.mention} has been put in timeout for {hours} hours.")

    @app_commands.command(name="end_timeout", description="Let user out of timeout")
    @app_commands.describe(member="The member to let out of timeout")
    async def end_timeout(self, interaction: discord.Interaction, member: discord.Member):
        # Load player permissions before running command
        await self.pm.load_permissions()
        if interaction.user.id not in self.pm.admins:
            await interaction.response.send_message("Only server administrators can use this command.")
            return
        
        # Check if user is restricted and remove using new method
        if not await self.pm.is_user_restricted(member.id):
            await interaction.response.send_message(f"{member.mention} is not in timeout.")
            return
        
        success = await self.pm.remove_timeout(member.id)
        if success:
            await interaction.response.send_message(f"{member.mention} has been let out of timeout.")
        else:
            await interaction.response.send_message(f"Failed to remove timeout for {member.mention}.")

    @app_commands.command(name="give_money", description="Give money to a user (admin compensation only)")
    @app_commands.describe(
        member="The member to give money to",
        amount="Amount of money to give (positive number)",
        reason="Required explanation for why money is being given"
    )
    async def give_money(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str):
        # Load player permissions before running command
        await self.pm.load_permissions()
        if interaction.user.id not in self.pm.admins:
            await interaction.response.send_message("Only server administrators can use this command.")
            return
        
        # Validate amount is positive
        if amount <= 0:
            await interaction.response.send_message("Amount must be a positive number.")
            return
        
        # Validate amount doesn't exceed maximum limit
        if amount > ADMIN_GIVE_MONEY_MAX_AMOUNT:
            await interaction.response.send_message(f"Amount cannot exceed ${ADMIN_GIVE_MONEY_MAX_AMOUNT:,}.")
            return
        
        # Prevent self-transfers
        if member.id == interaction.user.id:
            await interaction.response.send_message("You cannot give money to yourself.")
            return
        
        # Validate reason is provided and not empty
        if not reason or len(reason.strip()) == 0:
            await interaction.response.send_message("A reason must be provided for giving money.")
            return
        
        reason = reason.strip()
        
        # Validate reason length
        if len(reason) > ADMIN_GIVE_MONEY_REASON_MAX_LENGTH:
            await interaction.response.send_message(f"Reason must be {ADMIN_GIVE_MONEY_REASON_MAX_LENGTH} characters or less.")
            return
        
        try:
            # Give money to the user using currency manager
            admin_user = interaction.user
            new_balance = await self.bot.currency_manager.add_currency(
                user_id=str(member.id),
                amount=amount,
                command="admin_give_money",
                metadata={
                    "admin_id": str(admin_user.id),
                    "admin_name": admin_user.display_name,
                    "reason": reason,
                    "recipient_id": str(member.id),
                    "recipient_name": member.display_name
                },
                transaction_type="currency",
                display_name=member.display_name,
                mention=member.mention
            )
            
            # Log the admin action
            logger.info(f"Admin {admin_user.display_name} ({admin_user.id}) gave ${amount:,} to {member.display_name} ({member.id}). Reason: {reason}")
            
            await interaction.response.send_message(
                f"Successfully gave ${amount:,} to {member.mention}.\n"
                f"**Reason:** {reason}\n"
                f"Their new balance is ${new_balance:,.2f}."
            )
            
        except ValueError as e:
            logger.error(f"Value error in give_money command: {e}")
            await interaction.response.send_message("Invalid input provided. Please check your parameters.")
        except KeyError as e:
            logger.error(f"Key error in give_money command: {e}")
            await interaction.response.send_message("User data error. Please try again.")
        except Exception as e:
            logger.error(f"Unexpected error in give_money command: {e}")
            await interaction.response.send_message("An unexpected error occurred. Please try again.")
    

async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(Permissions(bot), guild=guild_id)