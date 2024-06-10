from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Optional, Self

import discord
from discord import ui

from config import ANILIST_URL
from utils import ErrorEmbed, SuccessEmbed

from .anime import Media
from .oauth import User
from .types import Edge, MediaRelation

if TYPE_CHECKING:
    from bot import Harmony

    from . import AniList
    from .client import AniListClient

PIXEL_LINE_URL = "https://i.imgur.com/IfBmnOp.png"  # For making multiple embeds the same width


async def callback(cog: AniList, id: int, interaction: discord.Interaction, user: Optional[User] = None):
    media = await cog.client.fetch_media(id, user_id=interaction.user.id)

    if media is None:
        return await interaction.response.send_message(
            "Something went wrong when trying to find that media.", ephemeral=True
        )

    view = discord.utils.MISSING
    if media.relations:
        view = RelationView(cog, media, user)

    embeds: list[discord.Embed] = []

    if not media.embed.image:
        em = media.embed.copy()
        em.set_image(url=PIXEL_LINE_URL)
        embeds.append(em)

    else:
        embeds.append(media.embed)

    if em := media.list_embed:
        em.set_image(url=PIXEL_LINE_URL)
        embeds.append(em)

    if em := media.following_status_embed(user):
        em.set_image(url=PIXEL_LINE_URL)
        embeds.append(em)

    await interaction.response.edit_message(embeds=embeds, view=view)


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
    def __init__(self, cog: AniList, options: list[discord.SelectOption]) -> None:
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

    async def callback(self, interaction: discord.Interaction):
        await callback(self.cog, self._edge_id, interaction)

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
    def __init__(self, cog: AniList, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="Select an adaptation to view",
            min_values=1,
            max_values=1,
            options=options[:25],
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await callback(self.cog, int(self.values[0].split("\u200b")[1]), interaction)


class RelationView(ui.View):
    def __init__(
        self,
        cog: AniList,
        media: Media,
        user: Optional[User] = None,
    ) -> None:
        super().__init__()
        self.media = media
        self.cog = cog

        relation_options: list[discord.SelectOption] = []
        adaptation_options: list[discord.SelectOption] = []
        relations = sorted(media.relations, key=self._sort_relations)
        for edge in relations:
            value = f"{edge.title}\u200b{edge.id}"
            if len(value) > 100:
                value = f"{edge.title[:100-len(value)]}\u200b{edge.id}"  # Shorten value to 100 characters, but keep ID

            if edge.type == MediaRelation.SOURCE:
                self.add_item(RelationButton(self.cog, edge, "Source", "\N{OPEN BOOK}", user=user))

            elif edge.type == MediaRelation.PREQUEL:
                self.add_item(RelationButton(self.cog, edge, "Prequel", "\N{LEFTWARDS BLACK ARROW}", user=user))

            elif edge.type == MediaRelation.SEQUEL:
                self.add_item(RelationButton(self.cog, edge, "Sequel", "\N{BLACK RIGHTWARDS ARROW}", user=user))

            elif edge.type == MediaRelation.ADAPTATION:
                adaptation_options.append(
                    discord.SelectOption(
                        emoji="\N{MOVIE CAMERA}",
                        label=edge.title[:100],
                        value=value,
                        description="Adaptation",
                    )
                )

            elif edge.type == MediaRelation.SIDE_STORY:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{TWISTED RIGHTWARDS ARROWS}",
                        label=edge.title[:100],
                        value=value,
                        description="Side Story",
                    )
                )

            elif edge.type == MediaRelation.ALTERNATIVE:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{TWISTED RIGHTWARDS ARROWS}",
                        label=edge.title[:100],
                        value=value,
                        description="Alternative",
                    )
                )

            elif edge.type == MediaRelation.SPIN_OFF:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
                        label=edge.title[:100],
                        value=value,
                        description="Spin Off",
                    )
                )

        if adaptation_options:
            self.add_item(AdaptationSelect(self.cog, adaptation_options))

        if relation_options:
            self.add_item(RelationSelect(self.cog, relation_options))

        if len(self.children) > 25:
            self._children = self._children[:25]

    @staticmethod
    def _sort_relations(edge: Edge) -> int:
        enums = [enum.value for enum in MediaRelation]
        return enums.index(edge.type)


class CodeModal(ui.Modal, title="Enter OAuth Code"):
    code: str
    code_input: ui.TextInput[Self] = ui.TextInput(label="OAuth Code", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        self.code = self.code_input.value
        await interaction.response.defer()


class CodeView(ui.View):
    def __init__(self, author: discord.User | discord.Member) -> None:
        super().__init__(timeout=120)
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("This is not your button.", ephemeral=True)
            return False
        return True

    @ui.button(label="Enter Code", style=discord.ButtonStyle.green)
    async def enter(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(CodeModal())


class LoginView(ui.View):
    def __init__(self, bot: Harmony, author: discord.User | discord.Member, client: AniListClient) -> None:
        super().__init__(timeout=120)
        self.author = author
        self.bot = bot
        self.client = client

        self._children.insert(
            0,
            ui.Button(
                url=ANILIST_URL,
                label="Get Code",
            ),
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("This is not your button.", ephemeral=True)
            return False

        return True

    async def check_login(
        self,
        code: Optional[str],
    ) -> bool:
        if code is None:
            return False

        resp = await self.client.oauth.get_access_token(code)
        if resp is None:
            return False

        token, expires_in = resp

        query = "INSERT INTO anilist_codes VALUES ($1, $2, $3)"
        await self.bot.pool.execute(
            query,
            self.author.id,
            token,
            expires_in,
        )

        return True

    @ui.button(label="Enter Code", style=discord.ButtonStyle.green)
    async def modal(self, interaction: discord.Interaction, _):
        modal = CodeModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        is_logged_in = await self.check_login(modal.code)
        if is_logged_in:
            await interaction.edit_original_response(
                embed=SuccessEmbed(description="Successfully logged you in."),
                view=None,
            )
        else:
            await interaction.followup.send(
                embed=ErrorEmbed(description="Invalid code, try again."),
                ephemeral=True,
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
