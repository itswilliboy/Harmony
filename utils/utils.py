from types import NoneType
from typing import Any, Optional

import discord
from discord.ext import commands
from jwt import decode

from . import Context

__all__ = ("argument_or_reference", "progress_bar", "try_get_ani_id", "plural")


def _check(ctx: Context) -> str:
    if ref := ctx.message.reference:
        if not isinstance(ref.resolved, (discord.DeletedReferencedMessage, NoneType)):
            return ref.resolved.content

    return ""


argument_or_reference = commands.parameter(default=_check, displayed_name="argument or message reply")


def progress_bar(percentage: float, *, length: int = 10) -> str:
    """Returns a progress bar from a value 0 through 100."""
    empty = "\N{LIGHT SHADE}"
    full = "\N{FULL BLOCK}"

    score = round(length * percentage / 100)
    return (full * score).ljust(length, empty)


async def try_get_ani_id(pool: Any, value: str | int) -> Optional[int]:
    """Returns an AniList user ID from a JWT-token or a Discord user ID"""
    if isinstance(value, int):
        if jwt := await pool.fetchval("SELECT token FROM anilist_tokens WHERE user_id = $1", value):
            jwt = jwt
    else:
        jwt = value

    uid = decode(jwt, options={"verify_signature": False})["sub"]
    return int(uid)


class plural:
    def __init__(self, value: int) -> None:
        self.value = value

    def __format__(self, format_spec: str) -> str:
        singular, _, plural = format_spec.partition("|")
        plural = plural or f"{singular}s"

        if abs(self.value) != 1:
            return plural
        return singular
