from types import NoneType

import discord
from discord.ext import commands

from . import Context


def _check(ctx: Context) -> str:
    if ref := ctx.message.reference:
        if not isinstance(ref.resolved, (discord.DeletedReferencedMessage, NoneType)):
            return ref.resolved.content

    return ""


argument_or_reference = commands.parameter(default=lambda ctx: _check(ctx), displayed_name="argument or message reply")  # type: ignore


def progress_bar(percentage: float, *, length: int = 10) -> str:
    """Returns a progress bar from a value 0 through 100."""
    empty = "\N{LIGHT SHADE}"
    full = "\N{FULL BLOCK}"

    score = round(length * percentage / 100)
    return (full * score).ljust(length, empty)
