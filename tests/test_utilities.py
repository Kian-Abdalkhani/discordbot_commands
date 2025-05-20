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
    def ctx(self):
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.author = MagicMock()
        ctx.author.mention = "@TestUser"
        return ctx
    
    @pytest.mark.asyncio
    async def test_timer_no_parameters(self, cog, ctx):
        # Test timer command with no parameters
        await cog.timer(ctx)
        
        # Verify ctx.send was called with the usage message
        ctx.send.assert_called_once_with("Please specify a time and unit. Example: `!timer 5 minutes`")
    
    @pytest.mark.asyncio
    async def test_timer_invalid_unit(self, cog, ctx):
        # Test timer command with an invalid unit
        await cog.timer(ctx, 5, "invalid")
        
        # Verify ctx.send was called with the invalid unit message
        ctx.send.assert_called_once_with("Invalid unit: invalid. Please use seconds, minutes, or hours.")
    
    @pytest.mark.asyncio
    async def test_timer_non_positive_time(self, cog, ctx):
        # Test timer command with a non-positive time value
        await cog.timer(ctx, 0, "seconds")
        
        # Verify ctx.send was called with the non-positive time message
        ctx.send.assert_called_once_with("Time must be a positive number.")
        
        # Reset the mock
        ctx.send.reset_mock()
        
        # Test with a negative time value
        await cog.timer(ctx, -5, "seconds")
        
        # Verify ctx.send was called with the non-positive time message
        ctx.send.assert_called_once_with("Time must be a positive number.")
    
    @pytest.mark.asyncio
    async def test_timer_seconds(self, cog, ctx, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)
        
        # Test timer command with seconds
        await cog.timer(ctx, 5, "seconds")
        
        # Verify ctx.send was called with the timer set message
        ctx.send.assert_any_call("⏰ Timer set for 5 seconds!")
        
        # Verify asyncio.sleep was called with the correct duration
        mock_sleep.assert_called_once_with(5)
        
        # Verify ctx.send was called with the timer finished message
        ctx.send.assert_any_call("⏰ @TestUser, your timer for 5 seconds has finished!")
    
    @pytest.mark.asyncio
    async def test_timer_minutes(self, cog, ctx, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)
        
        # Test timer command with minutes
        await cog.timer(ctx, 2, "minutes")
        
        # Verify ctx.send was called with the timer set message
        ctx.send.assert_any_call("⏰ Timer set for 2 minutes!")
        
        # Verify asyncio.sleep was called with the correct duration (2 minutes = 120 seconds)
        mock_sleep.assert_called_once_with(120)
        
        # Verify ctx.send was called with the timer finished message
        ctx.send.assert_any_call("⏰ @TestUser, your timer for 2 minutes has finished!")
    
    @pytest.mark.asyncio
    async def test_timer_hours(self, cog, ctx, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)
        
        # Test timer command with hours
        await cog.timer(ctx, 1, "hour")
        
        # Verify ctx.send was called with the timer set message
        ctx.send.assert_any_call("⏰ Timer set for 1 hour!")
        
        # Verify asyncio.sleep was called with the correct duration (1 hour = 3600 seconds)
        mock_sleep.assert_called_once_with(3600)
        
        # Verify ctx.send was called with the timer finished message
        ctx.send.assert_any_call("⏰ @TestUser, your timer for 1 hour has finished!")
    
    @pytest.mark.asyncio
    async def test_timer_unit_variations(self, cog, ctx, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)
        
        # Test various unit variations
        unit_variations = {
            "s": 1,
            "sec": 1,
            "secs": 1,
            "second": 1,
            "seconds": 1,
            "m": 60,
            "min": 60,
            "mins": 60,
            "minute": 60,
            "minutes": 60,
            "h": 3600,
            "hr": 3600,
            "hrs": 3600,
            "hour": 3600,
            "hours": 3600
        }
        
        for unit, multiplier in unit_variations.items():
            # Reset mocks
            mock_sleep.reset_mock()
            ctx.send.reset_mock()
            
            # Test timer with this unit
            await cog.timer(ctx, 1, unit)
            
            # Verify asyncio.sleep was called with the correct duration
            mock_sleep.assert_called_once_with(1 * multiplier)
    
    @pytest.mark.asyncio
    async def test_timer_format_time_str(self, cog, ctx, monkeypatch):
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", mock_sleep)
        
        # Test different time formats
        test_cases = [
            (30, "seconds", "30 seconds"),
            (1, "second", "1 second"),
            (5, "minutes", "5 minutes"),
            (1, "minute", "1 minute"),
            (2, "hours", "2 hours"),
            (1, "hour", "1 hour"),
            (1.5, "hours", "1 hour and 30 minutes")
        ]
        
        for time, unit, expected_str in test_cases:
            # Reset mocks
            mock_sleep.reset_mock()
            ctx.send.reset_mock()
            
            # Calculate expected seconds
            if unit in ["second", "seconds", "s", "sec", "secs"]:
                seconds = time
            elif unit in ["minute", "minutes", "m", "min", "mins"]:
                seconds = time * 60
            else:  # hours
                seconds = time * 3600
            
            # Test timer with this time and unit
            await cog.timer(ctx, time, unit)
            
            # Verify ctx.send was called with the expected time string
            ctx.send.assert_any_call(f"⏰ Timer set for {expected_str}!")
            ctx.send.assert_any_call(f"⏰ @TestUser, your timer for {expected_str} has finished!")