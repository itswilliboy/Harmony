from types import NoneType

import discord
from discord.ext import commands
from discord.utils import as_chunks as chunk  # noqa: F401

from . import Context


def _check(ctx: Context) -> str:
    if ref := ctx.message.reference:
        if not isinstance(ref.resolved, (discord.DeletedReferencedMessage, NoneType)):
            return ref.resolved.content

    return ""


argument_or_reference = commands.parameter(default=lambda ctx: _check(ctx))
