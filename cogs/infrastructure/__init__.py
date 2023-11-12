from __future__ import annotations

from typing import TYPE_CHECKING

from .blacklist import Blacklist
from .error_handler import ErrorHandler
from .help import Help
from .prefix import Prefix
from .statistics import Statistics

if TYPE_CHECKING:
    from bot import Harmony


class Infrastructure(Prefix, ErrorHandler, Help, Statistics, Blacklist):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Infrastructure(bot))
