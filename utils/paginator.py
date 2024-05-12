from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Optional, Self, Sequence, TypeVar

import discord
from discord import ui
from discord.utils import MISSING

if TYPE_CHECKING:
    from bot import Harmony

    Interaction = discord.Interaction[Harmony]


class Page:
    def __init__(
        self, content: Optional[str] = None, *, embed: Optional[discord.Embed] = None, file: Optional[discord.File] = None
    ) -> None:
        if not any((content, embed, file)):
            raise ValueError("At least one argument has to be supplied.")

        self.content = content
        self.embed = embed
        self.file = file


T = TypeVar("T", str, discord.Embed, Page)


class PageModal(ui.Modal, title="Hop to page"):
    def __init__(self, paginator: Paginator[T], min: int, max: int) -> None:
        super().__init__()
        self.paginator = paginator
        self.min = min
        self.max = max
        self.page: ui.TextInput[Self] = ui.TextInput(label=f"Select a page ({min}-{max})")

        self.add_item(self.page)

    async def on_submit(self, interaction: Interaction) -> None:
        val = self.page.value
        if not val.isnumeric() or int(val) not in range(self.min, self.max):
            return await interaction.response.send_message(
                f"The page number needs to be between {self.min} and {self.max}, not {val}.", ephemeral=True
            )

        self.paginator.page = int(val) - 1
        await self.paginator.view.update_message(interaction)


class Paginator(Generic[T]):
    def __init__(self, items: Sequence[T], user: Optional[discord.abc.User] = None) -> None:
        self.items = items[:]

        self._page = 0
        self._current = self.items[0]

        self.view = PageView(self, user)

    def __len__(self) -> int:
        return self.length

    @property
    def length(self) -> int:
        """Returns the length of the paginator."""
        return len(self.items)

    @property
    def current(self) -> T:
        """Returns the current item."""
        return self.items[self._page]

    @property
    def page(self) -> int:
        """Returns or sets the current page number (zero-indexed)."""
        return self._page

    @page.setter
    def page(self, val: int) -> None:
        self._page = val
        self._current = self.items[val]

    async def start(self, destination: discord.abc.Messageable) -> None:
        """Starts the paginator."""

        if isinstance(self.current, Page):
            await destination.send(
                content=self.current.content,
                embed=self.current.embed or MISSING,
                file=self.current.file or MISSING,
                view=self.view,
            )

        elif isinstance(self.current, discord.Embed):
            await destination.send(embed=self.current, view=self.view)

        else:
            await destination.send(self.current, view=self.view)

    async def update(self, interaction: Interaction) -> None:
        if isinstance(self.current, Page):
            if file := self.current.file:
                file.reset()

            await interaction.response.edit_message(
                content=self.current.content,
                embed=self.current.embed or MISSING,
                attachments=[self.current.file] if self.current.file else MISSING,
                view=self.view,
            )

        elif isinstance(self.current, discord.Embed):
            await interaction.response.edit_message(embed=self.current, view=self.view)

        else:
            await interaction.response.edit_message(content=self.current, view=self.view)


class PageView(ui.View):
    def __init__(self, paginator: Paginator[T], user: Optional[discord.abc.User] = None) -> None:
        super().__init__(timeout=180)
        self.user = user
        self.paginator = paginator

    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.user is not None:
            return self.user == interaction.user
        return True

    async def update_message(self, interaction: Interaction):
        p = self.paginator

        self.first.disabled = False
        self.prev.disabled = False
        self.next.disabled = False
        self.last.disabled = False

        self.prev.label = self.next.label = "..."

        if p.page <= 0:
            self.first.disabled = True
            self.prev.disabled = True

        if p.page + 1 >= p.length:
            self.last.disabled = True
            self.next.disabled = True

        self.curr.label = str(p.page + 1)

        if p.page > 0:
            self.prev.label = str(p.page)

        if p.page + 1 < p.length:
            self.next.label = str(p.page + 2)

        await p.update(interaction)

    @discord.ui.button(disabled=True, label="<<")
    async def first(self, interaction: Interaction, _):
        self.paginator.page = 0
        await self.update_message(interaction)

    @discord.ui.button(disabled=True, label="...", style=discord.ButtonStyle.blurple)
    async def prev(self, interaction: Interaction, _):
        self.paginator.page -= 1
        await self.update_message(interaction)

    @discord.ui.button(label="1", style=discord.ButtonStyle.green)
    async def curr(self, interaction: Interaction, _):
        await interaction.response.send_modal(PageModal(self.paginator, 1, self.paginator.length))

    @discord.ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: Interaction, _):
        self.paginator.page += 1
        await self.update_message(interaction)

    @discord.ui.button(label=">>")
    async def last(self, interaction: Interaction, _):
        self.paginator.page = self.paginator.length - 1
        await self.update_message(interaction)
