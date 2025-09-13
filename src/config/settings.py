import os

from dotenv import load_dotenv

load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None

# Transaction Logging Configuration
TRANSACTION_LOGGING_ENABLED = True
TRANSACTION_NICKNAME_TRACKING = True
TRANSACTION_DB_BACKUP_INTERVAL = 24  # hours
TRANSACTION_HISTORY_RETENTION = 365  # days (0 = unlimited)

# Tax Configuration
TAX_RATES = {
    "gambling": 0.25,      # 25% tax on gambling winnings
    "investment": 0.20,    # 20% tax on investment gains
}
TAX_LOSS_CARRYFORWARD = True
TAX_MINIMUM_THRESHOLD = 1000  # Only tax if gains > minimum threshold

# Transaction Type Configuration
TRANSACTION_TYPES = {
    "currency": "currency",      # Daily claims, transfers, bonuses
    "gambling": "gambling",      # Blackjack, horse racing
    "investment": "investment",  # Stock trades, dividends
    "fee": "fee"                # Service fees
}

# /daily
DAILY_CLAIM = 10_000 # $ amount users can claim daily

# Admin Commands
ADMIN_GIVE_MONEY_MAX_AMOUNT = 1_000_000  # Maximum amount admins can give in one transaction
ADMIN_GIVE_MONEY_REASON_MAX_LENGTH = 500  # Maximum length for reason field

# /blackjack
BLACKJACK_PAYOUT_MULTIPLIER = 2.5 #blackjack payout multiplier (bet * payout) = gain

# /*_stock (Stock options)
STOCK_MARKET_LEVERAGE = 1

# /hangman
HANGMAN_DAILY_BONUS = 10_000 # $ amount users can claim daily
HANGMAN_WORD_LISTS = {
    "easy": [
        "cat", "dog", "sun", "car", "hat", "run", "fun", "big", "red", "hot",
        "cup", "pen", "box", "egg", "ice", "key", "map", "net", "owl", "pig",
        "bat", "bee", "bus", "cow", "day", "ear", "eye", "fan", "fox", "gem",
        "gun", "hen", "jam", "jet", "kid", "leg", "man", "mom", "nut", "pan",
        "rat", "sea", "toy", "van", "web", "zoo", "arm", "bag", "bed", "bug",
        "cap", "dad", "den", "dot", "end", "fig", "gas", "hug", "ink", "job",
        "kit", "lap", "mud", "nap", "old", "pot", "rug", "sad", "top", "use",
        "win", "yes", "zip", "age", "air", "art", "bad", "boy", "can", "cut"
    ],
    "medium": [
        "apple", "beach", "chair", "dance", "eagle", "flame", "grape", "house",
        "island", "jungle", "knight", "lemon", "magic", "ocean", "piano", "queen",
        "river", "snake", "tiger", "uncle", "voice", "water", "zebra", "bridge",
        "castle", "dragon", "flower", "garden", "hammer", "jacket", "kitten", "ladder",
        "market", "nature", "orange", "palace", "rabbit", "silver", "temple", "violet",
        "window", "yellow", "anchor", "bottle", "candle", "dinner", "engine", "forest",
        "guitar", "helmet", "insect", "jungle", "kernel", "lizard", "monkey", "needle",
        "office", "pencil", "quartz", "rocket", "shadow", "turtle", "unique", "valley",
        "wizard", "yogurt", "zipper", "animal", "butter", "circle", "double", "eleven",
        "frozen", "global", "handle", "island", "jigsaw", "kettle", "legend", "marble"
    ],
    "hard": [
        "adventure", "beautiful", "challenge", "dangerous", "elephant", "fantastic",
        "gorgeous", "happiness", "important", "knowledge", "landscape", "mountain",
        "necessary", "opportunity", "powerful", "question", "remember", "strength",
        "together", "umbrella", "vacation", "wonderful", "yesterday", "zeppelin",
        "absolute", "birthday", "computer", "delivery", "exercise", "football", "generate",
        "hospital", "internet", "jealousy", "keyboard", "language", "magazine", "notebook",
        "organize", "painting", "quantity", "research", "sandwich", "telephone", "universe",
        "vegetable", "workshop", "xylophone", "yourself", "zoology", "airplane", "building",
        "calendar", "document", "elephant", "festival", "graceful", "hardware", "identity",
        "junction", "kindness", "laughter", "midnight", "negative", "opposite", "positive",
        "quotient", "republic", "standard", "triangle", "umbrella", "velocity", "wildlife",
        "xenophobia", "yearbook", "zucchini", "abstract", "bachelor", "category", "database",
        "envelope", "feedback", "graphics", "headline", "infinite", "junction", "keyboard",
        "location", "material", "national", "original", "platform", "question", "relative"
    ]
}

# /horserace_*
HORSE_RACE_MIN_BET = 100
HORSE_RACE_MAX_BET = 1_000_000
HORSE_RACE_HOUSE_EDGE = 0.05  # 5% house edge on odds
HORSE_ODDS_CURVE_STRENGTH = 5  # Higher = more skewed odds (1.0 = linear, 2.0+ = exponential)
HORSE_ODDS_MIN_MULTIPLIER = 1.2  # Minimum payout for favorites
HORSE_ODDS_MAX_MULTIPLIER = 25.0  # Maximum payout for longshots
HORSE_PROBABILITY_FLOOR = 0.005   # Minimum probability (prevents infinite odds)
HORSE_RACE_DURATION = 120  # Race animation duration in seconds (2 minutes) - dynamic system allows for more varied finish times
HORSE_RACE_UPDATE_INTERVAL = 1.0  # Update race progress every 1 second for smoother animation
HORSE_RACE_TRACK_LENGTH = 1200  # Track length in meters
HORSE_RANDOM_VARIATION = 80 # Per-update randomness factor for dynamic racing
HORSE_RACE_BET_WINDOW = 48 # The number of hours that betting is open prior to the upcoming horse race
HORSE_RACE_BET_TYPES = {
    "win": {
        "name": "Win",
        "description": "Horse must finish 1st place",
        "positions": [1],
    },
    "place": {
        "name": "Place", 
        "description": "Horse must finish 1st or 2nd place",
        "positions": [1, 2],
    },
    "show": {
        "name": "Show",
        "description": "Horse must finish 1st, 2nd, or 3rd place", 
        "positions": [1, 2, 3],
    },
    "last": {
        "name": "Last",
        "description": "Horse must finish in last place",
        "positions": [-1],  # Special case for last place
    }
}
HORSE_RACE_ALLOW_ADMIN_START = False #Set to True to allow admins to use /horserace_start command to manually trigger races
HORSE_RACE_CHANNEL_ID = int(os.getenv("HORSE_RACE_CHANNEL_ID")) if os.getenv("HORSE_RACE_CHANNEL_ID") else None # for scheduled horse races
HORSE_RACE_SCHEDULE = [
    {"day": 6, "hour": 20, "minute": 0}, # Sunday 8 PM
    {"day": 0, "hour": 20, "minute": 0},
    {"day": 1, "hour": 20, "minute": 0},  # Tuesday 8 PM
    {"day": 2, "hour": 20, "minute": 0},
    {"day": 3, "hour": 20, "minute": 0},  # Thursday 8 PM
    {"day": 4, "hour": 20, "minute": 0},
    {"day": 5, "hour": 20, "minute": 0},  # Saturday 8 PM

]
HORSE_STATS = [
    # Strong favorites (low odds, high stats)
    {"name": "Lightning Bolt", "speed": 92, "stamina": 88, "acceleration": 86, "color": "⚡️"},
    {"name": "Thunder Strike", "speed": 90, "stamina": 86, "acceleration": 84, "color": "🌩️"},

    # Good contenders (medium odds)
    {"name": "Fire Storm", "speed": 88, "stamina": 85, "acceleration": 87, "color": "🔥"},
    {"name": "Star Chaser", "speed": 86, "stamina": 87, "acceleration": 85, "color": "⭐"},

    # Dark horses (medium-low odds)
    {"name": "Wind Walker", "speed": 82, "stamina": 88, "acceleration": 80, "color": "💨"},
    {"name": "Midnight Runner", "speed": 80, "stamina": 86, "acceleration": 78, "color": "🌙"},

    # Longshots (high odds, lower stats)
    {"name": "Golden Arrow", "speed": 75, "stamina": 78, "acceleration": 83, "color": "🏹"},
    {"name": "Shadow Dash", "speed": 74, "stamina": 76, "acceleration": 85, "color": "👤"}
]

# /rename_horse
HORSE_RENAME_COST = 10000  # Cost to rename a horse
HORSE_RENAME_DURATION_DAYS = 7  # Number of days a horse stays renamed
