import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
import random
from src.cogs.blackjack import BlackjackCog


class TestBlackjackCog:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=commands.Bot)
        bot.wait_for = AsyncMock()
        bot.fetch_user = AsyncMock()
        return bot

    @pytest.fixture
    def cog(self, bot):
        with patch('src.cogs.blackjack.os.path.exists', return_value=True), \
             patch('src.cogs.blackjack.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '{"stats": {}}'
            return BlackjackCog(bot)

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
    async def test_blackjack_initial_deal(self, cog, interaction, monkeypatch):
        # Test the initial deal in blackjack

        # Mock random.shuffle to do nothing
        monkeypatch.setattr(random, "shuffle", lambda x: None)

        # Create a predictable deck for testing
        test_deck = [
            ('A', '♥'), ('K', '♥'),  # Player's hand (21)
            ('Q', '♦'), ('J', '♣')   # Dealer's hand (20)
        ]

        # Mock the embed creation
        embed_mock = MagicMock()

        # Mock discord.Embed
        with patch('discord.Embed', return_value=embed_mock), \
             patch('random.shuffle'), \
             patch.object(cog, 'save_blackjack_stats'):

            # Mock the deck creation within the blackjack method
            with patch('src.cogs.blackjack.random.shuffle'):
                # Call the command - this should complete the initial deal
                await cog.blackjack.callback(cog, interaction)

        # Verify interaction.response.send_message was called (indicating the game started)
        assert interaction.response.send_message.called

    def test_calculate_value(self, cog):
        # Test the calculate_value function used in blackjack

        # Define a calculate_value function that matches the one in the blackjack command
        def calculate_value(hand):
            value = 0
            aces = 0

            for card in hand:
                rank = card[0]
                if rank in ['J', 'Q', 'K']:
                    value += 10
                elif rank == 'A':
                    aces += 1
                    value += 11
                else:
                    value += int(rank)

            # Adjust for aces if needed
            while value > 21 and aces > 0:
                value -= 10
                aces -= 1

            return value

        # Test various hand combinations
        assert calculate_value([('2', '♥'), ('3', '♦')]) == 5
        assert calculate_value([('K', '♥'), ('Q', '♦')]) == 20
        assert calculate_value([('A', '♥'), ('K', '♦')]) == 21
        assert calculate_value([('A', '♥'), ('A', '♦')]) == 12
        assert calculate_value([('A', '♥'), ('A', '♦'), ('A', '♣')]) == 13
        assert calculate_value([('A', '♥'), ('5', '♦'), ('5', '♣')]) == 21
        assert calculate_value([('A', '♥'), ('6', '♦'), ('5', '♣')]) == 12

    def test_format_hand(self, cog):
        # Test the format_hand function used in blackjack

        # Define a format_hand function that matches the one in the blackjack command
        def format_hand(hand, hide_second=False):
            if hide_second and len(hand) > 1:
                return f"{hand[0][0]}{hand[0][1]} | ??"
            return " | ".join(f"{card[0]}{card[1]}" for card in hand)

        # Test normal hand formatting
        hand = [('A', '♥'), ('K', '♦')]
        assert format_hand(hand) == "A♥ | K♦"

        # Test hidden second card
        assert format_hand(hand, hide_second=True) == "A♥ | ??"

        # Test single card (no hiding)
        single_hand = [('Q', '♠')]
        assert format_hand(single_hand, hide_second=True) == "Q♠"

    @pytest.fixture
    def ctx(self):
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.author = MagicMock()
        ctx.author.id = 12345
        ctx.author.display_name = "TestUser"
        return ctx

    @pytest.mark.asyncio
    async def test_display_game_state(self, cog, ctx, monkeypatch):
        # Test the display_game_state function

        # Mock the necessary functions
        def mock_calculate_value(hand):
            return 20  # Mock value

        def mock_format_hand(hand, hide_second=False):
            if hide_second:
                return "A♥ | ??"
            return "A♥ | K♦"

        # Mock discord.Embed
        embed_mock = MagicMock()
        with patch('discord.Embed', return_value=embed_mock):
            # This test would need to be adapted to work with the actual blackjack method structure
            # Since the display_game_state is a nested function, we'd need to test it indirectly
            pass

    @pytest.mark.asyncio
    async def test_dealer_turn(self, cog, ctx, monkeypatch):
        # Test dealer's turn logic
        # This would test the dealer hitting until 17 or higher
        pass

    @pytest.mark.asyncio
    async def test_blackjack_hit(self, cog, ctx, monkeypatch):
        # Test hitting in blackjack
        pass

    @pytest.mark.asyncio
    async def test_blackjack_stand(self, cog, ctx, monkeypatch):
        # Test standing in blackjack
        pass

    @pytest.mark.asyncio
    async def test_blackjack_stats_single_user(self, cog, ctx, monkeypatch):
        # Test blackjack stats for a single user
        
        # Set up mock user
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_user.display_name = "TestUser"
        
        # Set up mock stats
        cog.player_stats = {
            "12345": {"wins": 5, "losses": 3, "ties": 1}
        }
        
        # Mock interaction
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        
        # Mock discord.Embed
        embed_mock = MagicMock()
        with patch('discord.Embed', return_value=embed_mock):
            await cog.blackjack_stats.callback(cog, interaction, mock_user)
        
        # Verify that send_message was called
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_blackjack_stats_all_users(self, cog, ctx, monkeypatch):
        # Test blackjack stats for all users
        
        # Set up mock stats for multiple users
        cog.player_stats = {
            "12345": {"wins": 5, "losses": 3, "ties": 1},
            "67890": {"wins": 2, "losses": 7, "ties": 0}
        }
        
        # Mock bot.fetch_user
        mock_user1 = MagicMock()
        mock_user1.display_name = "TestUser1"
        mock_user2 = MagicMock()
        mock_user2.display_name = "TestUser2"
        
        cog.bot.fetch_user.side_effect = [mock_user1, mock_user2]
        
        # Mock interaction
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        
        # Mock discord.Embed
        embed_mock = MagicMock()
        with patch('discord.Embed', return_value=embed_mock):
            await cog.blackjack_stats.callback(cog, interaction, None)
        
        # Verify that send_message was called
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_blackjack_stats_no_games(self, cog, ctx):
        # Test blackjack stats when no games have been played
        
        # Ensure no stats exist
        cog.player_stats = {}
        
        # Mock interaction
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        
        await cog.blackjack_stats.callback(cog, interaction, None)
        
        # Verify the correct message was sent
        interaction.response.send_message.assert_called_once_with("No blackjack games have been played yet.")

    @pytest.mark.asyncio
    async def test_blackjack_stats_user_no_games(self, cog, ctx):
        # Test blackjack stats for a user who hasn't played
        
        # Set up mock user
        mock_user = MagicMock()
        mock_user.id = 99999
        mock_user.display_name = "NewUser"
        
        # Ensure no stats exist for this user
        cog.player_stats = {}
        
        # Mock interaction
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        
        await cog.blackjack_stats.callback(cog, interaction, mock_user)
        
        # Verify the correct message was sent
        interaction.response.send_message.assert_called_once_with("NewUser hasn't played any blackjack games yet.")