from types import NoneType

import discord
from discord.ext import commands
from discord.utils import as_chunks as chunk  # type: ignore # noqa: F401

from . import Context


def _check(ctx: Context) -> str:
    if ref := ctx.message.reference:
        if not isinstance(ref.resolved, (discord.DeletedReferencedMessage, NoneType)):
            return ref.resolved.content

    return ""


argument_or_reference = commands.parameter(default=lambda ctx: _check(ctx))  # type: ignore


def progress_bar(percentage: float) -> str:
    """Returns a progress bar from a value 0 through 100."""
    empty = "\N{LIGHT SHADE}"
    full = "\N{FULL BLOCK}"

    score = round(percentage / 10)
    bar = (full * score).ljust(10, empty)
    return bar
