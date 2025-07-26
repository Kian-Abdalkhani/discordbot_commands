import os
import json
import logging
import aiofiles


logger = logging.getLogger(__name__)

class PermissionManager:
    def __init__(self):
        self.filepath = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "permissions.json")

        self.admins = []
        self.restricted_members = []
    
    async def initialize(self):
        """Initialize the permission manager by loading data"""
        await self.load_permissions()

    async def load_permissions(self):
        """Loads permissions from file if it exists"""
        try:
            if os.path.exists(self.filepath):
                async with aiofiles.open(self.filepath, 'r') as f:
                    content = await f.read()
                    data = json.loads(content)
                    self.admins = data.get('admins', [])
                    self.restricted_members = data.get('restricted', [])
                logger.info(f"Loaded {len(self.admins)} admins and {len(self.restricted_members)} from {self.filepath}")
            else:
                logger.info(f"Permission file not found at {self.filepath}")
        except Exception as e:
            logger.error(f"Error loading permissions: {e}")

    async def save_permissions(self):
        """Save permissions to file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            
            async with aiofiles.open(self.filepath, 'w') as f:
                await f.write(json.dumps({
                    'admins': self.admins,
                    'restricted': self.restricted_members
                }, indent=2))
            logger.info(f"Saved permissions to {self.filepath} successfully")
        except Exception as e:
            logger.error(f"Error saving permissions: {e}")