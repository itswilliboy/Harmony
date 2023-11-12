from discord.ext.commands import CommandInvokeError


class GenericError(CommandInvokeError):
    def __init__(self, message: str | None = None, footer: bool = False, /):
        self.message = message
        self.footer = footer

    def __str__(self) -> str:
        return self.message or ""
