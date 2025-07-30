import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
from src.cogs.currency import CurrencyCog


class TestCurrencyCog:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=commands.Bot)
        bot.currency_manager = MagicMock()
        bot.currency_manager.get_balance = AsyncMock(return_value=1000)
        bot.currency_manager.can_claim_daily = AsyncMock(return_value=(True, None))
        bot.currency_manager.claim_daily_bonus = AsyncMock()
        bot.currency_manager.transfer_currency = AsyncMock(return_value=True)
        bot.currency_manager.format_balance = MagicMock(return_value="1,000")
        return bot

    @pytest.fixture
    def cog(self, bot):
        with patch.object(CurrencyCog, 'daily_distribution_task') as mock_task:
            mock_task.start = MagicMock()
            return CurrencyCog(bot)

    @pytest.fixture
    def interaction(self):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.mention = "@TestUser"
        return interaction

    @pytest.mark.asyncio
    async def test_balance_command(self, cog, interaction):
        """Test the balance command"""
        await cog.balance.callback(cog, interaction)
        
        interaction.response.send_message.assert_called_once()
        cog.bot.currency_manager.get_balance.assert_called_once_with(str(interaction.user.id))

    @pytest.mark.asyncio
    async def test_daily_claim_available(self, cog, interaction):
        """Test daily claim when available"""
        cog.bot.currency_manager.can_claim_daily.return_value = (True, None)
        
        await cog.daily.callback(cog, interaction)
        
        cog.bot.currency_manager.claim_daily_bonus.assert_called_once_with(str(interaction.user.id))
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_daily_claim_not_available(self, cog, interaction):
        """Test daily claim when not available"""
        from datetime import timedelta
        time_left = timedelta(hours=5, minutes=30)
        cog.bot.currency_manager.can_claim_daily.return_value = (False, time_left)
        
        await cog.daily.callback(cog, interaction)
        
        cog.bot.currency_manager.claim_daily_bonus.assert_not_called()
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "5 hours and 30 minutes" in call_args

    @pytest.mark.asyncio
    async def test_transfer_success(self, cog, interaction):
        """Test successful currency transfer"""
        target_user = MagicMock()
        target_user.id = 67890
        target_user.mention = "@TargetUser"
        
        cog.bot.currency_manager.transfer_currency.return_value = True
        
        await cog.transfer.callback(cog, interaction, target_user, 500)
        
        cog.bot.currency_manager.transfer_currency.assert_called_once_with(
            str(interaction.user.id), str(target_user.id), 500
        )
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "successfully transferred" in call_args.lower()

    @pytest.mark.asyncio
    async def test_transfer_failure(self, cog, interaction):
        """Test failed currency transfer"""
        target_user = MagicMock()
        target_user.id = 67890
        
        cog.bot.currency_manager.transfer_currency.return_value = False
        
        await cog.transfer.callback(cog, interaction, target_user, 5000)
        
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "insufficient" in call_args.lower()

    @pytest.mark.asyncio
    async def test_transfer_to_self(self, cog, interaction):
        """Test transfer to self is blocked"""
        target_user = MagicMock()
        target_user.id = interaction.user.id  # Same as sender
        
        await cog.transfer.callback(cog, interaction, target_user, 100)
        
        cog.bot.currency_manager.transfer_currency.assert_not_called()
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "cannot transfer" in call_args.lower()

    @pytest.mark.asyncio
    async def test_transfer_invalid_amount(self, cog, interaction):
        """Test transfer with invalid amount"""
        target_user = MagicMock()
        target_user.id = 67890
        
        await cog.transfer.callback(cog, interaction, target_user, 0)
        
        cog.bot.currency_manager.transfer_currency.assert_not_called()
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args[0][0]
        assert "must be greater than 0" in call_args.lower()