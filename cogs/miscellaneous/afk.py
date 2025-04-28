from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Self

import discord
from asyncache import cachedmethod  # pyright: ignore[reportMissingTypeStubs]
from asyncpg import Record
from cachetools import TTLCache
from discord.app_commands import describe
from discord.ext import commands

from utils import BaseCog, Context, PrimaryEmbed, SuccessEmbed

if TYPE_CHECKING:
    from bot import Harmony


@dataclass
class AfkRecord:
    user_id: int
    timestamp: datetime.datetime
    reason: Optional[str]

    @classmethod
    def from_record(cls, record: Record) -> Self:
        return cls(record["user_id"], record["timestamp"], record.get("reason"))


class Afk(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        self.bot = bot

        self.afk_cache: TTLCache[int, AfkRecord] = TTLCache(maxsize=100, ttl=600)

    async def cog_load(self) -> None:
        query = "SELECT * FROM afk"
        records = await self.bot.pool.fetch(query)

        for record in records:
            afk = AfkRecord.from_record(record)
            self.afk_cache[afk.user_id] = afk

    async def set_afk(self, user: discord.abc.Snowflake, reason: Optional[str] = None) -> None:
        query = """
            INSERT INTO afk (user_id, reason)
                VALUES ($1, $2)
            ON CONFLICT (user_id)
                DO UPDATE
                SET reason = $2,
                timestamp = current_timestamp

            RETURNING *
        """
        resp = await self.bot.pool.fetchrow(query, user.id, reason)
        assert resp

        self.afk_cache[user.id] = AfkRecord.from_record(resp)

    async def unset_afk(self, user: discord.abc.Snowflake) -> None:
        query = "DELETE FROM afk WHERE user_id = $1"
        self.afk_cache.pop(user.id)
        await self.bot.pool.execute(query, user.id)

    @cachedmethod(lambda self: self.afk_cache)
    async def get_afk(self, user: discord.abc.Snowflake) -> Optional[AfkRecord]:
        query = "SELECT * FROM afk WHERE user_id = $1"
        await self.bot.pool.fetchrow(query, user.id)

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        author = message.author

        if author.id in self.afk_cache.keys():
            afk = self.afk_cache[author.id]
            await self.unset_afk(author)

            timestamp = discord.utils.format_dt(afk.timestamp, "R")
            embed = PrimaryEmbed(description=f"Welcome back, {author.mention}. You were afk since {timestamp}")

            await message.channel.send(embed=embed)

        if mentions := message.mentions:
            for user in mentions:
                if user == message.author:
                    continue

                if user.id in self.afk_cache.keys():
                    record = self.afk_cache.get(user.id)

                    if record is None:
                        return

                    timestamp = discord.utils.format_dt(record.timestamp, "R")
                    embed = PrimaryEmbed(description=f"{user.mention} went afk {timestamp} with reason: `{record.reason}`")

                    await message.reply(embed=embed, delete_after=5.0)

    @commands.hybrid_command()
    @describe(reason="The reason for going AFK")
    async def afk(self, ctx: Context, *, reason: str = "AFK"):
        """Sets you ask AFK, anyone pinging you will get notified that you are afk with the reason."""
        await self.set_afk(ctx.author, reason)

        embed = SuccessEmbed(description=f"Sucessfully set {ctx.author.mention} as AFK with reason: `{reason}`")
        await ctx.send(embed=embed)
