from discord.ext import commands
from discord import app_commands
import logging
import random
import json
import os
import discord

from config.settings import GUILD_ID

logger = logging.getLogger(__name__)


class QuotesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quotes = {}
        self.quote_counter = 0
        self.quotes_file = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "quotes.json")
        self._load_quotes()

    def _load_quotes(self):
        """Load quotes from file if it exists"""
        try:
            if os.path.exists(self.quotes_file):
                with open(self.quotes_file, 'r') as f:
                    data = json.load(f)
                    self.quotes = data.get('quotes', {})
                    self.quote_counter = data.get('counter', 0)
                logger.info(f"Loaded {len(self.quotes)} quotes from {self.quotes_file}")
            else:
                logger.info(f"No quotes file found at {self.quotes_file}")
        except Exception as e:
            logger.error(f"Error loading quotes: {e}")

    def _save_quotes(self):
        """Save quotes to file"""
        try:
            with open(self.quotes_file, 'w') as f:
                json.dump({
                    'quotes': self.quotes,
                    'counter': self.quote_counter
                }, f, indent=2)
            logger.info(f"Saved {len(self.quotes)} quotes to {self.quotes_file}")
        except Exception as e:
            logger.error(f"Error saving quotes: {e}")

    @app_commands.command(name="quote_add", description="Add a new quote to the collection")
    @app_commands.describe(quote_text="The quote itself", quote_author="The author of the quote")
    async def add_quote(self, interaction: discord.Interaction, quote_text: str, quote_author: str):
        """
        Add a new quote to the collection
        Usage: /addquote <quote text> - <author>
        Example: /addquote That's what she said - Michael Scott
        """

        # Increment counter and add the quote
        self.quote_counter += 1
        quote_id = str(self.quote_counter)

        self.quotes[quote_id] = {
            "text": quote_text.strip(),
            "author": quote_author.strip(),
            "added_by": str(interaction.user),
            "added_at": interaction.created_at.isoformat()
        }

        self._save_quotes()

        logger.info(f"{interaction.user} added quote #{quote_id}: '{quote_text}' by {quote_author}")
        await interaction.response.send_message(f"Quote #{quote_id} added successfully!")

    @app_commands.command(name="find_quote", description="Display a quote by ID or a random quote")
    @app_commands.describe(quote_id="The ID of the quote to display (optional)")
    async def quote(self, interaction: discord.Interaction, quote_id: int = None):
        """
        Display a quote by ID or a random quote if no ID is provided
        Usage: /quote [quote_id]
        Example: /quote 42
        """
        if not self.quotes:
            await interaction.response.send_message("No quotes have been added yet.")
            return

        if quote_id is None:
            # Get a random quote
            quote_id = random.choice(list(self.quotes.keys()))

        if quote_id in self.quotes:
            quote = self.quotes[quote_id]
            embed = discord.Embed(
                title=f"Quote #{quote_id}",
                description=f"\"{quote['text']}\"",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"- {quote['author']}")

            logger.info(f"{interaction.user} requested quote #{quote_id}")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"Quote #{quote_id} not found.")

    @app_commands.command(name="quotes_all", description="List all available quotes")
    async def list_quotes(self, interaction: discord.Interaction):
        """
        List all available quotes
        Usage: /listquotes
        """
        if not self.quotes:
            await interaction.response.send_message("No quotes have been added yet.")
            return

        # Create an embed with the list of quotes
        embed = discord.Embed(
            title="Available Quotes",
            color=discord.Color.green()
        )

        # Add quotes to the embed (limit to 25 to avoid hitting Discord's limits)
        quotes_list = list(self.quotes.items())
        for i, (quote_id, quote) in enumerate(quotes_list[:25]):
            embed.add_field(
                name=f"Quote #{quote_id}",
                value=f"\"{quote['text'][:50]}{'...' if len(quote['text']) > 50 else ''}\" - {quote['author']}",
                inline=False
            )

        # Add a note if there are more quotes
        if len(quotes_list) > 25:
            embed.set_footer(text=f"Showing 25/{len(quotes_list)} quotes. Use /quote <id> to see a specific quote.")

        logger.info(f"{interaction.user} requested the list of quotes")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quotes_by", description="Display all quotes by a specific author")
    @app_commands.describe(author="The author whose quotes to display")
    async def quotes_by(self, interaction: discord.Interaction, *, author: str):
        """
        Display all quotes by a specific author
        Usage: /quotesby <author>
        Example: /quotesby Michael Scott
        """
        if not self.quotes:
            await interaction.response.send_message("No quotes have been added yet.")
            return

        # Filter quotes by the specified author
        author_quotes = {qid: quote for qid, quote in self.quotes.items() 
                        if quote['author'].lower() == author.lower()}

        if not author_quotes:
            await interaction.response.send_message(f"No quotes found by '{author}'.")
            return

        # Create an embed with the list of quotes by this author
        embed = discord.Embed(
            title=f"Quotes by {author}",
            color=discord.Color.gold()
        )

        # Add quotes to the embed (limit to 25 to avoid hitting Discord's limits)
        quotes_list = list(author_quotes.items())
        for i, (quote_id, quote) in enumerate(quotes_list[:25]):
            embed.add_field(
                name=f"Quote #{quote_id}",
                value=f"\"{quote['text'][:50]}{'...' if len(quote['text']) > 50 else ''}\"",
                inline=False
            )

        # Add a note if there are more quotes
        if len(quotes_list) > 25:
            embed.set_footer(text=f"Showing 25/{len(quotes_list)} quotes. Use /quote <id> to see a specific quote.")
        else:
            embed.set_footer(text=f"Found {len(quotes_list)} quote(s) by {author}.")

        logger.info(f"{interaction.user} requested quotes by {author}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quote_delete", description="Delete a quote by ID")
    @app_commands.describe(quote_id="The ID of the quote to delete")
    async def delete_quote(self, interaction: discord.Interaction, quote_id: str):
        """
        Delete a quote by ID
        Usage: /deletequote <quote_id>
        Example: /deletequote 42
        """
        if quote_id in self.quotes:
            del self.quotes[quote_id]
            self._save_quotes()

            logger.info(f"{interaction.user} deleted quote #{quote_id}")
            await interaction.response.send_message(f"Quote #{quote_id} has been deleted.")
        else:
            await interaction.response.send_message(f"Quote #{quote_id} not found.")


async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(QuotesCog(bot), guild=guild_id)
