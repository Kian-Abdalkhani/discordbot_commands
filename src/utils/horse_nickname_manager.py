import json
import asyncio
import aiofiles
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path

from src.config.settings import HORSE_STATS, HORSE_RENAME_DURATION_DAYS

logger = logging.getLogger(__name__)

class HorseNicknameManager:
    def __init__(self, data_file: str = "data/horse_nicknames.json"):
        self.data_file = Path(data_file)
        self.lock = asyncio.Lock()
        self._data = self._load_data()

    def _load_data(self) -> Dict:
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("Invalid data format")
                    
                    if "user_nicknames" not in data:
                        data["user_nicknames"] = {}
                    if "horse_assignments" not in data:
                        data["horse_assignments"] = {}
                    
                    return data
            else:
                return {"user_nicknames": {}, "horse_assignments": {}}
        except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
            logger.warning(f"Error loading horse nicknames data: {e}. Using default structure.")
            return {"user_nicknames": {}, "horse_assignments": {}}

    async def _save_data(self):
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(self.data_file, 'w') as f:
                await f.write(json.dumps(self._data, indent=2))
        except Exception as e:
            logger.error(f"Error saving horse nicknames data: {e}")
            raise

    async def can_user_rename_horse(self, user_id: int) -> Tuple[bool, Optional[str]]:
        async with self.lock:
            await self._cleanup_expired_nicknames()
            
            user_id_str = str(user_id)
            
            if user_id_str in self._data["user_nicknames"]:
                return False, "You already have a horse renamed. Wait for your current nickname to expire before renaming another horse."
            
            return True, None

    async def can_horse_be_renamed(self, horse_index: int) -> Tuple[bool, Optional[str]]:
        async with self.lock:
            await self._cleanup_expired_nicknames()
            
            horse_index_str = str(horse_index)
            
            if horse_index_str in self._data["horse_assignments"]:
                nickname_data = self._data["horse_assignments"][horse_index_str]
                expiry_date = datetime.fromisoformat(nickname_data["expires_at"])
                return False, f"This horse is currently renamed by another user until {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}"
            
            return True, None

    async def rename_horse(self, user_id: int, horse_index: int, nickname: str) -> bool:
        async with self.lock:
            await self._cleanup_expired_nicknames()
            
            # Skip redundant validation - already done in the command
            # The validation methods would try to acquire the same lock causing deadlock
            
            expiry_date = datetime.now() + timedelta(days=HORSE_RENAME_DURATION_DAYS)
            
            user_id_str = str(user_id)
            horse_index_str = str(horse_index)
            
            nickname_data = {
                "nickname": nickname,
                "user_id": user_id,
                "expires_at": expiry_date.isoformat(),
                "original_name": HORSE_STATS[horse_index]["name"]
            }
            
            self._data["user_nicknames"][user_id_str] = {
                "horse_index": horse_index,
                "nickname": nickname,
                "expires_at": expiry_date.isoformat()
            }
            
            self._data["horse_assignments"][horse_index_str] = nickname_data
            
            await self._save_data()
            logger.info(f"Horse {horse_index} renamed to '{nickname}' for user {user_id}")
            return True

    async def get_horse_display_name(self, horse_index: int) -> str:
        async with self.lock:
            await self._cleanup_expired_nicknames()
            
            horse_index_str = str(horse_index)
            
            if horse_index_str in self._data["horse_assignments"]:
                return self._data["horse_assignments"][horse_index_str]["nickname"]
            
            return HORSE_STATS[horse_index]["name"]

    async def get_all_horse_display_names(self) -> Dict[int, str]:
        result = {}
        for i in range(len(HORSE_STATS)):
            result[i] = await self.get_horse_display_name(i)
        return result

    async def get_user_nickname_info(self, user_id: int) -> Optional[Dict]:
        async with self.lock:
            await self._cleanup_expired_nicknames()
            
            user_id_str = str(user_id)
            
            if user_id_str in self._data["user_nicknames"]:
                return self._data["user_nicknames"][user_id_str].copy()
            
            return None

    async def _cleanup_expired_nicknames(self):
        current_time = datetime.now()
        expired_users = []
        expired_horses = []
        
        for user_id, data in self._data["user_nicknames"].items():
            expiry_date = datetime.fromisoformat(data["expires_at"])
            if current_time >= expiry_date:
                expired_users.append(user_id)
        
        for horse_index, data in self._data["horse_assignments"].items():
            expiry_date = datetime.fromisoformat(data["expires_at"])
            if current_time >= expiry_date:
                expired_horses.append(horse_index)
        
        for user_id in expired_users:
            del self._data["user_nicknames"][user_id]
        
        for horse_index in expired_horses:
            del self._data["horse_assignments"][horse_index]
        
        if expired_users or expired_horses:
            await self._save_data()
            logger.info(f"Cleaned up {len(expired_users)} expired user nicknames and {len(expired_horses)} expired horse nicknames")

    async def force_cleanup_expired(self):
        async with self.lock:
            await self._cleanup_expired_nicknames()