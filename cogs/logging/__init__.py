from __future__ import annotations

from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Concatenate,
    ParamSpec,
    Self,
    TypeVar,
    cast,
)

import discord
from discord.ext import commands

from utils import ErrorEmbed

from .logging import Logging

if TYPE_CHECKING:
    from bot import Harmony


P = ParamSpec("P")
R = TypeVar("R")


class Events(
    Logging, name="Logging ", hidden=True
):  # Extra blankspace to make help command catch the 'logging' group rather than this cog
    @staticmethod
    def is_setup(func: Callable[Concatenate[Any, P], Awaitable[R]]):
        """A decorator to check if a guild has set-up logging."""

        @wraps(func)
        async def decorator(self: Self, *args: P.args, **kwargs: P.kwargs) -> None:
            if hasattr(args[0], "guild"):
                first = cast("Any", args[0])

                if first.guild:
                    config = await self.get_guild_config(first.guild)
                    if config and config.enabled:
                        await func(self, *args, **kwargs)

        return decorator

    @is_setup
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        assert message.guild is not None

        if message.author.bot:
            return

        if not message.content:
            return

        embed = ErrorEmbed(title="Message deleted")
        embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)

        assert isinstance(message.channel, discord.TextChannel)
        embed.description = (
            f"Channel: {message.channel.mention}\nContent: `{discord.utils.remove_markdown(message.content)}`"
        )
        embed.timestamp = discord.utils.utcnow()

        await self.log(message.guild, self.send(embed=embed))

    @is_setup
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        assert before.guild is not None

        if before.author.bot:
            return

        if not before.content and not after.content:
            return

        if before.content == after.content:
            return

        embed = discord.Embed(title="Message edited", colour=discord.Colour.yellow())
        embed.set_author(name=before.author.name, icon_url=before.author.display_avatar.url)

        assert isinstance(before.channel, discord.TextChannel)
        embed.description = (
            f"Channel: {before.channel.mention}\n"
            f"Message: {before.jump_url}\n\n"
            f"Before: `{discord.utils.remove_markdown(before.content)}`\n"
            f"After: `{discord.utils.remove_markdown(after.content)}`"
        )
        embed.timestamp = discord.utils.utcnow()

        await self.log(before.guild, self.send(embed=embed))


async def setup(bot: Harmony) -> None:
    await bot.add_cog(Events(bot))
