import os
import json
import logging
import aiofiles
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)

class PermissionManager:
    def __init__(self):
        self.filepath = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "permissions.json")

        self.admins = []
        self.restricted_members = {}
    
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
                    restricted_data = data.get('restricted', [])
                    
                    # Handle backwards compatibility - convert list to dict
                    if isinstance(restricted_data, list):
                        self.restricted_members = {str(user_id): None for user_id in restricted_data}
                    else:
                        self.restricted_members = restricted_data
                logger.info(f"Loaded {len(self.admins)} admins and {len(self.restricted_members)} restricted members from {self.filepath}")
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

    async def add_timeout(self, user_id: int, hours: float = None):
        """Add a user to timeout with optional expiry time"""
        await self.load_permissions()
        user_key = str(user_id)
        
        if hours is None:
            # Permanent timeout
            self.restricted_members[user_key] = None
        else:
            # Timed timeout - calculate expiry timestamp
            expiry_time = datetime.now() + timedelta(hours=hours)
            self.restricted_members[user_key] = expiry_time.isoformat()
        
        await self.save_permissions()

    async def remove_timeout(self, user_id: int):
        """Remove a user from timeout"""
        await self.load_permissions()
        user_key = str(user_id)
        
        if user_key in self.restricted_members:
            del self.restricted_members[user_key]
            await self.save_permissions()
            return True
        return False

    async def is_user_restricted(self, user_id: int) -> bool:
        """Check if user is currently restricted, removing expired timeouts"""
        await self.clean_expired_timeouts()
        return str(user_id) in self.restricted_members

    async def clean_expired_timeouts(self):
        """Remove expired timeouts automatically"""
        await self.load_permissions()
        current_time = datetime.now()
        expired_users = []
        
        for user_id, expiry_str in self.restricted_members.items():
            if expiry_str is not None:  # Skip permanent timeouts
                try:
                    expiry_time = datetime.fromisoformat(expiry_str)
                    if current_time >= expiry_time:
                        expired_users.append(user_id)
                except (ValueError, TypeError):
                    # Handle invalid datetime strings by removing them
                    expired_users.append(user_id)
        
        if expired_users:
            for user_id in expired_users:
                del self.restricted_members[user_id]
            await self.save_permissions()
            logger.info(f"Removed {len(expired_users)} expired timeouts")