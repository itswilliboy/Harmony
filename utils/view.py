from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord import ui

if TYPE_CHECKING:
    from .paginator import Page
    from .utils import Interaction

__all__ = ("BaseView", "SecretView")


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
        self.stop()
        if self.message is not None:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    async def remove(self) -> None:
        """Stops the views and updates the message (if it has been set) to remove it."""
        await self.on_timeout()

    def disable(self) -> None:
        """Stops the view and disables all items. Does not update the message."""
        self.stop()
        for item in self.children:
            item.disabled = True  # type: ignore


class SecretView(BaseView):
    def __init__(self, page: Page, *, text: Optional[str] = None, author: Optional[discord.abc.Snowflake] = None) -> None:
        super().__init__(author=author)
        self.page = page
        self.author = author

        self.view.label = f"View {text or ''}"

    @ui.button(style=discord.ButtonStyle.green)
    async def view(self, interaction: Interaction, _):
        await self.page.send(interaction)
