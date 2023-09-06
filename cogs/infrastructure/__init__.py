from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from .error_handler import ErrorHandler
from .help import Help
from .statistics import Statistics
from .prefix import Prefix

if TYPE_CHECKING:
    from bot import Harmony


class NotOwner(commands.NotOwner):
    pass


class Infrastructure(Prefix, ErrorHandler, Help, Statistics):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Infrastructure(bot))
