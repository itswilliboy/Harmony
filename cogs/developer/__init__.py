from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from .general import General
from .test import Test

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class Developer(Test, General, command_attrs=dict(hidden=True)):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        predicate = await self.bot.is_owner(ctx.author)

        if predicate is False:
            raise commands.NotOwner()
        return predicate


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Developer(bot))
