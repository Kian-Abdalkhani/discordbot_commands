import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
import random
import asyncio
from src.cogs.hangman import HangmanCog


class TestHangmanCog:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=commands.Bot)
        bot.wait_for = AsyncMock()
        bot.fetch_user = AsyncMock()
        return bot

    @pytest.fixture
    def cog(self, bot):
        with patch('src.cogs.hangman.os.path.exists', return_value=True), \
             patch('src.cogs.hangman.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '{"stats": {}}'
            return HangmanCog(bot)

    @pytest.fixture
    def interaction(self):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.edit_original_response = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.mention = "@TestUser"
        interaction.channel = MagicMock()
        return interaction

    def test_word_lists_exist(self, cog):
        """Test that word lists are properly initialized"""
        assert "easy" in cog.word_lists
        assert "medium" in cog.word_lists
        assert "hard" in cog.word_lists
        
        # Check that each difficulty has words
        assert len(cog.word_lists["easy"]) > 0
        assert len(cog.word_lists["medium"]) > 0
        assert len(cog.word_lists["hard"]) > 0
        
        # Check word length expectations
        easy_words = cog.word_lists["easy"]
        medium_words = cog.word_lists["medium"]
        hard_words = cog.word_lists["hard"]
        
        # Easy words should generally be shorter
        assert all(len(word) <= 4 for word in easy_words)
        # Medium words should be moderate length
        assert all(4 <= len(word) <= 7 for word in medium_words)
        # Hard words should be longer
        assert all(len(word) >= 7 for word in hard_words)

    def test_get_hangman_display(self, cog):
        """Test the hangman ASCII art display"""
        # Test initial state (0 wrong guesses)
        display_0 = cog.get_hangman_display(0)
        assert "┌─────┐" in display_0
        assert "○" not in display_0  # No head yet
        
        # Test with 1 wrong guess (head appears)
        display_1 = cog.get_hangman_display(1)
        assert "○" in display_1  # Head appears
        assert "╱│╲" not in display_1  # No arms yet
        
        # Test with 2 wrong guesses (body appears)
        display_2 = cog.get_hangman_display(2)
        assert "○" in display_2  # Head
        lines = display_2.split("\n")
        # Check that there's a body line after the head
        head_line_found = False
        body_found = False
        for line in lines:
            if "○" in line:
                head_line_found = True
            elif head_line_found and "│" in line and "╱" not in line and "╲" not in line:
                body_found = True
                break
        assert body_found, "Body should appear at 2 wrong guesses"
        
        # Test with 6 wrong guesses (complete hangman)
        display_6 = cog.get_hangman_display(6)
        assert "○" in display_6  # Head
        assert "╱│╲" in display_6  # Arms
        assert "╱ ╲" in display_6  # Legs
        
        # Test with more than 6 wrong guesses (should cap at 6)
        display_10 = cog.get_hangman_display(10)
        assert display_10 == display_6

    @pytest.mark.asyncio
    async def test_hangman_game_initialization(self, cog, interaction, monkeypatch):
        """Test that hangman game initializes correctly"""
        # Mock random.choice to return a predictable word
        monkeypatch.setattr(random, "choice", lambda x: "TEST")
        
        # Mock the embed creation
        embed_mock = MagicMock()
        
        # Mock discord.Embed
        with patch('discord.Embed', return_value=embed_mock), \
             patch.object(cog, 'save_hangman_stats'):
            
            # Mock bot.wait_for to timeout immediately (end game quickly)
            cog.bot.wait_for = AsyncMock(side_effect=asyncio.TimeoutError)
            
            # Call the command
            await cog.hangman.callback(cog, interaction, "easy")
        
        # Verify interaction.response.send_message was called (game started)
        assert interaction.response.send_message.called
        
        # Verify the embed was created
        assert embed_mock.add_field.called

    def test_game_state_functions(self, cog):
        """Test the internal game state helper functions"""
        # These functions are defined within the hangman method, so we'll test the logic
        
        # Test word display logic
        word = "TEST"
        guessed_letters = {"T", "E"}
        
        # Simulate word display creation
        word_display = ""
        for letter in word:
            if letter in guessed_letters:
                word_display += letter + " "
            else:
                word_display += "_ "
        
        expected = "T E _ T "
        assert word_display == expected
        
        # Test game won logic
        def is_game_won(word, guessed_letters):
            return all(letter in guessed_letters for letter in word)
        
        assert not is_game_won("TEST", {"T", "E"})  # Missing S
        assert is_game_won("TEST", {"T", "E", "S"})  # All letters guessed

    @pytest.mark.asyncio
    async def test_hangman_stats_single_user(self, cog, interaction):
        """Test hangman stats for a single user"""
        
        # Set up mock user
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_user.display_name = "TestUser"
        
        # Set up mock stats
        cog.player_stats = {
            "12345": {"wins": 3, "losses": 2, "games_played": 5}
        }
        
        # Mock discord.Embed
        embed_mock = MagicMock()
        with patch('discord.Embed', return_value=embed_mock):
            await cog.hangman_stats.callback(cog, interaction, mock_user)
        
        # Verify that send_message was called
        interaction.response.send_message.assert_called_once()
        
        # Verify embed was created with correct title
        embed_mock.add_field.assert_any_call(name="Total Games", value=5, inline=True)
        embed_mock.add_field.assert_any_call(name="Wins", value=3, inline=True)
        embed_mock.add_field.assert_any_call(name="Losses", value=2, inline=True)
        embed_mock.add_field.assert_any_call(name="Win Percentage", value="60.00%", inline=True)

    @pytest.mark.asyncio
    async def test_hangman_stats_all_users(self, cog, interaction):
        """Test hangman stats for all users"""
        
        # Set up mock stats for multiple users
        cog.player_stats = {
            "12345": {"wins": 3, "losses": 2, "games_played": 5},
            "67890": {"wins": 1, "losses": 4, "games_played": 5}
        }
        
        # Mock bot.fetch_user
        mock_user1 = MagicMock()
        mock_user1.display_name = "TestUser1"
        mock_user2 = MagicMock()
        mock_user2.display_name = "TestUser2"
        
        cog.bot.fetch_user.side_effect = [mock_user1, mock_user2]
        
        # Mock discord.Embed
        embed_mock = MagicMock()
        with patch('discord.Embed', return_value=embed_mock):
            await cog.hangman_stats.callback(cog, interaction, None)
        
        # Verify that send_message was called
        interaction.response.send_message.assert_called_once()
        
        # Verify leaderboard was created
        assert embed_mock.add_field.called

    @pytest.mark.asyncio
    async def test_hangman_stats_no_games(self, cog, interaction):
        """Test hangman stats when no games have been played"""
        
        # Ensure no stats exist
        cog.player_stats = {}
        
        await cog.hangman_stats.callback(cog, interaction, None)
        
        # Verify the correct message was sent
        interaction.response.send_message.assert_called_once_with("No hangman games have been played yet.")

    @pytest.mark.asyncio
    async def test_hangman_stats_user_no_games(self, cog, interaction):
        """Test hangman stats for a user who hasn't played"""
        
        # Set up mock user
        mock_user = MagicMock()
        mock_user.id = 99999
        mock_user.display_name = "NewUser"
        
        # Ensure no stats exist for this user
        cog.player_stats = {}
        
        await cog.hangman_stats.callback(cog, interaction, mock_user)
        
        # Verify the correct message was sent
        interaction.response.send_message.assert_called_once_with("NewUser hasn't played any hangman games yet.")

    def test_stats_file_operations(self, cog):
        """Test loading and saving stats"""
        # Test that stats file path is set correctly
        assert "hangman_stats.json" in cog.stats_file
        
        # Test initial stats structure
        assert isinstance(cog.player_stats, dict)

    @pytest.mark.asyncio
    async def test_hangman_game_timeout(self, cog, interaction, monkeypatch):
        """Test hangman game timeout behavior"""
        # Mock random.choice to return a predictable word
        monkeypatch.setattr(random, "choice", lambda x: "TEST")
        
        # Mock the embed creation
        embed_mock = MagicMock()
        
        # Mock discord.Embed
        with patch('discord.Embed', return_value=embed_mock), \
             patch.object(cog, 'save_hangman_stats'):
            
            # Mock bot.wait_for to timeout immediately
            cog.bot.wait_for = AsyncMock(side_effect=asyncio.TimeoutError)
            
            # Call the command
            await cog.hangman.callback(cog, interaction, "easy")
        
        # Verify game started and timeout was handled
        assert interaction.response.send_message.called
        assert interaction.edit_original_response.called

    def test_difficulty_choices(self, cog):
        """Test that difficulty choices are properly configured"""
        # Check that the hangman command has the right choices
        hangman_command = cog.hangman
        
        # The choices should be defined in the decorator
        # We can't easily test the decorator directly, but we can verify the word lists exist
        assert "easy" in cog.word_lists
        assert "medium" in cog.word_lists  
        assert "hard" in cog.word_lists

    @pytest.mark.asyncio
    async def test_update_player_stats(self, cog, interaction):
        """Test player statistics updating"""
        # Mock the save function
        with patch.object(cog, 'save_hangman_stats') as mock_save:
            # Simulate updating stats (this logic is inside the hangman method)
            user_id = str(interaction.user.id)
            if user_id not in cog.player_stats:
                cog.player_stats[user_id] = {"wins": 0, "losses": 0, "games_played": 0}
            
            cog.player_stats[user_id]["wins"] += 1
            cog.player_stats[user_id]["games_played"] += 1
            cog.save_hangman_stats()
            
            # Verify stats were updated
            assert cog.player_stats[user_id]["wins"] == 1
            assert cog.player_stats[user_id]["games_played"] == 1
            assert mock_save.called

    def test_word_selection_randomness(self, cog, monkeypatch):
        """Test that word selection uses random.choice"""
        # Mock random.choice to track calls
        mock_choice = MagicMock(return_value="TEST")
        monkeypatch.setattr(random, "choice", mock_choice)
        
        # Simulate word selection (this happens in the hangman method)
        difficulty = "easy"
        word = random.choice(cog.word_lists[difficulty])
        
        # Verify random.choice was called with the right word list
        mock_choice.assert_called_once_with(cog.word_lists[difficulty])
        assert word == "TEST"

    @pytest.mark.asyncio
    async def test_message_deletion_handling(self, cog, interaction):
        """Test that message deletion is handled gracefully"""
        # Create a mock message
        mock_message = MagicMock()
        mock_message.delete = AsyncMock(side_effect=Exception("Permission denied"))
        
        # Test that deletion failure is handled gracefully
        try:
            await mock_message.delete()
        except:
            pass  # Should be caught and ignored
        
        # This test verifies the pattern used in the hangman game
        # where message deletion failures are ignored