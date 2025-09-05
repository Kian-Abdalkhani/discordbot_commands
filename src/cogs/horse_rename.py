import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from src.config.settings import HORSE_STATS, HORSE_RENAME_COST, HORSE_RENAME_DURATION_DAYS,GUILD_ID, TRANSACTION_TYPES

logger = logging.getLogger(__name__)

class HorseRename(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rename_horse", description=f"Rename a horse for {HORSE_RENAME_DURATION_DAYS} days (Cost: {HORSE_RENAME_COST:,} coins)")
    @app_commands.describe(
        horse_number="The number of the horse to rename (1-8)",
        nickname="The new nickname for the horse (max 30 characters)"
    )
    async def rename_horse(self, interaction: discord.Interaction, horse_number: int, nickname: str):
        # Defer response to prevent timeout
        await interaction.response.defer(ephemeral=True)
        
        user_id = interaction.user.id
        user_id_str = str(user_id)
        logger.info(f"User {interaction.user} ({user_id}) attempting to rename horse {horse_number} to '{nickname}'")
        
        if horse_number < 1 or horse_number > len(HORSE_STATS):
            await interaction.followup.send(f"❌ Invalid horse number. Please choose a horse between 1 and {len(HORSE_STATS)}.", ephemeral=True)
            return
        
        horse_index = horse_number - 1
        original_name = HORSE_STATS[horse_index]["name"]
        
        if len(nickname) > 30:
            await interaction.followup.send("❌ Nickname must be 30 characters or less.", ephemeral=True)
            return
        
        if len(nickname.strip()) == 0:
            await interaction.followup.send("❌ Nickname cannot be empty.", ephemeral=True)
            return
        
        nickname = nickname.strip()
        
        if "@" in nickname or "#" in nickname or "`" in nickname:
            # Invalid characters in nickname
            await interaction.followup.send("❌ Nickname cannot contain @, #, or ` characters.", ephemeral=True)
            return
        
        current_balance = await self.bot.currency_manager.get_balance(user_id_str)
        if current_balance < HORSE_RENAME_COST:
            await interaction.followup.send(f"❌ You need {HORSE_RENAME_COST:,} coins to rename a horse. You have {current_balance:,} coins.", ephemeral=True)
            return
        
        can_user_rename, user_error = await self.bot.horse_nickname_manager.can_user_rename_horse(user_id)
        if not can_user_rename:
            await interaction.followup.send(f"❌ {user_error}", ephemeral=True)
            return
        
        can_horse_rename, horse_error = await self.bot.horse_nickname_manager.can_horse_be_renamed(horse_index)
        if not can_horse_rename:
            await interaction.followup.send(f"❌ {horse_error}", ephemeral=True)
            return
        
        success = await self.bot.horse_nickname_manager.rename_horse(user_id, horse_index, nickname)
        if not success:
            await interaction.followup.send("❌ Failed to rename horse. Please try again later.", ephemeral=True)
            return
        
        success, new_balance = await self.bot.currency_manager.subtract_currency(user_id_str, HORSE_RENAME_COST, command="horse_rename",
                                                                           transaction_type=TRANSACTION_TYPES["fee"])
        if not success:
            await interaction.followup.send("❌ Failed to process payment. Please try again later.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🐎 Horse Renamed Successfully!",
            description=f"**{original_name}** has been renamed to **{nickname}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Cost", value=f"{HORSE_RENAME_COST:,} coins", inline=True)
        embed.add_field(name="Duration", value=f"{HORSE_RENAME_DURATION_DAYS} days", inline=True)
        embed.add_field(name="Horse Number", value=str(horse_number), inline=True)
        embed.set_footer(text=f"Your current balance: {new_balance:,} coins")
        
        await interaction.followup.send(embed=embed)
        logger.info(f"Horse rename completed successfully: {interaction.user} renamed {original_name} → {nickname}")
        # Removed duplicate log (already logging above)

    @app_commands.command(name="horse_nicknames", description="View all current horse nicknames and their expiration dates")
    async def horse_nicknames(self, interaction: discord.Interaction):
        horse_names = await self.bot.horse_nickname_manager.get_all_horse_display_names()
        
        embed = discord.Embed(
            title="🐎 Current Horse Names",
            color=discord.Color.blue()
        )
        
        description_parts = []
        for i, name in horse_names.items():
            original_name = HORSE_STATS[i]["name"]
            color_emoji = HORSE_STATS[i]["color"]
            
            if name != original_name:
                description_parts.append(f"{color_emoji} **{i+1}.** {name} *(renamed)*")
            else:
                description_parts.append(f"{color_emoji} **{i+1}.** {name}")
        
        embed.description = "\n".join(description_parts)
        embed.set_footer(text=f"Use /rename_horse to rename a horse for {HORSE_RENAME_COST:,} coins ({HORSE_RENAME_DURATION_DAYS} days)")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="my_horse_nickname", description="Check if you have a horse renamed and when it expires")
    async def my_horse_nickname(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        nickname_info = await self.bot.horse_nickname_manager.get_user_nickname_info(user_id)
        
        if nickname_info is None:
            embed = discord.Embed(
                title="🐎 No Horse Renamed",
                description="You don't currently have any horse renamed.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Want to rename a horse?", 
                value=f"Use `/rename_horse` to rename a horse for {HORSE_RENAME_COST:,} coins ({HORSE_RENAME_DURATION_DAYS} days)",
                inline=False
            )
        else:
            horse_index = nickname_info["horse_index"]
            nickname = nickname_info["nickname"]
            original_name = HORSE_STATS[horse_index]["name"]
            color_emoji = HORSE_STATS[horse_index]["color"]
            expires_at = datetime.fromisoformat(nickname_info["expires_at"])
            
            embed = discord.Embed(
                title="🐎 Your Horse Nickname",
                color=discord.Color.green()
            )
            embed.add_field(name="Horse Number", value=str(horse_index + 1), inline=True)
            embed.add_field(name="Original Name", value=original_name, inline=True)
            embed.add_field(name="Current Nickname", value=f"{color_emoji} {nickname}", inline=True)
            embed.add_field(name="Expires On", value=expires_at.strftime('%Y-%m-%d %H:%M:%S'), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    """Setup function to load the cog"""
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(HorseRename(bot),guild=guild_id)