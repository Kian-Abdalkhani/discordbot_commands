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
HORSE_RACE_MAX_BET = 50_000
HORSE_RACE_HOUSE_EDGE = 0.01  # 1% house edge on odds
HORSE_RACE_DURATION = 20  # Race animation duration in seconds
HORSE_RACE_UPDATE_INTERVAL = 2  # Update race progress every 2 seconds
HORSE_RACE_TRACK_LENGTH = 100  # Track length in meters
HORSE_RACE_DAY = 5  # Saturday (0=Monday, 6=Sunday)
HORSE_RACE_HOUR = 20  # 8 PM
HORSE_RACE_MINUTE = 0

# Horse Stats Configuration
HORSE_STATS = [
    {"name": "Lightning Bolt", "speed": 85, "stamina": 78, "acceleration": 92, "color": "⚡"},
    {"name": "Thunder Strike", "speed": 88, "stamina": 82, "acceleration": 85, "color": "🌩️"},
    {"name": "Midnight Runner", "speed": 80, "stamina": 95, "acceleration": 75, "color": "🌙"},
    {"name": "Fire Storm", "speed": 90, "stamina": 70, "acceleration": 88, "color": "🔥"},
    {"name": "Wind Walker", "speed": 82, "stamina": 88, "acceleration": 80, "color": "💨"},
    {"name": "Star Chaser", "speed": 87, "stamina": 85, "acceleration": 78, "color": "⭐"},
    {"name": "Golden Arrow", "speed": 83, "stamina": 90, "acceleration": 82, "color": "🏹"},
    {"name": "Shadow Dash", "speed": 86, "stamina": 75, "acceleration": 90, "color": "👤"}
]
