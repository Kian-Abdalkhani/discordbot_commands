import os
import json
import logging
from discord.ext import commands
from discord import app_commands
import discord

from src.config.settings import GUILD_ID
from src.utils.permission_store import PermissionManager

logger = logging.getLogger(__name__)

class Permissions(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.ps = bot.ps

    @app_commands.command(name="timeout", description="Put a discord user in timeout")
    @app_commands.describe(member="The member to put in timeout")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id not in self.ps.admins:
            await interaction.response.send_message("Only server administrators can use this command.")
            return
        if member.id in self.ps.restricted_members:
            await interaction.response.send_message(f"{member.mention} is already in timeout.")
            return
        self.ps.restricted_members.append(member.id)
        self.ps.save_permissions()
        await interaction.response.send_message(f"{member.mention} has been put in timeout.")

    @app_commands.command(name="end_timeout", description="Let user out of timeout")
    @app_commands.describe(member="The member to let out of timeout")
    async def end_timeout(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id not in self.ps.admins:
            await interaction.response.send_message("Only server administrators can use this command.")
            return
        if member.id not in self.ps.restricted_members:
            await interaction.response.send_message(f"{member.mention} is not in timeout.")
            return
        self.ps.restricted_members.remove(member.id)
        self.ps.save_permissions()
        await interaction.response.send_message(f"{member.mention} has been let out of timeout.")

async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(Permissions(bot), guild=guild_id)