import logging
import sys
import os
import asyncio

from dotenv import load_dotenv

from bot import create_bot
from utils.logging import setup_logging
from cogs import games, quotes, utilities


async def async_main():

    load_dotenv()
    setup_logging()
    bot = create_bot()

    await bot.add_cog(games.GamesCog(bot))
    await bot.add_cog(quotes.QuotesCog(bot))
    await bot.add_cog(utilities.UtilitiesCog(bot))

    return bot

def main():
    loop = asyncio.new_event_loop()
    bot = loop.run_until_complete(async_main())

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logging.error("No bot token found in environment variables")
        sys.exit(1)
    bot.run(bot_token)

    asyncio.run(async_main())

if __name__ == "__main__":
    main()

