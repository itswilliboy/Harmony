from __future__ import annotations

from typing import TYPE_CHECKING

from .prefix import Prefix

if TYPE_CHECKING:
    from bot import Harmony


class Miscellaneous(Prefix):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Miscellaneous(bot))
