import os
import json
import logging


logger = logging.getLogger(__name__)

class PermissionManager:
    def __init__(self):
        self.filepath = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "permissions.json")

        self.admins = []
        self.restricted_members = []
        self.load_permissions()

    def load_permissions(self):
        """Loads permissions from file if it exists"""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    self.admins = data.get('admins', [])
                    self.restricted_members = data.get('restricted', [])
                logger.info(f"Loaded {len(self.admins)} admins and {len(self.restricted_members)} from {self.filepath}")
            else:
                logger.info(f"Permission file found at {self.filepath}")
        except Exception as e:
            logger.error(f"Error loading permissions: {e}")

    def save_permissions(self):
        """Save quotes to file"""
        try:
            with open(self.filepath, 'w') as f:
                json.dump({
                    'admins': self.admins,
                    'restricted': self.restricted_members
                }, f, indent=2)
            logger.info(f"Saved {self.filepath} successfully")
        except Exception as e:
            logger.error(f"Error saving quotes: {e}")