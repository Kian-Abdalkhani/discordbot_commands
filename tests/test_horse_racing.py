import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.utils.horse_race_manager import HorseRaceManager, Horse
from src.config.settings import HORSE_STATS, HORSE_RACE_MIN_BET, HORSE_RACE_MAX_BET


class TestHorse:
    def test_horse_initialization(self):
        """Test that horses are initialized correctly"""
        horse_data = HORSE_STATS[0]
        horse = Horse(horse_data, 1)
        
        assert horse.id == 1
        assert horse.name == horse_data["name"]
        assert horse.speed == horse_data["speed"]
        assert horse.stamina == horse_data["stamina"]
        assert horse.acceleration == horse_data["acceleration"]
        assert horse.color == horse_data["color"]
        assert horse.position == 0.0
        assert horse.energy == 100.0
        assert not horse.finished

    def test_calculate_odds(self):
        """Test odds calculation based on horse stats"""
        horse_data = HORSE_STATS[0]
        horse = Horse(horse_data, 1)
        
        odds = horse.calculate_odds()
        assert isinstance(odds, float)
        assert 0 < odds <= 1.0

    def test_update_race_position(self):
        """Test that horse position updates during race"""
        horse_data = HORSE_STATS[0]
        horse = Horse(horse_data, 1)
        
        initial_position = horse.position
        horse.update_race_position(2.0, 20.0)
        
        assert horse.position > initial_position
        # Energy is no longer used in the time-based system, test target_finish_time instead
        assert hasattr(horse, 'target_finish_time')
        assert horse.target_finish_time is not None


class TestHorseRaceManager:
    @pytest.mark.asyncio
    async def create_race_manager(self):
        """Create a race manager for testing"""
        manager = HorseRaceManager()
        # Mock the file operations
        with patch('aiofiles.open'), patch('os.path.exists', return_value=False):
            await manager.initialize()
        return manager

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test race manager initialization"""
        manager = await self.create_race_manager()
        assert manager.race_data == {"races": [], "total_races": 0}
        assert not manager.race_in_progress
        assert not manager.betting_open

    @pytest.mark.asyncio
    async def test_get_current_horses(self):
        """Test getting current horses"""
        manager = await self.create_race_manager()
        horses = await manager.get_current_horses()
        
        assert len(horses) == len(HORSE_STATS)
        for i, horse in enumerate(horses):
            assert horse.id == i + 1
            assert horse.name == HORSE_STATS[i]["name"]

    @pytest.mark.asyncio
    async def test_calculate_payout_odds(self):
        """Test payout odds calculation"""
        manager = await self.create_race_manager()
        horses = [Horse(horse_data, i + 1) for i, horse_data in enumerate(HORSE_STATS)]
        odds = manager.calculate_payout_odds(horses)
        
        assert len(odds) == len(HORSE_STATS)
        for horse_id, payout in odds.items():
            assert isinstance(payout, float)
            assert payout > 1.0  # Should be greater than 1x for payouts

    @pytest.mark.asyncio
    async def test_place_bet_validation(self):
        """Test bet placement validation"""
        manager = await self.create_race_manager()
        
        # Mock betting time to be open
        with patch.object(manager, 'is_betting_time', return_value=True):
            # Test minimum bet validation
            success, message = await manager.place_bet("123", 1, HORSE_RACE_MIN_BET - 1)
            assert not success
            assert "Minimum bet" in message
            
            # Test maximum bet validation
            success, message = await manager.place_bet("123", 1, HORSE_RACE_MAX_BET + 1)
            assert not success
            assert "Maximum bet" in message
            
            # Test invalid horse ID
            success, message = await manager.place_bet("123", 0, 1000)
            assert not success
            assert "Invalid horse ID" in message
            
            # Test valid bet
            success, message = await manager.place_bet("123", 1, 1000)
            assert success
            assert "Bet placed" in message

    @pytest.mark.asyncio
    async def test_place_bet_when_closed(self):
        """Test bet placement when betting is closed"""
        manager = await self.create_race_manager()
        
        # Mock betting time to be closed
        with patch.object(manager, 'is_betting_time', return_value=False):
            success, message = await manager.place_bet("123", 1, 1000)
            assert not success
            assert "not currently open" in message

    @pytest.mark.asyncio 
    async def test_get_next_race_time(self):
        """Test next race time calculation"""
        manager = await self.create_race_manager()
        next_race = manager.get_next_race_time()
        
        assert isinstance(next_race, datetime)
        assert next_race > datetime.now()
        assert next_race.weekday() == 5  # Saturday
        assert next_race.hour == 20  # 8 PM
        assert next_race.minute == 0

    @pytest.mark.asyncio
    async def test_start_race(self):
        """Test starting a race"""
        manager = await self.create_race_manager()
        horses = await manager.start_race()
        
        assert len(horses) == len(HORSE_STATS)
        assert manager.race_in_progress
        assert not manager.betting_open
        assert manager.current_race is not None

    @pytest.mark.asyncio
    async def test_start_race_when_in_progress(self):
        """Test that starting a race when one is in progress raises error"""
        manager = await self.create_race_manager()
        await manager.start_race()
        
        with pytest.raises(ValueError, match="Race already in progress"):
            await manager.start_race()

    @pytest.mark.asyncio
    async def test_get_user_bets(self):
        """Test getting user bets"""
        manager = await self.create_race_manager()
        
        # No bets initially
        bets = await manager.get_user_bets("123")
        assert bets == []
        
        # Add a bet
        with patch.object(manager, 'is_betting_time', return_value=True):
            await manager.place_bet("123", 1, 1000)
            
        bets = await manager.get_user_bets("123")
        assert len(bets) == 1
        assert bets[0]["horse_id"] == 1
        assert bets[0]["amount"] == 1000

    @pytest.mark.asyncio
    async def test_race_workflow(self):
        """Test complete race workflow"""
        manager = await self.create_race_manager()
        
        # Place some bets
        with patch.object(manager, 'is_betting_time', return_value=True):
            await manager.place_bet("123", 1, 1000)
            await manager.place_bet("456", 2, 2000)
        
        # Start race
        horses = await manager.start_race()
        assert len(horses) == len(HORSE_STATS)
        
        # Update race a few times
        for i in range(3):
            time_elapsed = (i + 1) * 2.0
            horses, finished = await manager.update_race(time_elapsed)
            
            # Check that horses are moving
            for horse in horses:
                if not finished:
                    assert horse.position >= 0
                    
        # Race should eventually finish
        horses, finished = await manager.update_race(25.0)  # Beyond race duration
        assert finished
        
        # Check results
        results = await manager.get_race_results()
        assert results is not None
        assert len(results) == len(HORSE_STATS)
        assert results[0]["position"] == 1  # Winner is first
        
        # Check payouts
        payouts = await manager.calculate_payouts()
        assert isinstance(payouts, dict)
        
        # Reset race
        await manager.reset_race()
        assert not manager.race_in_progress
        assert manager.current_race is None


if __name__ == "__main__":
    pytest.main([__file__])