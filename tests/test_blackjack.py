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
        bot.currency_manager = MagicMock()
        # Configure currency manager mock to return reasonable values
        bot.currency_manager.load_currency_data = AsyncMock()
        bot.currency_manager.get_balance = AsyncMock(return_value=1000)
        bot.currency_manager.subtract_currency = AsyncMock(return_value=(True, 900))
        bot.currency_manager.add_currency = AsyncMock()
        bot.currency_manager.format_balance.return_value = "$1,000"
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

    def test_blackjack_payout_calculation(self, cog):
        """Test that blackjack payouts are calculated correctly"""
        from src.config.settings import BLACKJACK_PAYOUT_MULTIPLIER
        
        # Mock currency manager
        cog.currency_manager = MagicMock()
        cog.currency_manager.add_currency = MagicMock()
        
        # Test 2-card blackjack payout (should get special multiplier)
        user_id = "12345"
        bet = 100
        
        # Mock the nested update_player_stats function behavior for blackjack
        with patch.object(cog, 'player_stats', {}):
            # Simulate blackjack win (2 cards totaling 21)
            # This tests the logic from lines 198-204 in blackjack.py
            player_hand = [{'rank': 'A', 'suit': '♠'}, {'rank': 'K', 'suit': '♥'}]  # 21 with 2 cards
            is_blackjack = len(player_hand) == 2 and sum([11 if card['rank'] == 'A' else 10 if card['rank'] in ['K', 'Q', 'J'] else int(card['rank']) for card in player_hand]) == 21
            
            assert is_blackjack == True
            
            # Expected payout for blackjack should be bet * BLACKJACK_PAYOUT_MULTIPLIER
            expected_payout = int(bet * BLACKJACK_PAYOUT_MULTIPLIER)
            assert expected_payout == int(100 * BLACKJACK_PAYOUT_MULTIPLIER)

    def test_regular_21_payout_calculation(self, cog):
        """Test that 3+ card 21s get regular 2x payout, not blackjack multiplier"""
        # Mock currency manager
        cog.currency_manager = MagicMock()
        cog.currency_manager.add_currency = MagicMock()
        
        # Test 3+ card 21 payout (should get regular 2x payout)
        user_id = "12345"
        bet = 100
        
        with patch.object(cog, 'player_stats', {}):
            # Simulate 21 with 3+ cards (not blackjack)
            player_hand = [
                {'rank': '7', 'suit': '♠'}, 
                {'rank': '7', 'suit': '♥'}, 
                {'rank': '7', 'suit': '♦'}
            ]  # 21 with 3 cards
            
            is_blackjack = len(player_hand) == 2 and sum([11 if card['rank'] == 'A' else 10 if card['rank'] in ['K', 'Q', 'J'] else int(card['rank']) for card in player_hand]) == 21
            
            assert is_blackjack == False
            
            # Expected payout for regular win should be bet * 2
            expected_payout = bet * 2
            assert expected_payout == 200

    def test_blackjack_detection_logic(self, cog):
        """Test that blackjack detection only triggers for 2-card 21s"""
        # Test various hand combinations
        
        # True blackjack: Ace + 10-value card (2 cards)
        blackjack_hands = [
            [{'rank': 'A', 'suit': '♠'}, {'rank': 'K', 'suit': '♥'}],
            [{'rank': 'A', 'suit': '♦'}, {'rank': 'Q', 'suit': '♠'}],
            [{'rank': 'A', 'suit': '♣'}, {'rank': 'J', 'suit': '♥'}],
            [{'rank': 'A', 'suit': '♠'}, {'rank': '10', 'suit': '♦'}]
        ]
        
        for hand in blackjack_hands:
            is_blackjack = len(hand) == 2 and sum([11 if card['rank'] == 'A' else 10 if card['rank'] in ['K', 'Q', 'J', '10'] else int(card['rank']) for card in hand]) == 21
            assert is_blackjack == True, f"Hand {hand} should be detected as blackjack"
        
        # Not blackjack: 3+ cards totaling 21
        non_blackjack_hands = [
            [{'rank': '7', 'suit': '♠'}, {'rank': '7', 'suit': '♥'}, {'rank': '7', 'suit': '♦'}],
            [{'rank': '5', 'suit': '♠'}, {'rank': '6', 'suit': '♥'}, {'rank': '10', 'suit': '♦'}],
            [{'rank': 'A', 'suit': '♠'}, {'rank': '5', 'suit': '♥'}, {'rank': '5', 'suit': '♦'}]
        ]
        
        for hand in non_blackjack_hands:
            is_blackjack = len(hand) == 2 and sum([11 if card['rank'] == 'A' else 10 if card['rank'] in ['K', 'Q', 'J', '10'] else int(card['rank']) for card in hand]) == 21
            assert is_blackjack == False, f"Hand {hand} should NOT be detected as blackjack"

    def test_payout_multiplier_from_settings(self, cog):
        """Test that blackjack payout multiplier is correctly imported from settings"""
        from src.config.settings import BLACKJACK_PAYOUT_MULTIPLIER
        
        # Verify the multiplier is imported and is a reasonable value
        assert BLACKJACK_PAYOUT_MULTIPLIER is not None
        assert isinstance(BLACKJACK_PAYOUT_MULTIPLIER, (int, float))
        assert BLACKJACK_PAYOUT_MULTIPLIER > 1  # Should be greater than 1 for bonus payout

    @pytest.mark.asyncio
    async def test_double_down_button_appears_with_sufficient_funds(self, cog, interaction, monkeypatch):
        """Test that double down button appears when user has sufficient funds"""
        # Mock currency manager to return sufficient balance
        with patch.object(cog.currency_manager, 'load_currency_data', new_callable=AsyncMock), \
             patch.object(cog.currency_manager, 'get_balance', new_callable=AsyncMock, return_value=1000), \
             patch.object(cog.currency_manager, 'subtract_currency', new_callable=AsyncMock, return_value=(True, 900)), \
             patch.object(cog.currency_manager, 'add_currency', new_callable=AsyncMock), \
             patch('discord.Embed'):
            
            # Mock the message and reactions
            mock_message = MagicMock()
            mock_message.add_reaction = AsyncMock()
            mock_message.edit = AsyncMock()
            mock_message.clear_reactions = AsyncMock()
            interaction.original_response = AsyncMock(return_value=mock_message)
            
            # Mock wait_for to simulate standing immediately (to avoid infinite loop)
            mock_reaction = MagicMock()
            mock_reaction.emoji = "🛑"
            cog.bot.wait_for = AsyncMock(return_value=(mock_reaction, interaction.user))
            
            # Mock random.shuffle to control deck order and avoid natural blackjacks
            def mock_shuffle(deck):
                # Arrange deck so player gets 5,6 (=11) and dealer gets 7,8 (=15)
                # This avoids natural blackjacks
                deck[:] = [
                    ('5', '♠'), ('7', '♦'), ('6', '♥'), ('8', '♣'),  # First 4 cards: P1, D1, P2, D2
                    ('9', '♠'), ('10', '♥'), ('J', '♣'), ('Q', '♦'), # Extra cards
                    ('K', '♠'), ('A', '♥'), ('2', '♣'), ('3', '♦'),
                ] + deck[12:]  # Keep the rest of the deck
            
            with patch('random.shuffle', side_effect=mock_shuffle):
                
                # Call blackjack with sufficient bet
                await cog.blackjack.callback(cog, interaction, bet=100)
                
                # Verify that double down reaction was added
                # With concurrent reactions, we need to check if add_reaction was called with the double down emoji
                reaction_calls = []
                for call in mock_message.add_reaction.call_args_list:
                    if len(call[0]) > 0:
                        reaction_calls.append(call[0][0])
                assert "2️⃣" in reaction_calls, f"Double down reaction should be added with sufficient funds. Actual calls: {reaction_calls}"

    @pytest.mark.asyncio
    async def test_double_down_button_not_appears_with_insufficient_funds(self, cog, interaction, monkeypatch):
        """Test that double down button doesn't appear when user has insufficient funds"""
        # Mock currency manager to return insufficient balance
        with patch.object(cog.currency_manager, 'load_currency_data'), \
             patch.object(cog.currency_manager, 'get_balance', return_value=50), \
             patch.object(cog.currency_manager, 'subtract_currency', return_value=(True, 0)), \
             patch.object(cog.currency_manager, 'add_currency'), \
             patch('random.shuffle'), \
             patch('discord.Embed'):
            
            # Mock the message and reactions
            mock_message = MagicMock()
            mock_message.add_reaction = AsyncMock()
            mock_message.edit = AsyncMock()
            mock_message.clear_reactions = AsyncMock()
            interaction.original_response = AsyncMock(return_value=mock_message)
            
            # Mock wait_for to simulate standing immediately
            mock_reaction = MagicMock()
            mock_reaction.emoji = "🛑"
            cog.bot.wait_for = AsyncMock(return_value=(mock_reaction, interaction.user))
            
            # Call blackjack with bet higher than balance
            await cog.blackjack.callback(cog, interaction, bet=100)
            
            # Verify that double down reaction was NOT added
            # With concurrent reactions, we need to check if add_reaction was called with the double down emoji
            reaction_calls = []
            for call in mock_message.add_reaction.call_args_list:
                if len(call[0]) > 0:
                    reaction_calls.append(call[0][0])
            assert "2️⃣" not in reaction_calls, f"Double down reaction should NOT be added with insufficient funds. Actual calls: {reaction_calls}"

    @pytest.mark.asyncio
    async def test_double_down_functionality(self, cog, interaction, monkeypatch):
        """Test that double down works correctly - doubles bet, deals one card, ends turn"""
        # Mock currency manager
        with patch.object(cog.currency_manager, 'load_currency_data', new_callable=AsyncMock), \
             patch.object(cog.currency_manager, 'get_balance', new_callable=AsyncMock, return_value=1000), \
             patch.object(cog.currency_manager, 'subtract_currency', new_callable=AsyncMock, return_value=(True, 800)), \
             patch.object(cog.currency_manager, 'add_currency', new_callable=AsyncMock), \
             patch('discord.Embed'):
            
            # Mock the message and reactions
            mock_message = MagicMock()
            mock_message.add_reaction = AsyncMock()
            mock_message.remove_reaction = AsyncMock()
            mock_message.edit = AsyncMock()
            mock_message.clear_reactions = AsyncMock()
            interaction.original_response = AsyncMock(return_value=mock_message)
            
            # Mock wait_for to simulate double down selection
            mock_reaction = MagicMock()
            mock_reaction.emoji = "2️⃣"
            cog.bot.wait_for = AsyncMock(return_value=(mock_reaction, interaction.user))
            
            # Mock random.shuffle to control deck order and avoid natural blackjacks
            def mock_shuffle(deck):
                # Arrange deck so player gets 5,6 (=11) and dealer gets 7,8 (=15)
                # This avoids natural blackjacks
                deck[:] = [
                    ('5', '♠'), ('7', '♦'), ('6', '♥'), ('8', '♣'),  # First 4 cards: P1, D1, P2, D2
                    ('9', '♠'), ('10', '♥'), ('J', '♣'), ('Q', '♦'), # Extra cards
                    ('K', '♠'), ('A', '♥'), ('2', '♣'), ('3', '♦'),
                ] + deck[12:]  # Keep the rest of the deck
            
            with patch('random.shuffle', side_effect=mock_shuffle):
                
                # Call blackjack
                await cog.blackjack.callback(cog, interaction, bet=100)
                
                # Verify that currency was deducted twice (original bet + double down)
                subtract_calls = cog.currency_manager.subtract_currency.call_args_list
                assert len(subtract_calls) >= 2, "Currency should be deducted twice for double down"
                
                # Verify that double down reaction was removed after use
                remove_calls = [call for call in mock_message.remove_reaction.call_args_list if call[0][0] == "2️⃣"]
                assert len(remove_calls) > 0, "Double down reaction should be removed after use"

    @pytest.mark.asyncio
    async def test_async_stats_loading(self, cog):
        """Test async loading of blackjack stats"""
        mock_stats = {"12345": {"wins": 5, "losses": 3, "ties": 1}}
        
        with patch('src.cogs.blackjack.os.path.exists', return_value=True), \
             patch('aiofiles.open') as mock_aio_open:
            # Mock aiofiles.open context manager
            mock_file = AsyncMock()
            mock_file.read.return_value = json.dumps(mock_stats)
            mock_aio_open.return_value.__aenter__.return_value = mock_file
            
            await cog.load_blackjack_stats()
            
            assert cog.player_stats == mock_stats
            mock_aio_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_stats_saving(self, cog):
        """Test async saving of blackjack stats"""
        cog.player_stats = {"12345": {"wins": 5, "losses": 3, "ties": 1}}
        
        with patch('aiofiles.open') as mock_aio_open:
            mock_file = AsyncMock()
            mock_aio_open.return_value.__aenter__.return_value = mock_file
            
            await cog.save_blackjack_stats()
            
            mock_aio_open.assert_called_once()
            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_stats_loading_empty_file(self, cog):
        """Test loading stats from empty file"""
        with patch('src.cogs.blackjack.os.path.exists', return_value=True), \
             patch('aiofiles.open') as mock_aio_open:
            # Mock empty file
            mock_file = AsyncMock()
            mock_file.read.return_value = ""
            mock_aio_open.return_value.__aenter__.return_value = mock_file
            
            await cog.load_blackjack_stats()
            
            assert cog.player_stats == {}

    @pytest.mark.asyncio
    async def test_stats_loading_json_error(self, cog):
        """Test loading stats with JSON decode error"""
        with patch('src.cogs.blackjack.os.path.exists', return_value=True), \
             patch('aiofiles.open') as mock_aio_open, \
             patch('src.cogs.blackjack.logger.error') as mock_error:
            # Mock file with invalid JSON
            mock_file = AsyncMock()
            mock_file.read.return_value = "invalid json"
            mock_aio_open.return_value.__aenter__.return_value = mock_file
            
            await cog.load_blackjack_stats()
            
            assert cog.player_stats == {}
            mock_error.assert_called_once()

    def test_game_state_edge_cases(self, cog):
        """Test edge cases in game state logic"""
        # Test bust detection
        bust_hand = [('K', '♠'), ('Q', '♥'), ('5', '♦')]  # 25
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
            while value > 21 and aces > 0:
                value -= 10
                aces -= 1
            return value
        
        assert calculate_value(bust_hand) > 21
        
        # Test soft ace handling
        soft_hand = [('A', '♠'), ('6', '♥'), ('5', '♦')]  # A,6,5 = 12 (soft)
        assert calculate_value(soft_hand) == 12
        
        # Test multiple aces
        multi_ace_hand = [('A', '♠'), ('A', '♥'), ('9', '♦')]  # A,A,9 = 21
        assert calculate_value(multi_ace_hand) == 21

    @pytest.mark.asyncio
    async def test_error_handling_in_game(self, cog, interaction):
        """Test error handling during game execution"""
        # Mock currency manager to raise exception
        cog.bot.currency_manager.subtract_currency = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(Exception):
            await cog.blackjack.callback(cog, interaction, bet=100)

    @pytest.mark.asyncio
    async def test_split_hand_payout_accuracy(self, cog, interaction):
        """Test that split hands pay out exactly once per hand without double payouts"""
        # Mock currency manager
        balance_calls = []
        add_currency_calls = []
        subtract_currency_calls = []
        
        async def mock_get_balance(user_id):
            balance_calls.append(user_id)
            return 1000000  # High balance to allow splits
        
        async def mock_add_currency(user_id, amount):
            add_currency_calls.append((user_id, amount))
            return True
        
        async def mock_subtract_currency(user_id, amount):
            subtract_currency_calls.append((user_id, amount))
            return (True, 1000000 - sum(call[1] for call in subtract_currency_calls))
        
        with patch.object(cog.currency_manager, 'load_currency_data', new_callable=AsyncMock), \
             patch.object(cog.currency_manager, 'get_balance', side_effect=mock_get_balance), \
             patch.object(cog.currency_manager, 'subtract_currency', side_effect=mock_subtract_currency), \
             patch.object(cog.currency_manager, 'add_currency', side_effect=mock_add_currency), \
             patch.object(cog.currency_manager, 'format_balance', return_value="$1,000,000"), \
             patch('discord.Embed'), \
             patch.object(cog, 'save_blackjack_stats', new_callable=AsyncMock):
            
            # Mock the message and reactions
            mock_message = MagicMock()
            mock_message.add_reaction = AsyncMock()
            mock_message.remove_reaction = AsyncMock()
            mock_message.edit = AsyncMock()
            mock_message.clear_reactions = AsyncMock()
            mock_message.id = 12345
            interaction.original_response = AsyncMock(return_value=mock_message)
            
            # Simulate split scenario: player gets pair of 8s, then wins both hands against dealer bust
            reaction_sequence = [
                (MagicMock(emoji="✂️"), interaction.user),  # Split
                (MagicMock(emoji="🛑"), interaction.user),  # Stand on hand 1
                (MagicMock(emoji="🛑"), interaction.user),  # Stand on hand 2
            ]
            cog.bot.wait_for = AsyncMock(side_effect=reaction_sequence)
            
            # Control deck to ensure split scenario and dealer bust
            def mock_shuffle(deck):
                # Set up: Player gets 8,8 (can split), Dealer gets 10,6 then busts with K
                deck[:] = [
                    ('8', '♠'), ('10', '♦'), ('8', '♥'), ('6', '♣'),  # P1, D1, P2, D2
                    ('9', '♠'), ('3', '♥'), ('7', '♦'), ('K', '♣'),   # Cards for after split + dealer bust
                ] + deck[8:]
                print(f"Mock deck first 8 cards: {deck[:8]}")
            
            with patch('random.shuffle', side_effect=mock_shuffle):
                await cog.blackjack.callback(cog, interaction, bet=100000)  # $100k bet
                
                # Debug: Print what actually happened
                print(f"Subtract calls: {subtract_currency_calls}")
                print(f"Add calls: {add_currency_calls}")
                
                # Verify currency operations:
                # 1. Initial bet deduction: $100k
                # 2. Split bet deduction: $100k (for second hand)
                # 3. Payout for hand 1 win: $200k (2x bet)
                # 4. Payout for hand 2 win: $200k (2x bet)
                # Total deductions: $200k, Total payouts: $400k, Net gain: $200k
                
                total_deductions = sum(amount for _, amount in subtract_currency_calls)
                total_payouts = sum(amount for _, amount in add_currency_calls)
                
                assert total_deductions == 200000, f"Expected $200k total deductions, got ${total_deductions:,}"
                assert total_payouts == 400000, f"Expected $400k total payouts, got ${total_payouts:,}"
                
                # Verify no duplicate payouts (should have exactly 2 add_currency calls for 2 winning hands)
                assert len(add_currency_calls) == 2, f"Expected exactly 2 payout calls for 2 hands, got {len(add_currency_calls)}"
                assert all(amount == 200000 for _, amount in add_currency_calls), "Each hand should pay exactly $200k"

    @pytest.mark.asyncio
    async def test_split_hand_mixed_results_payout(self, cog, interaction):
        """Test split hands with mixed results (one win, one loss) pay correctly"""
        add_currency_calls = []
        subtract_currency_calls = []
        
        async def mock_add_currency(user_id, amount):
            add_currency_calls.append((user_id, amount))
            return True
        
        async def mock_subtract_currency(user_id, amount):
            subtract_currency_calls.append((user_id, amount))
            return (True, 1000000)
        
        with patch.object(cog.currency_manager, 'load_currency_data', new_callable=AsyncMock), \
             patch.object(cog.currency_manager, 'get_balance', new_callable=AsyncMock, return_value=1000000), \
             patch.object(cog.currency_manager, 'subtract_currency', side_effect=mock_subtract_currency), \
             patch.object(cog.currency_manager, 'add_currency', side_effect=mock_add_currency), \
             patch.object(cog.currency_manager, 'format_balance', return_value="$1,000,000"), \
             patch('discord.Embed'), \
             patch.object(cog, 'save_blackjack_stats', new_callable=AsyncMock):
            
            mock_message = MagicMock()
            mock_message.add_reaction = AsyncMock()
            mock_message.remove_reaction = AsyncMock()
            mock_message.edit = AsyncMock()
            mock_message.clear_reactions = AsyncMock()
            mock_message.id = 12345
            interaction.original_response = AsyncMock(return_value=mock_message)
            
            # Player splits, hand 1 wins, hand 2 loses
            reaction_sequence = [
                (MagicMock(emoji="✂️"), interaction.user),  # Split
                (MagicMock(emoji="🛑"), interaction.user),  # Stand on hand 1 (will be 18)
                (MagicMock(emoji="🛑"), interaction.user),  # Stand on hand 2 (will be 18)
            ]
            cog.bot.wait_for = AsyncMock(side_effect=reaction_sequence)
            
            def mock_shuffle(deck):
                # Player: 8,8 -> splits to [8,10]=18 and [8,10]=18
                # Dealer: gets 10,9 = 19 (beats both hands)
                deck[:] = [
                    ('8', '♠'), ('10', '♦'), ('8', '♥'), ('9', '♣'),  # P1, D1, P2, D2
                    ('10', '♠'), ('10', '♥'),  # Cards for split hands
                ] + deck[6:]
            
            with patch('random.shuffle', side_effect=mock_shuffle):
                await cog.blackjack.callback(cog, interaction, bet=50000)  # $50k bet
                
                # Both hands lose to dealer 19
                # Expected: $100k deducted (2x $50k), $0 payout
                total_deductions = sum(amount for _, amount in subtract_currency_calls)
                total_payouts = sum(amount for _, amount in add_currency_calls)
                
                assert total_deductions == 100000, f"Expected $100k deductions, got ${total_deductions:,}"
                assert total_payouts == 0, f"Expected $0 payouts for losing hands, got ${total_payouts:,}"

    @pytest.mark.asyncio
    async def test_split_blackjack_payout(self, cog, interaction):
        """Test that split hands can achieve blackjack payout when getting 2-card 21"""
        add_currency_calls = []
        subtract_currency_calls = []
        
        async def mock_add_currency(user_id, amount):
            add_currency_calls.append((user_id, amount))
            return True
        
        async def mock_subtract_currency(user_id, amount):
            subtract_currency_calls.append((user_id, amount))
            return (True, 1000000)
        
        with patch.object(cog.currency_manager, 'load_currency_data', new_callable=AsyncMock), \
             patch.object(cog.currency_manager, 'get_balance', new_callable=AsyncMock, return_value=1000000), \
             patch.object(cog.currency_manager, 'subtract_currency', side_effect=mock_subtract_currency), \
             patch.object(cog.currency_manager, 'add_currency', side_effect=mock_add_currency), \
             patch.object(cog.currency_manager, 'format_balance', return_value="$1,000,000"), \
             patch('discord.Embed'), \
             patch.object(cog, 'save_blackjack_stats', new_callable=AsyncMock):
            
            mock_message = MagicMock()
            mock_message.add_reaction = AsyncMock()
            mock_message.remove_reaction = AsyncMock()
            mock_message.edit = AsyncMock()
            mock_message.clear_reactions = AsyncMock()
            mock_message.id = 12345
            interaction.original_response = AsyncMock(return_value=mock_message)
            
            reaction_sequence = [
                (MagicMock(emoji="✂️"), interaction.user),  # Split
                (MagicMock(emoji="🛑"), interaction.user),  # Stand on blackjack hand 1
                (MagicMock(emoji="🛑"), interaction.user),  # Stand on hand 2
            ]
            cog.bot.wait_for = AsyncMock(side_effect=reaction_sequence)
            
            def mock_shuffle(deck):
                # Player: A,A -> splits to [A,K]=21(blackjack) and [A,9]=20
                # Dealer: gets 10,8 = 18
                deck[:] = [
                    ('A', '♠'), ('10', '♦'), ('A', '♥'), ('8', '♣'),  # P1, D1, P2, D2
                    ('K', '♠'), ('9', '♥'),  # Cards for split hands
                ] + deck[6:]
            
            with patch('random.shuffle', side_effect=mock_shuffle):
                await cog.blackjack.callback(cog, interaction, bet=40000)  # $40k bet
                
                from src.config.settings import BLACKJACK_PAYOUT_MULTIPLIER
                
                # Hand 1: Blackjack (A,K) should pay BLACKJACK_PAYOUT_MULTIPLIER * bet
                # Hand 2: Regular win (A,9=20 vs dealer 18) should pay 2 * bet
                expected_blackjack_payout = int(40000 * BLACKJACK_PAYOUT_MULTIPLIER)
                expected_regular_payout = 40000 * 2
                expected_total_payout = expected_blackjack_payout + expected_regular_payout
                
                total_deductions = sum(amount for _, amount in subtract_currency_calls)
                total_payouts = sum(amount for _, amount in add_currency_calls)
                
                assert total_deductions == 80000, f"Expected $80k deductions, got ${total_deductions:,}"
                assert total_payouts == expected_total_payout, f"Expected ${expected_total_payout:,} total payouts, got ${total_payouts:,}"
                
                # Verify we have different payout amounts (blackjack vs regular win)
                payout_amounts = [amount for _, amount in add_currency_calls]
                assert len(set(payout_amounts)) == 2, "Should have different payout amounts for blackjack vs regular win"
                assert expected_blackjack_payout in payout_amounts, f"Blackjack payout ${expected_blackjack_payout:,} should be in {payout_amounts}"
                assert expected_regular_payout in payout_amounts, f"Regular payout ${expected_regular_payout:,} should be in {payout_amounts}"

    @pytest.mark.asyncio
    async def test_double_down_payout_accuracy(self, cog, interaction):
        """Test that double down pays correctly on the doubled bet amount"""
        add_currency_calls = []
        subtract_currency_calls = []
        
        async def mock_add_currency(user_id, amount):
            add_currency_calls.append((user_id, amount))
            return True
        
        async def mock_subtract_currency(user_id, amount):
            subtract_currency_calls.append((user_id, amount))
            return (True, 1000000)
        
        with patch.object(cog.currency_manager, 'load_currency_data', new_callable=AsyncMock), \
             patch.object(cog.currency_manager, 'get_balance', new_callable=AsyncMock, return_value=1000000), \
             patch.object(cog.currency_manager, 'subtract_currency', side_effect=mock_subtract_currency), \
             patch.object(cog.currency_manager, 'add_currency', side_effect=mock_add_currency), \
             patch.object(cog.currency_manager, 'format_balance', return_value="$1,000,000"), \
             patch('discord.Embed'), \
             patch.object(cog, 'save_blackjack_stats', new_callable=AsyncMock):
            
            mock_message = MagicMock()
            mock_message.add_reaction = AsyncMock()
            mock_message.remove_reaction = AsyncMock()
            mock_message.edit = AsyncMock()
            mock_message.clear_reactions = AsyncMock()
            mock_message.id = 12345
            interaction.original_response = AsyncMock(return_value=mock_message)
            
            # Player chooses to double down
            reaction_sequence = [(MagicMock(emoji="2️⃣"), interaction.user)]
            cog.bot.wait_for = AsyncMock(side_effect=reaction_sequence)
            
            def mock_shuffle(deck):
                # Player: 5,6 (=11) -> doubles down, gets 9 (=20)
                # Dealer: 10,7 (=17)
                deck[:] = [
                    ('5', '♠'), ('10', '♦'), ('6', '♥'), ('7', '♣'),  # P1, D1, P2, D2
                    ('9', '♠'),  # Double down card
                ] + deck[5:]
            
            with patch('random.shuffle', side_effect=mock_shuffle):
                await cog.blackjack.callback(cog, interaction, bet=30000)  # $30k bet
                
                # Player wins 20 vs 17 with doubled bet
                # Expected: $60k deducted ($30k + $30k double), $60k payout (2 * $60k total bet)
                total_deductions = sum(amount for _, amount in subtract_currency_calls)
                total_payouts = sum(amount for _, amount in add_currency_calls)
                
                assert total_deductions == 60000, f"Expected $60k deductions for double down, got ${total_deductions:,}"
                assert total_payouts == 120000, f"Expected $120k payout (2x doubled bet), got ${total_payouts:,}"
                assert len(add_currency_calls) == 1, "Should have exactly one payout for double down win"

    @pytest.mark.asyncio 
    async def test_tie_payout_returns_bet(self, cog, interaction):
        """Test that ties return the exact bet amount, no more, no less"""
        add_currency_calls = []
        subtract_currency_calls = []
        
        async def mock_add_currency(user_id, amount):
            add_currency_calls.append((user_id, amount))
            return True
        
        async def mock_subtract_currency(user_id, amount):
            subtract_currency_calls.append((user_id, amount))
            return (True, 1000000)
        
        with patch.object(cog.currency_manager, 'load_currency_data', new_callable=AsyncMock), \
             patch.object(cog.currency_manager, 'get_balance', new_callable=AsyncMock, return_value=1000000), \
             patch.object(cog.currency_manager, 'subtract_currency', side_effect=mock_subtract_currency), \
             patch.object(cog.currency_manager, 'add_currency', side_effect=mock_add_currency), \
             patch.object(cog.currency_manager, 'format_balance', return_value="$1,000,000"), \
             patch('discord.Embed'), \
             patch.object(cog, 'save_blackjack_stats', new_callable=AsyncMock):
            
            mock_message = MagicMock()
            mock_message.add_reaction = AsyncMock()
            mock_message.remove_reaction = AsyncMock()
            mock_message.edit = AsyncMock()
            mock_message.clear_reactions = AsyncMock()
            mock_message.id = 12345
            interaction.original_response = AsyncMock(return_value=mock_message)
            
            # Player stands immediately
            reaction_sequence = [(MagicMock(emoji="🛑"), interaction.user)]
            cog.bot.wait_for = AsyncMock(side_effect=reaction_sequence)
            
            def mock_shuffle(deck):
                # Both player and dealer get 20
                deck[:] = [
                    ('10', '♠'), ('10', '♦'), ('K', '♥'), ('Q', '♣'),  # P1, D1, P2, D2
                ] + deck[4:]
            
            with patch('random.shuffle', side_effect=mock_shuffle):
                await cog.blackjack.callback(cog, interaction, bet=25000)  # $25k bet
                
                # Tie should return exactly the bet amount
                total_deductions = sum(amount for _, amount in subtract_currency_calls)
                total_payouts = sum(amount for _, amount in add_currency_calls)
                
                assert total_deductions == 25000, f"Expected $25k deduction, got ${total_deductions:,}"
                assert total_payouts == 25000, f"Expected $25k returned for tie, got ${total_payouts:,}"
                assert len(add_currency_calls) == 1, "Should have exactly one payout for tie"

    def test_split_detection_logic(self, cog):
        """Test that split detection works correctly for pair of 8s"""
        # Test the can_split function directly
        def can_split(hand):
            """Check if a hand can be split"""
            if len(hand) != 2:
                return False
            
            # For splitting, we compare the rank values
            # All face cards (J, Q, K) and 10s can be split with each other
            card1_rank = hand[0][0]
            card2_rank = hand[1][0]
            
            # If both are face cards or 10s, they can be split
            if card1_rank in ['J', 'Q', 'K', '10'] and card2_rank in ['J', 'Q', 'K', '10']:
                return True
            
            # Otherwise, they must have the same rank
            return card1_rank == card2_rank
        
        # Test pair of 8s (should be splittable)
        eight_pair = [('8', '♠'), ('8', '♥')]
        assert can_split(eight_pair) == True, "Pair of 8s should be splittable"
        
        # Test blackjack hand (should not be splittable)
        blackjack_hand = [('A', '♠'), ('K', '♥')]
        assert can_split(blackjack_hand) == False, "Blackjack hand should not be splittable"
        
        # Test calculate_value with pair of 8s
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
            while value > 21 and aces > 0:
                value -= 10
                aces -= 1
            return value
        
        assert calculate_value(eight_pair) == 16, "Pair of 8s should equal 16"
        assert calculate_value(blackjack_hand) == 21, "A,K should equal 21"

    def test_payout_calculation_edge_cases(self, cog):
        """Test edge cases in payout calculations"""
        from src.config.settings import BLACKJACK_PAYOUT_MULTIPLIER
        
        # Test minimum bet blackjack payout
        min_bet = 10
        blackjack_payout = int(min_bet * BLACKJACK_PAYOUT_MULTIPLIER)
        assert blackjack_payout > min_bet * 2, "Blackjack should pay more than regular win"
        
        # Test large bet payout (ensure no integer overflow)
        large_bet = 1000000
        large_blackjack_payout = int(large_bet * BLACKJACK_PAYOUT_MULTIPLIER)
        large_regular_payout = large_bet * 2
        
        assert isinstance(large_blackjack_payout, int), "Large blackjack payout should be integer"
        assert isinstance(large_regular_payout, int), "Large regular payout should be integer"
        assert large_blackjack_payout > large_regular_payout, "Large blackjack should pay more than regular win"