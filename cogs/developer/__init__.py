from __future__ import annotations

from typing import TYPE_CHECKING

from .blacklist import Blacklist
from .general import General

if TYPE_CHECKING:
    from bot import Harmony


class Developer(General, Blacklist, hidden=True, owner_only=True):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Developer(bot))
