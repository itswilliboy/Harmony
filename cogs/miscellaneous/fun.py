from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from aiohttp import ClientSession
from discord.ext import commands

from utils import BaseCog, GenericError, PrimaryEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils.context import Context


class MemeView(discord.ui.View):
    ...


class Fun(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot
    
    @staticmethod
    async def fetch_meme(session: ClientSession) -> dict[str, Any] | None:
        is_nsfw: bool = True
        while is_nsfw:
            async with session.get("https://meme-api.com/gimme") as resp:
                json: dict[str, Any] = await resp.json()
                is_nsfw = json["nsfw"]

                return json
                

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

    @commands.command()
    async def meme(self, ctx: Context):
        """Displays a random meme."""
        meme = await self.fetch_meme(self.bot.session)

        if meme is None:
            raise GenericError("Couldn't fetch a meme right now, please try again later.")

        embed = PrimaryEmbed(title=meme["title"]) \
        .set_image(url=meme["url"]) \
        .set_footer(text=f"\N{THUMBS UP SIGN} {meme['ups']}")
        await ctx.send(embed=embed)