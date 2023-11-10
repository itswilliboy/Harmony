from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bot import Harmony


class BaseCog(commands.Cog):
    """Base class used in the creation of cogs."""

    def __init__(self, bot: Harmony, *args, **kwargs) -> None:
        self.bot = bot
        super().__init__(*args, **kwargs)

    def is_hidden(self) -> bool:
        """Returns `True` if every command in the cog is hidden."""
        return all([command.hidden for command in self.get_commands()])
