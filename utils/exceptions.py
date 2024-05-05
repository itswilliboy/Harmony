from typing import Optional
from discord.ext.commands import CommandInvokeError  # type: ignore


class GenericError(CommandInvokeError):
    def __init__(self, message: Optional[str] = None, footer: bool = False, /) -> None:
        self.message = message
        self.footer = footer

    def __str__(self) -> str:
        return self.message or "\u200b"

    def __repr__(self) -> str:
        return str(self)
