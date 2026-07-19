from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord.app_commands import allowed_contexts, allowed_installs, describe
from discord.ext import commands

from utils import BaseCog, Context, PrimaryEmbed

from .client import MyDramaList

if TYPE_CHECKING:
    from bot import Harmony

class Dramas(BaseCog, name="MyDramaList"):
    def __init__(self, bot: Harmony, *args: Any, **kwargs: Any) -> None:
        super().__init__(bot, *args, **kwargs)
        self.MDL = MyDramaList()

    @commands.hybrid_group(aliases=["mdl"])
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def mydramalist(self, ctx: Context):
        await ctx.send_help(ctx.command)

    @commands.hybrid_command()
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True, private_channels=True)
    @describe(search="The drama to search for")
    async def drama(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific manga."""
        res = await self.MDL.fetch_media(search)
        embed = PrimaryEmbed(title=res["title"])