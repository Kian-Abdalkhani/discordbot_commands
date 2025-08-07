import json
import os
import logging
import aiofiles
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import discord

from src.config.settings import (
    HORSE_STATS, HORSE_RACE_MIN_BET, HORSE_RACE_MAX_BET,
    HORSE_RACE_HOUSE_EDGE, HORSE_RACE_DURATION, HORSE_RANDOM_VARIATION, HORSE_RACE_UPDATE_INTERVAL,
    HORSE_RACE_TRACK_LENGTH, HORSE_RACE_SCHEDULE, BET_TYPES, HORSE_RACE_BET_WINDOW
)

logger = logging.getLogger(__name__)

class Horse:
    """Represents a horse with racing stats and current race state"""
    
    def __init__(self, horse_data: Dict, horse_id: int):
        self.id = horse_id
        self.name = horse_data["name"]
        self.speed = horse_data["speed"]
        self.stamina = horse_data["stamina"]
        self.acceleration = horse_data["acceleration"]
        self.color = horse_data["color"]
        
        # Race state
        self.position = 0.0
        self.current_speed = 0.0
        self.energy = 100.0
        self.finished = False
        self.finish_time = None

    def calculate_odds(self) -> float:
        """Calculate winning odds based on horse stats"""
        # Weighted combination of stats (speed most important, then stamina, then acceleration)
        total_stat = (self.speed * 0.5) + (self.stamina * 0.3) + (self.acceleration * 0.2)
        return total_stat

    def update_race_position(self, time_elapsed: float, total_race_time: float):
        """Update horse position during race based on stats and randomness - time-based finish system"""
        if self.finished:
            return
            
        # Calculate expected finish time based on horse stats (60-120 seconds range)
        # Higher stats = faster finish time
        total_stat = (self.speed * 0.5) + (self.stamina * 0.3) + (self.acceleration * 0.2)
        # Base time between 60-120 seconds, with some randomness
        base_finish_time = 120 - (total_stat / 100.0) * 60  # 120 - (0 to 60) = 60 to 120 seconds
        
        # Add random variation (±10 seconds) to make races more interesting
        if not hasattr(self, 'target_finish_time'):
            self.target_finish_time = base_finish_time + random.uniform(-HORSE_RANDOM_VARIATION, HORSE_RANDOM_VARIATION)
            self.target_finish_time = max(60, min(120, self.target_finish_time))  # Clamp to 60-120 seconds
        
        # Check if horse should finish now
        if time_elapsed >= self.target_finish_time and not self.finished:
            self.finished = True
            self.finish_time = self.target_finish_time
            self.position = HORSE_RACE_TRACK_LENGTH  # Horse reaches finish line
        elif not self.finished:
            # Calculate position based on progress toward finish time
            progress = min(time_elapsed / self.target_finish_time, 0.99)  # Don't show 100% until finished
            self.position = progress * HORSE_RACE_TRACK_LENGTH
            
            # Calculate current speed for display purposes
            remaining_time = self.target_finish_time - time_elapsed
            remaining_distance = HORSE_RACE_TRACK_LENGTH - self.position
            self.current_speed = (remaining_distance / max(remaining_time, 0.1)) * 3.6 if remaining_time > 0 else 0

class HorseRaceManager:
    """Manages horse racing events, betting, and payouts"""
    
    def __init__(self):
        self.data_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "horse_racing.json"
        )
        self.race_data = {}
        self.current_race = None
        self.race_in_progress = False
        self.betting_open = False
        self.race_lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize the horse race manager"""
        await self.load_race_data()
        await self.load_current_bets()
        
    async def load_race_data(self):
        """Load race data from JSON file"""
        try:
            if os.path.exists(self.data_file) and os.path.getsize(self.data_file) > 0:
                async with aiofiles.open(self.data_file, 'r') as f:
                    content = await f.read()
                    if content.strip():  # Check if file has content
                        self.race_data = json.loads(content)
                        logger.info(f"Loaded race data from {self.data_file}")
                    else:
                        logger.info(f"Race file is empty, starting with default data")
                        self.race_data = {"races": [], "total_races": 0}
            else:
                logger.info(f"No race file found at {self.data_file}, starting with empty data")
                self.race_data = {"races": [], "total_races": 0}
        except Exception as e:
            logger.error(f"Error loading race data: {e}")
            self.race_data = {"races": [], "total_races": 0}
            
    async def save_race_data(self):
        """Save race data to JSON file"""
        await self.load_race_data()
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            async with aiofiles.open(self.data_file, 'w') as f:
                await f.write(json.dumps(self.race_data, indent=2, default=str))
            logger.info(f"Saved race data to {self.data_file}")
        except Exception as e:
            logger.error(f"Error saving race data: {e}")
            
    async def save_current_bets(self):
        """Save current bets to JSON file asynchronously"""
        try:
            logger.debug("Starting save_current_bets")
            
            # Ensure race_data has current_bets section
            if not hasattr(self, 'current_bets'):
                self.current_bets = {}
                logger.debug("Initialized empty current_bets for saving")
                
            # Update race_data with current bets
            self.race_data["current_bets"] = self.current_bets
            logger.debug(f"Updated race_data with {len(self.current_bets)} user bet records")
            
            # Save to file asynchronously
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            async with aiofiles.open(self.data_file, 'w') as f:
                await f.write(json.dumps(self.race_data, indent=2, default=str))
            logger.debug(f"Successfully saved current bets to {self.data_file}")
            
        except Exception as e:
            logger.error(f"Error saving current bets: {e}", exc_info=True)
            
    async def load_current_bets(self):
        """Load current bets from JSON file"""
        try:
            if "current_bets" in self.race_data:
                self.current_bets = self.race_data["current_bets"]
                logger.info(f"Loaded {len(self.current_bets)} users with active bets")
            else:
                self.current_bets = {}
                logger.info("No current bets found in file")
        except Exception as e:
            logger.error(f"Error loading current bets: {e}")
            self.current_bets = {}
            
    def get_next_race_time(self) -> datetime:
        """Calculate the next scheduled race time from HORSE_RACE_SCHEDULE"""
        now = datetime.now()
        upcoming_races = []
        
        # Check all race times in the current week
        for race_config in HORSE_RACE_SCHEDULE:
            race_day = race_config["day"]
            race_hour = race_config["hour"] 
            race_minute = race_config["minute"]
            
            # Calculate days ahead for this race in current week
            days_ahead = race_day - now.weekday()
            
            # If race day has passed this week, or is today but time has passed
            if days_ahead < 0 or (days_ahead == 0 and now.hour >= race_hour):
                days_ahead += 7  # Move to next week
                
            race_time = now + timedelta(days=days_ahead)
            race_time = race_time.replace(hour=race_hour, minute=race_minute, second=0, microsecond=0)
            upcoming_races.append(race_time)
            
        # Return the earliest upcoming race
        return min(upcoming_races)
        
    def get_next_race_times(self, count: int = 3) -> List[datetime]:
        """Get the next N race times from the schedule"""
        all_upcoming_races = []
        now = datetime.now()
        
        # Generate races for the next few weeks to ensure we get enough
        weeks_to_check = max(2, count // len(HORSE_RACE_SCHEDULE) + 1)
        
        for week_offset in range(weeks_to_check):
            week_start = now + timedelta(weeks=week_offset)
            
            for race_config in HORSE_RACE_SCHEDULE:
                race_day = race_config["day"]
                race_hour = race_config["hour"]
                race_minute = race_config["minute"]
                
                # Calculate days ahead for this race in this week
                days_ahead = race_day - week_start.weekday()
                if week_offset == 0:
                    # For current week, check if race time has passed
                    if days_ahead < 0 or (days_ahead == 0 and now.hour >= race_hour):
                        continue  # Skip past races in current week
                elif days_ahead < 0:
                    days_ahead += 7  # Adjust for next week if needed
                    
                race_time = week_start + timedelta(days=days_ahead)
                race_time = race_time.replace(hour=race_hour, minute=race_minute, second=0, microsecond=0)
                
                # Only add if it's in the future
                if race_time > now:
                    all_upcoming_races.append(race_time)
        
        # Sort by datetime and return the requested count
        all_upcoming_races.sort()
        return all_upcoming_races[:count]
        
    def is_betting_time(self) -> bool:
        """Check if betting is currently allowed (before race starts)"""
        next_race = self.get_next_race_time()
        now = datetime.now()
        # Allow betting starting the configured # of hours before race until race starts
        betting_opens = next_race - timedelta(hours=HORSE_RACE_BET_WINDOW)
        return betting_opens <= now < next_race and not self.race_in_progress
        
    async def get_current_horses(self) -> List[Horse]:
        """Get the current race horses with calculated odds"""
        horses = []
        for i, horse_data in enumerate(HORSE_STATS):
            horse = Horse(horse_data, i + 1)
            horses.append(horse)
        return horses
        
    def calculate_payout_odds(self, horses: List[Horse], bet_type: str = "win") -> Dict[int, float]:
        """Calculate payout odds for each horse with proper house edge and realistic odds"""
        try:
            logger.debug(f"Calculating payout odds for bet_type: {bet_type}")
            
            # Get true probabilities based on horse stats
            probabilities = [horse.calculate_odds() for horse in horses]
            total_prob = sum(probabilities)
            logger.debug(f"Raw probabilities sum: {total_prob}")
            
            # Normalize probabilities to ensure they sum to 1
            normalized_probs = [p / total_prob for p in probabilities]
            logger.debug(f"Normalized probabilities: {normalized_probs}")
            
            # Get bet type configuration
            if bet_type not in BET_TYPES:
                logger.error(f"Invalid bet_type: {bet_type}")
                bet_type = "win"  # Fallback to win
            
            # Apply house edge more aggressively to create realistic odds
            odds = {}
            for i, prob in enumerate(normalized_probs):
                # Adjust probability based on bet type
                if bet_type == "place":
                    # For place bets, each horse has a chance to finish 1st OR 2nd
                    # Approximate this as roughly double the chance compared to win-only
                    adjusted_prob = min(prob * 2, 0.9)  # Cap at 90%
                elif bet_type == "show":
                    # For show bets, each horse has a chance to finish 1st, 2nd, OR 3rd
                    # Approximate this as roughly triple the chance compared to win-only
                    adjusted_prob = min(prob * 3, 0.95)  # Cap at 95%
                elif bet_type == "last":
                    # For last place, invert the probability (worst horse has best chance to finish last)
                    adjusted_prob = abs(1 - prob) / (len(horses) - 1)
                else:  # win
                    adjusted_prob = prob
                
                # Apply house edge by reducing the player's expected return
                house_adjusted_prob = adjusted_prob * (1 + HORSE_RACE_HOUSE_EDGE)
                
                # Convert to payout odds (what player receives per $1 bet)
                payout_multiplier = 1 / house_adjusted_prob if house_adjusted_prob > 0 else 50.0
                
                # Ensure minimum odds of 1.1 (slight profit) and maximum of 50 for longshots
                payout_multiplier = max(1.1, min(50.0, payout_multiplier))
                
                odds[i + 1] = round(payout_multiplier, 1)
                
            logger.debug(f"Calculated odds for {bet_type}: {odds}")
            return odds
            
        except Exception as e:
            logger.error(f"Error calculating payout odds for bet_type {bet_type}: {e}", exc_info=True)
            # Return default odds as fallback
            return {i + 1: 2.0 for i in range(len(horses))}
        
    async def place_bet(self, user_id: str, horse_id: int, amount: int, bet_type: str = "win") -> Tuple[bool, str]:
        """Place a bet on a horse with specified bet type"""
        try:
            logger.info(f"place_bet called - user_id: {user_id}, horse_id: {horse_id}, amount: {amount}, bet_type: {bet_type}")
            
            await self.load_current_bets()
            logger.debug(f"Current bets loaded, race_in_progress: {self.race_in_progress}")
            
            if not self.is_betting_time():
                logger.warning(f"User {user_id} attempted to bet when betting is closed")
                return False, "Betting is not currently open!"
                
            if amount < HORSE_RACE_MIN_BET:
                logger.warning(f"User {user_id} bet amount {amount} below minimum {HORSE_RACE_MIN_BET}")
                return False, f"Minimum bet is ${HORSE_RACE_MIN_BET:,.2f}!"
                
            if amount > HORSE_RACE_MAX_BET:
                logger.warning(f"User {user_id} bet amount {amount} above maximum {HORSE_RACE_MAX_BET}")
                return False, f"Maximum bet is ${HORSE_RACE_MAX_BET:,.2f}!"
                
            if horse_id < 1 or horse_id > len(HORSE_STATS):
                logger.warning(f"User {user_id} invalid horse_id: {horse_id}")
                return False, f"Invalid horse ID! Choose 1-{len(HORSE_STATS)}"
                
            if bet_type not in BET_TYPES:
                logger.warning(f"User {user_id} invalid bet_type: {bet_type}")
                return False, f"Invalid bet type! Choose from: {', '.join(BET_TYPES.keys())}"
                
            # Initialize current race if needed
            if not hasattr(self, 'current_bets'):
                self.current_bets = {}
                logger.debug("Initialized empty current_bets")
                
            # Store bet
            if user_id not in self.current_bets:
                self.current_bets[user_id] = []
                logger.debug(f"Created new bet list for user {user_id}")
                
            bet_data = {
                "horse_id": horse_id,
                "amount": amount,
                "bet_type": bet_type,
                "timestamp": datetime.now()
            }
            
            self.current_bets[user_id].append(bet_data)
            logger.debug(f"Added bet to user {user_id}: {bet_data}")
            
            # Save bets to file immediately (asynchronously)
            logger.debug("Saving current bets to file")
            await self.save_current_bets()
            
            horse_name = HORSE_STATS[horse_id - 1]["name"]
            bet_name = BET_TYPES[bet_type]["name"]
            bet_description = BET_TYPES[bet_type]["description"]
            success_message = f"{bet_name} bet placed: ${amount:,.2f} on {horse_name} ({bet_description})"
            
            logger.info(f"Bet successfully placed for user {user_id}: {success_message}")
            return True, success_message
            
        except Exception as e:
            logger.error(f"Error in place_bet for user {user_id}: {e}", exc_info=True)
            return False, "An error occurred while placing your bet. Please try again."
        
    async def get_user_bets(self, user_id: str) -> List[Dict]:
        """Get all bets for a user"""
        await self.load_current_bets()
        if not hasattr(self, 'current_bets') or user_id not in self.current_bets:
            return []
        return self.current_bets[user_id]
        
    async def get_all_bets(self) -> Dict[str, List[Dict]]:
        """Get all current bets from all users"""
        await self.load_current_bets()
        if not hasattr(self, 'current_bets'):
            return {}
        return self.current_bets
        
    async def format_all_bets_summary(self, all_bets: Dict[str, List[Dict]]) -> str:
        """Format all bets into a readable summary showing individual bets per horse with bet types"""
        if not all_bets:
            return "No bets placed yet"
            
        # Organize bets by horse
        horse_bets = {}
        total_bet_amount = 0
        total_bets = 0
        
        # Group bets by horse
        for user_id, bets in all_bets.items():
            for bet in bets:
                horse_id = bet['horse_id']
                amount = bet['amount']
                bet_type = bet.get('bet_type', 'win')  # Default to win for backward compatibility
                if horse_id not in horse_bets:
                    horse_bets[horse_id] = []
                horse_bets[horse_id].append({
                    'user_id': user_id, 
                    'amount': amount, 
                    'bet_type': bet_type
                })
                total_bet_amount += amount
                total_bets += 1
        
        # Format summary showing individual bets per horse
        summary_lines = []
        
        # Show bets for each horse (ordered by horse ID)
        for horse_id in sorted(horse_bets.keys()):
            horse_name = HORSE_STATS[horse_id - 1]['name']
            horse_color = HORSE_STATS[horse_id - 1]['color']
            bets = horse_bets[horse_id]
            
            # Calculate total for this horse
            horse_total = sum(bet['amount'] for bet in bets)
            
            summary_lines.append(f"{horse_color} **{horse_name}** (Total: {horse_total:,.2f}):")
            
            # Show individual bets with bet type
            for bet in bets:
                bet_type_name = BET_TYPES[bet['bet_type']]['name']
                # Show last 4 digits of user ID for privacy
                summary_lines.append(f"  • User {bet['user_id'][-4:]}: ${bet['amount']:,.2f} ({bet_type_name})")
            
            summary_lines.append("")  # Empty line between horses
            
        summary_lines.append(f"**Grand Total**: {total_bets} bets, ${total_bet_amount:,.2f}")
        return "\n".join(summary_lines)
        
    async def start_race(self) -> List[Horse]:
        """Start a new race and return the horses"""
        async with self.race_lock:
            if self.race_in_progress:
                raise ValueError("Race already in progress!")
                
            self.race_in_progress = True
            self.betting_open = False
            
            # Initialize horses
            horses = await self.get_current_horses()
            self.current_race = {
                "horses": horses,
                "start_time": datetime.now(),
                "finished": False,
                "results": []
            }
            
            return horses
            
    async def update_race(self, time_elapsed: float) -> Tuple[List[Horse], bool]:
        """Update race positions and return (horses, race_finished)"""
        if not self.current_race:
            return [], True
            
        horses = self.current_race["horses"]
        race_finished = False
        
        # Update each horse's position
        for horse in horses:
            horse.update_race_position(time_elapsed, HORSE_RACE_DURATION)
            
        # Check if race is finished (all horses finished)
        finished_horses = [h for h in horses if h.finished]
        if len(finished_horses) == len(horses):
            race_finished = True
            
        if race_finished and not self.current_race["finished"]:
            await self._finish_race(horses)
            
        return horses, race_finished
        
    async def _finish_race(self, horses: List[Horse]):
        """Finish the race and calculate results based on finish times"""
        # Sort horses by finish time (fastest wins)
        sorted_horses = sorted(horses, key=lambda h: h.finish_time or float('inf'))
        
        self.current_race["results"] = [
            {
                "position": i + 1,
                "horse_id": horse.id,
                "horse_name": horse.name,
                "finish_time": horse.finish_time,
                "final_position": horse.position
            }
            for i, horse in enumerate(sorted_horses)
        ]
        
        self.current_race["finished"] = True
        
        # Save race to history
        race_record = {
            "race_id": self.race_data["total_races"] + 1,
            "date": datetime.now(),
            "results": self.current_race["results"],
            "total_bets": len(getattr(self, 'current_bets', {}))
        }
        
        self.race_data["races"].append(race_record)
        self.race_data["total_races"] += 1
        await self.save_race_data()
        
    async def get_race_results(self) -> Optional[List[Dict]]:
        """Get the results of the current race"""
        if not self.current_race or not self.current_race["finished"]:
            return None
        return self.current_race["results"]
        
    async def calculate_payouts(self) -> Dict[str, Dict]:
        """Calculate payouts for all bets based on bet type and finishing positions"""
        if not self.current_race or not self.current_race["finished"]:
            return {}
            
        if not hasattr(self, 'current_bets'):
            return {}
            
        results = self.current_race["results"]
        horses = await self.get_current_horses()
        
        payouts = {}
        
        for user_id, bets in self.current_bets.items():
            user_payout = {"total_winnings": 0, "winning_bets": [], "losing_bets": []}
            
            for bet in bets:
                bet_type = bet.get("bet_type", "win")  # Default to win for backward compatibility
                horse_id = bet["horse_id"]
                amount = bet["amount"]
                
                # Get odds for this bet type
                odds = self.calculate_payout_odds(horses, bet_type)
                
                # Check if this bet won based on the bet type
                bet_won = self._check_bet_win(horse_id, bet_type, results)
                
                if bet_won:
                    # Winning bet
                    winnings = int(amount * odds[horse_id])
                    user_payout["total_winnings"] += winnings
                    user_payout["winning_bets"].append({
                        "horse_id": horse_id,
                        "horse_name": HORSE_STATS[horse_id - 1]["name"],
                        "bet_amount": amount,
                        "bet_type": BET_TYPES[bet_type]["name"],
                        "winnings": winnings,
                        "odds": odds[horse_id]
                    })
                else:
                    # Losing bet
                    user_payout["losing_bets"].append({
                        "horse_id": horse_id,
                        "horse_name": HORSE_STATS[horse_id - 1]["name"],
                        "bet_amount": amount,
                        "bet_type": BET_TYPES[bet_type]["name"]
                    })
                    
            payouts[user_id] = user_payout
            
        return payouts
    
    def _check_bet_win(self, horse_id: int, bet_type: str, results: List[Dict]) -> bool:
        """Check if a bet wins based on the bet type and race results"""
        bet_config = BET_TYPES[bet_type]
        
        # Find the horse's finishing position
        horse_position = None
        for i, result in enumerate(results):
            if result["horse_id"] == horse_id:
                horse_position = i + 1  # Position is 1-indexed
                break
        
        if horse_position is None:
            return False
        
        # Check if the horse finished in a winning position for this bet type
        if bet_type == "last":
            # For last place bets, check if horse finished last
            return horse_position == len(results)
        else:
            # For win, place, show bets, check if position is in the winning positions
            return horse_position in bet_config["positions"]
        
    async def reset_race(self):
        """Reset race state after completion"""
        async with self.race_lock:
            self.current_race = None
            self.race_in_progress = False
            self.betting_open = False
            if hasattr(self, 'current_bets'):
                self.current_bets = {}
                # Clear saved bets from file
                await self.save_current_bets()
                
    def create_race_embed(self, horses: List[Horse], time_elapsed: float) -> discord.Embed:
        """Create Discord embed showing race progress with improved visualization"""
        embed = discord.Embed(
            title="🏇 Horse Race in Progress! 🏇",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        # Create more dynamic track visualization
        track_display = ""
        track_length = 25  # Longer visual track for better spread
        
        # Display horses by ID order (not by position)
        display_horses = sorted(horses, key=lambda h: h.id)
        
        # Get finished horses sorted by finish time to assign place medals
        finished_horses = [h for h in horses if h.finished]
        finished_horses_by_time = sorted(finished_horses, key=lambda h: h.finish_time)
        
        for horse in display_horses:
            progress = min(horse.position / HORSE_RACE_TRACK_LENGTH, 1.0)
            horse_pos = int(progress * track_length)
            
            # Create more visually appealing track with gaps
            track_chars = ["·"] * track_length
            
            # Add some track markers every 5 positions
            for i in range(0, track_length, 5):
                track_chars[i] = "|"
                
            # Place horse
            if horse_pos < track_length:
                track_chars[horse_pos] = horse.color
            else:
                track_chars[-1] = horse.color
                
            track_str = "".join(track_chars)

            if horse.finished:
                # Get the horse's finishing position and add appropriate emoji
                finish_position = finished_horses_by_time.index(horse) + 1
                if finish_position == 1:
                    finish_emoji = "🥇"
                elif finish_position == 2:
                    finish_emoji = "🥈"
                elif finish_position == 3:
                    finish_emoji = "🥉"
                else:
                    # Use number emojis for 4th and beyond
                    number_emojis = ["4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
                    if finish_position <= 8:
                        finish_emoji = number_emojis[finish_position - 4]
                    else:
                        finish_emoji = f"{finish_position}️⃣"
                        
                status = f"{finish_emoji}({horse.finish_time:.1f}s)"
            else:
                status = f"{horse.position:.1f}m"
            
            track_display += f"`{track_str}` - {status} **{horse.name}**\n"
            
        embed.add_field(
            name="🏁 Race Track",
            value=track_display,
            inline=False
        )
        
        # Progress bar showing completion % based on leading horse
        leading_horse = max(horses, key=lambda h: h.position)
        race_completion_percent = min((leading_horse.position / HORSE_RACE_TRACK_LENGTH) * 100, 100.0)
        
        progress_bar_length = 20
        progress_pos = int((race_completion_percent / 100.0) * progress_bar_length)
        progress_bar = "█" * progress_pos + "░" * (progress_bar_length - progress_pos)
        
        embed.add_field(
            name="🏁 Race Progress (Leading Horse)",
            value=f"`{progress_bar}` {race_completion_percent:.1f}%",
            inline=True
        )
        
        # Show current standings with more detail (still sorted by position for standings)
        position_horses = sorted(horses, key=lambda h: (-h.position, h.finish_time or float('inf')))
        standings = []
        for i, horse in enumerate(position_horses[:3]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            if horse.finished:
                standings.append(f"{medal} {horse.color} **{horse.name}** - ({horse.finish_time:.1f}s)")
            else:
                gap = position_horses[0].position - horse.position if i > 0 else 0
                gap_text = f" (-{gap:.1f}m)" if gap > 0.1 else ""
                standings.append(f"{medal} {horse.color} **{horse.name}** - {horse.position:.1f}m{gap_text}")
                
        embed.add_field(
            name="🏆 Current Standings",
            value="\n".join(standings),
            inline=True
        )
        
        return embed
        
    def create_betting_embed(self, horses: List[Horse], bot=None, display_type: str = "stats") -> discord.Embed:
        """Create Discord embed for betting information with all bet types and odds shown under each horse"""
        embed = discord.Embed(
            title="🏇 Horse Racing - Place Your Bets! 🏇",
            description="Multiple races per week! Check the schedule below.",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # Get odds for all bet types
        win_odds = self.calculate_payout_odds(horses, "win")
        place_odds = self.calculate_payout_odds(horses, "place")
        show_odds = self.calculate_payout_odds(horses, "show")
        last_odds = self.calculate_payout_odds(horses, "last")
        
        # Get current bets organized by horse
        horse_bets = {}
        if hasattr(self, 'current_bets'):
            for user_id, bets in self.current_bets.items():
                for bet in bets:
                    horse_id = bet['horse_id']
                    bet_type = bet.get('bet_type', 'win')
                    if horse_id not in horse_bets:
                        horse_bets[horse_id] = []
                    horse_bets[horse_id].append({
                        'user_id': user_id, 
                        'amount': bet['amount'],
                        'bet_type': bet_type
                    })
        
        # Build content based on display_type
        if display_type == "stats":
            # Show only horse stats and odds (more concise)
            horses_info = ""
            for horse in horses:
                horses_info += f"{horse.color} **{horse.id}. {horse.name}**\n"
                horses_info += f"Speed:{horse.speed} | Stamina:{horse.stamina} | Acceleration:{horse.acceleration}\n"
                horses_info += f"Win:{win_odds[horse.id]:.1f}x | Place:{place_odds[horse.id]:.1f}x | "
                horses_info += f"Show:{show_odds[horse.id]:.1f}x | Last:{last_odds[horse.id]:.1f}x\n\n"

            embed.add_field(
                name="🐎 Horses & Odds",
                value=horses_info,
                inline=False
            )
            
        elif display_type == "bets":
            # Show only current bets (truncate if too long)
            if horse_bets:
                bets_info = ""
                for horse in horses:
                    if horse.id in horse_bets:
                        bets_info += f"{horse.color} **{horse.name}**\n"
                        
                        # Group bets by type
                        bet_types = {}
                        for bet in horse_bets[horse.id]:
                            bet_type = bet['bet_type']
                            if bet_type not in bet_types:
                                bet_types[bet_type] = []
                            bet_types[bet_type].append(bet)
                        
                        for bet_type, type_bets in bet_types.items():
                            bet_name = BET_TYPES[bet_type]['name']
                            bets_info += f"  {bet_name}: "
                            bet_strings = []
                            for bet in type_bets:
                                # Get username from bot if available
                                if bot:
                                    user = bot.get_user(int(bet['user_id']))
                                    username = user.display_name if user else f"User {bet['user_id'][-4:]}"
                                else:
                                    username = f"User {bet['user_id'][-4:]}"
                                bet_strings.append(f"{username} ${bet['amount']:,.2f}")
                            bets_info += ", ".join(bet_strings) + "\n"
                        bets_info += "\n"
                        
                        # Check if we're getting close to the character limit
                        if len(bets_info) > 900:
                            bets_info += "... (truncated due to length)"
                            break
                
                embed.add_field(
                    name="🎰 Current Bets",
                    value=bets_info if bets_info else "No bets placed yet.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎰 Current Bets",
                    value="No bets placed yet.",
                    inline=False
                )
        
        # Add bet type explanations
        bet_explanations = ""
        for bet_type, config in BET_TYPES.items():
            bet_explanations += f"**{config['name']}**: {config['description']}\n"
        
        embed.add_field(
            name="📋 Bet Types",
            value=bet_explanations,
            inline=False
        )
        
        next_race = self.get_next_race_time()
        embed.add_field(
            name="Next Race",
            value=f"<t:{int(next_race.timestamp())}:F>",
            inline=True
        )
        
        embed.add_field(
            name="Betting Info",
            value=f"Min bet: ${HORSE_RACE_MIN_BET:,.2f}\nMax bet: ${HORSE_RACE_MAX_BET:,.2f}",
            inline=True
        )
        
        # Show betting status
        if self.is_betting_time():
            embed.add_field(
                name="🎰 Betting Status",
                value="✅ Betting is OPEN!",
                inline=True
            )
        else:
            embed.add_field(
                name="🎰 Betting Status",
                value="❌ Betting is CLOSED",
                inline=True
            )
        
        embed.set_footer(text="Use /horserace_bet to place a bet with different bet types!")
        
        return embed