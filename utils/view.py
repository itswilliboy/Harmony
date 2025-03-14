from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord import ui

if TYPE_CHECKING:
    from bot import Harmony

    Interaction = discord.Interaction[Harmony]


__all__ = ("BaseView",)


class BaseView(ui.View):
    def __init__(
        self,
        author: Optional[discord.abc.Snowflake] = None,
        message: Optional[discord.Message] = None,
        *,
        timeout: float = 600.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author = author
        self.message = message

    async def interaction_check(self, interaction: Interaction) -> bool:
        if not self.author:
            return True

        if self.author.id == interaction.user.id:
            return True

        await interaction.response.send_message("This is not for you.", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        if self.message is not None:
            self.stop()

            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def remove(self) -> None:
        """Stops the views and updates the message (if it has been set) to remove it."""
        await self.on_timeout()
