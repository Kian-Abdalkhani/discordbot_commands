from discord.ext import commands
import logging
import asyncio

logger = logging.getLogger(__name__)


class UtilitiesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def timer(self, ctx, time: int = None, unit: str = None):
        """
        Set a timer for a specified duration.
        Usage: !timer <time> <unit>
        Example: !timer 5 minutes
        Units: seconds, minutes, hours
        """
        if time is None or unit is None:
            logger.info(f"{ctx.author} attempted to use timer command without proper parameters")
            await ctx.send("Please specify a time and unit. Example: `!timer 5 minutes`")
            return

        # Convert unit to lowercase and handle singular/plural forms
        unit = unit.lower()
        if unit.endswith('s') and unit != 'seconds' and unit != 'minutes' and unit != 'hours':
            unit = unit[:-1]  # Remove 's' from the end if it's not one of the standard plural forms

        # Calculate seconds based on the unit
        if unit in ['second', 'seconds', 's', 'sec', 'secs']:
            seconds = time
        elif unit in ['minute', 'minutes', 'm', 'min', 'mins']:
            seconds = time * 60
        elif unit in ['hour', 'hours', 'h', 'hr', 'hrs']:
            seconds = time * 3600
        else:
            logger.info(f"{ctx.author} attempted to use timer command with invalid unit: {unit}")
            await ctx.send(f"Invalid unit: {unit}. Please use seconds, minutes, or hours.")
            return

        if seconds <= 0:
            logger.info(f"{ctx.author} attempted to use timer command with non-positive time value: {time}")
            await ctx.send("Time must be a positive number.")
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
        logger.info(f"{ctx.author} set a timer for {time_str}")
        await ctx.send(f"⏰ Timer set for {time_str}!")

        # Wait for the specified time
        await asyncio.sleep(seconds)

        # Notify the user when the timer is done
        logger.info(f"{ctx.author}'s timer for {time_str} has finished")
        await ctx.send(f"⏰ {ctx.author.mention}, your timer for {time_str} has finished!")
