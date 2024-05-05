from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

import discord
from aiohttp import ClientSession
from asyncpg import Pool
from discord.ext import commands

from config import DEFAULT_PREFIX

if TYPE_CHECKING:
    from asyncpg import Record

    from bot import Harmony  # noqa: F401

    Command = commands.Command[Any, Any, Any]


class Context(commands.Context["Harmony"]):
    """Custom bot context."""
    
    guild: discord.Guild
    command: Command

    @property
    def clean_prefix(self) -> str:
        clean = super().clean_prefix
        if clean:
            if clean[0] == "@":
                return "(at) "

            return clean

        else:
            return DEFAULT_PREFIX

    @property
    def session(self) -> ClientSession:
        """Returns the bot's client session."""
        
        return self.bot.session

    @property
    def pool(self) -> Pool[Record]:
        """Returns the bot's database connection pool."""
        
        return self.bot.pool

    def is_blacklisted(self) -> bool:
        """Checks if the guild or author is blacklisted."""
        
        blacklist = self.bot.blacklist

        if self.guild is not None:  # type: ignore
            if self.guild.id in self.bot.guild_blacklist:
                return True

        if self.author.id in blacklist:
            item = blacklist[self.author.id]

            if item.is_global:
                return True

            if self.guild is not None:  # type: ignore
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
    """Returns the command's signature."""
    if isinstance(arg, (Context, commands.Context)):
        prefix, command = arg.clean_prefix, arg.command
    else:
        prefix, command = arg

    base = f"{prefix}{command.full_parent_name + ' ' if command.full_parent_name else ''}{command.name}"
    if usage := command.usage:
        return f"{base} {usage}"

    return f"{base} {command.signature}".rstrip()
