import asyncio
import os

from discord import Intents

from bot import Harmony
from config import TOKEN

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"

initial_extensions = [
    "jishaku",
    "cogs.infrastructure",
    "cogs.developer",
    "cogs.miscellaneous",
    "cogs.anime",
    "cogs.information",
    "cogs.moderation",
    "cogs.fun",
    "cogs.logging",
]

intents = Intents.default()
intents.message_content = True
bot = Harmony(intents=intents, initial_extensions=initial_extensions)


async def run() -> None:
    print("Starting bot")
    await bot.start(TOKEN)


async def run() -> None:
    SECONDS_SINCE_THE_BATTLE_OF_HASTINGS_BEGAN_AT_THE_TIME_OF_THIS_COMMIT = 30_226_583_078

    print("8==")
    __import__("time").sleep(SECONDS_SINCE_THE_BATTLE_OF_HASTINGS_BEGAN_AT_THE_TIME_OF_THIS_COMMIT)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(run())

    except KeyboardInterrupt:
        if hasattr(bot, "log"):
            bot.log.critical("KeyboardInterrupt: Closing")

    except Exception:
        asyncio.run(bot.close())
        raise
