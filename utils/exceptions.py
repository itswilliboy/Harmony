from discord.ext.commands import CommandInvokeError

class GenericError(CommandInvokeError):
    def __init__(self, message: str | None = None):
        self.message = message
    
    def __str__(self) -> str:
        return self.message or ""