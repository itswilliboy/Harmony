from __future__ import annotations

from typing import Any, Awaitable, Optional, Self

import discord
from asyncpg import Record
from discord.ext import commands

from utils import BaseCog, Context, GenericError


class LoggingConfig:
    def __init__(self, cog: Logging, guild_id: int, enabled: bool, channel_id: int) -> None:
        self.cog = cog
        self.guild_id = guild_id
        self.enabled = enabled
        self.channel_id = channel_id

    @classmethod
    def from_record(cls, cog: Logging, record: Record) -> Self:
        return cls(cog, record["guild_id"], record["enabled"], record["channel_id"])

    async def set_enabled(self, enabled: bool) -> None:
        query = """
            UPDATE logging_config
                SET enabled = $1
            WHERE guild_id = $2
        """
        await self.cog.bot.pool.execute(query, enabled, self.guild_id)
        self.enabled = enabled

    async def delete(self) -> None:
        query = "DELETE FROM logging_config WHERE guild_id = $1"
        await self.cog.bot.pool.execute(query, self.guild_id)


class Logging(BaseCog):
    async def create_guild_config(self, guild: discord.abc.Snowflake, channel: discord.TextChannel) -> LoggingConfig:
        query = "INSERT INTO logging_config VALUES ($1, $2, $3) RETURNING *"
        res = await self.bot.pool.fetchrow(query, guild.id, True, channel.id)

        assert res is not None
        return LoggingConfig.from_record(self, res)

    async def get_guild_config(self, guild: discord.abc.Snowflake) -> Optional[LoggingConfig]:
        query = "SELECT * FROM logging_config WHERE guild_id = $1"
        res = await self.bot.pool.fetchrow(query, guild.id)

        if res is not None:
            return LoggingConfig.from_record(self, res)

    async def send(self, content: str = "", *, embed: Optional[discord.Embed] = None) -> dict[str, Any]:
        return {"content": content, "embed": embed}

    async def log(self, guild: discord.abc.Snowflake, send: Awaitable[Any]) -> None:
        config = await self.get_guild_config(guild)

        if config is not None:
            guild_ = self.bot.get_guild(guild.id)
            assert guild_

            channel = guild_.get_channel(config.channel_id)
            if channel is not None:
                assert isinstance(channel, discord.TextChannel)
                await channel.send(**await send)

    @commands.group(invoke_without_command=True)
    async def logging(self, ctx: Context):
        await ctx.send_help(ctx.command)

    @commands.has_permissions(manage_guild=True)
    @logging.command()
    async def setup(self, ctx: Context, channel: discord.TextChannel):
        if await self.get_guild_config(ctx.guild):
            cp = ctx.clean_prefix
            raise GenericError(
                "This server is already set-up, "
                f"run `{cp}logging delete` or `{cp}logging toggle` to delete or disable the logging setup."
            )

        await self.create_guild_config(ctx.guild, channel)
        await ctx.send(f"Successfully set {channel.mention} as the loggnig channel.")

    @logging.command()
    async def toggle(self, ctx: Context):
        pass

    @logging.command()
    async def test(self, ctx: Context, *, content: str):
        await self.log(ctx.guild, self.send(content))
