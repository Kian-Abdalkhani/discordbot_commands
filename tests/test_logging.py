import pytest
import logging
import sys
from unittest.mock import patch, MagicMock
from src.utils.logging import setup_logging


class TestLogging:
    def test_setup_logging_configuration(self):
        """Test that setup_logging configures logging correctly"""
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging()
            
            # Verify basicConfig was called
            mock_basic_config.assert_called_once()
            
            # Get the call arguments
            call_kwargs = mock_basic_config.call_args[1]
            
            # Verify logging level
            assert call_kwargs['level'] == logging.INFO
            
            # Verify format string
            expected_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            assert call_kwargs['format'] == expected_format
            
            # Verify date format
            expected_datefmt = '%Y-%m-%d %I:%M:%S %p'
            assert call_kwargs['datefmt'] == expected_datefmt
            
            # Verify handlers
            assert 'handlers' in call_kwargs
            handlers = call_kwargs['handlers']
            assert len(handlers) == 1
            assert isinstance(handlers[0], logging.StreamHandler)
            assert handlers[0].stream == sys.stdout

    def test_setup_logging_creates_stream_handler(self):
        """Test that setup_logging creates a StreamHandler for stdout"""
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging()
            
            # Get the handlers from the call
            call_kwargs = mock_basic_config.call_args[1]
            handlers = call_kwargs['handlers']
            
            # Verify the handler is configured for stdout
            stream_handler = handlers[0]
            assert stream_handler.stream == sys.stdout

    def test_logging_format_components(self):
        """Test that the logging format includes all expected components"""
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging()
            
            call_kwargs = mock_basic_config.call_args[1]
            format_string = call_kwargs['format']
            
            # Check that all expected format components are present
            assert '%(asctime)s' in format_string
            assert '%(levelname)s' in format_string
            assert '%(name)s' in format_string
            assert '%(message)s' in format_string

    def test_date_format_specification(self):
        """Test that the date format is correctly specified"""
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging()
            
            call_kwargs = mock_basic_config.call_args[1]
            datefmt = call_kwargs['datefmt']
            
            # Verify the date format matches expected pattern
            # Format should be: 2023-05-15 02:32:10 PM
            assert '%Y-%m-%d' in datefmt  # Year-Month-Day
            assert '%I:%M:%S' in datefmt  # Hour:Minute:Second (12-hour format)
            assert '%p' in datefmt        # AM/PM

    def test_logging_level_is_info(self):
        """Test that logging level is set to INFO"""
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging()
            
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs['level'] == logging.INFO

    def test_setup_logging_can_be_called_multiple_times(self):
        """Test that setup_logging can be called multiple times without issues"""
        with patch('logging.basicConfig') as mock_basic_config:
            # Call setup_logging multiple times
            setup_logging()
            setup_logging()
            setup_logging()
            
            # Should be called each time
            assert mock_basic_config.call_count == 3

    def test_imports_are_correct(self):
        """Test that the module imports are working correctly"""
        # This test verifies that the imports in the logging module work
        import src.utils.logging
        
        # Verify the function exists and is callable
        assert hasattr(src.utils.logging, 'setup_logging')
        assert callable(src.utils.logging.setup_logging)

    def test_logging_integration(self):
        """Test that logging actually works after setup"""
        # Set up logging
        setup_logging()
        
        # Create a logger and test it
        logger = logging.getLogger('test_logger')
        
        # Verify the logger has the correct level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        
        # Verify handlers are set up
        assert len(root_logger.handlers) > 0