import os
import logging
import sys

from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord import app_commands

from src.utils.logging import setup_logging
from src.config.settings import GUILD_ID

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

class Client(commands.Bot):

    async def on_ready(self):
        logger.info(f"{self.user} ready for commands")

        # sync the app commands to discord
        try:
            guild = discord.Object(id=GUILD_ID)
            await self.load_extension('src.cogs.utilities')
            await self.load_extension('src.cogs.quotes')
            await self.load_extension('src.cogs.games')
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

        # Note: This functionality requires message_content intent to work properly
        # For now, we only respond to mentions which should work without the intent
        if self.user.mentioned_in(message):
            await message.channel.send(f"Hello {message.author.mention}, I am the server's minigame bot!")
            return

        # Traditional command processing - requires message_content intent
        # Since we primarily use slash commands, this is optional
        await self.process_commands(message)



intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix="!", intents=intents)

def main():
    # pass bot token to Client
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logging.error("No bot token found in environment variables")
        sys.exit(1)
    client.run(bot_token)

if __name__ == "__main__":
    main()
