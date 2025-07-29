import os
import json
import logging
import aiofiles
import asyncio
import shutil
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self):
        # Path to the data directory
        self.data_dir = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data")
        
        # Path to the backup directory
        self.backup_dir = os.path.join(self.data_dir, "backups")
        
        # Backup interval in seconds (1 hour = 3600 seconds)
        self.backup_interval = 3600
        
        # Task for the backup loop
        self._backup_task = None
        
    async def initialize(self):
        """Initialize the backup manager and start the backup loop"""
        await self._ensure_backup_directory()
        await self._start_backup_loop()
        logger.info("BackupManager initialized and backup loop started")
        
    async def _ensure_backup_directory(self):
        """Ensure the backup directory exists"""
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            logger.info(f"Backup directory ensured at {self.backup_dir}")
        except Exception as e:
            logger.error(f"Error creating backup directory: {e}")
            
    async def _start_backup_loop(self):
        """Start the hourly backup loop"""
        if self._backup_task is None or self._backup_task.done():
            self._backup_task = asyncio.create_task(self._backup_loop())
            
    async def _backup_loop(self):
        """Main backup loop that runs every hour"""
        while True:
            try:
                await self.create_backup()
                logger.info(f"Next backup scheduled in {self.backup_interval} seconds")
                await asyncio.sleep(self.backup_interval)
            except asyncio.CancelledError:
                logger.info("Backup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in backup loop: {e}")
                # Wait a bit before retrying to avoid rapid error loops
                await asyncio.sleep(60)
                
    async def create_backup(self):
        """Create a backup of all files in the data directory"""
        try:
            # Create timestamp for backup folder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = os.path.join(self.backup_dir, f"backup_{timestamp}")
            
            # Create the backup folder
            os.makedirs(backup_folder, exist_ok=True)
            
            # Get list of files to backup (exclude the backups directory itself)
            files_to_backup = await self._get_files_to_backup()
            
            if not files_to_backup:
                logger.warning("No files found to backup")
                return
                
            # Copy each file to the backup folder
            backup_count = 0
            for file_path in files_to_backup:
                try:
                    filename = os.path.basename(file_path)
                    backup_file_path = os.path.join(backup_folder, filename)
                    
                    # Use async file operations for consistency
                    async with aiofiles.open(file_path, 'rb') as src:
                        content = await src.read()
                        async with aiofiles.open(backup_file_path, 'wb') as dst:
                            await dst.write(content)
                    
                    backup_count += 1
                    logger.debug(f"Backed up {filename}")
                    
                except Exception as e:
                    logger.error(f"Error backing up {file_path}: {e}")
                    
            logger.info(f"Backup completed: {backup_count} files backed up to {backup_folder}")
            
            # Clean up old backups to prevent disk space issues
            await self._cleanup_old_backups()
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            
    async def _get_files_to_backup(self) -> List[str]:
        """Get list of files in the data directory to backup"""
        files_to_backup = []
        try:
            for item in os.listdir(self.data_dir):
                item_path = os.path.join(self.data_dir, item)
                # Only backup files, not directories (skip the backups directory)
                if os.path.isfile(item_path):
                    files_to_backup.append(item_path)
            logger.debug(f"Found {len(files_to_backup)} files to backup")
        except Exception as e:
            logger.error(f"Error getting files to backup: {e}")
        return files_to_backup
        
    async def _cleanup_old_backups(self, max_backups: int = 168):
        """Clean up old backups, keeping only the most recent ones
        Default keeps 168 backups (7 days * 24 hours)"""
        try:
            backup_folders = []
            for item in os.listdir(self.backup_dir):
                item_path = os.path.join(self.backup_dir, item)
                if os.path.isdir(item_path) and item.startswith("backup_"):
                    backup_folders.append((item_path, os.path.getctime(item_path)))
            
            # Sort by creation time (newest first)
            backup_folders.sort(key=lambda x: x[1], reverse=True)
            
            # Remove old backups if we have more than max_backups
            if len(backup_folders) > max_backups:
                folders_to_remove = backup_folders[max_backups:]
                for folder_path, _ in folders_to_remove:
                    try:
                        shutil.rmtree(folder_path)
                        logger.debug(f"Removed old backup: {os.path.basename(folder_path)}")
                    except Exception as e:
                        logger.error(f"Error removing old backup {folder_path}: {e}")
                        
                logger.info(f"Cleaned up {len(folders_to_remove)} old backups")
                
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
            
    async def get_backup_status(self) -> dict:
        """Get status information about the backup system"""
        try:
            backup_folders = []
            if os.path.exists(self.backup_dir):
                for item in os.listdir(self.backup_dir):
                    item_path = os.path.join(self.backup_dir, item)
                    if os.path.isdir(item_path) and item.startswith("backup_"):
                        backup_folders.append({
                            'name': item,
                            'path': item_path,
                            'created': datetime.fromtimestamp(os.path.getctime(item_path))
                        })
            
            # Sort by creation time (newest first)
            backup_folders.sort(key=lambda x: x['created'], reverse=True)
            
            return {
                'backup_count': len(backup_folders),
                'latest_backup': backup_folders[0] if backup_folders else None,
                'backup_directory': self.backup_dir,
                'backup_interval_hours': self.backup_interval / 3600,
                'is_running': self._backup_task is not None and not self._backup_task.done()
            }
        except Exception as e:
            logger.error(f"Error getting backup status: {e}")
            return {'error': str(e)}
            
    async def stop_backup_loop(self):
        """Stop the backup loop"""
        if self._backup_task and not self._backup_task.done():
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
            logger.info("Backup loop stopped")