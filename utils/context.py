from __future__ import annotations

from typing import TYPE_CHECKING, overload

import discord
from discord.ext import commands
from discord.ext.commands import Context as DiscordContext
from discord.ext.commands.core import Command

if TYPE_CHECKING:
    from bot import Harmony  # noqa: F401


class Context(DiscordContext["Harmony"]):
    guild: discord.Guild
    command: commands.Command

    @property
    def clean_prefix(self) -> str:
        clean = super().clean_prefix
        if clean[0] == "@":
            return "(at) "

        return clean


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
