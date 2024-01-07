from __future__ import annotations

from typing import TYPE_CHECKING

from .error_handler import ErrorHandler
from .help import Help
from .prefix import Prefix
from .statistics import Statistics
from .ipc import IPC

if TYPE_CHECKING:
    from bot import Harmony


class Infrastructure(Prefix, ErrorHandler, Help, Statistics, IPC):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Infrastructure(bot))
