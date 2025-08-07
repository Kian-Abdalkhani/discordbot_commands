import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import discord
from discord.ext import commands

from src.utils.horse_race_manager import HorseRaceManager, Horse
from src.config.settings import HORSE_STATS, HORSE_RACE_MIN_BET, HORSE_RACE_MAX_BET, BET_TYPES, HORSE_RACE_SCHEDULE
from src.cogs.horse_racing import HorseRacingCog, HorseSelect, BetTypeSelect, BetAmountView, BetView


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
        assert horse.current_stamina == 100.0
        assert not horse.finished

    def test_calculate_odds(self):
        """Test odds calculation based on horse stats"""
        horse_data = HORSE_STATS[0]
        horse = Horse(horse_data, 1)
        
        odds = horse.calculate_odds()
        assert isinstance(odds, float)
        assert odds > 0  # Should be positive, range depends on horse stats

    def test_update_race_position(self):
        """Test that horse position updates during race"""
        horse_data = HORSE_STATS[0]
        horse = Horse(horse_data, 1)
        
        initial_position = horse.position
        initial_stamina = horse.current_stamina
        horse.update_race_position(2.0, 2.0)  # 2 seconds elapsed, 2 second delta
        
        assert horse.position > initial_position
        assert horse.current_stamina < initial_stamina  # Stamina should decrease


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
            assert "bet placed" in message.lower()

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
        # Should be one of the scheduled race days (Tuesday=1, Thursday=3, Saturday=5)
        assert next_race.weekday() in [1, 3, 5]
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
                    
        # Race should eventually finish - use a much larger time to ensure completion
        horses, finished = await manager.update_race(150.0)  # Beyond race duration - horses finish between 60-120s
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


class TestHorseRacingCogNewUI:
    """Test the new UI components and betting flow"""
    
    @pytest_asyncio.fixture
    async def mock_bot(self):
        """Create a mock bot for testing"""
        bot = AsyncMock(spec=commands.Bot)
        bot.currency_manager = AsyncMock()
        bot.currency_manager.get_balance = AsyncMock(return_value=50000)
        bot.currency_manager.subtract_currency = AsyncMock()
        bot.get_user = MagicMock(return_value=None)
        return bot
    
    @pytest_asyncio.fixture 
    async def horse_racing_cog(self, mock_bot):
        """Create a HorseRacingCog for testing"""
        cog = HorseRacingCog(mock_bot)
        # Mock the horse race manager
        cog.horse_race_manager = AsyncMock()
        cog.horse_race_manager.is_betting_time = MagicMock(return_value=True)
        cog.horse_race_manager.race_in_progress = False
        cog.horse_race_manager.get_current_horses = AsyncMock(
            return_value=[Horse(horse_data, i + 1) for i, horse_data in enumerate(HORSE_STATS)]
        )
        cog.horse_race_manager.calculate_payout_odds = MagicMock(
            return_value={i + 1: 2.5 for i in range(len(HORSE_STATS))}
        )
        cog.horse_race_manager.place_bet = AsyncMock(return_value=(True, "Win bet placed: $1,000.00 on Lightning Bolt"))
        return cog
        
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 123456789
        interaction.response = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.followup = AsyncMock()
        return interaction

    @pytest.mark.asyncio
    async def test_horserace_bet_command_with_amount_only(self, horse_racing_cog, mock_interaction):
        """Test the new /horserace_bet command that only takes amount parameter"""
        # Test the command with valid amount
        await horse_racing_cog.horserace_bet.callback(horse_racing_cog, mock_interaction, 1000)
        
        # Should call show_horse_selection with the amount
        mock_interaction.response.send_message.assert_called_once()
        
        # Check that the embed and view were created
        call_args = mock_interaction.response.send_message.call_args
        assert 'embed' in call_args.kwargs
        assert 'view' in call_args.kwargs
        assert call_args.kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_show_horse_selection_insufficient_funds(self, horse_racing_cog, mock_interaction):
        """Test horse selection when user has insufficient funds"""
        # Mock insufficient balance
        horse_racing_cog.currency_manager.get_balance.return_value = 500
        
        await horse_racing_cog.show_horse_selection(mock_interaction, 1000)
        
        # Should send error message
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "Insufficient funds" in call_args[0][0]
        assert call_args.kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_show_horse_selection_betting_closed(self, horse_racing_cog, mock_interaction):
        """Test horse selection when betting is closed"""
        # Mock betting closed
        horse_racing_cog.horse_race_manager.is_betting_time.return_value = False
        
        await horse_racing_cog.show_horse_selection(mock_interaction, 1000)
        
        # Should send error message
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "not currently open" in call_args[0][0]
        assert call_args.kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_show_horse_selection_race_in_progress(self, horse_racing_cog, mock_interaction):
        """Test horse selection when race is in progress"""
        # Mock race in progress
        horse_racing_cog.horse_race_manager.race_in_progress = True
        
        await horse_racing_cog.show_horse_selection(mock_interaction, 1000)
        
        # Should send error message
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "Race is in progress" in call_args[0][0]
        assert call_args.kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_show_horse_selection_success(self, horse_racing_cog, mock_interaction):
        """Test successful horse selection display"""
        await horse_racing_cog.show_horse_selection(mock_interaction, 1000)
        
        # Should send embed with view
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        
        assert 'embed' in call_args.kwargs
        assert 'view' in call_args.kwargs
        assert call_args.kwargs['ephemeral'] is True
        
        # Check embed content
        embed = call_args.kwargs['embed']
        assert "Select Your Horse" in embed.title
        assert "$1,000" in embed.description
    
    @pytest.mark.asyncio 
    async def test_show_bet_type_selection_after_horse_invalid_horse_id(self, horse_racing_cog, mock_interaction):
        """Test bet type selection with invalid horse ID"""
        await horse_racing_cog.show_bet_type_selection_after_horse(mock_interaction, 999, 1000)
        
        # Should edit message with error
        mock_interaction.response.edit_message.assert_called_once()
        call_args = mock_interaction.response.edit_message.call_args
        assert "Invalid horse ID" in call_args.kwargs['content']
    
    @pytest.mark.asyncio
    async def test_show_bet_type_selection_after_horse_success(self, horse_racing_cog, mock_interaction):
        """Test successful bet type selection display after horse selection"""
        await horse_racing_cog.show_bet_type_selection_after_horse(mock_interaction, 1, 1000)
        
        # Should edit message with embed and view
        mock_interaction.response.edit_message.assert_called_once()
        call_args = mock_interaction.response.edit_message.call_args
        
        assert 'embed' in call_args.kwargs
        assert 'view' in call_args.kwargs
        assert call_args.kwargs['content'] is None
        
        # Check embed content
        embed = call_args.kwargs['embed']
        assert "Select Bet Type" in embed.title
        assert "Lightning Bolt" in embed.description
        assert "$1,000" in embed.description
    
    @pytest.mark.asyncio
    async def test_place_bet_with_type_success(self, horse_racing_cog, mock_interaction):
        """Test successful bet placement with type"""
        await horse_racing_cog.place_bet_with_type(mock_interaction, 1, 1000, "win")
        
        # Should subtract currency and edit message with success
        horse_racing_cog.currency_manager.subtract_currency.assert_called_once_with("123456789", 1000)
        
        mock_interaction.response.edit_message.assert_called_once()
        call_args = mock_interaction.response.edit_message.call_args
        
        assert 'embed' in call_args.kwargs
        assert call_args.kwargs['content'] is None
        assert call_args.kwargs['view'] is None
        
        # Check success embed
        embed = call_args.kwargs['embed']
        assert "Bet Placed Successfully" in embed.title
    
    @pytest.mark.asyncio
    async def test_place_bet_with_type_insufficient_funds(self, horse_racing_cog, mock_interaction):
        """Test bet placement with insufficient funds"""
        # Mock insufficient balance
        horse_racing_cog.currency_manager.get_balance.return_value = 500
        
        await horse_racing_cog.place_bet_with_type(mock_interaction, 1, 1000, "win")
        
        # Should edit message with error, no currency subtraction
        horse_racing_cog.currency_manager.subtract_currency.assert_not_called()
        
        mock_interaction.response.edit_message.assert_called_once()
        call_args = mock_interaction.response.edit_message.call_args
        assert "Insufficient funds" in call_args.kwargs['content']
    
    def test_horse_select_initialization(self):
        """Test HorseSelect dropdown initialization"""
        cog = MagicMock()
        horse_select = HorseSelect(1000, cog)
        
        # Should have options for all horses
        assert len(horse_select.options) == len(HORSE_STATS)
        
        # Check first option
        first_option = horse_select.options[0]
        assert "Horse 1: Lightning Bolt" in first_option.label
        assert "⚡" in first_option.description
        assert first_option.value == "1"
    
    def test_bet_type_select_initialization(self):
        """Test BetTypeSelect dropdown initialization"""
        cog = MagicMock()
        bet_type_select = BetTypeSelect(1, 1000, cog)
        
        # Should have options for all bet types
        assert len(bet_type_select.options) == len(BET_TYPES)
        
        # Check that all bet types are included
        option_values = [option.value for option in bet_type_select.options]
        for bet_type in BET_TYPES.keys():
            assert bet_type in option_values
    
    @pytest.mark.asyncio
    async def test_bet_amount_view_initialization(self):
        """Test BetAmountView initialization"""
        cog = MagicMock()
        view = BetAmountView(1000, cog)
        
        # Should have timeout and contain HorseSelect
        assert view.timeout == 300
        assert len(view.children) == 1
        assert isinstance(view.children[0], HorseSelect)
    
    @pytest.mark.asyncio
    async def test_bet_view_initialization(self):
        """Test BetView initialization"""
        cog = MagicMock()
        view = BetView(1, 1000, cog)
        
        # Should have timeout and contain BetTypeSelect  
        assert view.timeout == 300
        assert len(view.children) == 1
        assert isinstance(view.children[0], BetTypeSelect)
    
    @pytest.mark.asyncio
    async def test_horse_select_callback(self, horse_racing_cog):
        """Test HorseSelect callback functionality"""
        # Create HorseSelect and mock interaction
        horse_select = HorseSelect(1000, horse_racing_cog)
        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.user.id = 123456789
        
        # Mock the cog method
        horse_racing_cog.show_bet_type_selection_after_horse = AsyncMock()
        
        # Manually set the values list (this simulates Discord setting it when user selects)
        horse_select._values = ["1"]
        
        # Mock the values property getter
        with patch.object(type(horse_select), 'values', new_callable=lambda: property(lambda self: self._values)):
            await horse_select.callback(mock_interaction)
            
            # Should call the cog method with correct parameters
            horse_racing_cog.show_bet_type_selection_after_horse.assert_called_once_with(mock_interaction, 1, 1000)
    
    @pytest.mark.asyncio
    async def test_bet_type_select_callback(self, horse_racing_cog):
        """Test BetTypeSelect callback functionality"""
        # Create BetTypeSelect and mock interaction
        bet_type_select = BetTypeSelect(1, 1000, horse_racing_cog)
        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.user.id = 123456789
        
        # Mock the cog method
        horse_racing_cog.place_bet_with_type = AsyncMock()
        
        # Manually set the values list (this simulates Discord setting it when user selects)
        bet_type_select._values = ["win"]
        
        # Mock the values property getter
        with patch.object(type(bet_type_select), 'values', new_callable=lambda: property(lambda self: self._values)):
            await bet_type_select.callback(mock_interaction)
            
            # Should call the cog method with correct parameters
            horse_racing_cog.place_bet_with_type.assert_called_once_with(mock_interaction, 1, 1000, "win")
    
    @pytest.mark.asyncio
    async def test_complete_betting_flow_integration(self, horse_racing_cog, mock_interaction):
        """Test the complete betting flow: command -> horse selection -> bet type -> place bet"""
        
        # Step 1: Command called with amount
        await horse_racing_cog.horserace_bet.callback(horse_racing_cog, mock_interaction, 1000)
        
        # Should show horse selection
        assert mock_interaction.response.send_message.called
        
        # Step 2: Horse selected (simulate callback)
        horse_select = HorseSelect(1000, horse_racing_cog)
        horse_select._values = ["1"]
        
        # Reset mock for the next interaction
        mock_interaction.reset_mock()
        
        with patch.object(type(horse_select), 'values', new_callable=lambda: property(lambda self: self._values)):
            await horse_select.callback(mock_interaction)
            
            # Should show bet type selection
            assert mock_interaction.response.is_done.called or mock_interaction.response.edit_message.called
        
        # Step 3: Bet type selected (simulate callback) 
        bet_type_select = BetTypeSelect(1, 1000, horse_racing_cog)
        bet_type_select._values = ["win"]
        
        # Reset mock for the final interaction
        mock_interaction.reset_mock()
        
        with patch.object(type(bet_type_select), 'values', new_callable=lambda: property(lambda self: self._values)):
            await bet_type_select.callback(mock_interaction)
            
            # Should place the bet
            horse_racing_cog.horse_race_manager.place_bet.assert_called_with("123456789", 1, 1000, "win")
            horse_racing_cog.currency_manager.subtract_currency.assert_called_with("123456789", 1000)



class TestBetTypeIntegration:
    """Test bet type functionality with the horse race manager"""
    
    @pytest.mark.asyncio
    async def test_all_bet_types_supported(self):
        """Test that all configured bet types work with the manager"""
        manager = HorseRaceManager()
        
        # Mock file operations
        with patch('aiofiles.open'), patch('os.path.exists', return_value=False):
            await manager.initialize()
        
        # Test each bet type
        with patch.object(manager, 'is_betting_time', return_value=True):
            for bet_type in BET_TYPES.keys():
                success, message = await manager.place_bet("123", 1, 1000, bet_type)
                assert success, f"Bet type {bet_type} should be supported"
                assert bet_type.lower() in message.lower() or BET_TYPES[bet_type]["name"].lower() in message.lower()
    
    @pytest.mark.asyncio 
    async def test_invalid_bet_type(self):
        """Test that invalid bet types are rejected"""
        manager = HorseRaceManager()
        
        # Mock file operations  
        with patch('aiofiles.open'), patch('os.path.exists', return_value=False):
            await manager.initialize()
        
        with patch.object(manager, 'is_betting_time', return_value=True):
            success, message = await manager.place_bet("123", 1, 1000, "invalid_bet_type")
            assert not success
            assert "Invalid bet type" in message
    
    def test_bet_type_odds_calculation(self):
        """Test that different bet types produce different odds"""
        manager = HorseRaceManager()
        horses = [Horse(horse_data, i + 1) for i, horse_data in enumerate(HORSE_STATS)]
        
        win_odds = manager.calculate_payout_odds(horses, "win") 
        place_odds = manager.calculate_payout_odds(horses, "place")
        show_odds = manager.calculate_payout_odds(horses, "show")
        last_odds = manager.calculate_payout_odds(horses, "last")
        
        # All should return valid odds dictionaries
        for odds_dict in [win_odds, place_odds, show_odds, last_odds]:
            assert len(odds_dict) == len(HORSE_STATS)
            for horse_id, payout in odds_dict.items():
                assert isinstance(payout, float)
                assert payout > 1.0  # All payouts should be profitable
        
        # Place odds should generally be lower than win odds (easier to hit)
        for horse_id in range(1, len(HORSE_STATS) + 1):
            assert place_odds[horse_id] <= win_odds[horse_id] * 1.5  # Allow some variance


if __name__ == "__main__":
    pytest.main([__file__])