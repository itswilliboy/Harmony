from typing import Self, overload

import discord
from discord.ext import commands
from discord.ext.commands import Context as DiscordContext
from discord.ext.commands.core import Command

from bot import Harmony


class Context(DiscordContext[Harmony]):
    guild: discord.Guild
    command: commands.Command

    @classmethod
    def from_context(cls, context: DiscordContext) -> Self:
        return cls(
            message=context.message,
            bot=context.bot,
            view=context.view,
            args=context.args,
            kwargs=context.kwargs,
            prefix=context.prefix,
            command=context.command,
            invoked_with=context.invoked_with,
            invoked_parents=context.invoked_parents,
            invoked_subcommand=context.invoked_subcommand,
            subcommand_passed=context.subcommand_passed,
            command_failed=context.command_failed,
            current_parameter=context.current_parameter,
            current_argument=context.current_argument,
            interaction=context.interaction,
        )

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
