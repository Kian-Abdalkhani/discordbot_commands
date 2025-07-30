import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
from src.cogs.permissions import Permissions


class TestPermissions:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=commands.Bot)
        bot.ps = MagicMock()  # Permission store mock
        bot.ps.admins = [12345]  # Admin user ID
        bot.ps.restricted_members = []
        bot.ps.save_permissions = MagicMock()
        return bot

    @pytest.fixture
    def cog(self, bot):
        return Permissions(bot)

    @pytest.fixture
    def interaction(self):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345  # Admin user
        interaction.guild = MagicMock()
        return interaction

    @pytest.fixture
    def target_member(self):
        member = MagicMock(spec=discord.Member)
        member.id = 67890
        member.mention = "@TargetUser"
        return member

    @pytest.mark.asyncio
    async def test_timeout_command_success(self, cog, interaction, target_member):
        """Test successful timeout command"""
        await cog.timeout.callback(cog, interaction, target_member)
        
        # Verify user was added to restricted members
        assert target_member.id in cog.bot.ps.restricted_members
        
        # Verify permissions were saved
        cog.bot.ps.save_permissions.assert_called_once()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "timeout" in call_args

    @pytest.mark.asyncio
    async def test_timeout_command_not_admin(self, cog, interaction, target_member):
        """Test timeout command when user is not admin"""
        interaction.user.id = 99999  # Non-admin user
        
        await cog.timeout.callback(cog, interaction, target_member)
        
        # User should not be added to restricted members
        assert target_member.id not in cog.bot.ps.restricted_members
        cog.bot.ps.save_permissions.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "administrator" in call_args

    @pytest.mark.asyncio
    async def test_timeout_command_user_already_restricted(self, cog, interaction, target_member):
        """Test timeout command when user is already in timeout"""
        cog.bot.ps.restricted_members = [target_member.id]  # User already restricted
        
        await cog.timeout.callback(cog, interaction, target_member)
        
        # Should not modify restricted members list
        assert len(cog.bot.ps.restricted_members) == 1
        cog.bot.ps.save_permissions.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "already" in call_args

    @pytest.mark.asyncio 
    async def test_end_timeout_command_success(self, cog, interaction, target_member):
        """Test successful end timeout command"""
        cog.bot.ps.restricted_members = [target_member.id]  # User in timeout
        
        await cog.end_timeout.callback(cog, interaction, target_member)
        
        # Verify user was removed from restricted members
        assert target_member.id not in cog.bot.ps.restricted_members
        
        # Verify permissions were saved
        cog.bot.ps.save_permissions.assert_called_once()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "let out" in call_args

    @pytest.mark.asyncio
    async def test_end_timeout_command_not_admin(self, cog, interaction, target_member):
        """Test end timeout command when user is not admin"""
        interaction.user.id = 99999  # Non-admin user
        cog.bot.ps.restricted_members = [target_member.id]
        
        await cog.end_timeout.callback(cog, interaction, target_member)
        
        # User should remain in restricted members
        assert target_member.id in cog.bot.ps.restricted_members
        cog.bot.ps.save_permissions.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "administrator" in call_args

    @pytest.mark.asyncio
    async def test_end_timeout_command_user_not_restricted(self, cog, interaction, target_member):
        """Test end timeout command when user is not in timeout"""
        cog.bot.ps.restricted_members = []  # User not restricted
        
        await cog.end_timeout.callback(cog, interaction, target_member)
        
        # Should not modify restricted members list
        assert len(cog.bot.ps.restricted_members) == 0
        cog.bot.ps.save_permissions.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "not in timeout" in call_args

    def test_initialization(self, cog, bot):
        """Test cog initialization"""
        assert cog.bot is bot
        assert cog.ps is bot.ps

    def test_cog_structure(self, cog):
        """Test that cog has required commands"""
        assert hasattr(cog, 'timeout')
        assert hasattr(cog, 'end_timeout')
        assert callable(cog.timeout.callback)
        assert callable(cog.end_timeout.callback)