from __future__ import annotations

import re
from datetime import datetime
from random import randint
from typing import TYPE_CHECKING, Any

import discord
from aiohttp import ClientSession
from discord.ext import commands

from utils import BaseCog, GenericError, Paginator, PrimaryEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class UrbanEntry:
    DEFINITION = re.compile(r"(\[(.+?)\])")

    def __init__(self, data: dict[str, Any]) -> None:
        self.definition: str = data["definition"]
        self.permalink: str = data["permalink"]
        self.ups: int = data["thumbs_up"]
        self.downs: int = data["thumbs_down"]
        self.author: str = data["author"]
        self.word: str = data["word"]
        self.id: int = data["defid"]
        self._written_on: str = data["written_on"]
        self.example: str = data["example"]

    @property
    def written_on(self) -> datetime:
        return datetime.fromisoformat(self._written_on)

    @staticmethod
    def hyperlinked(text: str, *, pattern=DEFINITION) -> str:
        """Returns the text, but with bracketed words replaced by a hyperlink to the definition."""

        def repl(match: re.Match) -> str:
            word = match.group(2)
            return f"**[{word}](http://{word.replace(' ', '-')}.urbanup.com)**"

        return pattern.sub(repl, text)


class MemeView(discord.ui.View):
    pass  # TODO: Implement later


class Fun(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @staticmethod
    async def fetch_meme(session: ClientSession) -> dict[str, Any] | None:
        is_nsfw: bool = True
        while is_nsfw:
            async with session.get("https://meme-api.com/gimme") as resp:
                json: dict[str, Any] = await resp.json()
                is_nsfw = json["nsfw"]

            return json

    @commands.command()
    async def fox(self, ctx: Context):
        """Sends a random picture of a fox."""
        await ctx.typing()
        async with self.bot.session.get("https://randomfox.ca/floof") as resp:
            json = await resp.json()

        embed = PrimaryEmbed().set_image(url=json["image"])
        await ctx.send(embed=embed)

    @commands.command()
    async def dog(self, ctx: Context):
        """Sends a random picture of a dog."""
        await ctx.typing()
        async with self.bot.session.get("https://random.dog/woof.json") as resp:
            json = await resp.json()

        embed = PrimaryEmbed().set_image(url=json["url"])
        await ctx.send(embed=embed)

    @commands.command()
    async def cat(self, ctx: Context):
        """Sends a random picture of a cat"""
        await ctx.typing()
        async with self.bot.session.get("https://cataas.com/cat?json=true") as resp:
            json = await resp.json()

        url = f"https://cataas.com/cat/{json['_id']}"
        embed = PrimaryEmbed().set_image(url=url)
        await ctx.send(embed=embed)

    @commands.command()
    async def meme(self, ctx: Context):
        """Sends a meme."""
        await ctx.typing()
        meme = await self.fetch_meme(self.bot.session)

        if meme is None:
            raise GenericError("Couldn't fetch a meme right now, please try again later.")

        embed = (
            PrimaryEmbed(title=meme["title"]).set_image(url=meme["url"]).set_footer(text=f"\N{THUMBS UP SIGN} {meme['ups']}")
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=["ud", "define"])
    async def urban(self, ctx: Context, *, query: str):
        """Get a defnition of a phrase from the Urban Dictionary."""
        url = "http://api.urbandictionary.com/v0/define"
        async with self.bot.session.get(url, params={"term": query}) as resp:
            json = await resp.json()
            data = json.get("list")

        embeds: list[discord.Embed] = []
        for item in data:
            entry = UrbanEntry(item)

            embed = PrimaryEmbed(
                title=entry.word.title(), url=entry.permalink, description=entry.hyperlinked(entry.definition)
            )
            embed.timestamp = entry.written_on
            embed.add_field(name="Example", value=entry.hyperlinked(entry.example))
            embed.set_footer(text=f"{entry.ups} ↑ | {entry.downs} ↓ | {entry.author}")

            embeds.append(embed)

        if not embeds:
            raise GenericError("Couldn't find any definitions for that term.")

        await Paginator(embeds, ctx.author).start(ctx)

    @commands.command(aliases=["cf", "flip"])
    async def coinflip(self, ctx: Context):
        """Flips a coin."""
        await ctx.send(f"\N{COIN} {'Heads' if randint(0, 1) else 'Tails'}")


# This line is just useless af haha. ~ 20.03.2024 Marvin
