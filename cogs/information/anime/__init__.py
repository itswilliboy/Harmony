from __future__ import annotations

import datetime
from typing import Any, Optional, Self

import discord
from discord import ui
from discord.ext import commands

from bot import Harmony
from config import ANILIST_URL
from utils import (
    BaseCog,
    Context,
    ErrorEmbed,
    GenericError,
    PrimaryEmbed,
    SuccessEmbed,
    progress_bar,
)

from .anime import AniListClient, Media
from .types import Edge, MediaRelation, MediaType


async def callback(cog: AniList, id: int, interaction: discord.Interaction):
    media = await cog.client.fetch_media(id)

    if media is None:
        return await interaction.response.send_message(
            "Something went wrong when trying to find that media.", ephemeral=True
        )

    view = discord.utils.MISSING
    if media.relations:
        view = RelationView(cog, media)

    await interaction.response.send_message(embed=media.embed, view=view, ephemeral=True)


class RelationButton(ui.Button["RelationView"]):
    def __init__(
        self,
        cog: AniList,
        edge: Edge,
        text: str,
        emoji: str,
        row: Optional[int] = None,
    ) -> None:
        label = f"{text}: {edge.title}"
        if len(label) > 80:
            label = label[:77] + "..."

        super().__init__(label=label, emoji=emoji, row=row)
        self.cog = cog
        self.edge = edge
        self.text = text

    async def callback(self, interaction: discord.Interaction) -> None:
        await callback(self.cog, self.edge.id, interaction)


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
                self.add_item(RelationButton(self.cog, edge, "Source", "\N{OPEN BOOK}"))

            elif edge.type == MediaRelation.PREQUEL:
                self.add_item(RelationButton(self.cog, edge, "Prequel", "\N{LEFTWARDS BLACK ARROW}"))

            elif edge.type == MediaRelation.SEQUEL:
                self.add_item(RelationButton(self.cog, edge, "Sequel", "\N{BLACK RIGHTWARDS ARROW}"))

            elif edge.type == MediaRelation.ADAPTATION:
                adaptation_options.append(
                    discord.SelectOption(
                        emoji="\N{MOVIE CAMERA}",
                        label=edge.title,
                        value=value,
                        description="Adaptation",
                    )
                )

            elif edge.type == MediaRelation.SIDE_STORY:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{TWISTED RIGHTWARDS ARROWS}",
                        label=edge.title,
                        value=value,
                        description="Side Story",
                    )
                )

            elif edge.type == MediaRelation.ALTERNATIVE:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{TWISTED RIGHTWARDS ARROWS}",
                        label=edge.title,
                        value=value,
                        description="Alternative",
                    )
                )

            elif edge.type == MediaRelation.SPIN_OFF:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
                        label=edge.title,
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


class AniList(BaseCog):
    def __init__(
        self,
        bot: Harmony,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(bot, *args, **kwargs)

        self.client = AniListClient(bot)

    async def search(
        self,
        ctx: Context,
        search: str,
        search_type: MediaType,
    ):
        assert not isinstance(ctx.channel, discord.PartialMessageable | discord.GroupChannel)

        media, user = await self.client.search_media(
            search,
            type=search_type,
            user_id=ctx.author.id,
        )

        if media is None:
            raise GenericError(f"Couldn't find any {search_type.value.lower()} with that name.")

        if media.is_adult and not (
            isinstance(
                ctx.channel,
                discord.DMChannel,
            )
            or ctx.channel.is_nsfw()
        ):
            raise GenericError(
                (
                    f"This {search_type.value.lower()} was flagged as NSFW. "
                    "Please try searching in an NSFW channel or in my DMs."
                )
            )

        view = discord.utils.MISSING

        if media.relations:
            view = RelationView(self, media)

        embeds: list[discord.Embed] = []

        PIXEL_LINE_URL = "https://i.imgur.com/IfBmnOp.png"  # For making the embeds the same width

        if not media.embed.image:
            em = media.embed.copy()
            em.set_image(url=PIXEL_LINE_URL)
            embeds.append(em)

        else:
            embeds.append(media.embed)

        if em := media.list_embed:
            em.set_image(url=PIXEL_LINE_URL)
            em.set_thumbnail(url=ctx.author.display_avatar.url)
            embeds.append(em)

        if em := media.following_status_embed(user):
            em.set_image(url=PIXEL_LINE_URL)
            embeds.append(em)

        await ctx.send(embeds=embeds, view=view)

    @commands.command()
    async def anime(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific anime."""
        await self.search(ctx, search, MediaType.ANIME)

    @commands.command()
    async def manga(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific manga."""
        await self.search(ctx, search, MediaType.MANGA)

    @commands.group(invoke_without_command=True)
    async def anilist(self, ctx: Context, username: Optional[str] = None):
        if username is None:
            token = await self.client.get_token(ctx.author.id)
            if token is None:
                cp = ctx.clean_prefix
                raise commands.BadArgument(
                    message=f"You need to pass an AniList username or log in with {cp}anilist login to view yourself."
                )
            elif token.expiry < datetime.datetime.now():
                raise GenericError(
                    f"Your token has expired, create a new one with {ctx.clean_prefix}anilist login.",
                )

            user = await self.client.oauth.get_current_user(token.token)
        else:
            user = await self.client.oauth.get_user(username)

            if user is None:
                raise GenericError("Couldn't find any user with that name.")

        embed = PrimaryEmbed(
            title=user.name,
            url=user.url,
            description=user.about + "\n\u200b" if user.about else "",
        )

        embed.set_footer(text="Account Created")
        embed.timestamp = user.created_at

        if url := user.banner_url:
            embed.set_image(url=url)

        if url := user.avatar_url:
            embed.set_thumbnail(url=url)

        if user.anime_stats.episodes_watched:
            s = user.anime_stats
            embed.add_field(
                name="Anime Statistics",
                value=(
                    f"Anime Watched: **`{s.count:,}`**\n"
                    f"Episodes Watched: **`{s.episodes_watched:,}`**\n"
                    f"Minutes Watched: **`{s.minutes_watched:,}` (`{(s.minutes_watched / 1440):.1f} days`)**"
                ),
                inline=True,
            )

            if s.mean_score:
                embed.add_field(
                    name="Average Anime Score",
                    value=f"**{s.mean_score} // 100**\n{progress_bar(s.mean_score)}",
                    inline=False,
                )

        if user.manga_stats.chapters_read:
            s = user.manga_stats
            embed.add_field(
                name="Manga Statistics",
                value=(
                    f"Manga Read: **`{s.count:,}`**\n"
                    f"Volumes Read: **`{s.volumes_read:,}`**\n"
                    f"Chapters Read: **`{s.chapters_read:,}`**"
                ),
                inline=True,
            )

            if s.mean_score:
                embed.add_field(
                    name="Average Manga Score",
                    value=f"**{s.mean_score} // 100**\n{progress_bar(s.mean_score)}",
                    inline=False,
                )

        values: list[str] = []
        for node in user.favourites:
            name = node["_type"].title()

            if name.endswith("s"):
                name = name[:-1]

            for item in node["items"]:
                values.append(f"{name}: **[{item.name}]({item.site_url})**")
                break

        if values:
            embed.add_field(name="Favourites", value="\n".join(values), inline=False)

        await ctx.send(embed=embed)

    @anilist.command(aliases=["auth"])
    async def login(self, ctx: Context):
        query = "SELECT expires_in FROM anilist_codes WHERE user_id = $1"
        expiry: Optional[datetime.datetime] = await self.bot.pool.fetchval(
            query,
            ctx.author.id,
        )

        if expiry and expiry > datetime.datetime.now():
            embed = SuccessEmbed(description="You are already logged in. Log out and back in to re-new session.")
            embed.set_footer(text=f"Run `{ctx.clean_prefix}anilist logout` to log out.")
            return await ctx.send(embed=embed)

        embed = PrimaryEmbed(
            title="Authorise with Anilist",
            description="Copy the code from the link below, and then press the green button for the next step.",
        )

        await ctx.send(
            embed=embed,
            view=LoginView(ctx.bot, ctx.author, self.client),
        )

    @anilist.command()
    async def logout(self, ctx: Context):
        query = "SELECT EXISTS(SELECT 1 FROM anilist_codes WHERE user_id = $1)"
        exists = await self.bot.pool.fetchval(query, ctx.author.id)

        if not exists:
            raise GenericError("You are not logged in.")

        query = "DELETE FROM anilist_codes WHERE user_id = $1"
        await self.bot.pool.execute(query, ctx.author.id)

        await ctx.send(
            embed=SuccessEmbed(description="Successfully logged you out."),
        )
