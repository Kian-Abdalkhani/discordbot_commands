import random
import asyncio
import discord
import json
import os
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
        self.load_blackjack_stats()
        
        # Initialize currency manager
        self.currency_manager = bot.currency_manager

    def load_blackjack_stats(self):
        """Load blackjack stats from JSON file"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    self.player_stats = json.load(f)
                logger.info(f"Loaded blackjack stats from {self.stats_file}")
            else:
                logger.info(f"No blackjack stats file found at {self.stats_file}, starting with empty stats")
        except Exception as e:
            logger.error(f"Error loading blackjack stats: {e}")
            self.player_stats = {}

    def save_blackjack_stats(self):
        """Save blackjack stats to JSON file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)

            with open(self.stats_file, 'w') as f:
                json.dump(self.player_stats, f, indent=4)
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

        self.currency_manager.load_currency_data()
        # Check if user has enough currency
        current_balance = self.currency_manager.get_balance(user_id)
        if current_balance < bet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You need ${bet:,} to play but only have {self.currency_manager.format_balance(current_balance)}!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Deduct bet from user's balance
        success, new_balance = self.currency_manager.subtract_currency(user_id, bet)
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

        # Function to format hand for display
        def format_hand(hand, hide_second=False):
            if hide_second and len(hand) > 1:
                return f"{hand[0][0]}{hand[0][1]} | ??"
            return " | ".join(f"{card[0]}{card[1]}" for card in hand)

        # Helper function to update player statistics and handle currency payouts
        def update_player_stats(result_type, is_blackjack=False):
            user_id = str(interaction.user.id)
            if user_id not in self.player_stats:
                self.player_stats[user_id] = {"wins": 0, "losses": 0, "ties": 0}

            self.player_stats[user_id][result_type] += 1
            
            # Handle currency payouts
            payout = 0
            if result_type == "wins":
                if is_blackjack:
                    # Blackjack pays 2.25x (bet + 1.5x bet)
                    payout = int(bet * BLACKJACK_PAYOUT_MULTIPLIER)
                else:
                    # Regular win pays 2x (bet + bet)
                    payout = bet * 2
                self.currency_manager.add_currency(user_id, payout)
                logger.info(f"Player {user_id} won ${payout} (bet: ${bet}, blackjack: {is_blackjack})")
            elif result_type == "ties":
                # Return the original bet
                payout = bet
                self.currency_manager.add_currency(user_id, payout)
                logger.info(f"Player {user_id} tied, returned ${payout}")
            # For losses, no payout (bet was already deducted)
            
            logger.info(f"Updated blackjack stats for {interaction.user}: {self.player_stats[user_id]}")
            self.save_blackjack_stats()
            return payout

        # Function to display game state
        async def display_game_state(hide_dealer=True, final=False):
            player_value = calculate_value(player_hand)
            dealer_value = calculate_value(dealer_hand)

            embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
            
            # Show bet information
            embed.add_field(name="💰 Bet", value=f"${bet:,}", inline=True)
            current_balance = self.currency_manager.get_balance(user_id)
            embed.add_field(name="💳 Balance", value=self.currency_manager.format_balance(current_balance), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)  # Empty field for spacing

            if hide_dealer:
                embed.add_field(name="Dealer's Hand", value=format_hand(dealer_hand, True), inline=False)
            else:
                embed.add_field(name=f"Dealer's Hand ({dealer_value})", value=format_hand(dealer_hand), inline=False)

            embed.add_field(name=f"Your Hand ({player_value})", value=format_hand(player_hand), inline=False)

            if final:
                result = ""
                payout = 0
                is_blackjack = False
                
                if player_value > 21:
                    result = "💥 You busted! Dealer wins."
                    payout = update_player_stats("losses")
                elif dealer_value > 21:
                    result = "🎉 Dealer busted! You win!"
                    payout = update_player_stats("wins")
                elif player_value > dealer_value:
                    # Check if it's a blackjack (21 with 2 cards)
                    if player_value == 21 and len(player_hand) == 2:
                        result = "🃏 BLACKJACK! You win!"
                        is_blackjack = True
                    else:
                        result = "🎉 You win!"
                    payout = update_player_stats("wins", is_blackjack)
                elif dealer_value > player_value:
                    result = "😔 Dealer wins."
                    payout = update_player_stats("losses")
                else:
                    result = "🤝 It's a tie!"
                    payout = update_player_stats("ties")

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
                new_balance = self.currency_manager.get_balance(user_id)
                embed.add_field(name="💳 New Balance", value=self.currency_manager.format_balance(new_balance), inline=True)

            return embed

        # Initial game state
        await interaction.response.send_message(embed=await display_game_state())
        game_message = await interaction.original_response()

        # Check for natural blackjack
        player_value = calculate_value(player_hand)
        dealer_value = calculate_value(dealer_hand)

        if player_value == 21 or dealer_value == 21:
            # Natural blackjack - show final result (payout handled in display_game_state)
            await game_message.edit(embed=await display_game_state(hide_dealer=False, final=True))
            return

        # Add hit/stand reactions
        await game_message.add_reaction("👊")  # Hit
        await game_message.add_reaction("🛑")  # Stand

        def check(reaction, user):
            return user == interaction.user and str(reaction.emoji) in ["👊", "🛑"] and reaction.message.id == game_message.id

        # Player's turn
        while calculate_value(player_hand) < 21:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)

                if str(reaction.emoji) == "👊":  # Hit
                    player_hand.append(deck.pop())
                    await game_message.edit(embed=await display_game_state())

                    # Remove the user's reaction
                    await game_message.remove_reaction("👊", user)

                    if calculate_value(player_hand) >= 21:
                        break

                elif str(reaction.emoji) == "🛑":  # Stand
                    break

            except asyncio.TimeoutError:
                await interaction.followup.send("⏰ Game timed out. This counts as a loss.")
                # Count timeout as a loss
                update_player_stats("losses")
                logger.info(f"Blackjack game timed out for {interaction.user}. Counted as a loss.")
                return

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
            # Show stats for all users
            if not self.player_stats:
                await interaction.response.send_message("No blackjack games have been played yet.")
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

            await interaction.response.send_message(embed=embed)


async def setup(bot):
    guild_id = discord.Object(id=GUILD_ID)
    await bot.add_cog(BlackjackCog(bot), guild=guild_id)