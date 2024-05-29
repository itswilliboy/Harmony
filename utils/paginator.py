from __future__ import annotations

from math import ceil
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Optional,
    Self,
    Sequence,
    TypeVar,
)

import discord
from asyncpg import Pool, Record
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
PT = TypeVar("PT", "Paginator[Any]", "DynamicPaginator[Any]")


class PageModalBase(Generic[PT], ui.Modal, title="Hop to page"):
    def __init__(self, paginator: PT, min: int, max: int) -> None:
        super().__init__()
        self.paginator = paginator
        self.min = min
        self.max = max
        self.page: ui.TextInput[Self] = ui.TextInput(label=f"Select a page ({min}-{max})")

        self.add_item(self.page)

    async def on_submit(self, interaction: Interaction) -> None:
        val = self.page.value
        if not val.isnumeric() or int(val) not in range(self.min, self.max + 1):
            return await interaction.response.send_message(
                f"The page number needs to be between {self.min} and {self.max}, not {val}.", ephemeral=True
            )

        await self.switch_page(interaction)

    async def switch_page(self, interaction: Interaction) -> None:
        raise NotImplementedError


class PageModal(PageModalBase["Paginator[T]"]):
    async def switch_page(self, interaction: Interaction) -> None:
        self.paginator.page = int(self.page.value) - 1
        await self.paginator.view.update_message(interaction)


class DynamicPageModal(PageModalBase["DynamicPaginator[T]"]):
    async def switch_page(self, interaction: Interaction) -> None:
        await self.paginator.go_to(interaction, int(self.page.value) - 1)


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

        self.last.label = f"{len(paginator)}"

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
        self.first.label = self.last.label = "..."

        if p.page <= 0:
            self.first.disabled = True
            self.prev.disabled = True

        if p.page + 1 >= len(p):
            self.last.disabled = True
            self.next.disabled = True

        self.curr.label = str(p.page + 1)

        if p.page > 0:
            self.first.label = "1"
            self.prev.label = str(p.page)

        if p.page + 1 < len(p):
            self.last.label = f"{len(self.paginator)}"
            self.next.label = str(p.page + 2)

        await p.update(interaction)

    @discord.ui.button(disabled=True, label="...")
    async def first(self, interaction: Interaction, _):
        self.paginator.page = 0
        await self.update_message(interaction)

    @discord.ui.button(disabled=True, label="...", style=discord.ButtonStyle.blurple)
    async def prev(self, interaction: Interaction, _):
        self.paginator.page -= 1
        await self.update_message(interaction)

    @discord.ui.button(label="1", style=discord.ButtonStyle.green)
    async def curr(self, interaction: Interaction, _):
        await interaction.response.send_modal(PageModal(self.paginator, 1, len(self.paginator)))

    @discord.ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: Interaction, _):
        self.paginator.page += 1
        await self.update_message(interaction)

    @discord.ui.button(label=">>")
    async def last(self, interaction: Interaction, _):
        self.paginator.page = len(self.paginator) - 1
        await self.update_message(interaction)

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.red)
    async def quit(self, interaction: Interaction, _):
        await interaction.response.edit_message()
        await interaction.delete_original_response()


class DynamicPaginator(ui.View, Generic[T]):
    PER_CHUNK: ClassVar[int] = 20

    pool: Pool[Record]
    items: Sequence[T]
    count: int
    page: int
    offset: int

    current: T

    args: Any
    kwargs: Any

    def __len__(self) -> int:
        return len(self.items)

    @classmethod
    async def populate(cls, pool: Pool[Record], count: int, *args: Any, **kwargs: Any) -> Self:
        inst = cls()

        inst.args = args
        inst.kwargs = kwargs

        inst.pool = pool
        inst.count = count

        inst.items = await inst.fetch_chunk(0)
        inst.page = 0
        inst.offset = 0
        inst.current = inst.items[0]

        inst.update_butons()

        return inst

    async def fetch_chunk(self, chunk: int) -> Sequence[T]:
        raise NotImplementedError

    async def go_to(self, interaction: Interaction, page: int) -> None:
        if (page + 1) > self.count or page < 0:
            return await interaction.response.send_message("a")

        self.page = page
        page += 1

        if not ((self.offset + self.PER_CHUNK) > page > self.offset):
            offset = abs((ceil(page / self.PER_CHUNK) - 1) * self.PER_CHUNK)
            self.items = await self.fetch_chunk(offset)
            self.offset = offset

        self.current = self.items[self.page % self.PER_CHUNK]
        self.update_butons()
        await self.update(interaction)

    async def start(self, destination: discord.abc.Messageable) -> None:
        """Starts the paginator."""

        if isinstance(self.current, Page):
            await destination.send(
                content=self.current.content,
                embed=self.current.embed or MISSING,
                file=self.current.file or MISSING,
                view=self,
            )

        elif isinstance(self.current, discord.Embed):
            await destination.send(embed=self.current, view=self)

        else:
            await destination.send(self.current, view=self)

    async def update(self, interaction: Interaction) -> None:
        if isinstance(self.current, Page):
            if file := self.current.file:
                file.reset()

            await interaction.response.edit_message(
                content=self.current.content,
                embed=self.current.embed or MISSING,
                attachments=[self.current.file] if self.current.file else MISSING,
                view=self,
            )

        elif isinstance(self.current, discord.Embed):
            await interaction.response.edit_message(embed=self.current, view=self)

        else:
            await interaction.response.edit_message(content=self.current, view=self)

    def update_butons(self):
        """
        self.first.disabled = False
        self.prev.disabled  = False
        self.curr.disabled  = False
        self.next.disabled  = False
        self.last.disabled  = False

        self.first.label = "1"
        self.prev.label = str(self.page)
        self.curr.label = str(self.page + 1)
        self.next.label = str(self.page + 2)
        self.last.label = str(len(self) + 1)

        if self.page <= 0:
            self.first.disabled = True
            self.prev.disabled = True

            self.first.label = "..."
            self.prev.label = "..."

        if (self.page + 1) >= len(self):
            self.next.disabled = True
            self.last.disabled = True

            self.next.label = "..."
            self.last.label = "..." """

        self.first.disabled = False
        self.prev.disabled = False
        self.next.disabled = False
        self.last.disabled = False

        self.prev.label = self.next.label = "..."
        self.first.label = self.last.label = "..."

        if self.page <= 0:
            self.first.disabled = True
            self.prev.disabled = True

        if self.page + 1 >= self.count:
            self.last.disabled = True
            self.next.disabled = True

        self.curr.label = str(self.page + 1)

        if self.page > 0:
            self.first.label = "1"
            self.prev.label = str(self.page)

        if self.page == 1:
            self.first.label = "..."
            self.first.disabled = True

        if self.page + 1 < self.count:
            self.last.label = str(self.count)
            self.next.label = str(self.page + 2)

        if self.page + 2 >= self.count:
            self.last.label = "..."
            self.last.disabled = True

    @ui.button(label="...", style=discord.ButtonStyle.gray)
    async def first(self, interaction: Interaction, _):
        await self.go_to(interaction, 0)

    @ui.button(label="...", style=discord.ButtonStyle.blurple)
    async def prev(self, interaction: Interaction, _):
        await self.go_to(interaction, self.page - 1)

    @ui.button(label="1", style=discord.ButtonStyle.green)
    async def curr(self, interaction: Interaction, _):
        await interaction.response.send_modal(DynamicPageModal(self, 1, self.count))

    @ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: Interaction, _):
        await self.go_to(interaction, self.page + 1)

    @ui.button(label="...", style=discord.ButtonStyle.gray)
    async def last(self, interaction: Interaction, _):
        await self.go_to(interaction, self.count - 1)
