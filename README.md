# Discord Bot Commands

A Discord bot built with Python that provides various minigames and utility commands using slash commands.

## Features

### 🎮 Games
- **Blackjack**: Play blackjack against the dealer with persistent statistics tracking
- **Coin Flip**: Simple heads or tails coin flip game

### 💬 Quotes
- **Add Quotes**: Add memorable quotes with author attribution
- **Random Quotes**: Get random quotes from the collection
- **Quote Search**: Find quotes by specific authors
- **Quote Management**: List all quotes and delete quotes by ID

### ⏰ Utilities
- **Timer**: Set timers with flexible time units (seconds, minutes, hours)

## Installation

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Discord Server with appropriate permissions

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd discordbot_commands
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   Or using uv:
   ```bash
   uv sync
   ```

3. **Environment Configuration**
   - Copy `.env.template` to `.env`
   - Fill in your Discord bot token and guild ID:
   ```env
   BOT_TOKEN=your_discord_bot_token_here
   GUILD_ID=your_discord_server_id_here
   ```

4. **Run the bot**
   ```bash
   python src/main.py
   ```

### Docker Setup

Alternatively, you can run the bot using Docker:

```bash
# Build the image
docker build -t discord-bot .

# Run with docker-compose
docker-compose up -d
```

## Commands

### Games Commands

#### `/blackjack`
Start a game of blackjack against the dealer.
- Interactive game with hit/stand options
- Automatic win/loss detection
- Statistics tracking per user

#### `/blackjack_stats [user]`
View blackjack statistics for yourself or another user.
- Shows wins, losses, and ties
- Optional user parameter to view others' stats

#### `/flip_coin`
Flip a coin and get heads or tails.

### Quotes Commands

#### `/add_quote <quote_text> <quote_author>`
Add a new quote to the collection.
- `quote_text`: The quote content
- `quote_author`: The author of the quote

#### `/quote [quote_id]`
Get a quote by ID or a random quote if no ID is provided.
- `quote_id` (optional): Specific quote ID to retrieve

#### `/list_quotes`
Display all quotes in the collection with pagination.

#### `/quotes_by <author>`
Find all quotes by a specific author.
- `author`: The author name to search for

#### `/delete_quote <quote_id>`
Delete a quote by its ID.
- `quote_id`: The ID of the quote to delete

### Utility Commands

#### `/timer <time> <unit>`
Set a timer for a specified duration.
- `time`: The duration (positive number)
- `unit`: Time unit (seconds, minutes, hours, or their abbreviations)
- Maximum duration: 24 hours

**Supported time units:**
- Seconds: `s`, `sec`, `secs`, `second`, `seconds`
- Minutes: `m`, `min`, `mins`, `minute`, `minutes`
- Hours: `h`, `hr`, `hrs`, `hour`, `hours`

## Project Structure

```
discordbot_commands/
├── src/
│   ├── main.py              # Bot entry point and client setup
│   ├── cogs/                # Command modules
│   │   ├── games.py         # Game commands (blackjack, coin flip)
│   │   ├── quotes.py        # Quote management commands
│   │   └── utilities.py     # Utility commands (timer)
│   ├── config/              # Configuration management
│   │   └── settings.py      # Environment variable handling
│   └── utils/               # Utility modules
│       └── logging.py       # Logging configuration
├── data/                    # Data storage
│   ├── quotes.json          # Quotes database
│   └── blackjack_stats.json # Blackjack statistics
├── tests/                   # Test suite
├── Dockerfile               # Docker configuration
├── docker-compose.yml       # Docker Compose setup
├── pyproject.toml          # Python project configuration
└── uv.lock                 # Dependency lock file
```

## Data Storage

The bot uses JSON files for data persistence:

- **Quotes**: Stored in `data/quotes.json` with metadata including author, added by, and timestamp
- **Blackjack Stats**: User statistics stored in `data/blackjack_stats.json` tracking wins, losses, and ties

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_discord_bot.py

# Run with coverage
pytest --cov=src
```

### Code Structure

The bot uses a modular architecture with:
- **Cogs**: Separate modules for different command categories
- **Slash Commands**: Modern Discord app commands for better UX
- **Async/Await**: Proper asynchronous programming patterns
- **Error Handling**: Comprehensive error handling and logging
- **Data Persistence**: JSON-based storage for quotes and statistics

### Adding New Commands

1. Create or modify a cog in `src/cogs/`
2. Use `@app_commands.command()` decorator for slash commands
3. Add proper error handling and logging
4. Update tests in the corresponding test file
5. Update this README with the new command documentation

## Configuration

### Environment Variables

- `BOT_TOKEN`: Your Discord bot token (required)
- `GUILD_ID`: Your Discord server ID for command syncing (required)

### Bot Permissions

The bot requires the following Discord permissions:
- Send Messages
- Use Slash Commands
- Embed Links
- Read Message History

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Update documentation
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the existing issues on GitHub
2. Create a new issue with detailed information
3. Include logs and error messages when applicable

## Changelog

### Recent Updates
- Migrated from prefix commands to slash commands
- Updated bot architecture to use custom Client class
- Improved error handling and logging
- Added comprehensive test suite
- Enhanced data persistence for quotes and statistics