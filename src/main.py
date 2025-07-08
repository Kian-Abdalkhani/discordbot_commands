import os
import logging
import sys

from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord import app_commands

from utils.logging import setup_logging
from config.settings import GUILD_ID

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

class Client(commands.Bot):

    async def on_ready(self):
        logger.info(f"{self.user} ready for commands")

        # sync the app commands to discord
        try:
            guild = discord.Object(id=GUILD_ID)
            await self.load_extension('cogs.utilities')
            await self.load_extension('cogs.quotes')
            await self.load_extension('cogs.games')
            synced = await self.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")

    async def on_connect(self):
        logger.info(f"{self.user} connected to discord successfully")

    async def on_disconnect(self):
        logger.info(f"{self.user} disconnected from discord")

    async def on_message(self, message):
        if message.author == self.user:
            return
        if self.user.mentioned_in(message):
            await message.channel.send(f"Hello {message.author.mention}, I am the server's minigame bot!")
            return

        await self.process_commands(message)



intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = Client(command_prefix="!", intents=intents)

# pass bot token to Client
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    logging.error("No bot token found in environment variables")
    sys.exit(1)
client.run(bot_token)
