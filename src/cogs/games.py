import random
import asyncio
import discord
import json
import os
from discord.ext import commands
from discord import app_commands
import logging

from src.config.settings import GUILD_ID

logger = logging.getLogger(__name__)


class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Flips a coin and returns heads or tails")
    async def flip_coin(self, interaction: discord.Interaction):
        """Flips a coin and returns heads or tails"""
        logger.info(f"{interaction.user} flipped a coin")
        coin = random.choice(["heads", "tails"])
        await interaction.response.send_message(coin)



async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(GamesCog(bot), guild=guild_id)
