from __future__ import annotations

import re
from os import urandom
from typing import TYPE_CHECKING, Any, Optional, Self

import discord
from discord import ui

from utils import BaseView

from .anime import Media
from .oauth import User
from .types import Edge, MediaRelation, SearchMedia

if TYPE_CHECKING:
    from bot import Harmony

    from . import AniList, AniListClient

    Interaction = discord.Interaction[Harmony]


async def callback(cog: AniList, id: int, interaction: discord.Interaction, user: Optional[User] = None):
    media = await cog.client.fetch_media(id, user_id=interaction.user.id)

    if media is None:
        return await interaction.response.send_message(
            "Something went wrong when trying to fetch that media", ephemeral=True
        )

    view = EmbedRelationView(cog, media, user, author=interaction.user)

    await interaction.response.edit_message(embed=media.embed, view=view)


class RelationButton(ui.Button["RelationView"]):
    def __init__(
        self,
        cog: AniList,
        edge: Edge,
        text: str,
        emoji: str,
        row: Optional[int] = None,
        user: Optional[User] = None,
    ) -> None:
        label = f"{text}: {edge.title}"
        if len(label) > 80:
            label = label[:77] + "..."

        super().__init__(label=label, emoji=emoji, row=row)
        self.cog = cog
        self.edge = edge
        self.text = text
        self.user = user

    async def callback(self, interaction: discord.Interaction) -> None:
        await callback(self.cog, self.edge.id, interaction, self.user)


class RelationSelect(ui.Select["RelationView"]):
    def __init__(self, cog: AniList, options: list[discord.SelectOption], user: Optional[User] = None) -> None:
        for option in options:
            if len(option.label) > 80:
                option.label = option.label[:77] + "..."

        super().__init__(
            placeholder="Select a relation to view",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

        self.cog = cog
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        await callback(self.cog, self._edge_id, interaction, self.user)

    @property
    def _edge_name(self) -> str:
        return self.values[0].split("\u200b")[0]

    @property
    def _edge_id(self) -> int:
        return int(self.values[0].split("\u200b")[1])

    @staticmethod
    def _get_name(value: str) -> str:
        return value.split("\u200b")[0]


class AdaptationSelect(ui.Select["RelationView"]):
    def __init__(self, cog: AniList, options: list[discord.SelectOption], user: Optional[User] = None) -> None:
        super().__init__(
            placeholder="Select an adaptation to view",
            min_values=1,
            max_values=1,
            options=options[:25],
        )
        self.cog = cog
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        await callback(self.cog, int(self.values[0].split("\u200b")[1]), interaction, self.user)


class RelationView(BaseView):
    def __init__(
        self, cog: AniList, media: Media, user: Optional[User] = None, author: Optional[discord.abc.Snowflake] = None
    ) -> None:
        super().__init__(author)
        self.media = media
        self.cog = cog
        self.author = author

        relation_options: list[discord.SelectOption] = []
        adaptation_options: list[discord.SelectOption] = []
        relations = sorted(media.relations, key=self._sort_relations)
        for edge in relations:
            value = f"{edge.title}\u200b{edge.id}"
            if len(value) > 100:
                value = f"{edge.title[: 100 - len(value)]}\u200b{edge.id}"  # Shorten value to 100 characters, but keep ID

            if edge.type == MediaRelation.SOURCE:
                self.add_item(RelationButton(self.cog, edge, "Source", "\N{OPEN BOOK}", user=user))

            elif edge.type == MediaRelation.PREQUEL:
                self.add_item(RelationButton(self.cog, edge, "Prequel", "\N{LEFTWARDS BLACK ARROW}", user=user))

            elif edge.type == MediaRelation.SEQUEL:
                self.add_item(RelationButton(self.cog, edge, "Sequel", "\N{BLACK RIGHTWARDS ARROW}", user=user))

            elif edge.type == MediaRelation.ADAPTATION:
                adaptation_options.append(
                    discord.SelectOption(
                        emoji="\N{MOVIE CAMERA}", label=edge.title[:100], value=value, description=self.get_edge_data(edge)
                    )
                )

            elif edge.type == MediaRelation.SIDE_STORY:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{TWISTED RIGHTWARDS ARROWS}",
                        label=edge.title[:100],
                        value=value,
                        description=self.get_edge_data(edge),
                    )
                )

            elif edge.type == MediaRelation.ALTERNATIVE:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{TWISTED RIGHTWARDS ARROWS}",
                        label=edge.title[:100],
                        value=value,
                        description=self.get_edge_data(edge),
                    )
                )

            elif edge.type == MediaRelation.SPIN_OFF:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
                        label=edge.title[:100],
                        value=value,
                        description=self.get_edge_data(edge),
                    )
                )

        if adaptation_options:
            self.add_item(AdaptationSelect(self.cog, adaptation_options, user))

        if relation_options:
            self.add_item(RelationSelect(self.cog, relation_options, user))

        if len(self.children) > 25:
            self._children = self._children[:25]

    @staticmethod
    def _sort_relations(edge: Edge) -> int:
        enums = [enum.value for enum in MediaRelation]
        return enums.index(edge.type)

    @staticmethod
    def get_edge_data(edge: Edge) -> str:
        format = (edge.format or "N/A").title().replace("_", " ")
        status = (edge.status or "N/A").title().replace("_", " ")
        type = str(edge.type).title().replace("_", " ")

        if len(format) <= 3:  # Capitalise TV, OVA, & ONA
            format = format.upper()

        return f"{type} - {format} {f'({edge.year})' if edge.year else ''} - {status}"


class CodeModal(ui.Modal, title="Enter OAuth Code"):
    code: str
    code_input: ui.TextInput[Self] = ui.TextInput(label="OAuth Code", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        self.code = self.code_input.value
        await interaction.response.defer()


class CodeView(BaseView):
    def __init__(self, author: discord.User | discord.Member) -> None:
        super().__init__(author, timeout=120)
        self.author = author

    @ui.button(label="Enter Code", style=discord.ButtonStyle.green)
    async def enter(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(CodeModal())


class LoginView(BaseView):
    def __init__(self, bot: Harmony, author: discord.User | discord.Member, client: AniListClient) -> None:
        super().__init__(author, timeout=120)
        self.author = author
        self.bot = bot
        self.client = client

        random = urandom(16).hex()
        self.client.random_store[self.author.id] = random
        self._children.insert(
            0,
            ui.Button(
                url=f"https://harmony.itswilli.dev/login?id={self.author.id}&r={random}",
                label="Login with Anilist",
            ),
        )


class Delete(discord.ui.DynamicItem[discord.ui.Button[discord.ui.View]], template=r"DELETE:(?P<USER_ID>\d+)"):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(discord.ui.Button(emoji="\N{WASTEBASKET}", custom_id=f"DELETE:{user_id}"))

    async def callback(self, interaction: discord.Interaction[Harmony]) -> Any:
        if not interaction.message:
            return interaction.response.defer()
        await interaction.message.delete()

    async def interaction_check(self, interaction: discord.Interaction[Harmony]) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return False
        return True

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction[Harmony], item: discord.ui.Item[Any], match: re.Match[str]
    ) -> Self:
        return cls(int(match.group("USER_ID")))

    @classmethod
    def view(cls, user: discord.abc.Snowflake) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        view.add_item(cls(user.id))
        return view


class EmbedSelect(discord.ui.Select["EmbedRelationView"]):
    def __init__(self, media: Media, user: Optional[User] = None) -> None:
        self.media = media
        self.user = user
        self.children: list[discord.ui.Item["EmbedRelationView"]]

        options = [
            discord.SelectOption(
                label="Information",
                description="General information about the media.",
                emoji="\N{INFORMATION SOURCE}\N{VARIATION SELECTOR-16}",
                default=True,
                value="0",
            )
        ]

        if media.status_embed(user):
            options.append(
                discord.SelectOption(
                    label="Your & Friends' Statuses",
                    description="View watching status, progress, rating, etc.",
                    emoji="\N{BUSTS IN SILHOUETTE}",
                    value="1",
                )
            )

        super().__init__(options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction[Harmony]):
        value = self.values[0]

        for option in self.options:
            option.default = False
        self.options[int(value)].default = True

        embed: discord.Embed
        if value == "0":
            embed = self.media.embed

            assert self.view
            self.view._children = self.children

        else:
            embed = self.media.status_embed(self.user) or discord.Embed(description="Something went wrong...")

            assert self.view
            self.children = self.view.children.copy()
            for item in self.view.children:
                if not isinstance(item, EmbedSelect):
                    self.view._children.remove(item)

        await interaction.response.edit_message(embed=embed, view=self.view)


class EmbedRelationView(RelationView):
    def __init__(
        self, cog: AniList, media: Media, user: Optional[User] = None, author: Optional[discord.abc.Snowflake] = None
    ) -> None:
        super().__init__(cog, media, user, author)

        if media.status_embed(user):
            self.add_item(EmbedSelect(media, user))


class ProfileManagementView(BaseView):
    def __init__(self, cog: AniList, user: User, author: Optional[discord.abc.Snowflake] = None) -> None:
        super().__init__(author)

        self.cog = cog
        self.user = user

    @ui.button(label="Logout", style=discord.ButtonStyle.red)
    async def logout(self, interaction: Interaction, _):
        await interaction.response.send_message("logged out")


class SearchSelect(ui.Select["SearchView"]):
    def __init__(
        self,
        cog: AniList,
        media: list[SearchMedia],
        user: Optional[User] = None,
        author: Optional[discord.abc.Snowflake] = None,
    ) -> None:
        options = [
            discord.SelectOption(label=m["title"]["romaji"][:100], description=m["type"].title(), value=str(m["id"]))
            for m in media
        ]
        super().__init__(options=options, min_values=1, max_values=1)

        self.cog = cog
        self.user = user
        self.author = author

    async def callback(self, interaction: Interaction):
        media = await self.cog.client.fetch_media(int(self.values[0]), user_id=self.author.id if self.author else None)
        assert media

        view = EmbedRelationView(self.cog, media, self.user, self.author)

        await interaction.response.edit_message(view=view, embed=media.embed, content=None)


class SearchView(BaseView):
    def __init__(
        self,
        cog: AniList,
        media: list[SearchMedia],
        author: Optional[discord.abc.Snowflake] = None,
        user: Optional[User] = None,
    ) -> None:
        super().__init__(author)

        self.user = user

        self.add_item(SearchSelect(cog, media, user, author))
