from src.config.settings import GUILD_ID
from src.utils.feature_request_store import FeatureRequestManager

import logging
import discord
from discord.ext import commands
from discord import app_commands
import traceback

class FeatureRequest(discord.ui.Modal, title='Feature Request'):
    def __init__(self):
        super().__init__()
        self.feature_manager = FeatureRequestManager()

    name = discord.ui.TextInput(
        label='Name',
        placeholder='Your name here...',
    )

    feature_request = discord.ui.TextInput(
        label='What feature would you like to see added?',
        style=discord.TextStyle.long,
        placeholder='Describe your feature request here...',
        required=True,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Store the feature request
            request_data = self.feature_manager.add_request(
                name=self.name.value,
                request_text=self.feature_request.value,
                user_id=interaction.user.id,
                username=interaction.user.name
            )
            
            await interaction.response.send_message(
                f'Thanks for your feature request, {self.name.value}! '
                f'Your request has been saved with ID #{request_data["id"]} and will be reviewed.',
                ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error saving feature request: {e}")
            await interaction.response.send_message(
                'There was an error saving your feature request. Please try again later.',
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)

class FeatureRequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="feature_request", description="Submit a feature request for the bot")
    async def feature_request(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FeatureRequest())

async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(FeatureRequestCog(bot), guild=guild_id)