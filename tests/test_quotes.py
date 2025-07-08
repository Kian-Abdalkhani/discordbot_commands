import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import discord
from discord.ext import commands
from datetime import datetime
from src.cogs.quotes import QuotesCog


class TestQuotesCog:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=commands.Bot)
        return bot

    @pytest.fixture
    def mock_quotes_file(self, tmp_path):
        # Create a temporary quotes file for testing
        quotes_file = tmp_path / "quotes.json"
        quotes_data = {
            "quotes": {
                "1": {
                    "text": "Test quote 1",
                    "author": "Test Author",
                    "added_by": "Test User",
                    "added_at": "2023-01-01T00:00:00"
                },
                "2": {
                    "text": "Test quote 2",
                    "author": "Another Author",
                    "added_by": "Test User",
                    "added_at": "2023-01-02T00:00:00"
                }
            },
            "counter": 2
        }
        quotes_file.write_text(json.dumps(quotes_data))
        return quotes_file

    @pytest.fixture
    def cog(self, bot, mock_quotes_file, monkeypatch):
        # Create a custom initialization method for testing
        def mock_init(self, bot, quotes_file):
            self.bot = bot
            self.quotes_file = quotes_file
            self.quotes = {}
            self.quote_counter = 0
            self._load_quotes()
            return self

        # Create a new instance of QuotesCog without calling __init__
        cog = QuotesCog.__new__(QuotesCog)

        # Call our custom initialization method
        mock_init(cog, bot, str(mock_quotes_file))

        return cog

    @pytest.fixture
    def interaction(self):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.edit_original_response = AsyncMock()
        interaction.user = MagicMock(spec=discord.Member)
        interaction.user.__str__ = lambda self: "Test User"
        interaction.user.name = "testuser"
        interaction.created_at = datetime.now()
        return interaction

    def test_load_quotes(self, cog):
        # Test that quotes are loaded correctly
        assert len(cog.quotes) == 2
        assert cog.quote_counter == 2
        assert cog.quotes["1"]["text"] == "Test quote 1"
        assert cog.quotes["2"]["author"] == "Another Author"

    @pytest.mark.asyncio
    async def test_add_quote(self, cog, interaction):
        # Test adding a quote with author
        await cog.add_quote(interaction, quote_text="This is a test quote", quote_author="Test Author")

        # Verify the quote was added
        assert "3" in cog.quotes
        assert cog.quotes["3"]["text"] == "This is a test quote"
        assert cog.quotes["3"]["author"] == "Test Author"
        assert cog.quotes["3"]["added_by"] == "testuser"

        # Verify interaction.response.send_message was called with the success message
        interaction.response.send_message.assert_called_once_with("Quote #3 added successfully!")

    @pytest.mark.asyncio
    async def test_add_quote_no_author(self, cog, interaction):
        # Test adding a quote without an author (using empty string)
        await cog.add_quote(interaction, quote_text="This is a test quote without author", quote_author="")

        # Verify the quote was added with "Unknown" author
        assert "3" in cog.quotes
        assert cog.quotes["3"]["text"] == "This is a test quote without author"
        assert cog.quotes["3"]["author"] == "Unknown"
        assert cog.quotes["3"]["added_by"] == "testuser"

        # Verify interaction.response.send_message was called with the success message
        interaction.response.send_message.assert_called_once_with("Quote #3 added successfully!")

    @pytest.mark.asyncio
    async def test_quote_by_id(self, cog, interaction):
        # Test getting a quote by ID
        await cog.quote(interaction, quote_id=1)

        # Verify interaction.response.send_message was called with an embed
        assert interaction.response.send_message.called
        embed = interaction.response.send_message.call_args[1]['embed']
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Quote #1"
        assert "Test quote 1" in embed.description

    @pytest.mark.asyncio
    async def test_quote_random(self, cog, ctx, monkeypatch):
        # Mock random.choice to return a predictable result
        monkeypatch.setattr("random.choice", lambda x: "1")

        # Test getting a random quote
        await cog.quote(ctx)

        # Verify ctx.send was called with an embed
        assert ctx.send.called
        embed = ctx.send.call_args[0][0]
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Quote #1"
        assert "Test quote 1" in embed.description

    @pytest.mark.asyncio
    async def test_quote_not_found(self, cog, ctx):
        # Test getting a quote that doesn't exist
        await cog.quote(ctx, quote_id="999")

        # Verify ctx.send was called with the not found message
        ctx.send.assert_called_once_with("Quote #999 not found.")

    @pytest.mark.asyncio
    async def test_list_quotes(self, cog, ctx):
        # Test listing all quotes
        await cog.list_quotes(ctx)

        # Verify ctx.send was called with an embed
        assert ctx.send.called
        embed = ctx.send.call_args[0][0]
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Available Quotes"

        # Check that both quotes are in the embed fields
        field_names = [field.name for field in embed.fields]
        assert "Quote #1" in field_names
        assert "Quote #2" in field_names

    @pytest.mark.asyncio
    async def test_quotes_by(self, cog, ctx):
        # Test getting quotes by a specific author
        await cog.quotes_by(ctx, author="Test Author")

        # Verify ctx.send was called with an embed
        assert ctx.send.called
        embed = ctx.send.call_args[0][0]
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Quotes by Test Author"

        # Check that only quotes by Test Author are in the embed
        field_names = [field.name for field in embed.fields]
        assert "Quote #1" in field_names
        assert "Quote #2" not in field_names

    @pytest.mark.asyncio
    async def test_quotes_by_not_found(self, cog, ctx):
        # Test getting quotes by an author that doesn't exist
        await cog.quotes_by(ctx, author="Nonexistent Author")

        # Verify ctx.send was called with the not found message
        ctx.send.assert_called_once_with("No quotes found by 'Nonexistent Author'.")

    @pytest.mark.asyncio
    async def test_delete_quote(self, cog, ctx):
        # Test deleting a quote
        await cog.delete_quote(ctx, quote_id="1")

        # Verify the quote was deleted
        assert "1" not in cog.quotes

        # Verify ctx.send was called with the success message
        ctx.send.assert_called_once_with("Quote #1 has been deleted.")

    @pytest.mark.asyncio
    async def test_delete_quote_not_found(self, cog, ctx):
        # Test deleting a quote that doesn't exist
        await cog.delete_quote(ctx, quote_id="999")

        # Verify ctx.send was called with the not found message
        ctx.send.assert_called_once_with("Quote #999 not found.")

    def test_save_quotes(self, cog, tmp_path):
        # Add a new quote
        cog.quotes["3"] = {
            "text": "New test quote",
            "author": "New Author",
            "added_by": "Test User",
            "added_at": "2023-01-03T00:00:00"
        }
        cog.quote_counter = 3

        # Save the quotes
        cog._save_quotes()

        # Load the saved file and verify the content
        with open(cog.quotes_file, 'r') as f:
            data = json.load(f)

        assert len(data["quotes"]) == 3
        assert data["counter"] == 3
        assert data["quotes"]["3"]["text"] == "New test quote"
