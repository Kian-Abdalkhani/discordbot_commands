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

        # Mock the logger to verify logging
        with patch('src.cogs.games.logger') as mock_logger:
            # Call the command
            await cog.flip_coin.callback(cog, interaction)

            # Verify interaction.response.send_message was called with "heads"
            interaction.response.send_message.assert_called_once_with("heads")
            
            # Verify logging occurred
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert "flipped a coin" in log_call_args

        # Reset the mocks
        interaction.response.send_message.reset_mock()

        # Change the mock to return tails
        monkeypatch.setattr(random, "choice", lambda x: "tails")

        with patch('src.cogs.games.logger') as mock_logger:
            # Call the command again
            await cog.flip_coin.callback(cog, interaction)

            # Verify interaction.response.send_message was called with "tails"
            interaction.response.send_message.assert_called_once_with("tails")
            
            # Verify logging occurred
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert "flipped a coin" in log_call_args

    @pytest.mark.asyncio
    async def test_flip_coin_random_behavior(self, cog, interaction):
        # Test that flip_coin actually uses random.choice with correct options
        with patch('random.choice') as mock_choice, \
             patch('src.cogs.games.logger'):
            
            mock_choice.return_value = "heads"
            
            await cog.flip_coin.callback(cog, interaction)
            
            # Verify random.choice was called with the correct options
            mock_choice.assert_called_once_with(["heads", "tails"])
            
            # Verify the result was sent
            interaction.response.send_message.assert_called_once_with("heads")

