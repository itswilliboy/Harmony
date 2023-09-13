from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from utils import PrimaryEmbed
from utils.cog import BaseCog

if TYPE_CHECKING:
    from bot import Harmony
    from utils.context import Context


class Fun(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot

    async def cog_check(self, ctx: Context):
        await ctx.typing()
        return True

    @commands.command()
    async def fox(self, ctx: Context):
        """Sends a random cute picture of a fox."""
        async with self.bot.session.get("https://randomfox.ca/floof") as resp:
            json = await resp.json()

        embed = PrimaryEmbed().set_image(url=json["image"])
        await ctx.send(embed=embed)

    @commands.command()
    async def dog(self, ctx: Context):
        async with self.bot.session.get("https://random.dog/woof.json") as resp:
            json = await resp.json()

        embed = PrimaryEmbed().set_image(url=json["url"])
        await ctx.send(embed=embed)

    @commands.command()
    async def cat(self, ctx: Context):
        async with self.bot.session.get("https://cataas.com/cat?json=true") as resp:
            json = await resp.json()

        url = f"https://cataas.com/{json['url']}"
        embed = PrimaryEmbed().set_image(url=url)
        await ctx.send(embed=embed)
