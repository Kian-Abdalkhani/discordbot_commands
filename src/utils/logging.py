import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import shutil

def setup_logging(file_logging=True):
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if file_logging:
        # Clean up logs older than 7 days
        logs_base_dir = Path('logs')
        if logs_base_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=7)
            for log_dir in logs_base_dir.iterdir():
                if log_dir.is_dir():
                    try:
                        dir_date = datetime.strptime(log_dir.name, '%Y-%m-%d')
                        if dir_date < cutoff_date:
                            shutil.rmtree(log_dir)
                    except ValueError:
                        # Skip directories that don't match the date format
                        continue
        
        # Create logs directory structure
        today = datetime.now().strftime('%Y-%m-%d')
        logs_dir = Path('logs') / today
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create handlers for each log level
        debug_handler = logging.FileHandler(logs_dir / 'debug.log')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)
        
        info_handler = logging.FileHandler(logs_dir / 'info.log')
        info_handler.setLevel(logging.INFO)
        info_handler.addFilter(lambda record: record.levelno == logging.INFO)
        
        warning_handler = logging.FileHandler(logs_dir / 'warning.log')
        warning_handler.setLevel(logging.WARNING)
        warning_handler.addFilter(lambda record: record.levelno == logging.WARNING)
        
        error_handler = logging.FileHandler(logs_dir / 'error.log')
        error_handler.setLevel(logging.ERROR)
        error_handler.addFilter(lambda record: record.levelno >= logging.ERROR)
        
        # Set format for file handlers
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %I:%M:%S %p'
        )
        debug_handler.setFormatter(file_formatter)
        info_handler.setFormatter(file_formatter)
        warning_handler.setFormatter(file_formatter)
        error_handler.setFormatter(file_formatter)
        
        handlers.extend([debug_handler, info_handler, warning_handler, error_handler])
    
    logging.basicConfig(
        level=logging.DEBUG,  # Set to DEBUG to capture all levels
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %I:%M:%S %p',
        handlers=handlers,
        force=True  # Force reconfiguration if already configured
    )