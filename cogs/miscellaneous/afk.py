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
        super().__init__(bot)
        self.bot = bot

        self.afk_cache: TTLCache[int, AfkRecord] = TTLCache(maxsize=100, ttl=600)

    async def set_afk(self, user: discord.abc.Snowflake, reason: Optional[str] = None) -> None:
        query = """
            INSERT INTO afk (user_id, reason)
                VALUES ($1, $2)
            ON CONFLICT (user_id)
                DO UPDATE
            SET reason = $2,
            timestamp = current_timestamp
        """
        await self.bot.pool.execute(query, user.id, reason)
        self.afk_cache.pop(user.id, None)

    async def unset_afk(self, user: discord.abc.Snowflake) -> None:
        query = "DELETE FROM afk WHERE user_id = $1"
        await self.bot.pool.execute(query, user.id)
        self.afk_cache.pop(user.id)

    def _key(self, snowflake: discord.abc.Snowflake) -> int:
        return snowflake.id

    @cachedmethod(lambda self: self.afk_cache, key=_key)
    async def get_afk(self, user: discord.abc.Snowflake) -> Optional[AfkRecord]:
        query = "SELECT * FROM afk WHERE user_id = $1"
        record = await self.bot.pool.fetchrow(query, user.id)

        if record is None:
            return None
        return AfkRecord.from_record(record)

    @commands.Cog.listener("on_message")
    async def afk_listener(self, message: discord.Message):
        author = message.author

        ctx = await self.bot.get_context(message)
        if ctx.command or ctx.is_blacklisted():
            return

        if afk := await self.get_afk(author):
            await self.unset_afk(author)

            timestamp = discord.utils.format_dt(afk.timestamp, "R")
            embed = PrimaryEmbed(description=f"Welcome back, {author.mention}. You were afk since {timestamp}")

            await message.channel.send(embed=embed)

        if mentions := message.mentions:
            for user in mentions:
                if user == message.author:
                    continue

                if afk := await self.get_afk(user):
                    timestamp = discord.utils.format_dt(afk.timestamp, "R")
                    embed = PrimaryEmbed(description=f"{user.mention} went afk {timestamp} with reason: `{afk.reason}`")

                    await message.reply(
                        embed=embed, delete_after=30.0, allowed_mentions=discord.AllowedMentions(replied_user=True)
                    )

    @commands.hybrid_command()
    @describe(reason="The reason for going AFK")
    async def afk(self, ctx: Context, *, reason: str = "AFK"):
        """Sets you ask AFK, anyone pinging you will get notified that you are afk with the reason."""
        await self.set_afk(ctx.author, reason)

        embed = SuccessEmbed(description=f"Sucessfully set {ctx.author.mention} as AFK with reason: `{reason}`")
        await ctx.send(embed=embed)
