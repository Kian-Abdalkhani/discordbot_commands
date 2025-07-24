# Discord Bot Commands

A Discord bot built with Python that provides various minigames and utility commands using slash commands.

## Features

### 🎮 Games
- **Blackjack**: Play blackjack against the dealer with betting system and persistent statistics tracking
- **Hangman**: Classic word guessing game with multiple difficulty levels and statistics tracking
- **Coin Flip**: Simple heads or tails coin flip game

### 💰 Economy & Trading
- **Currency System**: Earn, send, and manage virtual currency with daily rewards and leaderboards
- **Stock Market**: Buy and sell stocks with real-time pricing, portfolio management, and leverage trading

### 💬 Quotes
- **Add Quotes**: Add memorable quotes with author attribution
- **Random Quotes**: Get random quotes from the collection
- **Quote Search**: Find quotes by specific authors
- **Quote Management**: List all quotes and delete quotes by ID

### ⚙️ Administration
- **Permission Management**: Admin-only timeout and moderation commands
- **Feature Requests**: Submit feature requests through an interactive modal system

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

#### `/blackjack [bet]`
Start a game of blackjack against the dealer with optional betting.
- Interactive game with hit/stand options
- Automatic win/loss detection
- Statistics tracking per user
- Currency betting system (default bet: 100)
- Enhanced payouts for blackjack wins

#### `/blackjack_stats [user]`
View blackjack statistics for yourself or another user.
- Shows wins, losses, and ties
- Optional user parameter to view others' stats

#### `/hangman [difficulty]`
Start a hangman word guessing game.
- Multiple difficulty levels: easy, medium (default), hard
- Interactive gameplay with letter guessing
- Statistics tracking per user
- Visual hangman display

#### `/hangman_stats [user]`
View hangman statistics for yourself or another user.
- Shows wins, losses, and win rate
- Optional user parameter to view others' stats

#### `/flip_coin`
Flip a coin and get heads or tails.

### Economy & Trading Commands

#### `/balance [user]`
Check your currency balance or another user's balance.
- Shows current currency amount
- Optional user parameter to view others' balance

#### `/daily`
Claim your daily currency reward.
- Daily currency distribution
- Cooldown prevents multiple claims per day

#### `/send_currency <user> <amount>`
Send currency to another user.
- Transfer currency between users
- Validates sufficient balance before transfer
- `user`: The recipient user
- `amount`: Amount of currency to send

#### `/leaderboard`
View the currency leaderboard.
- Shows top users by currency amount
- Paginated display for large servers

#### `/buy_stock <symbol> <amount>`
Buy stocks with your currency.
- Real-time stock pricing
- `symbol`: Stock ticker symbol (e.g., AAPL, GOOGL)
- `amount`: Number of shares to buy

#### `/sell_stock <symbol> [amount] [sell_all]`
Sell your stocks for currency.
- Sell specific amounts or all shares
- `symbol`: Stock ticker symbol
- `amount`: Number of shares to sell (optional)
- `sell_all`: Set to "all" to sell all shares (optional)

#### `/portfolio [user]`
View your stock portfolio or another user's portfolio.
- Shows all owned stocks with current values
- Displays total portfolio value and profit/loss
- Optional user parameter to view others' portfolios

#### `/stock_price <symbol>`
Get the current price of a stock.
- Real-time stock price information
- `symbol`: Stock ticker symbol

#### `/popular_stocks`
View a list of popular stocks for trading.
- Shows commonly traded stocks with current prices

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

### Administration Commands

#### `/timeout <member>`
Put a Discord user in timeout (Admin only).
- Restricts user from using bot commands
- Only server administrators can use this command
- `member`: The Discord member to put in timeout

#### `/end_timeout <member>`
Remove a user from timeout (Admin only).
- Restores user's ability to use bot commands
- Only server administrators can use this command
- `member`: The Discord member to remove from timeout

#### `/feature_request`
Submit a feature request for the bot.
- Opens an interactive modal for feature submission
- Collects user name and feature description
- Assigns unique ID to each request for tracking

## Project Structure

```
discordbot_commands/
├── src/
│   ├── main.py                    # Bot entry point and client setup
│   ├── cogs/                      # Command modules
│   │   ├── blackjack.py           # Blackjack game with betting system
│   │   ├── currency.py            # Currency system and daily rewards
│   │   ├── feature_request.py     # Feature request submission system
│   │   ├── games.py               # Simple games (coin flip)
│   │   ├── hangman.py             # Hangman word guessing game
│   │   ├── permissions.py         # Admin permission and timeout management
│   │   ├── quotes.py              # Quote management commands
│   │   ├── stock_market.py        # Stock trading and portfolio management
│   │   └── utilities.py           # Utility commands (timer)
│   ├── config/                    # Configuration management
│   │   └── settings.py            # Environment variable handling
│   └── utils/                     # Utility modules
│       ├── currency_manager.py    # Currency system management
│       ├── feature_request_store.py # Feature request data management
│       ├── logging.py             # Logging configuration
│       ├── permission_store.py    # Permission and timeout management
│       └── stock_market_manager.py # Stock market data and API integration
├── data/                          # Data storage
│   ├── blackjack_stats.json       # Blackjack game statistics
│   ├── currency.json              # User currency balances and transactions
│   ├── feature_requests.json      # Submitted feature requests
│   ├── hangman_stats.json         # Hangman game statistics
│   ├── permissions.json           # User permissions and timeouts
│   └── quotes.json                # Quotes database
├── tests/                         # Test suite
├── Dockerfile                     # Docker configuration
├── docker-compose.yml             # Docker Compose setup
├── pyproject.toml                # Python project configuration
└── uv.lock                       # Dependency lock file
```

## Data Storage

The bot uses JSON files for data persistence:

- **Quotes**: Stored in `data/quotes.json` with metadata including author, added by, and timestamp
- **Blackjack Stats**: User statistics stored in `data/blackjack_stats.json` tracking wins, losses, and ties
- **Hangman Stats**: User statistics stored in `data/hangman_stats.json` tracking wins, losses, and win rates
- **Currency**: User balances and transaction history stored in `data/currency.json` with daily reward tracking
- **Feature Requests**: User-submitted feature requests stored in `data/feature_requests.json` with unique IDs and metadata
- **Permissions**: Admin permissions and user timeouts stored in `data/permissions.json` for moderation management

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
- **Cogs**: Separate modules for different command categories (games, economy, administration, etc.)
- **Slash Commands**: Modern Discord app commands for better UX
- **Async/Await**: Proper asynchronous programming patterns
- **Error Handling**: Comprehensive error handling and logging
- **Data Persistence**: JSON-based storage for user data, game statistics, currency, and system settings
- **External APIs**: Integration with stock market APIs for real-time trading data

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

### Recent Updates (July 2025)

#### 🐛 Bug Fixes
- **Hangman Stats**: Fixed crash when hangman stats file is empty or corrupted - now gracefully initializes with empty stats and logs the issue
- **Blackjack Payouts**: Fixed critical bug where 3+ card hands totaling 21 were incorrectly receiving blackjack payout multipliers - now only true 2-card blackjacks get the enhanced payout
- **Stock Market**: Fixed leverage multiplier being counted twice on stock gains and losses, causing incorrect profit/loss calculations
- **Settings**: Centralized blackjack payout multiplier configuration in settings file for easier management

#### ✨ Improvements
- **Stock Trading**: Added number formatting to stock trading logs and messages for improved readability (e.g., $1,234.56 instead of 1234.56)
- **Daily Bonus**: Updated daily bonus amount to $5,000 and centralized configuration via settings file
- **Dependencies**: Added comprehensive stock market functionality with new packages: BeautifulSoup4, certifi, cffi, charset-normalizer, curl-cffi, frozendict, multitasking, numpy, and yfinance
- **Testing**: Added comprehensive test coverage for all recent bug fixes and new functionality

#### 🏗️ System Improvements
- **Stock Market System**: Introduced complete stock market simulation with leverage support, real-time price fetching, portfolio management, and currency integration
- **Error Handling**: Enhanced error handling for file operations and API calls with proper logging
- **Code Quality**: Improved code organization and removed obsolete documentation files

### Previous Updates
- **New Games**: Added Hangman game with multiple difficulty levels and statistics tracking
- **Economy System**: Implemented comprehensive currency system with daily rewards, transfers, and leaderboards
- **Stock Market**: Added full stock trading functionality with real-time pricing and portfolio management
- **Enhanced Blackjack**: Integrated betting system with currency rewards and enhanced statistics
- **Administration Tools**: Added timeout/moderation commands and feature request submission system
- **Modular Architecture**: Separated games into individual cogs for better organization
- **Data Persistence**: Expanded JSON-based storage for all new features
- **Comprehensive Testing**: Updated test suite to cover all new functionality
- Migrated from prefix commands to slash commands
- Updated bot architecture to use custom Client class
- Improved error handling and logging