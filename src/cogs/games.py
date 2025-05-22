import random
import asyncio
import discord
import json
import os
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dictionary to store blackjack statistics for each player
        # Format: {user_id: {"wins": 0, "losses": 0, "ties": 0}}
        self.blackjack_stats = {}
        self.stats_file = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "blackjack_stats.json")
        self.load_blackjack_stats()

    def load_blackjack_stats(self):
        """Load blackjack stats from JSON file"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    self.blackjack_stats = json.load(f)
                logger.info(f"Loaded blackjack stats from {self.stats_file}")
            else:
                logger.info(f"No blackjack stats file found at {self.stats_file}, starting with empty stats")
        except Exception as e:
            logger.error(f"Error loading blackjack stats: {e}")
            self.blackjack_stats = {}

    def save_blackjack_stats(self):
        """Save blackjack stats to JSON file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)

            with open(self.stats_file, 'w') as f:
                json.dump(self.blackjack_stats, f, indent=4)
            logger.info(f"Saved blackjack stats to {self.stats_file}")
        except Exception as e:
            logger.error(f"Error saving blackjack stats: {e}")

    @commands.command(name="coinflip")
    async def flip_coin(self, ctx):
        """Flips a coin and returns heads or tails"""
        logger.info(f"{ctx.author} flipped a coin")
        coin = random.choice(["heads", "tails"])
        await ctx.send(coin)

    @commands.command()
    async def blackjack(self, ctx):
        """Plays a game of blackjack"""
        logger.info(f"{ctx.author} started a blackjack game")

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

        # Helper function to update player statistics
        def update_player_stats(result_type):
            user_id = str(ctx.author.id)
            if user_id not in self.blackjack_stats:
                self.blackjack_stats[user_id] = {"wins": 0, "losses": 0, "ties": 0}

            self.blackjack_stats[user_id][result_type] += 1
            logger.info(f"Updated blackjack stats for {ctx.author}: {self.blackjack_stats[user_id]}")
            self.save_blackjack_stats()

        # Function to display game state
        async def display_game_state(hide_dealer=True, final=False):
            player_value = calculate_value(player_hand)
            dealer_value = calculate_value(dealer_hand)

            embed = discord.Embed(title="Blackjack", color=discord.Color.green())

            if hide_dealer:
                embed.add_field(name="Dealer's Hand", value=format_hand(dealer_hand, True), inline=False)
            else:
                embed.add_field(name=f"Dealer's Hand ({dealer_value})", value=format_hand(dealer_hand), inline=False)

            embed.add_field(name=f"Your Hand ({player_value})", value=format_hand(player_hand), inline=False)

            if final:
                result = ""
                if player_value > 21:
                    result = "You busted! Dealer wins."
                    update_player_stats("losses")
                elif dealer_value > 21:
                    result = "Dealer busted! You win!"
                    update_player_stats("wins")
                elif player_value > dealer_value:
                    result = "You win!"
                    update_player_stats("wins")
                elif dealer_value > player_value:
                    result = "Dealer wins."
                    update_player_stats("losses")
                else:
                    result = "It's a tie!"
                    update_player_stats("ties")

                embed.add_field(name="Result", value=result, inline=False)

            return embed

        # Initial game state
        game_message = await ctx.send(embed=await display_game_state())

        # Check for natural blackjack
        player_value = calculate_value(player_hand)
        dealer_value = calculate_value(dealer_hand)

        if player_value == 21 or dealer_value == 21:
            # Natural blackjack - determine winner
            if player_value == 21 and dealer_value != 21:
                # Player has natural blackjack
                update_player_stats("wins")
            elif dealer_value == 21 and player_value != 21:
                # Dealer has natural blackjack
                update_player_stats("losses")
            elif player_value == 21 and dealer_value == 21:
                # Both have natural blackjack - it's a tie
                update_player_stats("ties")

            await game_message.edit(embed=await display_game_state(hide_dealer=False, final=True))
            return

        # Add hit/stand reactions
        await game_message.add_reaction("👊")  # Hit
        await game_message.add_reaction("🛑")  # Stand

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["👊", "🛑"] and reaction.message.id == game_message.id

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
                await ctx.send("Game timed out.")
                # Count timeout as a loss
                user_id = str(ctx.author.id)
                if user_id not in self.blackjack_stats:
                    self.blackjack_stats[user_id] = {"wins": 0, "losses": 0, "ties": 0}
                self.blackjack_stats[user_id]["losses"] += 1
                logger.info(f"Blackjack game timed out for {ctx.author}. Counted as a loss.")
                self.save_blackjack_stats()
                return

        # Dealer's turn
        while calculate_value(dealer_hand) < 17:
            dealer_hand.append(deck.pop())

        # Show final result
        await game_message.edit(embed=await display_game_state(hide_dealer=False, final=True))

        # Clean up reactions
        await game_message.clear_reactions()

    @commands.command(name="blackjack_stats")
    async def blackjack_stats(self, ctx, user: discord.Member = None):
        """Shows blackjack statistics for a user or all users if no user is specified"""
        if user:
            # Show stats for the specified user
            user_id = str(user.id)
            if user_id in self.blackjack_stats:
                stats = self.blackjack_stats[user_id]
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

                await ctx.send(embed=embed)
            else:
                await ctx.send(f"{user.display_name} hasn't played any blackjack games yet.")
        else:
            # Show stats for all users
            if not self.blackjack_stats:
                await ctx.send("No blackjack games have been played yet.")
                return

            embed = discord.Embed(
                title="Blackjack Leaderboard",
                description="Statistics for all players",
                color=discord.Color.gold()
            )

            # Sort users by win percentage
            sorted_stats = []
            for user_id, stats in self.blackjack_stats.items():
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

            await ctx.send(embed=embed)
