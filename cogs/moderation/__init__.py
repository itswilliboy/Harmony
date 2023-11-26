from __future__ import annotations

from typing import TYPE_CHECKING

from .general import General

if TYPE_CHECKING:
    from bot import Harmony


class Moderation(General):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

async def setup(bot: Harmony) -> None:
    await bot.add_cog(Moderation(bot))
