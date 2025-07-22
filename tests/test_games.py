import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
import random
from src.cogs.games import GamesCog


class TestGamesCog:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=commands.Bot)
        bot.wait_for = AsyncMock()
        bot.fetch_user = AsyncMock()
        return bot

    @pytest.fixture
    def cog(self, bot):
        return GamesCog(bot)

    @pytest.fixture
    def interaction(self):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.edit_original_response = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.mention = "@TestUser"
        return interaction

    @pytest.mark.asyncio
    async def test_flip_coin(self, cog, interaction, monkeypatch):
        # Test that flip_coin returns either heads or tails

        # Mock random.choice to return a predictable result
        monkeypatch.setattr(random, "choice", lambda x: "heads")

        # Call the command
        await cog.flip_coin.callback(cog, interaction)

        # Verify interaction.response.send_message was called with "heads"
        interaction.response.send_message.assert_called_once_with("heads")

        # Reset the mock
        interaction.response.send_message.reset_mock()

        # Change the mock to return tails
        monkeypatch.setattr(random, "choice", lambda x: "tails")

        # Call the command again
        await cog.flip_coin.callback(cog, interaction)

        # Verify interaction.response.send_message was called with "tails"
        interaction.response.send_message.assert_called_once_with("tails")

