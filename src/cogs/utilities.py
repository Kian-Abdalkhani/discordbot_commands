import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging

from src.config.settings import GUILD_ID

logger = logging.getLogger(__name__)


class UtilitiesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="timer", description="Set a timer for a specified duration")
    @app_commands.describe(
        time="The amount of time for the timer (10,30,60,etc..)",
        unit="The unit of time (seconds, minutes, hours)"
    )
    async def timer(self, interaction: discord.Interaction, time: int, unit: str):
        """
        Set a timer for a specified duration.
        Usage: !timer <time> <unit>
        Example: !timer 5 minutes
        Units: seconds, minutes, hours
        """
        # Convert unit to lowercase and handle singular/plural forms
        unit = unit.lower()
        if unit.endswith('s') and unit not in ['seconds', 'minutes', 'hours', 's', 'secs', 'mins', 'hrs']:
            unit = unit[:-1]  # Remove 's' from the end if it's not one of the standard plural forms

        # Calculate seconds based on the unit
        if unit in ['second', 'seconds', 's', 'sec', 'secs']:
            seconds = time
        elif unit in ['minute', 'minutes', 'm', 'min', 'mins']:
            seconds = time * 60
        elif unit in ['hour', 'hours', 'h', 'hr', 'hrs']:
            seconds = time * 3600
        else:
            logger.info(f"{interaction.user} attempted to use timer command with invalid unit: {unit}")
            await interaction.response.send_message(f"Invalid unit: {unit}. Please use seconds, minutes, or hours.")
            return

        if seconds >= 86400:
            logger.info(f"{interaction.user} attempted to use timer command with too large of a time value: {time}")
            await interaction.response.send_message("Time must be below 24hrs")
            return
        elif seconds <= 0:
            logger.info(f"{interaction.user} attempted to use timer command with non-positive time value: {time}")
            await interaction.response.send_message("Time must be a positive number.")
            return

        # Format the time for display
        if seconds < 60:
            time_str = f"{seconds} second{'s' if seconds != 1 else ''}"
        elif seconds < 3600:
            minutes = seconds // 60
            time_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                time_str = f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
            else:
                time_str = f"{hours} hour{'s' if hours != 1 else ''}"

        # Confirm timer start
        logger.info(f"{interaction.user} set a timer for {time_str}")
        await interaction.response.send_message(f"⏰ Timer set for {time_str}!")

        # Wait for the specified time
        await asyncio.sleep(seconds)

        # Notify the user when the timer is done
        logger.info(f"{interaction.user}'s timer for {time_str} has finished")
        await interaction.followup.send(f"⏰ {interaction.user.mention}, your timer for {time_str} has finished!")


async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(UtilitiesCog(bot),guild=guild_id)
