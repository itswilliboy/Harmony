import logging
from os import environ
from types import NoneType
from typing import Any, Optional

import discord
from cryptography.fernet import Fernet
from discord.ext import commands
from jwt import decode

from . import Context

__all__ = ("argument_or_reference", "progress_bar", "try_get_ani_id", "plural", "encrypt", "decrypt")

logger = logging.Logger(__name__)


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


class plural:
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
    fernet = Fernet(environ['FERNET_KEY'])

    return fernet.encrypt(text.encode())

def decrypt(encrypted: bytes) -> str:
    """Decrypts with fernet and returns the decrypted value as a string."""
    fernet = Fernet(environ["FERNET_KEY"])

    return fernet.decrypt(encrypted).decode("utf-8")