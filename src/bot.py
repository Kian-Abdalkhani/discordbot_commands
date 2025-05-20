import discord
from discord.ext import commands
from bot_llm import bot_response
import logging


logger = logging.getLogger(__name__)


def create_bot():

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"{bot.user} ready for commands")

    @bot.event
    async def on_connect():
        logger.info(f"{bot.user} connected to discord successfully")

    @bot.event
    async def on_disconnect():
        logger.info(f"{bot.user} disconnected from discord")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        if bot.user.mentioned_in(message):
            logger.info(f"{message.author} mentioned bot in {message.channel}")
            response = bot_response(prompt=message.content)
            await message.channel.send(response)

        await bot.process_commands(message)

    return bot