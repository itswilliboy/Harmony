from __future__ import annotations

from typing import TYPE_CHECKING

from utils import BaseCog, HelpCommand

if TYPE_CHECKING:
    from bot import Harmony


class Help(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.help_command = HelpCommand()
