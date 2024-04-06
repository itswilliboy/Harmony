import asyncio
import os

from discord import Intents

from bot import Harmony
from config import TOKEN

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"

# fmt: off
initial_extensions = [
    "jishaku",
    "cogs.infrastructure",
    "cogs.developer",
    "cogs.miscellaneous",
    "cogs.information",
    "cogs.moderation",
    "cogs.fun"
]
# fmt: on

intents = Intents.all()
bot = Harmony(intents=intents, initial_extensions=initial_extensions)


async def run():
    print("Starting bot")
    await bot.start(TOKEN)


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
