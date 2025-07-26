import os
import json
import logging
import aiofiles
from datetime import datetime


logger = logging.getLogger(__name__)

class FeatureRequestManager:
    def __init__(self):
        self.filepath = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "feature_requests.json")

        self.requests = []
    
    async def initialize(self):
        """Initialize the feature request manager by loading data"""
        await self.load_requests()

    async def load_requests(self):
        """Loads feature requests from file if it exists"""
        try:
            if os.path.exists(self.filepath):
                async with aiofiles.open(self.filepath, 'r') as f:
                    content = await f.read()
                    data = json.loads(content)
                    self.requests = data.get('requests', [])
                logger.info(f"Loaded {len(self.requests)} feature requests from {self.filepath}")
            else:
                logger.info(f"Feature requests file not found at {self.filepath}, starting with empty list")
        except Exception as e:
            logger.error(f"Error loading feature requests: {e}")

    async def add_request(self, name, request_text, user_id=None, username=None):
        """Add a new feature request"""
        request_data = {
            "id": len(self.requests) + 1,
            "name": name,
            "request": request_text,
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        self.requests.append(request_data)
        await self.save_requests()
        logger.info(f"Added new feature request from {name}")
        return request_data

    async def save_requests(self):
        """Save feature requests to file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            
            async with aiofiles.open(self.filepath, 'w') as f:
                await f.write(json.dumps({
                    'requests': self.requests
                }, indent=2))
            logger.info(f"Saved feature requests to {self.filepath} successfully")
        except Exception as e:
            logger.error(f"Error saving feature requests: {e}")