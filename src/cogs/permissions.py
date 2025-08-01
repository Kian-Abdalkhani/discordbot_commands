import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.config.settings import GUILD_ID

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
    

async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(Permissions(bot), guild=guild_id)