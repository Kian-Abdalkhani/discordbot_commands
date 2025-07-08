import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
import asyncio
from src.cogs.utilities import UtilitiesCog


class TestUtilitiesCog:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=commands.Bot)
        return bot

    @pytest.fixture
    def cog(self, bot):
        return UtilitiesCog(bot)

    @pytest.fixture
    def interaction(self):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.mention = "@TestUser"
        return interaction

    @pytest.mark.asyncio
    async def test_timer_invalid_unit(self, cog, interaction):
        # Test timer command with an invalid unit
        with patch('src.cogs.utilities.logger') as mock_logger:
            await cog.timer.callback(cog, interaction, 5, "invalid")

            # Verify interaction.response.send_message was called with the invalid unit message
            interaction.response.send_message.assert_called_once_with("Invalid unit: invalid. Please use seconds, minutes, or hours.")
            # Verify it was logged
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_timer_non_positive_time(self, cog, interaction):
        # Test timer command with a non-positive time value
        with patch('src.cogs.utilities.logger') as mock_logger:
            await cog.timer.callback(cog, interaction, 0, "seconds")

            # Verify interaction.response.send_message was called with the non-positive time message
            interaction.response.send_message.assert_called_once_with("Time must be a positive number.")
            # Verify it was logged
            mock_logger.info.assert_called_once()

            # Reset the mock
            interaction.response.send_message.reset_mock()
            mock_logger.reset_mock()

            # Test with a negative time value
            await cog.timer.callback(cog, interaction, -5, "seconds")

            # Verify interaction.response.send_message was called with the non-positive time message
            interaction.response.send_message.assert_called_once_with("Time must be a positive number.")
            # Verify it was logged
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_timer_too_large(self, cog, interaction):
        # Test timer command with time >= 24 hours
        with patch('src.cogs.utilities.logger') as mock_logger:
            await cog.timer.callback(cog, interaction, 25, "hours")

            # Verify interaction.response.send_message was called with the too large message
            interaction.response.send_message.assert_called_once_with("Time must be below 24hrs")
            # Verify it was logged
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_timer_seconds(self, cog, interaction, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        with patch('src.cogs.utilities.logger') as mock_logger:
            # Test timer command with seconds
            await cog.timer.callback(cog, interaction, 5, "seconds")

            # Verify interaction.response.send_message was called with the timer set message
            interaction.response.send_message.assert_called_once_with("⏰ Timer set for 5 seconds!")

            # Verify asyncio.sleep was called with the correct duration
            mock_sleep.assert_called_once_with(5)

            # Verify interaction.followup.send was called with the timer finished message
            interaction.followup.send.assert_called_once_with("⏰ @TestUser, your timer for 5 seconds has finished!")

            # Verify logging
            assert mock_logger.info.call_count == 2  # Start and finish

    @pytest.mark.asyncio
    async def test_timer_minutes(self, cog, interaction, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        with patch('src.cogs.utilities.logger') as mock_logger:
            # Test timer command with minutes
            await cog.timer.callback(cog, interaction, 2, "minutes")

            # Verify interaction.response.send_message was called with the timer set message
            interaction.response.send_message.assert_called_once_with("⏰ Timer set for 2 minutes!")

            # Verify asyncio.sleep was called with the correct duration (2 minutes = 120 seconds)
            mock_sleep.assert_called_once_with(120)

            # Verify interaction.followup.send was called with the timer finished message
            interaction.followup.send.assert_called_once_with("⏰ @TestUser, your timer for 2 minutes has finished!")

    @pytest.mark.asyncio
    async def test_timer_hours(self, cog, interaction, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        with patch('src.cogs.utilities.logger') as mock_logger:
            # Test timer command with hours
            await cog.timer.callback(cog, interaction, 1, "hour")

            # Verify interaction.response.send_message was called with the timer set message
            interaction.response.send_message.assert_called_once_with("⏰ Timer set for 1 hour!")

            # Verify asyncio.sleep was called with the correct duration (1 hour = 3600 seconds)
            mock_sleep.assert_called_once_with(3600)

            # Verify interaction.followup.send was called with the timer finished message
            interaction.followup.send.assert_called_once_with("⏰ @TestUser, your timer for 1 hour has finished!")

    @pytest.mark.asyncio
    async def test_timer_unit_variations(self, cog, interaction, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        # Test various unit variations - just verify they are accepted
        unit_variations = [
            "s", "sec", "secs", "second", "seconds",
            "m", "min", "mins", "minute", "minutes", 
            "h", "hr", "hrs", "hour", "hours"
        ]

        with patch('src.cogs.utilities.logger'):
            for unit in unit_variations:
                # Reset mocks
                interaction.response.send_message.reset_mock()
                interaction.followup.send.reset_mock()

                # Test timer with this unit - should not raise an exception
                await cog.timer.callback(cog, interaction, 1, unit)

                # Verify the timer was set (response was sent)
                interaction.response.send_message.assert_called_once()

                # Verify the message contains timer set text
                call_args = interaction.response.send_message.call_args[0][0]
                assert "⏰ Timer set for" in call_args
