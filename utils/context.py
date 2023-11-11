from typing import Tuple, Union, overload

import discord
from discord.ext import commands
from discord.ext.commands import Context as DiscordContext
from discord.ext.commands.core import Command

from bot import Harmony


class Context(DiscordContext[Harmony]):
    guild: discord.Guild
    command: commands.Command

@overload
def get_command_signature(arg: Tuple[str, Command]) -> str: ...

@overload
def get_command_signature(arg: Context) -> str: ...

def get_command_signature(arg: Union[Context, Tuple[str, Command]]) -> str:
    if isinstance(arg, Context):
        prefix, command = arg.prefix, arg.command
    else:
        prefix, command = arg

    base = f"{prefix}{command.full_parent_name} {command.name}"
    if usage := command.usage:
        return f"{base} {usage}"

    return f"{base} {command.signature}"