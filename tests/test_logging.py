import pytest
import logging
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from datetime import datetime
from src.utils.logging import setup_logging


class TestLogging:
    def setup_method(self):
        """Reset logging configuration before each test"""
        # Clear all existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Reset logging level
        root_logger.setLevel(logging.WARNING)

    def test_setup_logging_default_console_only(self):
        """Test that setup_logging with default parameters only creates console handler"""
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging()
            
            # Verify basicConfig was called
            mock_basic_config.assert_called_once()
            
            # Get the call arguments
            call_kwargs = mock_basic_config.call_args[1]
            
            # Verify logging level is DEBUG to capture all levels
            assert call_kwargs['level'] == logging.DEBUG
            
            # Verify format string
            expected_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            assert call_kwargs['format'] == expected_format
            
            # Verify date format
            expected_datefmt = '%Y-%m-%d %I:%M:%S %p'
            assert call_kwargs['datefmt'] == expected_datefmt
            
            # Verify force=True for reconfiguration
            assert call_kwargs['force'] == True
            
            # Verify only console handler exists
            assert 'handlers' in call_kwargs
            handlers = call_kwargs['handlers']
            assert len(handlers) == 1
            assert isinstance(handlers[0], logging.StreamHandler)
            assert handlers[0].stream == sys.stdout

    def test_setup_logging_file_logging_false_explicit(self):
        """Test that setup_logging with file_logging=False only creates console handler"""
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging(file_logging=False)
            
            call_kwargs = mock_basic_config.call_args[1]
            handlers = call_kwargs['handlers']
            
            # Should only have console handler
            assert len(handlers) == 1
            assert isinstance(handlers[0], logging.StreamHandler)

    @patch('src.utils.logging.datetime')
    @patch('src.utils.logging.Path')
    def test_setup_logging_file_logging_true_creates_directory(self, mock_path_class, mock_datetime):
        """Test that setup_logging with file_logging=True creates proper directory structure"""
        # Mock datetime to return consistent date
        mock_now = MagicMock()
        mock_now.strftime.return_value = '2023-12-25'
        mock_datetime.now.return_value = mock_now
        
        # Mock Path operations
        mock_logs_dir = MagicMock()
        mock_path_class.return_value.__truediv__.return_value = mock_logs_dir
        
        with patch('logging.basicConfig') as mock_basic_config, \
             patch('logging.FileHandler') as mock_file_handler:
            
            setup_logging(file_logging=True)
            
            # Verify directory creation
            mock_path_class.assert_called_with('logs')
            mock_logs_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            
            # Verify date formatting
            mock_datetime.now.assert_called_once()
            mock_now.strftime.assert_called_once_with('%Y-%m-%d')

    @patch('src.utils.logging.datetime')
    @patch('src.utils.logging.Path')
    @patch('logging.FileHandler')
    def test_setup_logging_file_logging_creates_all_handlers(self, mock_file_handler, mock_path_class, mock_datetime):
        """Test that setup_logging with file_logging=True creates handlers for all log levels"""
        # Mock datetime
        mock_now = MagicMock()
        mock_now.strftime.return_value = '2023-12-25'
        mock_datetime.now.return_value = mock_now
        
        # Mock Path operations
        mock_logs_dir = MagicMock()
        mock_path_class.return_value.__truediv__.return_value = mock_logs_dir
        
        # Mock file handler creation
        mock_handlers = [MagicMock() for _ in range(4)]  # debug, info, warning, error
        mock_file_handler.side_effect = mock_handlers
        
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging(file_logging=True)
            
            # Verify FileHandler was called for each log level
            assert mock_file_handler.call_count == 4
            
            # Verify each handler was created with correct file path
            expected_files = ['debug.log', 'info.log', 'warning.log', 'error.log']
            for i, expected_file in enumerate(expected_files):
                mock_file_handler.assert_any_call(mock_logs_dir.__truediv__(expected_file))
            
            # Verify all handlers are passed to basicConfig (1 console + 4 file handlers)
            call_kwargs = mock_basic_config.call_args[1]
            handlers = call_kwargs['handlers']
            assert len(handlers) == 5  # 1 console + 4 file handlers

    @patch('src.utils.logging.datetime')
    @patch('src.utils.logging.Path')
    @patch('logging.FileHandler')
    def test_file_handlers_have_correct_levels_and_filters(self, mock_file_handler, mock_path_class, mock_datetime):
        """Test that file handlers have correct log levels and filters"""
        # Mock datetime
        mock_now = MagicMock()
        mock_now.strftime.return_value = '2023-12-25'
        mock_datetime.now.return_value = mock_now
        
        # Mock Path operations
        mock_logs_dir = MagicMock()
        mock_path_class.return_value.__truediv__.return_value = mock_logs_dir
        
        # Mock file handlers
        mock_debug_handler = MagicMock()
        mock_info_handler = MagicMock()
        mock_warning_handler = MagicMock()
        mock_error_handler = MagicMock()
        mock_file_handler.side_effect = [mock_debug_handler, mock_info_handler, 
                                       mock_warning_handler, mock_error_handler]
        
        with patch('logging.basicConfig'):
            setup_logging(file_logging=True)
            
            # Verify debug handler
            mock_debug_handler.setLevel.assert_called_once_with(logging.DEBUG)
            mock_debug_handler.addFilter.assert_called_once()
            
            # Verify info handler
            mock_info_handler.setLevel.assert_called_once_with(logging.INFO)
            mock_info_handler.addFilter.assert_called_once()
            
            # Verify warning handler
            mock_warning_handler.setLevel.assert_called_once_with(logging.WARNING)
            mock_warning_handler.addFilter.assert_called_once()
            
            # Verify error handler
            mock_error_handler.setLevel.assert_called_once_with(logging.ERROR)
            mock_error_handler.addFilter.assert_called_once()

    def test_log_level_filters_work_correctly(self):
        """Test that the log level filters correctly filter records"""
        # Test debug filter (only DEBUG level)
        debug_record = logging.LogRecord("test", logging.DEBUG, "", 0, "debug msg", (), None)
        info_record = logging.LogRecord("test", logging.INFO, "", 0, "info msg", (), None)
        
        # Create the filter function as it would be in the actual code
        debug_filter = lambda record: record.levelno == logging.DEBUG
        
        assert debug_filter(debug_record) == True
        assert debug_filter(info_record) == False
        
        # Test error filter (ERROR and above)
        error_record = logging.LogRecord("test", logging.ERROR, "", 0, "error msg", (), None)
        critical_record = logging.LogRecord("test", logging.CRITICAL, "", 0, "critical msg", (), None)
        warning_record = logging.LogRecord("test", logging.WARNING, "", 0, "warning msg", (), None)
        
        error_filter = lambda record: record.levelno >= logging.ERROR
        
        assert error_filter(error_record) == True
        assert error_filter(critical_record) == True
        assert error_filter(warning_record) == False

    @patch('src.utils.logging.datetime')
    @patch('src.utils.logging.Path')
    @patch('logging.FileHandler')
    def test_file_handlers_have_correct_formatter(self, mock_file_handler, mock_path_class, mock_datetime):
        """Test that file handlers have the correct formatter applied"""
        # Mock datetime
        mock_now = MagicMock()
        mock_now.strftime.return_value = '2023-12-25'
        mock_datetime.now.return_value = mock_now
        
        # Mock Path operations
        mock_logs_dir = MagicMock()
        mock_path_class.return_value.__truediv__.return_value = mock_logs_dir
        
        # Mock file handlers
        mock_handlers = [MagicMock() for _ in range(4)]
        mock_file_handler.side_effect = mock_handlers
        
        with patch('logging.basicConfig'), \
             patch('logging.Formatter') as mock_formatter:
            
            setup_logging(file_logging=True)
            
            # Verify formatter was created with correct format
            mock_formatter.assert_called_once_with(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %I:%M:%S %p'
            )
            
            # Verify all file handlers got the formatter
            for handler in mock_handlers:
                handler.setFormatter.assert_called_once_with(mock_formatter.return_value)

    def test_setup_logging_multiple_calls_with_force_true(self):
        """Test that setup_logging can be called multiple times due to force=True"""
        with patch('logging.basicConfig') as mock_basic_config:
            setup_logging()
            setup_logging()
            setup_logging(file_logging=True)
            
            # Should be called each time due to force=True
            assert mock_basic_config.call_count == 3
            
            # Verify force=True in all calls
            for call in mock_basic_config.call_args_list:
                assert call[1]['force'] == True

    @patch('src.utils.logging.Path')
    def test_directory_creation_with_parents_and_exist_ok(self, mock_path_class):
        """Test that directory creation uses parents=True and exist_ok=True"""
        mock_logs_dir = MagicMock()
        mock_path_class.return_value.__truediv__.return_value = mock_logs_dir
        
        with patch('logging.basicConfig'), \
             patch('logging.FileHandler'), \
             patch('src.utils.logging.datetime') as mock_datetime:
            
            mock_now = MagicMock()
            mock_now.strftime.return_value = '2023-12-25'
            mock_datetime.now.return_value = mock_now
            
            setup_logging(file_logging=True)
            
            # Verify mkdir was called with correct parameters
            mock_logs_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch('src.utils.logging.Path')
    def test_directory_creation_permission_error_handling(self, mock_path_class):
        """Test handling of permission errors during directory creation"""
        mock_logs_dir = MagicMock()
        mock_logs_dir.mkdir.side_effect = PermissionError("Permission denied")
        mock_path_class.return_value.__truediv__.return_value = mock_logs_dir
        
        with patch('logging.basicConfig'), \
             patch('src.utils.logging.datetime') as mock_datetime:
            
            mock_now = MagicMock()
            mock_now.strftime.return_value = '2023-12-25'
            mock_datetime.now.return_value = mock_now
            
            # Should raise the PermissionError
            with pytest.raises(PermissionError):
                setup_logging(file_logging=True)

    def test_console_logging_still_works_with_file_logging(self):
        """Test that console logging continues to work when file logging is enabled"""
        with patch('logging.basicConfig') as mock_basic_config, \
             patch('src.utils.logging.Path'), \
             patch('logging.FileHandler'), \
             patch('src.utils.logging.datetime') as mock_datetime:
            
            mock_now = MagicMock()
            mock_now.strftime.return_value = '2023-12-25'
            mock_datetime.now.return_value = mock_now
            
            setup_logging(file_logging=True)
            
            # Verify console handler is still present
            call_kwargs = mock_basic_config.call_args[1]
            handlers = call_kwargs['handlers']
            
            # Should have 1 console handler + 4 file handlers
            console_handlers = [h for h in handlers if isinstance(h, logging.StreamHandler)]
            assert len(console_handlers) == 1
            assert console_handlers[0].stream == sys.stdout

    def test_daily_directory_structure(self):
        """Test that the directory structure uses the correct date format"""
        with patch('src.utils.logging.datetime') as mock_datetime, \
             patch('src.utils.logging.Path') as mock_path_class, \
             patch('logging.basicConfig'), \
             patch('logging.FileHandler'):
            
            # Test different dates
            test_cases = [
                ('2023-01-01', '2023-01-01'),
                ('2023-12-31', '2023-12-31'),
                ('2024-02-29', '2024-02-29'),  # Leap year
            ]
            
            for date_str, expected_dir in test_cases:
                mock_now = MagicMock()
                mock_now.strftime.return_value = date_str
                mock_datetime.now.return_value = mock_now
                
                mock_logs_dir = MagicMock()
                mock_path_class.return_value.__truediv__.return_value = mock_logs_dir
                
                setup_logging(file_logging=True)
                
                # Verify the path construction
                mock_path_class.assert_called_with('logs')
                mock_path_class.return_value.__truediv__.assert_called_with(expected_dir)

    def test_imports_are_correct(self):
        """Test that the module imports are working correctly"""
        import src.utils.logging
        
        # Verify the function exists and is callable
        assert hasattr(src.utils.logging, 'setup_logging')
        assert callable(src.utils.logging.setup_logging)

    def test_logging_integration_console_only(self):
        """Test that logging actually works after setup with console only"""
        setup_logging()
        
        # Create a logger and test it
        logger = logging.getLogger('test_logger')
        
        # Verify the root logger has the correct level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        
        # Verify handlers are set up
        assert len(root_logger.handlers) > 0
        
        # Verify we can log messages
        try:
            logger.debug("Test debug message")
            logger.info("Test info message")
            logger.warning("Test warning message")
            logger.error("Test error message")
        except Exception as e:
            pytest.fail(f"Logging failed with exception: {e}")

    def test_format_string_components(self):
        """Test that the format string contains all expected components"""
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
            assert '%Y-%m-%d' in datefmt  # Year-Month-Day
            assert '%I:%M:%S' in datefmt  # Hour:Minute:Second (12-hour format)
            assert '%p' in datefmt        # AM/PM