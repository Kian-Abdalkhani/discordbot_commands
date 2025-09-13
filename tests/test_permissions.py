import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
from src.cogs.permissions import Permissions
from src.config.settings import ADMIN_GIVE_MONEY_MAX_AMOUNT, ADMIN_GIVE_MONEY_REASON_MAX_LENGTH


class TestPermissions:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=commands.Bot)
        # Mock permission manager (pm)
        bot.pm = MagicMock()
        bot.pm.admins = [12345]  # Admin user ID
        bot.pm.load_permissions = AsyncMock()
        bot.pm.is_user_restricted = AsyncMock(return_value=False)
        bot.pm.add_timeout = AsyncMock()
        bot.pm.remove_timeout = AsyncMock(return_value=True)
        
        # Mock currency manager for give_money command
        bot.currency_manager = MagicMock()
        bot.currency_manager.add_currency = AsyncMock(return_value=150000.0)
        
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
        member.display_name = "TargetUser"
        return member

    @pytest.fixture
    def admin_member(self, interaction):
        """Create a member object that matches the admin user for self-transfer tests"""
        member = MagicMock(spec=discord.Member)
        member.id = interaction.user.id  # Same ID as admin
        member.mention = "@AdminUser"
        member.display_name = "AdminUser"
        return member

    @pytest.mark.asyncio
    async def test_timeout_command_success(self, cog, interaction, target_member):
        """Test successful timeout command"""
        await cog.timeout.callback(cog, interaction, target_member)
        
        # Verify permission manager methods were called
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.pm.is_user_restricted.assert_called_once_with(target_member.id)
        cog.bot.pm.add_timeout.assert_called_once_with(target_member.id, None)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "timeout" in call_args

    @pytest.mark.asyncio
    async def test_timeout_command_not_admin(self, cog, interaction, target_member):
        """Test timeout command when user is not admin"""
        interaction.user.id = 99999  # Non-admin user
        
        await cog.timeout.callback(cog, interaction, target_member)
        
        # Verify permission manager was checked but timeout not added
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.pm.add_timeout.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "administrator" in call_args

    @pytest.mark.asyncio
    async def test_timeout_command_user_already_restricted(self, cog, interaction, target_member):
        """Test timeout command when user is already in timeout"""
        cog.bot.pm.is_user_restricted = AsyncMock(return_value=True)  # User already restricted
        
        await cog.timeout.callback(cog, interaction, target_member)
        
        # Should check but not add timeout
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.pm.is_user_restricted.assert_called_once_with(target_member.id)
        cog.bot.pm.add_timeout.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "already" in call_args

    @pytest.mark.asyncio 
    async def test_end_timeout_command_success(self, cog, interaction, target_member):
        """Test successful end timeout command"""
        cog.bot.pm.is_user_restricted = AsyncMock(return_value=True)  # User in timeout
        
        await cog.end_timeout.callback(cog, interaction, target_member)
        
        # Verify permission manager methods were called
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.pm.is_user_restricted.assert_called_once_with(target_member.id)
        cog.bot.pm.remove_timeout.assert_called_once_with(target_member.id)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "let out" in call_args

    @pytest.mark.asyncio
    async def test_end_timeout_command_not_admin(self, cog, interaction, target_member):
        """Test end timeout command when user is not admin"""
        interaction.user.id = 99999  # Non-admin user
        
        await cog.end_timeout.callback(cog, interaction, target_member)
        
        # Should check permissions but not remove timeout
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.pm.remove_timeout.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "administrator" in call_args

    @pytest.mark.asyncio
    async def test_end_timeout_command_user_not_restricted(self, cog, interaction, target_member):
        """Test end timeout command when user is not in timeout"""
        cog.bot.pm.is_user_restricted = AsyncMock(return_value=False)  # User not restricted
        
        await cog.end_timeout.callback(cog, interaction, target_member)
        
        # Should check but not remove timeout
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.pm.is_user_restricted.assert_called_once_with(target_member.id)
        cog.bot.pm.remove_timeout.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "not in timeout" in call_args

    def test_initialization(self, cog, bot):
        """Test cog initialization"""
        assert cog.bot is bot
        assert cog.pm is bot.pm

    def test_cog_structure(self, cog):
        """Test that cog has required commands"""
        assert hasattr(cog, 'timeout')
        assert hasattr(cog, 'end_timeout')
        assert hasattr(cog, 'give_money')
        assert callable(cog.timeout.callback)
        assert callable(cog.end_timeout.callback)
        assert callable(cog.give_money.callback)

    @pytest.mark.asyncio
    async def test_give_money_command_success(self, cog, interaction, target_member):
        """Test successful give money command"""
        interaction.user.display_name = "AdminUser"
        amount = 50000
        reason = "Server glitch compensation"
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Verify permission manager was checked
        cog.bot.pm.load_permissions.assert_called_once()
        
        # Verify currency manager was called with correct parameters
        cog.bot.currency_manager.add_currency.assert_called_once()
        call_args = cog.bot.currency_manager.add_currency.call_args
        assert call_args[1]['user_id'] == str(target_member.id)
        assert call_args[1]['amount'] == amount
        assert call_args[1]['command'] == "admin_give_money"
        assert call_args[1]['metadata']['reason'] == reason
        assert call_args[1]['metadata']['admin_id'] == str(interaction.user.id)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert f"${amount:,}" in call_args
        assert reason in call_args
        assert "$150,000.00" in call_args  # New balance from mock

    @pytest.mark.asyncio
    async def test_give_money_command_not_admin(self, cog, interaction, target_member):
        """Test give money command when user is not admin"""
        interaction.user.id = 99999  # Non-admin user
        amount = 50000
        reason = "Server glitch compensation"
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Should check permissions but not give money
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "administrator" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_invalid_amount(self, cog, interaction, target_member):
        """Test give money command with invalid amount"""
        amount = -1000
        reason = "Server glitch compensation"
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Should check permissions but not give money
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "positive" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_empty_reason(self, cog, interaction, target_member):
        """Test give money command with empty reason"""
        amount = 50000
        reason = "   "  # Empty/whitespace reason
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Should check permissions but not give money
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "reason must be provided" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_no_reason(self, cog, interaction, target_member):
        """Test give money command with no reason"""
        amount = 50000
        reason = ""
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Should check permissions but not give money
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "reason must be provided" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_excessive_amount(self, cog, interaction, target_member):
        """Test give money command with amount exceeding maximum limit"""
        amount = ADMIN_GIVE_MONEY_MAX_AMOUNT + 1
        reason = "Testing upper limits"
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Should check permissions but reject the amount
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "cannot exceed" in call_args
        assert f"${ADMIN_GIVE_MONEY_MAX_AMOUNT:,}" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_zero_amount(self, cog, interaction, target_member):
        """Test give money command with zero amount"""
        amount = 0
        reason = "Testing edge case"
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "positive" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_self_transfer(self, cog, interaction, admin_member):
        """Test that admin cannot give money to themselves"""
        amount = 50000
        reason = "Self compensation attempt"
        
        await cog.give_money.callback(cog, interaction, admin_member, amount, reason)
        
        # Should check permissions but reject self-transfer
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "cannot give money to yourself" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_excessive_reason_length(self, cog, interaction, target_member):
        """Test give money command with reason exceeding maximum length"""
        amount = 50000
        reason = "A" * (ADMIN_GIVE_MONEY_REASON_MAX_LENGTH + 1)  # One character over limit
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Should check permissions but reject the reason
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_not_called()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert f"{ADMIN_GIVE_MONEY_REASON_MAX_LENGTH} characters or less" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_max_valid_amount(self, cog, interaction, target_member):
        """Test give money command with maximum valid amount"""
        interaction.user.display_name = "AdminUser"
        amount = ADMIN_GIVE_MONEY_MAX_AMOUNT  # Exactly at the limit
        reason = "Maximum valid transfer"
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Should succeed
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_called_once()
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert f"${amount:,}" in call_args
        assert reason in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_max_valid_reason_length(self, cog, interaction, target_member):
        """Test give money command with maximum valid reason length"""
        interaction.user.display_name = "AdminUser"
        amount = 50000
        reason = "A" * ADMIN_GIVE_MONEY_REASON_MAX_LENGTH  # Exactly at the limit
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Should succeed
        cog.bot.pm.load_permissions.assert_called_once()
        cog.bot.currency_manager.add_currency.assert_called_once()
        
        # Verify the full reason was stored
        call_args = cog.bot.currency_manager.add_currency.call_args
        stored_reason = call_args[1]['metadata']['reason']
        assert stored_reason == reason
        assert len(stored_reason) == ADMIN_GIVE_MONEY_REASON_MAX_LENGTH

    @pytest.mark.asyncio
    async def test_give_money_command_currency_manager_value_error(self, cog, interaction, target_member):
        """Test give money command when currency manager raises ValueError"""
        interaction.user.display_name = "AdminUser"
        amount = 50000
        reason = "Server glitch compensation"
        
        # Mock currency manager to raise ValueError
        cog.bot.currency_manager.add_currency = AsyncMock(side_effect=ValueError("Invalid user data"))
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "Invalid input provided" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_currency_manager_key_error(self, cog, interaction, target_member):
        """Test give money command when currency manager raises KeyError"""
        interaction.user.display_name = "AdminUser"
        amount = 50000
        reason = "Server glitch compensation"
        
        # Mock currency manager to raise KeyError
        cog.bot.currency_manager.add_currency = AsyncMock(side_effect=KeyError("Missing user key"))
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "User data error" in call_args

    @pytest.mark.asyncio
    async def test_give_money_command_unexpected_error(self, cog, interaction, target_member):
        """Test give money command when currency manager raises unexpected error"""
        interaction.user.display_name = "AdminUser"
        amount = 50000
        reason = "Server glitch compensation"
        
        # Mock currency manager to raise unexpected error
        cog.bot.currency_manager.add_currency = AsyncMock(side_effect=RuntimeError("Unexpected database error"))
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "unexpected error occurred" in call_args

    @pytest.mark.asyncio
    async def test_give_money_currency_manager_integration(self, cog, interaction, target_member):
        """Test that currency manager is called with all required parameters"""
        interaction.user.display_name = "AdminUser"
        amount = 75000
        reason = "Event prize compensation"
        
        await cog.give_money.callback(cog, interaction, target_member, amount, reason)
        
        # Verify all parameters are correctly passed
        call_kwargs = cog.bot.currency_manager.add_currency.call_args[1]
        
        assert call_kwargs['user_id'] == str(target_member.id)
        assert call_kwargs['amount'] == amount
        assert call_kwargs['command'] == "admin_give_money"
        assert call_kwargs['transaction_type'] == "currency"
        assert call_kwargs['display_name'] == target_member.display_name
        assert call_kwargs['mention'] == target_member.mention
        
        # Verify metadata completeness
        metadata = call_kwargs['metadata']
        assert metadata['admin_id'] == str(interaction.user.id)
        assert metadata['admin_name'] == interaction.user.display_name
        assert metadata['reason'] == reason
        assert metadata['recipient_id'] == str(target_member.id)
        assert metadata['recipient_name'] == target_member.display_name

    @pytest.mark.asyncio
    async def test_give_money_command_reason_with_special_characters(self, cog, interaction, target_member):
        """Test give money command with special characters in reason"""
        interaction.user.display_name = "AdminUser"
        amount = 25000
        
        special_reasons = [
            "Reason with\nnewlines\nand\ttabs",
            "Reason with emojis 💰🚨⚠️",
            "Reason with unicode: ñoël café naïve",
            "Quotes and 'apostrophes' in \"reason\"",
            "Numbers 12345 and symbols !@#$%^&*()"
        ]
        
        for reason in special_reasons:
            if len(reason) <= ADMIN_GIVE_MONEY_REASON_MAX_LENGTH:
                cog.bot.currency_manager.add_currency.reset_mock()
                interaction.response.send_message.reset_mock()
                
                await cog.give_money.callback(cog, interaction, target_member, amount, reason)
                
                # Should handle gracefully
                cog.bot.currency_manager.add_currency.assert_called_once()
                call_args = cog.bot.currency_manager.add_currency.call_args
                stored_reason = call_args[1]['metadata']['reason']
                
                # Verify reason is stored correctly
                assert stored_reason == reason.strip()