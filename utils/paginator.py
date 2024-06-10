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


class PageModal(ui.Modal, title="Hop to page"):
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
        await self.paginator.go_to(interaction, int(self.page.value) - 1)


class Paginator(ui.View, Generic[T]):
    items: Sequence[T]
    count: int
    page: int

    current: T

    args: Any
    kwargs: Any
    message: discord.Message

    def __init__(self, items: Sequence[T], user: Optional[discord.abc.Snowflake] = None) -> None:
        super().__init__()

        self.items = items
        self.count = len(self)
        self.user = user

        self.page = 0
        self.current = self.items[0]

        self.update_buttons()

    def __len__(self) -> int:
        return len(self.items)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.user and self.user.id == interaction.user.id:
            return True
        return False

    async def on_timeout(self) -> None:
        self.stop()
        await self.message.edit(view=None)

    async def go_to(self, interaction: Interaction, page: int) -> None:
        """Goes to a specific page."""

        if (page + 1) > self.count or page < 0:
            return await interaction.response.send_message("a")

        self.page = page
        self.current = self.items[page]

        self.update_buttons()
        await self.update(interaction)

    async def start(self, destination: discord.abc.Messageable) -> None:
        """Starts the paginator."""

        if isinstance(self.current, Page):
            msg = await destination.send(
                content=self.current.content,
                embed=self.current.embed or MISSING,
                file=self.current.file or MISSING,
                view=self,
            )

        elif isinstance(self.current, discord.Embed):
            msg = await destination.send(embed=self.current, view=self)

        else:
            msg = await destination.send(self.current, view=self)

        self.message = msg

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

    def update_buttons(self):
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
        await interaction.response.send_modal(PageModal(self, 1, self.count))

    @ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: Interaction, _):
        await self.go_to(interaction, self.page + 1)

    @ui.button(label="...", style=discord.ButtonStyle.gray)
    async def last(self, interaction: Interaction, _):
        await self.go_to(interaction, self.count - 1)


class DynamicPaginator(ui.View, Generic[T]):
    PER_CHUNK: ClassVar[int] = 20

    pool: Pool[Record]
    items: Sequence[T]
    count: int
    user: Optional[discord.abc.User]
    page: int
    offset: int

    current: T

    args: Any
    kwargs: Any
    message: discord.Message

    def __len__(self) -> int:
        return len(self.items)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.user == interaction.user:
            return True
        return False

    async def on_timeout(self) -> None:
        self.stop()
        await self.message.edit(view=None)

    @classmethod
    async def populate(
        cls, pool: Pool[Record], count: int, user: Optional[discord.abc.User] = None, *args: Any, **kwargs: Any
    ) -> Self:
        inst = cls()

        inst.args = args
        inst.kwargs = kwargs

        inst.pool = pool
        inst.count = count
        inst.user = user

        inst.items = await inst.fetch_chunk(0)
        inst.page = 0
        inst.offset = 0
        inst.current = inst.items[0]

        inst.update_buttons()

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
        self.update_buttons()
        await self.update(interaction)

    async def start(self, destination: discord.abc.Messageable) -> None:
        """Starts the paginator."""

        if isinstance(self.current, Page):
            msg = await destination.send(
                content=self.current.content,
                embed=self.current.embed or MISSING,
                file=self.current.file or MISSING,
                view=self,
            )

        elif isinstance(self.current, discord.Embed):
            msg = await destination.send(embed=self.current, view=self)

        else:
            msg = await destination.send(self.current, view=self)

        self.message = msg

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

    def update_buttons(self):
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
        await interaction.response.send_modal(PageModal(self, 1, self.count))

    @ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: Interaction, _):
        await self.go_to(interaction, self.page + 1)

    @ui.button(label="...", style=discord.ButtonStyle.gray)
    async def last(self, interaction: Interaction, _):
        await self.go_to(interaction, self.count - 1)
