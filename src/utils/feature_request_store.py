import os
import json
import logging
from datetime import datetime


logger = logging.getLogger(__name__)

class FeatureRequestManager:
    def __init__(self):
        self.filepath = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "feature_requests.json")

        self.requests = []
        self.load_requests()

    def load_requests(self):
        """Loads feature requests from file if it exists"""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    self.requests = data.get('requests', [])
                logger.info(f"Loaded {len(self.requests)} feature requests from {self.filepath}")
            else:
                logger.info(f"Feature requests file not found at {self.filepath}, starting with empty list")
        except Exception as e:
            logger.error(f"Error loading feature requests: {e}")

    def add_request(self, name, request_text, user_id=None, username=None):
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
        self.save_requests()
        logger.info(f"Added new feature request from {name}")
        return request_data

    def save_requests(self):
        """Save feature requests to file"""
        try:
            with open(self.filepath, 'w') as f:
                json.dump({
                    'requests': self.requests
                }, f, indent=2)
            logger.info(f"Saved {self.filepath} successfully")
        except Exception as e:
            logger.error(f"Error saving feature requests: {e}")