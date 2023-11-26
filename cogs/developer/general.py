from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands
from jishaku.codeblocks import codeblock_converter as CodeblockConverter

from utils import BaseCog

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class General(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.command(aliases=["e"])
    async def eval(self, ctx: Context, *, code: CodeblockConverter):  # type: ignore
        await ctx.invoke(self.bot.get_command("jishaku python"), argument=code)  # type: ignore
