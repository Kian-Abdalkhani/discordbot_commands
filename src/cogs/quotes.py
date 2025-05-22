from discord.ext import commands
import logging
import random
import json
import os
import discord

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

    @commands.command(name="addquote")
    async def add_quote(self, ctx, *, quote_text):
        """
        Add a new quote to the collection
        Usage: !addquote <quote text> - <author>
        Example: !addquote That's what she said - Michael Scott
        """
        if not quote_text:
            await ctx.send("Please provide a quote to add.")
            return

        # Check if the quote has an author specified
        if " - " in quote_text:
            quote_content, author = quote_text.rsplit(" - ", 1)
        else:
            quote_content = quote_text
            author = "Unknown"

        # Increment counter and add the quote
        self.quote_counter += 1
        quote_id = str(self.quote_counter)

        self.quotes[quote_id] = {
            "text": quote_content.strip(),
            "author": author.strip(),
            "added_by": str(ctx.author),
            "added_at": ctx.message.created_at.isoformat()
        }

        self._save_quotes()

        logger.info(f"{ctx.author} added quote #{quote_id}: '{quote_content}' by {author}")
        await ctx.send(f"Quote #{quote_id} added successfully!")

    @commands.command(name="quote")
    async def quote(self, ctx, quote_id=None):
        """
        Display a quote by ID or a random quote if no ID is provided
        Usage: !quote [quote_id]
        Example: !quote 42
        """
        if not self.quotes:
            await ctx.send("No quotes have been added yet.")
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

            logger.info(f"{ctx.author} requested quote #{quote_id}")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Quote #{quote_id} not found.")

    @commands.command(name="listquotes")
    async def list_quotes(self, ctx):
        """
        List all available quotes
        Usage: !listquotes
        """
        if not self.quotes:
            await ctx.send("No quotes have been added yet.")
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
            embed.set_footer(text=f"Showing 25/{len(quotes_list)} quotes. Use !quote <id> to see a specific quote.")

        logger.info(f"{ctx.author} requested the list of quotes")
        await ctx.send(embed=embed)

    @commands.command(name="quotesby")
    async def quotes_by(self, ctx, *, author):
        """
        Display all quotes by a specific author
        Usage: !quotesby <author>
        Example: !quotesby Michael Scott
        """
        if not self.quotes:
            await ctx.send("No quotes have been added yet.")
            return

        # Filter quotes by the specified author
        author_quotes = {qid: quote for qid, quote in self.quotes.items() 
                        if quote['author'].lower() == author.lower()}

        if not author_quotes:
            await ctx.send(f"No quotes found by '{author}'.")
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
            embed.set_footer(text=f"Showing 25/{len(quotes_list)} quotes. Use !quote <id> to see a specific quote.")
        else:
            embed.set_footer(text=f"Found {len(quotes_list)} quote(s) by {author}.")

        logger.info(f"{ctx.author} requested quotes by {author}")
        await ctx.send(embed=embed)

    @commands.command(name="deletequote")
    async def delete_quote(self, ctx, quote_id):
        """
        Delete a quote by ID
        Usage: !deletequote <quote_id>
        Example: !deletequote 42
        """
        if quote_id in self.quotes:
            del self.quotes[quote_id]
            self._save_quotes()

            logger.info(f"{ctx.author} deleted quote #{quote_id}")
            await ctx.send(f"Quote #{quote_id} has been deleted.")
        else:
            await ctx.send(f"Quote #{quote_id} not found.")
