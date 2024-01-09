from __future__ import annotations

from typing import TYPE_CHECKING

from .anime import AniList
from .general import General

if TYPE_CHECKING:
    from bot import Harmony


class Information(General, AniList):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Information(bot))
