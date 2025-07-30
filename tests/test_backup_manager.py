import pytest
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
from datetime import datetime, timedelta
from src.utils.backup_manager import BackupManager


class TestBackupManager:
    @pytest.fixture
    def backup_manager(self):
        with patch('src.utils.backup_manager.os.makedirs'):
            return BackupManager()

    @pytest.fixture
    def mock_file_data(self):
        return {
            '/fake/data/currency.json': '{"user1": {"balance": 1000}}',
            '/fake/data/blackjack_stats.json': '{"user1": {"wins": 5}}',
            '/fake/data/hangman_stats.json': '{"user1": {"games": 10}}'
        }

    def test_initialization(self, backup_manager):
        """Test BackupManager initialization"""
        assert backup_manager.data_dir.endswith("data")
        assert backup_manager.backup_dir.endswith("data/backups")
        assert backup_manager.backup_interval == 3600  # 1 hour in seconds
        assert backup_manager._backup_task is None

    @pytest.mark.asyncio
    async def test_initialize(self, backup_manager):
        """Test initialization creates directories and starts task"""
        with patch('src.utils.backup_manager.os.makedirs') as mock_makedirs, \
             patch.object(backup_manager, '_start_backup_task') as mock_start:
            
            await backup_manager.initialize()
            
            mock_makedirs.assert_called_once()
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_backup_success(self, backup_manager, mock_file_data):
        """Test successful backup creation"""
        def mock_listdir(path):
            if path.endswith('data'):
                return ['currency.json', 'blackjack_stats.json', 'hangman_stats.json']
            return []

        def mock_exists(path):
            return path in mock_file_data

        def mock_open_func(path, mode='r'):
            if path in mock_file_data:
                return mock_open(read_data=mock_file_data[path]).return_value
            return mock_open().return_value

        with patch('src.utils.backup_manager.os.listdir', side_effect=mock_listdir), \
             patch('src.utils.backup_manager.os.path.exists', side_effect=mock_exists), \
             patch('builtins.open', mock_open_func), \
             patch('src.utils.backup_manager.shutil.copy2') as mock_copy, \
             patch('src.utils.backup_manager.logger') as mock_logger:

            await backup_manager.create_backup()

            assert mock_copy.call_count == 3  # 3 files copied
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_create_backup_no_files(self, backup_manager):
        """Test backup creation when no data files exist"""
        with patch('src.utils.backup_manager.os.listdir', return_value=[]), \
             patch('src.utils.backup_manager.logger') as mock_logger:

            await backup_manager.create_backup()

            mock_logger.info.assert_called_with("No data files found to backup")

    @pytest.mark.asyncio
    async def test_create_backup_error(self, backup_manager):
        """Test backup creation with error"""
        with patch('src.utils.backup_manager.os.listdir', side_effect=Exception("File error")), \
             patch('src.utils.backup_manager.logger') as mock_logger:

            await backup_manager.create_backup()

            mock_logger.error.assert_called_once()

    def test_cleanup_old_backups(self, backup_manager):
        """Test cleanup of old backup directories"""
        # Create mock backup directories with timestamps
        now = datetime.now()
        old_backup = now - timedelta(days=8)  # Older than 7 days
        recent_backup = now - timedelta(days=3)  # Within 7 days

        mock_dirs = [
            f"backup_{old_backup.strftime('%Y%m%d_%H%M%S')}",
            f"backup_{recent_backup.strftime('%Y%m%d_%H%M%S')}",
            "not_a_backup_dir"
        ]

        with patch('src.utils.backup_manager.os.listdir', return_value=mock_dirs), \
             patch('src.utils.backup_manager.os.path.isdir', return_value=True), \
             patch('src.utils.backup_manager.shutil.rmtree') as mock_rmtree, \
             patch('src.utils.backup_manager.logger') as mock_logger:

            backup_manager._cleanup_old_backups()

            # Only the old backup should be removed
            mock_rmtree.assert_called_once()
            assert old_backup.strftime('%Y%m%d_%H%M%S') in mock_rmtree.call_args[0][0]
            mock_logger.info.assert_called()

    def test_cleanup_old_backups_error(self, backup_manager):
        """Test cleanup with error"""
        with patch('src.utils.backup_manager.os.listdir', side_effect=Exception("List error")), \
             patch('src.utils.backup_manager.logger') as mock_logger:

            backup_manager._cleanup_old_backups()

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_backup_task_loop(self, backup_manager):
        """Test the backup task loop"""
        call_count = 0
        
        async def mock_create_backup():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:  # Stop after 2 calls to avoid infinite loop
                backup_manager._backup_task.cancel()

        with patch.object(backup_manager, 'create_backup', side_effect=mock_create_backup), \
             patch('asyncio.sleep', side_effect=lambda x: None):  # Make sleep return immediately

            try:
                await backup_manager._backup_loop()
            except asyncio.CancelledError:
                pass  # Expected when task is cancelled

            assert call_count == 2

    @pytest.mark.asyncio
    async def test_start_backup_task(self, backup_manager):
        """Test starting backup task"""
        with patch('asyncio.create_task') as mock_create_task:
            backup_manager._start_backup_task()
            
            mock_create_task.assert_called_once()
            assert backup_manager._backup_task is not None

    @pytest.mark.asyncio
    async def test_stop_backup_task(self, backup_manager):
        """Test stopping backup task"""
        # Mock a running task
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        backup_manager._backup_task = mock_task

        await backup_manager.stop()

        mock_task.cancel.assert_called_once()
        assert backup_manager._backup_task is None

    @pytest.mark.asyncio
    async def test_stop_no_task(self, backup_manager):
        """Test stopping when no task is running"""
        backup_manager._backup_task = None

        # Should not raise an exception
        await backup_manager.stop()

        assert backup_manager._backup_task is None