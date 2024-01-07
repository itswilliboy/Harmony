from __future__ import annotations

import discord
from discord.interactions import Interaction


class PaginatorView(discord.ui.View):
    def __init__(self, paginator: Paginator) -> None:
        super().__init__(timeout=300)
        self.paginator = paginator
        self.page.label = f"1/{paginator.length}"

    def update(self):
        self.prev.disabled = False
        self.next.disabled = False

        if self.paginator.index == 0:
            self.prev.disabled = True

        elif self.paginator.user_page == self.paginator.length:
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

        if page.index == 0:
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

    async def start(self, messageable: discord.abc.Messageable) -> None:
        view = self.view if len(self.embeds) > 1 else discord.utils.MISSING
        await messageable.send(embed=self.current_page, view=view)
