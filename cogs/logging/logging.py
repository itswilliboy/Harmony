from __future__ import annotations

from typing import Any, Optional, Self

import discord
from asyncpg import Record
from discord.ext import commands

from utils import BaseCog, Context, GenericError, SuccessEmbed


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
        """Sets the enabled-state of the logging config."""

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
        """Creates a new logging config for a guild."""

        query = "INSERT INTO logging_config VALUES ($1, $2, $3) RETURNING *"
        res = await self.bot.pool.fetchrow(query, guild.id, True, channel.id)

        assert res is not None
        return LoggingConfig.from_record(self, res)

    async def get_guild_config(self, guild: discord.abc.Snowflake) -> Optional[LoggingConfig]:
        """Returns the guild's logging config, if any."""

        query = "SELECT * FROM logging_config WHERE guild_id = $1"
        res = await self.bot.pool.fetchrow(query, guild.id)

        if res is not None:
            return LoggingConfig.from_record(self, res)

    def send(self, content: str = "", *, embed: Optional[discord.Embed] = None) -> dict[str, Any]:
        """Returns a `dict` of arguments to use whilst sending a logging message."""

        return {"content": content, "embed": embed}

    async def log(self, guild: discord.abc.Snowflake, args: dict[str, Any]) -> None:
        """Logs to a guild's logging channel, if found."""

        config = await self.get_guild_config(guild)

        if config is not None:
            guild_ = self.bot.get_guild(guild.id)
            assert guild_

            channel = guild_.get_channel(config.channel_id)
            if channel is not None:
                assert isinstance(channel, discord.TextChannel)
                await channel.send(**args)

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
        conf = await self.get_guild_config(ctx.guild)
        if conf is None:
            cp = ctx.clean_prefix
            raise GenericError(f"This server is not set-up, use `{cp}logging setup` to set-up the server.")

        await conf.set_enabled(not conf.enabled)
        await ctx.send(
            embed=SuccessEmbed(
                description=f"Successfully **{'enabled' if conf.enabled else 'disabled'}** logging in this server."
            )
        )

    @logging.command()
    async def test(self, ctx: Context, *, content: str):
        await self.log(ctx.guild, self.send(content))
