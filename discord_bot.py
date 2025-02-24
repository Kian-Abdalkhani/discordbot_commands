import discord
import os
from dotenv import load_dotenv
import json

from bot_llm import bot_response

load_dotenv()

#include a json string of close members in your discord for bot to recall
dict_string: str = os.environ.get("CORD_MEMBERS")
close_members: dict = json.loads(dict_string)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message):
    # if message is from boug bot
    if message.author == client.user:
        return

        # if user @'s boug bot
    if client.user.mentioned_in(message):  # type: ignore
        member_name = close_members.get(str(message.author))

        # if user is in boug bot's database
        if type(member_name) == str:
            await message.channel.send(bot_response(prompt=f"{member_name}:{message.content}"))

        else:
            await message.channel.send(bot_response(prompt=message.content))


client.run(token=os.getenv("BOT_TOKEN"))  # type: ignore