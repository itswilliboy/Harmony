from __future__ import annotations

import logging
from os import environ
from types import NoneType
from typing import TYPE_CHECKING, Any, Optional

import discord
from cryptography.fernet import Fernet
from discord.ext import commands
from jwt import decode

if TYPE_CHECKING:
    from bot import Harmony  # noqa: F401
    from cogs.anime.types import ScoreFormat

    from . import Context

__all__ = (
    "argument_or_reference",
    "progress_bar",
    "try_get_ani_id",
    "plural",
    "encrypt",
    "decrypt",
    "get_score",
    "Interaction",
    "snowflake_key",
    "meth_snowflake_key",
)

logger = logging.Logger(__name__)

Interaction = discord.Interaction["Harmony"]


def _check(ctx: Context) -> str:
    if (ref := ctx.message.reference) and not isinstance(ref.resolved, (discord.DeletedReferencedMessage, NoneType)):
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
    jwt: Optional[str] = None

    if isinstance(value, int):
        val: Optional[bytes]
        if val := await pool.fetchval("SELECT token FROM anilist_tokens_new WHERE user_id = $1", value):
            decrypted = decrypt(val)
            jwt = decrypted

    else:
        jwt = value

    if jwt is None:
        return None

    uid = decode(jwt, options={"verify_signature": False})["sub"]
    return int(uid)


class plural:  # noqa: N801
    def __init__(self, value: int) -> None:
        self.value = value

    def __format__(self, format_spec: str) -> str:
        singular, _, plural = format_spec.partition("|")
        plural = plural or f"{singular}s"

        if abs(self.value) != 1:
            return plural
        return singular


def encrypt(text: str) -> bytes:
    """Encrypts with fernet and returns the encrypted value in bytes"""
    fernet = Fernet(environ["FERNET_KEY"])

    return fernet.encrypt(text.encode())


def decrypt(encrypted: bytes) -> str:
    """Decrypts with fernet and returns the decrypted value as a string."""
    fernet = Fernet(environ["FERNET_KEY"])

    return fernet.decrypt(encrypted).decode("utf-8")


def get_score(score: float, format: ScoreFormat) -> str:
    """Returns the score in the appropriate scoring system."""
    if int(score) == 0:
        return "Unrated"

    match format:
        case "POINT_10":
            return f"{score // 10} / 10"

        case "POINT_10_DECIMAL":
            return f"{score / 10} / 10.0"

        case "POINT_100":
            return f"{score} / 100"

        case "POINT_5":
            new = (score * 5) // 100
            return f"{new} / 5"

        case "POINT_3":
            if score <= 35:
                return "\N{WHITE FROWNING FACE}\N{VARIATION SELECTOR-16}"

            if score <= 60:
                return "\N{NEUTRAL FACE}"

            return "\N{SLIGHTLY SMILING FACE}"

        case _:
            return "N/A"  # Should never trigger


def snowflake_key(snowflake: discord.abc.Snowflake) -> int:
    return snowflake.id


def meth_snowflake_key(_: Any, snowflake: discord.abc.Snowflake) -> int:
    return snowflake.id
