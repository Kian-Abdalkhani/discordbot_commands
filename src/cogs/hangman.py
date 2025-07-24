import random
import asyncio
import discord
import json
import os
from discord.ext import commands
from discord import app_commands
import logging

from src.config.settings import GUILD_ID, HANGMAN_WORD_LISTS

logger = logging.getLogger(__name__)


class HangmanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dictionary to store hangman statistics for each player
        # Format: {user_id: {"wins": 0, "losses": 0, "games_played": 0}}
        self.player_stats = {}
        self.stats_file = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
            "data", "hangman_stats.json")
        self.load_hangman_stats()
        
        # Import word lists from settings
        self.word_lists = HANGMAN_WORD_LISTS

    def load_hangman_stats(self):
        """Load hangman stats from JSON file"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    # Check if file is empty before trying to load JSON
                    file_content = f.read().strip()
                    if file_content:
                        self.player_stats = json.loads(file_content)
                    else:
                        logger.info(f"Empty hangman stats file at {self.stats_file}, starting with empty stats")
                logger.info(f"Loaded hangman stats from {self.stats_file}")
            else:
                logger.info(f"No hangman stats file found at {self.stats_file}, starting with empty stats")
        except Exception as e:
            logger.error(f"Error loading hangman stats: {e}")
            self.player_stats = {}

    def save_hangman_stats(self):
        """Save hangman stats to JSON file"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)

            with open(self.stats_file, 'w') as f:
                json.dump(self.player_stats, f, indent=4)
            logger.info(f"Saved hangman stats to {self.stats_file}")
        except Exception as e:
            logger.error(f"Error saving hangman stats: {e}")

    def get_hangman_display(self, wrong_guesses):
        """Return the hangman ASCII art based on number of wrong guesses"""
        stages = [
            # 0 wrong guesses
            """
            ┌─────┐
            │     │
            │      
            │      
            │      
            │      
            └─────
            """,
            # 1 wrong guess
            """
            ┌─────┐
            │     │
            │     ○
            │      
            │      
            │      
            └─────
            """,
            # 2 wrong guesses
            """
            ┌─────┐
            │     │
            │     ○
            │     │
            │      
            │      
            └─────
            """,
            # 3 wrong guesses
            """
            ┌─────┐
            │     │
            │     ○
            │    ╱│
            │      
            │      
            └─────
            """,
            # 4 wrong guesses
            """
            ┌─────┐
            │     │
            │     ○
            │    ╱│╲
            │      
            │      
            └─────
            """,
            # 5 wrong guesses
            """
            ┌─────┐
            │     │
            │     ○
            │    ╱│╲
            │    ╱ 
            │      
            └─────
            """,
            # 6 wrong guesses (game over)
            """
            ┌─────┐
            │     │
            │     ○
            │    ╱│╲
            │    ╱ ╲
            │      
            └─────
            """
        ]
        return stages[min(wrong_guesses, 6)]

    @app_commands.command(name="hangman", description="Play a game of hangman")
    @app_commands.describe(difficulty="Choose difficulty level (easy, medium, hard)")
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy (3-4 letters)", value="easy"),
        app_commands.Choice(name="Medium (5-6 letters)", value="medium"),
        app_commands.Choice(name="Hard (7+ letters)", value="hard")
    ])
    async def hangman(self, interaction: discord.Interaction, difficulty: str = "medium"):
        """Play a game of hangman"""
        logger.info(f"{interaction.user} started a hangman game with difficulty: {difficulty}")

        # Select a random word from the chosen difficulty
        word = random.choice(self.word_lists[difficulty]).upper()
        guessed_letters = set()
        wrong_guesses = 0
        max_wrong_guesses = 6

        # Helper function to update player statistics
        def update_player_stats(result_type):
            user_id = str(interaction.user.id)
            if user_id not in self.player_stats:
                self.player_stats[user_id] = {"wins": 0, "losses": 0, "games_played": 0}

            self.player_stats[user_id][result_type] += 1
            self.player_stats[user_id]["games_played"] += 1
            logger.info(f"Updated hangman stats for {interaction.user}: {self.player_stats[user_id]}")
            self.save_hangman_stats()

        # Function to display current game state
        def display_game_state():
            # Create the word display with guessed letters
            word_display = ""
            for letter in word:
                if letter in guessed_letters:
                    word_display += letter + " "
                else:
                    word_display += "_ "

            # Create the embed
            embed = discord.Embed(title="🎯 Hangman Game", color=discord.Color.blue())
            
            # Add hangman display
            embed.add_field(
                name="Hangman", 
                value=f"```{self.get_hangman_display(wrong_guesses)}```", 
                inline=False
            )
            
            # Add word display
            embed.add_field(
                name="Word", 
                value=f"```{word_display.strip()}```", 
                inline=False
            )
            
            # Add guessed letters
            if guessed_letters:
                sorted_guesses = sorted(list(guessed_letters))
                embed.add_field(
                    name="Guessed Letters", 
                    value=" ".join(sorted_guesses), 
                    inline=False
                )
            
            # Add remaining guesses
            remaining = max_wrong_guesses - wrong_guesses
            embed.add_field(
                name="Remaining Guesses", 
                value=str(remaining), 
                inline=True
            )
            
            # Add difficulty
            embed.add_field(
                name="Difficulty", 
                value=difficulty.capitalize(), 
                inline=True
            )

            return embed

        # Function to check if game is won
        def is_game_won():
            return all(letter in guessed_letters for letter in word)

        # Function to check if game is lost
        def is_game_lost():
            return wrong_guesses >= max_wrong_guesses

        # Send initial game state
        await interaction.response.send_message(
            embed=display_game_state(),
            content="**Type a letter to guess! You have 60 seconds for each guess.**"
        )

        # Game loop
        while not is_game_won() and not is_game_lost():
            try:
                # Wait for user message
                def check(message):
                    return (message.author == interaction.user and 
                           message.channel == interaction.channel and
                           len(message.content) == 1 and 
                           message.content.isalpha())

                message = await self.bot.wait_for("message", timeout=60.0, check=check)
                guess = message.content.upper()

                # Delete the user's guess message to keep chat clean
                try:
                    await message.delete()
                except:
                    pass  # Ignore if we can't delete (permissions)

                # Check if letter was already guessed
                if guess in guessed_letters:
                    await interaction.followup.send(
                        f"You already guessed **{guess}**! Try a different letter.",
                        ephemeral=True
                    )
                    continue

                # Add the guess to guessed letters
                guessed_letters.add(guess)

                # Check if the guess is correct
                if guess in word:
                    # Correct guess
                    if is_game_won():
                        # Game won!
                        embed = display_game_state()
                        embed.color = discord.Color.green()
                        embed.add_field(
                            name="🎉 Congratulations!", 
                            value=f"You won! The word was **{word}**", 
                            inline=False
                        )
                        update_player_stats("wins")
                        await interaction.edit_original_response(embed=embed, content="**Game Over - You Won!**")
                        break
                    else:
                        # Continue game
                        await interaction.edit_original_response(
                            embed=display_game_state(),
                            content=f"**Good guess! '{guess}' is in the word. Keep going!**"
                        )
                else:
                    # Wrong guess
                    wrong_guesses += 1
                    
                    if is_game_lost():
                        # Game lost!
                        embed = display_game_state()
                        embed.color = discord.Color.red()
                        embed.add_field(
                            name="💀 Game Over!", 
                            value=f"You lost! The word was **{word}**", 
                            inline=False
                        )
                        update_player_stats("losses")
                        await interaction.edit_original_response(embed=embed, content="**Game Over - You Lost!**")
                        break
                    else:
                        # Continue game
                        await interaction.edit_original_response(
                            embed=display_game_state(),
                            content=f"**Wrong! '{guess}' is not in the word. Try again!**"
                        )

            except asyncio.TimeoutError:
                # Game timed out
                embed = display_game_state()
                embed.color = discord.Color.orange()
                embed.add_field(
                    name="⏰ Time's Up!", 
                    value=f"Game timed out! The word was **{word}**", 
                    inline=False
                )
                update_player_stats("losses")
                await interaction.edit_original_response(
                    embed=embed, 
                    content="**Game Over - Time's Up!**"
                )
                break

    @app_commands.command(name="hangman_stats", description="Shows hangman statistics for a user or all users")
    @app_commands.describe(user="The user to show stats for (optional - shows all users if not specified)")
    async def hangman_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        """Shows hangman statistics for a user or all users if no user is specified"""
        if user:
            # Show stats for the specified user
            user_id = str(user.id)
            if user_id in self.player_stats:
                stats = self.player_stats[user_id]
                total_games = stats["games_played"]
                win_percentage = (stats["wins"] / total_games) * 100 if total_games > 0 else 0

                embed = discord.Embed(
                    title=f"🎯 Hangman Stats for {user.display_name}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Total Games", value=total_games, inline=True)
                embed.add_field(name="Wins", value=stats["wins"], inline=True)
                embed.add_field(name="Losses", value=stats["losses"], inline=True)
                embed.add_field(name="Win Percentage", value=f"{win_percentage:.2f}%", inline=True)

                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"{user.display_name} hasn't played any hangman games yet.")
        else:
            # Show stats for all users
            if not self.player_stats:
                await interaction.response.send_message("No hangman games have been played yet.")
                return

            embed = discord.Embed(
                title="🎯 Hangman Leaderboard",
                description="Statistics for all players",
                color=discord.Color.gold()
            )

            # Sort users by win percentage
            sorted_stats = []
            for user_id, stats in self.player_stats.items():
                total_games = stats["games_played"]
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
    await bot.add_cog(HangmanCog(bot), guild=guild_id)