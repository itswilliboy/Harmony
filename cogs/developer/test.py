from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from utils import BaseCog

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class Test(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        self.bot = bot

    @commands.command()
    async def hi(self, ctx: Context):
        await ctx.send("Hello, There!")

    @commands.command()
    async def arg(self, ctx: Context, cool_arg: str, cooler_arg: str, even_cooler_arg: str):
        raise commands.BadArgument()
