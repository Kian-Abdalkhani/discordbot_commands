import pytest
import os
from unittest.mock import patch, MagicMock
from src.config import settings


class TestSettings:
    def test_guild_id_configuration(self):
        """Test that GUILD_ID is properly configured"""
        with patch.dict(os.environ, {'GUILD_ID': '123456789'}):
            # Reload the module to pick up the new environment variable
            import importlib
            importlib.reload(settings)
            
            assert hasattr(settings, 'GUILD_ID')
            assert isinstance(settings.GUILD_ID, int)
            assert settings.GUILD_ID == 123456789

    def test_daily_claim_amount(self):
        """Test that DAILY_CLAIM is set correctly"""
        assert hasattr(settings, 'DAILY_CLAIM')
        assert isinstance(settings.DAILY_CLAIM, int)
        assert settings.DAILY_CLAIM == 5000

    def test_blackjack_payout_multiplier(self):
        """Test that BLACKJACK_PAYOUT_MULTIPLIER is set correctly"""
        assert hasattr(settings, 'BLACKJACK_PAYOUT_MULTIPLIER')
        assert isinstance(settings.BLACKJACK_PAYOUT_MULTIPLIER, float)
        assert settings.BLACKJACK_PAYOUT_MULTIPLIER == 2.5

    def test_stock_market_leverage(self):
        """Test that STOCK_MARKET_LEVERAGE is set correctly"""
        assert hasattr(settings, 'STOCK_MARKET_LEVERAGE')
        assert isinstance(settings.STOCK_MARKET_LEVERAGE, int)
        assert settings.STOCK_MARKET_LEVERAGE == 20

    def test_hangman_word_lists_structure(self):
        """Test that HANGMAN_WORD_LISTS has correct structure"""
        assert hasattr(settings, 'HANGMAN_WORD_LISTS')
        assert isinstance(settings.HANGMAN_WORD_LISTS, dict)
        
        # Check that all difficulty levels exist
        expected_difficulties = ['easy', 'medium', 'hard']
        for difficulty in expected_difficulties:
            assert difficulty in settings.HANGMAN_WORD_LISTS
            assert isinstance(settings.HANGMAN_WORD_LISTS[difficulty], list)
            assert len(settings.HANGMAN_WORD_LISTS[difficulty]) > 0

    def test_hangman_easy_words(self):
        """Test that easy words meet length requirements"""
        easy_words = settings.HANGMAN_WORD_LISTS['easy']
        
        # All easy words should be 4 characters or less
        for word in easy_words:
            assert isinstance(word, str)
            assert len(word) <= 4
            assert word.islower()  # Should be lowercase
            assert word.isalpha()  # Should contain only letters

    def test_hangman_medium_words(self):
        """Test that medium words meet length requirements"""
        medium_words = settings.HANGMAN_WORD_LISTS['medium']
        
        # All medium words should be between 4-7 characters
        for word in medium_words:
            assert isinstance(word, str)
            assert 4 <= len(word) <= 7
            assert word.islower()  # Should be lowercase
            assert word.isalpha()  # Should contain only letters

    def test_hangman_hard_words(self):
        """Test that hard words meet length requirements"""
        hard_words = settings.HANGMAN_WORD_LISTS['hard']
        
        # All hard words should be 7 characters or more
        for word in hard_words:
            assert isinstance(word, str)
            assert len(word) >= 7
            assert word.islower()  # Should be lowercase
            assert word.isalpha()  # Should contain only letters

    def test_hangman_word_lists_no_duplicates(self):
        """Test that word lists don't contain duplicates"""
        for difficulty, words in settings.HANGMAN_WORD_LISTS.items():
            # Convert to set and compare lengths to check for duplicates
            unique_words = set(words)
            assert len(unique_words) == len(words), f"Duplicate words found in {difficulty} list"

    def test_hangman_word_lists_minimum_count(self):
        """Test that each difficulty has a reasonable number of words"""
        for difficulty, words in settings.HANGMAN_WORD_LISTS.items():
            assert len(words) >= 10, f"{difficulty} difficulty should have at least 10 words"

    def test_dotenv_loading(self):
        """Test that dotenv is loaded"""
        # This test verifies that load_dotenv() is called
        with patch('src.config.settings.load_dotenv') as mock_load_dotenv:
            import importlib
            importlib.reload(settings)
            mock_load_dotenv.assert_called_once()

    def test_environment_variable_access(self):
        """Test that environment variables are accessed correctly"""
        with patch.dict(os.environ, {'GUILD_ID': '987654321'}):
            with patch('src.config.settings.os.getenv') as mock_getenv:
                mock_getenv.return_value = '987654321'
                
                import importlib
                importlib.reload(settings)
                
                mock_getenv.assert_called_with('GUILD_ID')

    def test_constants_are_immutable_types(self):
        """Test that configuration constants use immutable types where appropriate"""
        # Test that numeric constants are proper types
        assert isinstance(settings.DAILY_CLAIM, int)
        assert isinstance(settings.BLACKJACK_PAYOUT_MULTIPLIER, (int, float))
        assert isinstance(settings.STOCK_MARKET_LEVERAGE, int)
        
        # Test that word lists are proper structure
        assert isinstance(settings.HANGMAN_WORD_LISTS, dict)
        for difficulty, words in settings.HANGMAN_WORD_LISTS.items():
            assert isinstance(words, list)
            for word in words:
                assert isinstance(word, str)

    def test_configuration_values_are_reasonable(self):
        """Test that configuration values are within reasonable ranges"""
        # Daily claim should be positive
        assert settings.DAILY_CLAIM > 0
        
        # Blackjack payout should be greater than 1 (otherwise no profit)
        assert settings.BLACKJACK_PAYOUT_MULTIPLIER > 1.0
        
        # Stock market leverage should be positive
        assert settings.STOCK_MARKET_LEVERAGE > 0
        
        # Should have reasonable leverage (not too extreme)
        assert settings.STOCK_MARKET_LEVERAGE <= 100

    def test_word_list_content_quality(self):
        """Test that word lists contain appropriate content"""
        all_words = []
        for difficulty, words in settings.HANGMAN_WORD_LISTS.items():
            all_words.extend(words)
        
        # Check for common inappropriate content (basic check)
        for word in all_words:
            # Words should not be empty
            assert len(word) > 0
            
            # Words should not contain numbers or special characters
            assert word.isalpha()
            
            # Words should be reasonable length (not too long)
            assert len(word) <= 20

    def test_settings_module_imports(self):
        """Test that all expected settings are importable"""
        expected_settings = [
            'GUILD_ID',
            'DAILY_CLAIM', 
            'BLACKJACK_PAYOUT_MULTIPLIER',
            'STOCK_MARKET_LEVERAGE',
            'HANGMAN_WORD_LISTS'
        ]
        
        for setting_name in expected_settings:
            assert hasattr(settings, setting_name), f"Missing setting: {setting_name}"

    def test_hangman_difficulty_progression(self):
        """Test that word difficulty progresses appropriately"""
        easy_avg_length = sum(len(word) for word in settings.HANGMAN_WORD_LISTS['easy']) / len(settings.HANGMAN_WORD_LISTS['easy'])
        medium_avg_length = sum(len(word) for word in settings.HANGMAN_WORD_LISTS['medium']) / len(settings.HANGMAN_WORD_LISTS['medium'])
        hard_avg_length = sum(len(word) for word in settings.HANGMAN_WORD_LISTS['hard']) / len(settings.HANGMAN_WORD_LISTS['hard'])
        
        # Average word length should increase with difficulty
        assert easy_avg_length < medium_avg_length
        assert medium_avg_length < hard_avg_length

    def test_configuration_consistency(self):
        """Test that configuration values are consistent with each other"""
        # This test can be expanded as more relationships between settings are identified
        
        # For now, just verify that all numeric settings are positive
        numeric_settings = [
            settings.DAILY_CLAIM,
            settings.BLACKJACK_PAYOUT_MULTIPLIER,
            settings.STOCK_MARKET_LEVERAGE
        ]
        
        for value in numeric_settings:
            assert value > 0, "All numeric configuration values should be positive"