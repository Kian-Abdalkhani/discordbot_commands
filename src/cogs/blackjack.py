import random
import asyncio
import discord
import json
import os
import aiofiles
from discord.ext import commands
from discord import app_commands
import logging

from src.config.settings import GUILD_ID
from src.config.settings import BLACKJACK_PAYOUT_MULTIPLIER

logger = logging.getLogger(__name__)


class BlackjackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dictionary to store blackjack statistics for each player
        # Format: {user_id: {"wins": 0, "losses": 0, "ties": 0}}
        self.player_stats = {}
        self.stats_file = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "blackjack_stats.json")
        
        # Initialize currency manager
        self.currency_manager = bot.currency_manager
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        await self.load_blackjack_stats()

    async def load_blackjack_stats(self):
        """Load blackjack stats from JSON file"""
        try:
            if os.path.exists(self.stats_file):
                async with aiofiles.open(self.stats_file, 'r') as f:
                    content = await f.read()
                    self.player_stats = json.loads(content)
                logger.info(f"Loaded blackjack stats from {self.stats_file}")
            else:
                logger.info(f"No blackjack stats file found at {self.stats_file}, starting with empty stats")
        except Exception as e:
            logger.error(f"Error loading blackjack stats: {e}")
            self.player_stats = {}

    async def save_blackjack_stats(self):
        """Save blackjack stats to JSON file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)

            async with aiofiles.open(self.stats_file, 'w') as f:
                await f.write(json.dumps(self.player_stats, indent=4))
            logger.info(f"Saved blackjack stats to {self.stats_file}")
        except Exception as e:
            logger.error(f"Error saving blackjack stats: {e}")

    @app_commands.command(name="blackjack", description="Plays a game of blackjack with betting")
    @app_commands.describe(bet="Amount to bet (default: 100)")
    async def blackjack(self, interaction: discord.Interaction, bet: int = 100):
        """Plays a game of blackjack with betting"""
        user_id = str(interaction.user.id)
        
        # Validate bet amount
        if bet < 10:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Minimum bet is $10!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await self.currency_manager.load_currency_data()
        # Check if user has enough currency
        current_balance = await self.currency_manager.get_balance(user_id)
        if current_balance < bet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You need ${bet:,} to play but only have {self.currency_manager.format_balance(current_balance)}!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Deduct bet from user's balance
        success, new_balance = await self.currency_manager.subtract_currency(user_id, bet)
        if not success:
            embed = discord.Embed(
                title="❌ Transaction Failed",
                description="Failed to process bet. Please try again.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        logger.info(f"{interaction.user} started a blackjack game with bet ${bet}")

        # Card representations
        suits = ['♥', '♦', '♣', '♠']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

        # Create and shuffle the deck
        deck = [(rank, suit) for suit in suits for rank in ranks]
        random.shuffle(deck)

        # Deal initial cards
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        
        # Initialize game state variables
        doubled_down = False
        is_split = False
        player_hands = [player_hand]  # List to handle multiple hands when split
        current_hand_index = 0
        split_bets = [bet]  # Track bets for each hand

        # Function to calculate hand value
        def calculate_value(hand):
            value = 0
            aces = 0

            for card in hand:
                rank = card[0]
                if rank in ['J', 'Q', 'K']:
                    value += 10
                elif rank == 'A':
                    aces += 1
                    value += 11
                else:
                    value += int(rank)

            # Adjust for aces if needed
            while value > 21 and aces > 0:
                value -= 10
                aces -= 1

            return value

        # Function to check if a hand can be split
        def can_split(hand):
            """Check if a hand can be split"""
            if len(hand) != 2:
                return False
            
            # For splitting, we compare the rank values
            # All face cards (J, Q, K) and 10s can be split with each other
            card1_rank = hand[0][0]
            card2_rank = hand[1][0]
            
            # If both are face cards or 10s, they can be split
            if card1_rank in ['J', 'Q', 'K', '10'] and card2_rank in ['J', 'Q', 'K', '10']:
                return True
            
            # Otherwise, they must have the same rank
            return card1_rank == card2_rank

        # Function to format hand for display
        def format_hand(hand, hide_second=False):
            if hide_second and len(hand) > 1:
                return f"{hand[0][0]}{hand[0][1]} | ??"
            return " | ".join(f"{card[0]}{card[1]}" for card in hand)

        # Helper function to update player statistics and handle currency payouts
        async def update_player_stats(result_type, is_blackjack=False, actual_bet=None):
            # Reload currency data to ensure we have the latest state
            await self.currency_manager.load_currency_data()
            
            user_id = str(interaction.user.id)
            if user_id not in self.player_stats:
                self.player_stats[user_id] = {"wins": 0, "losses": 0, "ties": 0}

            self.player_stats[user_id][result_type] += 1
            
            # Use actual_bet if provided, otherwise fall back to original bet
            bet_amount = actual_bet if actual_bet is not None else bet
            
            # Handle currency payouts
            payout = 0
            if result_type == "wins":
                if is_blackjack:
                    # Blackjack pays 2.25x (bet + 1.5x bet)
                    payout = int(bet_amount * BLACKJACK_PAYOUT_MULTIPLIER)
                else:
                    # Regular win pays 2x (bet + bet)
                    payout = bet_amount * 2
                await self.currency_manager.add_currency(user_id, payout)
                logger.info(f"Player {user_id} won ${payout} (bet: ${bet_amount}, blackjack: {is_blackjack})")
            elif result_type == "ties":
                # Return the original bet
                payout = bet_amount
                await self.currency_manager.add_currency(user_id, payout)
                logger.info(f"Player {user_id} tied, returned ${payout}")
            # For losses, no payout (bet was already deducted)
            
            logger.info(f"Updated blackjack stats for {interaction.user}: {self.player_stats[user_id]}")
            await self.save_blackjack_stats()
            return payout

        # Function to display game state
        async def display_game_state(hide_dealer=True, final=False):
            dealer_value = calculate_value(dealer_hand)

            embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
            
            # Show bet information
            if is_split:
                total_bet = sum(split_bets)
                bet_text = f"${total_bet:,} (Split)"
                if doubled_down:
                    bet_text += " (Doubled Down!)"
            else:
                bet_text = f"${bet:,}"
                if doubled_down:
                    bet_text += " (Doubled Down!)"
            embed.add_field(name="💰 Bet", value=bet_text, inline=True)
            current_balance = await self.currency_manager.get_balance(user_id)
            embed.add_field(name="💳 Balance", value=self.currency_manager.format_balance(current_balance), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)  # Empty field for spacing

            if hide_dealer:
                embed.add_field(name="Dealer's Hand", value=format_hand(dealer_hand, True), inline=False)
            else:
                embed.add_field(name=f"Dealer's Hand ({dealer_value})", value=format_hand(dealer_hand), inline=False)

            # Display player hands
            if is_split:
                for i, hand in enumerate(player_hands):
                    hand_value = calculate_value(hand)
                    hand_status = ""
                    if not final and i == current_hand_index:
                        hand_status = " (Current)"
                    elif final:
                        hand_status = f" (Bet: ${split_bets[i]:,})"
                    embed.add_field(name=f"Your Hand {i+1} ({hand_value}){hand_status}", value=format_hand(hand), inline=False)
            else:
                player_value = calculate_value(player_hands[0])
                embed.add_field(name=f"Your Hand ({player_value})", value=format_hand(player_hands[0]), inline=False)

            if final:
                if is_split:
                    # Handle split hands results
                    total_payout = 0
                    results = []
                    
                    for i, hand in enumerate(player_hands):
                        hand_value = calculate_value(hand)
                        hand_bet = split_bets[i]
                        hand_payout = 0
                        hand_result = ""
                        hand_is_blackjack = False
                        
                        if hand_value > 21:
                            hand_result = f"Hand {i+1}: 💥 Busted"
                            # No payout for bust
                        elif dealer_value > 21:
                            hand_result = f"Hand {i+1}: 🎉 Win (Dealer busted)"
                            hand_payout = hand_bet * 2
                        elif hand_value > dealer_value:
                            # Check if it's a blackjack (21 with 2 cards)
                            if hand_value == 21 and len(hand) == 2:
                                hand_result = f"Hand {i+1}: 🃏 BLACKJACK!"
                                hand_is_blackjack = True
                                hand_payout = int(hand_bet * BLACKJACK_PAYOUT_MULTIPLIER)
                            else:
                                hand_result = f"Hand {i+1}: 🎉 Win"
                                hand_payout = hand_bet * 2
                        elif dealer_value > hand_value:
                            hand_result = f"Hand {i+1}: 😔 Loss"
                            # No payout for loss
                        else:
                            hand_result = f"Hand {i+1}: 🤝 Tie"
                            hand_payout = hand_bet  # Return bet
                        
                        results.append(hand_result)
                        total_payout += hand_payout
                        
                        # Add payout to user's balance
                        if hand_payout > 0:
                            # Reload currency data before adding payout
                            await self.currency_manager.load_currency_data()
                            await self.currency_manager.add_currency(user_id, hand_payout)
                    
                    # Update stats based on overall result
                    wins = sum(1 for result in results if "Win" in result or "BLACKJACK" in result)
                    losses = sum(1 for result in results if "Loss" in result or "Busted" in result)
                    ties = sum(1 for result in results if "Tie" in result)
                    
                    if wins > losses:
                        await update_player_stats("wins")
                    elif losses > wins:
                        await update_player_stats("losses")
                    else:
                        await update_player_stats("ties")
                    
                    embed.add_field(name="Results", value="\n".join(results), inline=False)
                    embed.add_field(name="💰 Total Payout", value=f"${total_payout:,}", inline=True)
                    
                else:
                    # Handle single hand result
                    player_value = calculate_value(player_hands[0])
                    result = ""
                    payout = 0
                    is_blackjack = False
                    
                    # Use the actual bet amount (which includes doubled down amount)
                    actual_bet_amount = split_bets[0]
                    
                    if player_value > 21:
                        result = "💥 You busted! Dealer wins."
                        payout = await update_player_stats("losses", actual_bet=actual_bet_amount)
                    elif dealer_value > 21:
                        result = "🎉 Dealer busted! You win!"
                        payout = await update_player_stats("wins", actual_bet=actual_bet_amount)
                    elif player_value > dealer_value:
                        # Check if it's a blackjack (21 with 2 cards)
                        if player_value == 21 and len(player_hands[0]) == 2:
                            result = "🃏 BLACKJACK! You win!"
                            is_blackjack = True
                        else:
                            result = "🎉 You win!"
                        payout = await update_player_stats("wins", is_blackjack, actual_bet=actual_bet_amount)
                    elif dealer_value > player_value:
                        result = "😔 Dealer wins."
                        payout = await update_player_stats("losses", actual_bet=actual_bet_amount)
                    else:
                        result = "🤝 It's a tie!"
                        payout = await update_player_stats("ties", actual_bet=actual_bet_amount)

                    embed.add_field(name="Result", value=result, inline=False)
                    
                    # Show payout information
                    if payout > 0:
                        if result.startswith("🤝"):  # Tie
                            embed.add_field(name="💰 Payout", value=f"${payout:,} (bet returned)", inline=True)
                        elif is_blackjack:
                            embed.add_field(name="💰 Payout", value=f"${payout:,} ({BLACKJACK_PAYOUT_MULTIPLIER}x bet!)", inline=True)
                        else:
                            embed.add_field(name="💰 Payout", value=f"${payout:,} (2x bet)", inline=True)
                    else:
                        embed.add_field(name="💰 Payout", value="$0", inline=True)
                
                # Show new balance
                new_balance = await self.currency_manager.get_balance(user_id)
                embed.add_field(name="💳 New Balance", value=self.currency_manager.format_balance(new_balance), inline=True)

            return embed

        # Initial game state
        await interaction.response.send_message(embed=await display_game_state())
        game_message = await interaction.original_response()

        # Check for natural blackjack
        player_value = calculate_value(player_hands[0])
        dealer_value = calculate_value(dealer_hand)

        if player_value == 21 or dealer_value == 21:
            # Natural blackjack - show final result (payout handled in display_game_state)
            await game_message.edit(embed=await display_game_state(hide_dealer=False, final=True))
            return

        # Add hit/stand/double down/split reactions
        # Check if user can afford to double down
        current_balance = await self.currency_manager.get_balance(user_id)
        can_double_down = current_balance >= bet
        
        # Check if user can split (and afford it)
        can_split_hand = can_split(player_hands[0]) and current_balance >= bet and not is_split
        
        # Build list of reactions to add concurrently
        reactions_to_add = ["👊", "🛑"]  # Hit, Stand
        if can_double_down:
            reactions_to_add.append("2️⃣")  # Double Down
        if can_split_hand:
            reactions_to_add.append("✂️")  # Split
        
        # Add all reactions concurrently
        await asyncio.gather(*[
            game_message.add_reaction(emoji) for emoji in reactions_to_add
        ])

        def check(reaction, user):
            valid_emojis = ["👊", "🛑"]
            if can_double_down:
                valid_emojis.append("2️⃣")
            if can_split_hand:
                valid_emojis.append("✂️")
            return user == interaction.user and str(reaction.emoji) in valid_emojis and reaction.message.id == game_message.id

        # Player's turn - handle each hand
        hand_index = 0
        while hand_index < len(player_hands):
            current_hand_index = hand_index
            current_hand = player_hands[hand_index]
            first_decision = True
            
            # For split hands, check if double down is available for this specific hand
            # For non-split hands, use the original can_double_down variable
            if is_split:
                current_balance = await self.currency_manager.get_balance(user_id)
                hand_can_double_down = current_balance >= split_bets[hand_index] and len(current_hand) == 2
            else:
                hand_can_double_down = can_double_down
            
            # Update display to show current hand
            await game_message.edit(embed=await display_game_state())
            
            # Add reactions for each split hand
            if is_split:
                # Clear existing reactions and add new ones for each split hand
                await game_message.clear_reactions()
                
                # Build reactions list for split hand
                split_reactions = ["👊", "🛑"]  # Hit, Stand
                if hand_can_double_down:
                    split_reactions.append("2️⃣")  # Double Down
                
                # Add all reactions concurrently
                await asyncio.gather(*[
                    game_message.add_reaction(emoji) for emoji in split_reactions
                ])
            
            # Update the check function for this specific hand
            def check_for_hand(reaction, user):
                valid_emojis = ["👊", "🛑"]
                if hand_can_double_down and first_decision:
                    valid_emojis.append("2️⃣")
                if can_split_hand and first_decision and not is_split:
                    valid_emojis.append("✂️")
                return user == interaction.user and str(reaction.emoji) in valid_emojis and reaction.message.id == game_message.id
            
            while calculate_value(current_hand) < 21:
                try:
                    reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check_for_hand)

                    if str(reaction.emoji) == "👊":  # Hit
                        current_hand.append(deck.pop())
                        await game_message.edit(embed=await display_game_state())

                        # Remove the user's reaction
                        await game_message.remove_reaction("👊", user)
                        
                        # After first hit, remove double down option for this hand
                        if first_decision and hand_can_double_down:
                            await game_message.remove_reaction("2️⃣", self.bot.user)
                            hand_can_double_down = False
                        first_decision = False

                        if calculate_value(current_hand) >= 21:
                            break

                    elif str(reaction.emoji) == "🛑":  # Stand
                        await game_message.remove_reaction("🛑", user)
                        break
                        
                    elif str(reaction.emoji) == "2️⃣" and hand_can_double_down and first_decision:  # Double Down
                        # Double the bet for current hand
                        current_bet = split_bets[hand_index]
                        success, new_balance = await self.currency_manager.subtract_currency(user_id, current_bet)
                        if not success:
                            # This shouldn't happen since we checked balance, but handle it gracefully
                            await interaction.followup.send("❌ Unable to double down - insufficient funds!", ephemeral=True)
                            await game_message.remove_reaction("2️⃣", user)
                            continue
                        
                        split_bets[hand_index] = current_bet * 2  # Update bet amount for this hand
                        doubled_down = True
                        
                        # Deal exactly one card
                        current_hand.append(deck.pop())
                        await game_message.edit(embed=await display_game_state())
                        
                        # Remove the user's reaction and end turn for this hand
                        await game_message.remove_reaction("2️⃣", user)
                        break
                    
                    elif str(reaction.emoji) == "✂️" and can_split_hand and first_decision and not is_split:  # Split
                        # Check if user can afford to split
                        success, new_balance = await self.currency_manager.subtract_currency(user_id, bet)
                        if not success:
                            await interaction.followup.send("❌ Unable to split - insufficient funds!", ephemeral=True)
                            await game_message.remove_reaction("✂️", user)
                            continue
                        
                        # Split the hand
                        is_split = True
                        card1 = current_hand[0]
                        card2 = current_hand[1]
                        
                        # Create two new hands
                        player_hands = [[card1, deck.pop()], [card2, deck.pop()]]
                        split_bets = [bet, bet]
                        
                        # Remove split and double down options
                        await game_message.remove_reaction("✂️", self.bot.user)
                        if can_double_down:
                            await game_message.remove_reaction("2️⃣", self.bot.user)
                        can_split_hand = False
                        can_double_down = False
                        
                        # Update display and restart from first hand
                        await game_message.edit(embed=await display_game_state())
                        await game_message.remove_reaction("✂️", user)
                        hand_index = -1  # Will be incremented to 0 at end of loop
                        break

                except asyncio.TimeoutError:
                    await interaction.followup.send("⏰ Game timed out. This counts as a loss.")
                    # Count timeout as a loss
                    await update_player_stats("losses")
                    logger.info(f"Blackjack game timed out for {interaction.user}. Counted as a loss.")
                    return
            
            hand_index += 1

        # Dealer's turn
        while calculate_value(dealer_hand) < 17:
            dealer_hand.append(deck.pop())

        # Show final result
        await game_message.edit(embed=await display_game_state(hide_dealer=False, final=True))

        # Clean up reactions
        await game_message.clear_reactions()

    @app_commands.command(name="blackjack_stats", description="Shows blackjack statistics for a user or all users")
    @app_commands.describe(user="The user to show stats for (optional - shows all users if not specified)")
    async def blackjack_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        """Shows blackjack statistics for a user or all users if no user is specified"""
        if user:
            # Show stats for the specified user
            user_id = str(user.id)
            if user_id in self.player_stats:
                stats = self.player_stats[user_id]
                total_games = stats["wins"] + stats["losses"] + stats["ties"]
                win_percentage = (stats["wins"] / total_games) * 100 if total_games > 0 else 0

                embed = discord.Embed(
                    title=f"Blackjack Stats for {user.display_name}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Total Games", value=total_games, inline=True)
                embed.add_field(name="Wins", value=stats["wins"], inline=True)
                embed.add_field(name="Losses", value=stats["losses"], inline=True)
                embed.add_field(name="Ties", value=stats["ties"], inline=True)
                embed.add_field(name="Win Percentage", value=f"{win_percentage:.2f}%", inline=True)

                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"{user.display_name} hasn't played any blackjack games yet.")
        else:
            # Show stats for all users - defer response to prevent timeout
            await interaction.response.defer()
            
            if not self.player_stats:
                await interaction.followup.send("No blackjack games have been played yet.")
                return

            embed = discord.Embed(
                title="Blackjack Leaderboard",
                description="Statistics for all players",
                color=discord.Color.gold()
            )

            # Sort users by win percentage
            sorted_stats = []
            for user_id, stats in self.player_stats.items():
                total_games = stats["wins"] + stats["losses"] + stats["ties"]
                if total_games > 0:
                    win_percentage = (stats["wins"] / total_games) * 100
                    try:
                        user = await self.bot.fetch_user(int(user_id))
                        username = user.display_name
                    except:
                        username = f"User {user_id}"

                    sorted_stats.append({
                        "username": username,
                        "total_games": total_games,
                        "wins": stats["wins"],
                        "win_percentage": win_percentage
                    })

            # Sort by win percentage (descending)
            sorted_stats.sort(key=lambda x: x["win_percentage"], reverse=True)

            # Add top players to the embed
            for i, player in enumerate(sorted_stats[:10]):  # Show top 10 players
                embed.add_field(
                    name=f"{i+1}. {player['username']}",
                    value=f"Games: {player['total_games']} | Wins: {player['wins']} | Win Rate: {player['win_percentage']:.2f}%",
                    inline=False
                )

            await interaction.followup.send(embed=embed)


async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(BlackjackCog(bot), guild=guild_id)