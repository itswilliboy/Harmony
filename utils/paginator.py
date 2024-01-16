from __future__ import annotations
from typing import TYPE_CHECKING

import discord
from discord.interactions import Interaction

if TYPE_CHECKING:
    from bot import Harmony


class PageModal(discord.ui.Modal):
    def __init__(self, paginator: Paginator, view: PaginatorView, min_page: int, max_page: int) -> None:
        super().__init__(title=f"Enter a page number ({min_page}-{max_page})")
        self.paginator = paginator
        self.view = view
        self.min_page = min_page
        self.max_page = max_page

        self.page = discord.ui.TextInput(
            label="Page", min_length=len(str(self.min_page)), max_length=len(str(self.max_page))
        )
        self.add_item(self.page)

    async def on_submit(self, interaction: Interaction[Harmony]):
        if not self.page.value.isnumeric() or int(self.page.value) not in range(self.min_page, self.max_page+1):
            return await interaction.response.send_message(
                f"The page number needs to be between {self.min_page} and {self.max_page}", ephemeral=True
            )
        self.paginator.set_page(int(self.page.value) - 1)
        self.view.update()
        await interaction.response.edit_message(embed=self.paginator.current_page, view=self.view)


class PaginatorView(discord.ui.View):
    def __init__(self, paginator: Paginator) -> None:
        super().__init__(timeout=300)
        self.paginator = paginator
        self.page.label = f"1/{paginator.length}"

    def update(self):
        self.prev.disabled = False
        self.next.disabled = False

        if self.paginator.index <= 0:
            self.prev.disabled = True

        elif self.paginator.user_page >= self.paginator.length:
            self.next.disabled = True

        self.page.label = f"{self.paginator.user_page}/{self.paginator.length}"

    async def interaction_check(self, interaction: Interaction) -> bool:
        if author := self.paginator.author:
            if author != interaction.user:
                await interaction.response.send_message("This is not for you.", ephemeral=True)
                return False

        return True

    @discord.ui.button(label="<<", style=discord.ButtonStyle.blurple, disabled=True)
    async def prev(self, interaction: discord.Interaction, _):
        page = self.paginator

        if page.index <= 0:
            pass

        else:
            page.previous_page()

        self.update()
        await interaction.response.edit_message(embed=page.current_page, view=self)

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, disabled=True)
    async def page(self, *_):
        pass

    @discord.ui.button(label=">>", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, _):
        page = self.paginator

        if page.index + 1 == page.length:
            pass

        else:
            page.next_page()

        self.update()
        await interaction.response.edit_message(embed=page.current_page, view=self)

    @discord.ui.button(label="\N{WASTEBASKET}\N{VARIATION SELECTOR-16}", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, _):
        assert interaction.message
        await interaction.message.delete()

    @discord.ui.button(label="Enter Page", style=discord.ButtonStyle.blurple, row=1)
    async def enter_page(self, interaction: discord.Interaction, _):
        modal = PageModal(self.paginator, self, 1, self.paginator.length)
        await interaction.response.send_modal(modal)


class Paginator:
    def __init__(self, embeds: list[discord.Embed], author: discord.User | discord.Member | None = None) -> None:
        self.embeds = embeds
        self.author = author
        self._current_page = embeds[0]
        self.page = 0

        self.view = PaginatorView(self)

    @property
    def current_page(self) -> discord.Embed:
        return self._current_page

    @current_page.setter
    def current_page(self, embed: discord.Embed) -> None:
        self._current_page = embed

    @property
    def length(self) -> int:
        return len(self.embeds)

    @property
    def user_page(self) -> int:
        return self.page + 1

    @property
    def index(self) -> int:
        return self.embeds.index(self.current_page)

    def next_page(self) -> None:
        self.page += 1
        index = self.index
        self.current_page = self.embeds[index + 1]

    def previous_page(self) -> None:
        self.page -= 1
        index = self.index
        self.current_page = self.embeds[index - 1]

    def set_page(self, page: int) -> None:
        self.page = page
        self.current_page = self.embeds[page]

    async def start(self, messageable: discord.abc.Messageable) -> None:
        view = self.view if len(self.embeds) > 1 else discord.utils.MISSING
        await messageable.send(embed=self.current_page, view=view)
