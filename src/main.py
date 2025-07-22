import os
import logging
import sys

from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord import app_commands

from src.utils.logging import setup_logging
from src.config.settings import GUILD_ID
from src.utils.permission_store import PermissionManager

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

class MyClient(commands.Bot):

    def __init__(self) -> None:
        # set the bot intents
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix='!', intents=intents)

        self.guild = discord.Object(id=GUILD_ID)

        # set the permissions
        self.ps = PermissionManager()

        # override the self.tree.interaction_check method
        self.tree.interaction_check = self.interaction_check

    async def on_ready(self):
        logger.info(f"{self.user} ready for commands")

        # Automatically discover all cog modules in src/cogs/ folder
        cogs_dir = os.path.join(os.path.dirname(__file__), 'cogs')
        extensions = []
        
        for filename in os.listdir(cogs_dir):
            if filename.endswith('.py') and filename != '__init__.py':
                module_name = filename[:-3]  # Remove .py extension
                extensions.append(f'src.cogs.{module_name}')
        
        logger.info(f"Discovered extensions: {extensions}")

        for extension in extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")

        try:
            synced = await self.tree.sync(guild=self.guild)
            logger.info(f"Synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")

    async def on_connect(self):
        logger.info(f"{self.user} connected to discord successfully")

    async def on_disconnect(self):
        logger.info(f"{self.user} disconnected from discord")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Global interaction check to ensure only authorized users can use the bot"""
        logger.info(f"{interaction.user} ({interaction.user.id}) tried to use a command")
        if interaction.user.id in self.ps.restricted_members:
            await interaction.response.send_message("You are still in timeout")
            return False
        else:
            return True

    @staticmethod
    async def on_app_command_completion(interaction: discord.Interaction,command):
        logger.info(f"{interaction.user} ({interaction.user.id}) used command:  /{command.name}")

    async def on_message(self, message):
        if message.author == self.user:
            return
        else:
            return



def main():
    # pass bot token to Client
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logging.error("No bot token found in environment variables")
        sys.exit(1)
    client = MyClient()
    client.run(bot_token)

if __name__ == "__main__":
    main()
