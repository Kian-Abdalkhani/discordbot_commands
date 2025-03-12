from typing import Dict, Optional
import discord
import os
from dotenv import load_dotenv
import json

from bot_llm import bot_response

class DiscordBot:
    """Discord bot that responds when mentioned by user."""

    def __init__(self):
        """Initialize the Discord bot with configuration from environment variables."""
        load_dotenv()

        self.close_members = self.load_members()

        self.intents = discord.Intents.default()
        self.client = discord.Client(intents=self.intents)

        self.client.event(self.on_ready)
        self.client.event(self.on_message)

    def load_members(self) -> Dict[str,str]:
        """Load member information from environment variables

        Returns:
            Dict Mapping member IDs to names

        Raises:
            json.JSONDecodeError: If the JSON string is malformed
        """
        dict_string: str = os.environ.get("CORD_MEMBERS")
        return json.loads(dict_string)

    async def on_ready(self):
        """Event handler for when bot has connected to Discord."""
        print(f'We have logged in as {self.client.user}')

    async def on_message(self,message: discord.Message):
        """Event handler for when a message is received.
        Args:
            message: The Discord message object
        """
        #only respond when mentioned
        if self.client.user.mentioned_in(message):
            await self.process_mention(message)

    async def process_mention(self,message: discord.Message):
        """Process a message where the bot was mentioned
        Args:
            message: The Discord message object
        """
        member_id = str(message.author.id)
        member_name = self.get_member_name(member_id)

        if member_name in self.close_members:
            prompt = f"{member_name}:{message.content}"
        else:
            prompt = message.content

        response = self.generate_response(prompt)
        await message.channel.send(response)

    def get_member_name(self, member_id: str) -> Optional[str]:
        """Get a member's name from the database.

                Args:
                    member_id: The Discord member ID.

                Returns:
                    The member's name or None if not found.
                """
        member_name = self.close_members.get(member_id)
        return member_name if isinstance(member_name, str) else None

    def generate_response(self, prompt: str) -> str:
        """Generate a response using the bot_llm module.

                Args:
                    prompt: The prompt to send to the LLM.

                Returns:
                    The generated response.
                """
        return bot_response(prompt=prompt)

    def run(self):
        """Run the Discord bot."""
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError("BOT_TOKEN environment variable not set")
        self.client.run(token=token)


def main():
    """Main entry point for the bot."""
    bot = DiscordBot()
    bot.run()

if __name__ == "__main__":
    main()