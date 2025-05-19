import random
import asyncio
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class GamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
                elif dealer_value > 21:
                    result = "Dealer busted! You win!"
                elif player_value > dealer_value:
                    result = "You win!"
                elif dealer_value > player_value:
                    result = "Dealer wins."
                else:
                    result = "It's a tie!"

                embed.add_field(name="Result", value=result, inline=False)

            return embed

        # Initial game state
        game_message = await ctx.send(embed=await display_game_state())

        # Check for natural blackjack
        player_value = calculate_value(player_hand)
        dealer_value = calculate_value(dealer_hand)

        if player_value == 21 or dealer_value == 21:
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
                return

        # Dealer's turn
        while calculate_value(dealer_hand) < 17:
            dealer_hand.append(deck.pop())

        # Show final result
        await game_message.edit(embed=await display_game_state(hide_dealer=False, final=True))

        # Clean up reactions
        await game_message.clear_reactions()

