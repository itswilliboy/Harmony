from __future__ import annotations

from typing import TYPE_CHECKING

from .afk import Afk
from .utilities import Utilities

if TYPE_CHECKING:
    from bot import Harmony


class Miscellaneous(Utilities, Afk):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Miscellaneous(bot))
