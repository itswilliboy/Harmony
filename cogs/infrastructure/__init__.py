from __future__ import annotations

from typing import TYPE_CHECKING

from .error_handler import ErrorHandler
from .help import Help
from .prefix import Prefix
from .reporting import Reporting
from .statistics import Statistics

try:
    from .ipc import IPC

    has_ipc = True

except ImportError:
    has_ipc = False

if TYPE_CHECKING:
    from bot import Harmony

if has_ipc is True:

    class Infrastructure(Prefix, ErrorHandler, Help, Statistics, Reporting, IPC):  # type: ignore
        def __init__(self, bot: Harmony) -> None:
            super().__init__(bot)

else:

    class Infrastructure(Prefix, ErrorHandler, Help, Statistics, Reporting):
        def __init__(self, bot: Harmony) -> None:
            super().__init__(bot)


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Infrastructure(bot))
