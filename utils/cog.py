from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bot import Harmony


class BaseCog(commands.Cog):
    def __init__(self, bot: Harmony, *args, **kwargs) -> None:
        self.bot = bot
        super().__init__(*args, **kwargs)
