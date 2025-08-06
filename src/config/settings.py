import os

from dotenv import load_dotenv

load_dotenv()

GUILD_ID = int(os.getenv("GUILD_ID"))

# Daily payout
DAILY_CLAIM = 10_000

#blackjack payout multiplier (bet * payout) = gain
BLACKJACK_PAYOUT_MULTIPLIER = 2.5

# Stock market leverage multiplier
STOCK_MARKET_LEVERAGE = 20

# Hangman daily bonus for hard difficulty wins
HANGMAN_DAILY_BONUS = 10_000

# Hangman word lists for different difficulty levels
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

# Horse Racing Configuration
HORSE_RACE_MIN_BET = 100
HORSE_RACE_MAX_BET = 1_000_000
HORSE_RACE_HOUSE_EDGE = 0.05  # 1% house edge on odds
HORSE_RACE_DURATION = 90  # Race animation duration in seconds (1.5 minutes)
HORSE_RACE_UPDATE_INTERVAL = 1.5  # Update race progress every 1.5 seconds for smoother animation
HORSE_RACE_TRACK_LENGTH = 1200  # Track length in meters
HORSE_RANDOM_VARIATION = 15 # The randomness factor; the higher, the more random race outputs are
HORSE_RACE_BET_WINDOW = 48 # The number of hours that betting is open prior to the upcoming horse race

# Bet Types Configuration
BET_TYPES = {
    "win": {
        "name": "Win",
        "description": "Horse must finish 1st place",
        "positions": [1],
        "payout_multiplier": 1.0  # Base payout
    },
    "place": {
        "name": "Place", 
        "description": "Horse must finish 1st or 2nd place",
        "positions": [1, 2],
        "payout_multiplier": 0.6  # Reduced payout for easier bet
    },
    "show": {
        "name": "Show",
        "description": "Horse must finish 1st, 2nd, or 3rd place", 
        "positions": [1, 2, 3],
        "payout_multiplier": 0.4  # Further reduced payout
    },
    "last": {
        "name": "Last",
        "description": "Horse must finish in last place",
        "positions": [-1],  # Special case for last place
        "payout_multiplier": 0.8  # High payout but not as high as win
    }
}

# Admin Controls
# Set to False to disable admin manual race starts (races will only run on schedule)
# Set to True to allow admins to use /horserace_start command to manually trigger races
HORSE_RACE_ALLOW_ADMIN_START = True

# Set horse race channel id
HORSE_RACE_CHANNEL_ID = os.getenv("HORSE_RACE_CHANNEL_ID")

# Horse race schedule configuration
# IMPORTANT: All times are in the system's local timezone. For Docker deployments,
# ensure the TZ environment variable is set in docker-compose.yml to match your local timezone.
# Days: Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
HORSE_RACE_SCHEDULE = [
    {"day": 1, "hour": 20, "minute": 0},  # Tuesday 8 PM
    {"day": 3, "hour": 20, "minute": 0},  # Thursday 8 PM
    {"day": 5, "hour": 20, "minute": 0},  # Saturday 8 PM
]

# Horse Stats Configuration - 8 racing horses with varied stats (favorites to longshots)
HORSE_STATS = [
    # Strong favorites (low odds, high stats)
    {"name": "Lightning Bolt", "speed": 95, "stamina": 90, "acceleration": 92, "color": "⚡"},
    {"name": "Thunder Strike", "speed": 92, "stamina": 88, "acceleration": 90, "color": "🌩️"},
    
    # Good contenders (medium odds)
    {"name": "Fire Storm", "speed": 88, "stamina": 85, "acceleration": 87, "color": "🔥"},
    {"name": "Star Chaser", "speed": 86, "stamina": 87, "acceleration": 85, "color": "⭐"},
    
    # Dark horses (medium-low odds)
    {"name": "Wind Walker", "speed": 82, "stamina": 84, "acceleration": 80, "color": "💨"},
    {"name": "Midnight Runner", "speed": 80, "stamina": 86, "acceleration": 78, "color": "🌙"},
    
    # Longshots (high odds, lower stats)
    {"name": "Golden Arrow", "speed": 75, "stamina": 78, "acceleration": 72, "color": "🏹"},
    {"name": "Shadow Dash", "speed": 72, "stamina": 74, "acceleration": 70, "color": "👤"}
]
