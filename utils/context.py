from __future__ import annotations

from typing import TYPE_CHECKING, overload

import discord
from discord.ext import commands
from discord.ext.commands import Context as DiscordContext
from discord.ext.commands.core import Command

if TYPE_CHECKING:
    from bot import Harmony  # noqa: F401
    from cogs.developer.blacklist import BlacklistItem


class Context(DiscordContext["Harmony"]):
    guild: discord.Guild
    command: commands.Command

    @property
    def clean_prefix(self) -> str:
        clean = super().clean_prefix
        if clean[0] == "@":
            return "(at) "

        return clean

    def is_blacklisted(self):
        """Checks if the guild or author is blacklisted."""
        cog = self.bot.cogs["developer"]
        blacklist, guild_blacklist = cog.blacklist, cog.guild_blacklist # type: ignore

        if self.guild.id in guild_blacklist:
            return True

        if self.author.id in blacklist:
            item: BlacklistItem = blacklist[self.author.id]

            if item.is_global:
                return True

            if self.guild is not None:
                if self.guild.id in item.guild_ids:
                    return True

        return False


@overload
def get_command_signature(arg: tuple[str, Command]) -> str:
    ...


@overload
def get_command_signature(arg: Context) -> str:
    ...


def get_command_signature(arg: Context | tuple[str, Command]) -> str:
    if isinstance(arg, (Context, commands.Context)):
        prefix, command = arg.clean_prefix, arg.command
    else:
        prefix, command = arg

    base = f"{prefix}{command.full_parent_name + ' ' if command.full_parent_name else ''}{command.name}"
    if usage := command.usage:
        return f"{base} {usage}"

    return f"{base} {command.signature}".rstrip()
