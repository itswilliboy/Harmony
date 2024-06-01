from __future__ import annotations

import asyncio
import datetime
import re
from typing import Any, Optional, Self

import discord
from discord import ui
from discord.ext import commands
from jwt import decode

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

from .anime import AniListClient, Media, MinifiedMedia
from .oauth import User
from .types import Edge, FavouriteTypes, MediaRelation, MediaType

ANIME_REGEX = re.compile(r"\{(.*?)\}")
MANGA_REGEX = re.compile(r"\[(.*?)\]")
INLINE_CB_REGEX = re.compile(r"(?P<CB>(`{1,2})[^`^\n]+?\2)(?:$|[^`])")
CB_REGEX = re.compile(r"```[\S\s]+?```")


def add_favourite(embed: discord.Embed, *, user: User, type: FavouriteTypes, maxlen: int = 1024, empty: bool = False):
    favourites = discord.utils.find(lambda f: f["_type"] == type, user.favourites)

    if favourites and favourites["items"]:
        value = ""
        for favourite in favourites["items"][:5]:
            fmt = f"\n- **[{favourite.name}]({favourite.site_url})**"
            if len(value + fmt) > maxlen:
                break
            value += fmt
    elif empty:
        value = "No Favourites Found..."
    else:
        return

    embed.add_field(name=f"Favourite {type.title()}", value=value, inline=False)


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
    async def from_custom_id(cls, interaction: discord.Interaction[Harmony], item: discord.ui.Item[Any], match: re.Match[str]) -> Self:
        return cls(int(match.group("USER_ID")))

    @classmethod
    def view(cls, user: discord.abc.Snowflake) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        view.add_item(cls(user.id))
        return view


class AniUser(commands.UserConverter):
    async def convert(self, ctx: Context, argument: str) -> Optional[str | int]:
        try:
            user = await super().convert(ctx, argument)

            if jwt := await ctx.pool.fetchval("SELECT access_token FROM anilist_codes WHERE user_id = $1", user.id):
                uid = decode(jwt, options={"verify_signature": False})["sub"]
                return int(uid)

        except commands.BadArgument:
            pass

        return argument


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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if await self.bot.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM inline_search_optout WHERE user_id = $1)", message.author.id
        ):
            return

        content = message.content

        for match in reversed(list(INLINE_CB_REGEX.finditer(content))):
            start, end = match.span("CB")
            content = content[:start] + content[end:]

        content = CB_REGEX.sub(" ", content)

        anime = list(set(ANIME_REGEX.findall(content)))
        manga = list(set(MANGA_REGEX.findall(content)))

        if not anime and not manga:
            return

        found: list[MinifiedMedia] = []

        async with message.channel.typing():
            embed = PrimaryEmbed()

            for name in anime:
                media = await self.client.search_minified_media(name, type=MediaType.ANIME)
                if media and media not in found:
                    found.append(media)
                    embed.add_field(name=f"**__{media.name}__**", value=media.small_info, inline=False)

            for name in manga:
                media = await self.client.search_minified_media(name, type=MediaType.MANGA)
                if media and media not in found:
                    found.append(media)
                    embed.add_field(name=f"**__{media.name}__**", value=media.small_info, inline=False)

        if not embed:
            try:
                await message.add_reaction("\N{BLACK QUESTION MARK ORNAMENT}")
                await asyncio.sleep(3)
                await message.remove_reaction("\N{BLACK QUESTION MARK ORNAMENT}", self.bot.user)
            except discord.HTTPException:
                pass
            return

        prefixes = await self.bot.get_prefix(message)
        prefix = next(iter(sorted(prefixes, key=len)), "ht;")

        embed.set_footer(text=f'{{anime}} \N{EM DASH} [manga] \N{EM DASH} Run "{prefix}optout" to disable this.')

        if len(embed.fields) == 1:
            media = found[0]
            embed.set_thumbnail(url=media.cover["extraLarge"])

            if media.cover["color"]:
                embed.color = discord.Colour.from_str(media.cover["color"])

        await message.channel.send(embed=embed, view=Delete.view(message.author))

    async def search(
        self,
        ctx: Context,
        search: str,
        search_type: MediaType,
    ) -> None:
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

    @commands.command(hidden=True)
    async def optout(self, ctx: Context):
        """Opts you out (or back in) of inline search."""
        if await ctx.pool.fetchval("SELECT EXISTS(SELECT 1 FROM inline_search_optout WHERE user_id = $1)", ctx.author.id):
            await ctx.pool.execute("DELETE FROM inline_search_optout WHERE user_id = $1", ctx.author.id)
            await ctx.send("Opted back into inline search.")
        else:
            await ctx.pool.execute("INSERT INTO inline_search_optout (user_id) VALUES ($1)", ctx.author.id)
            await ctx.send("Opted out of inline search.")

    @commands.command()
    async def anime(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific anime."""
        await self.search(ctx, search, MediaType.ANIME)

    @commands.command()
    async def manga(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific manga."""
        await self.search(ctx, search, MediaType.MANGA)

    @commands.group(invoke_without_command=True)
    async def anilist(self, ctx: Context, user: Optional[str | int] = commands.parameter(converter=AniUser, default=None)):

        if user is None:
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

            user_ = await self.client.oauth.get_current_user(token.token)
        else:
            if isinstance(user, str) and user.isnumeric():
                user = int(user)
            user_ = await self.client.oauth.get_user(user)

            if user_ is None:
                raise GenericError("Couldn't find any user with that name.")

        embed = PrimaryEmbed(
            title=user_.name,
            url=user_.url,
            description=user_.about + "\n\u200b" if user_.about else "",
        )

        embed.set_footer(text="Account Created")
        embed.timestamp = user_.created_at

        if url := user_.banner_url:
            embed.set_image(url=url)

        if url := user_.avatar_url:
            embed.set_thumbnail(url=url)

        if user_.anime_stats.episodes_watched:
            s = user_.anime_stats
            embed.add_field(
                name="Anime Statistics",
                value=(
                    f"Anime Watched: **`{s.count:,}`**\n"
                    f"Episodes Watched: **`{s.episodes_watched:,}`**\n"
                    f"Hours Watched: **`{(s.minutes_watched / 60):.1f}` (`{(s.minutes_watched / 1440):.1f} days`)**"
                ),
                inline=True,
            )

            if s.mean_score:
                embed.add_field(
                    name="Average Anime Score",
                    value=f"**{s.mean_score} // 100**\n{progress_bar(s.mean_score)}",
                    inline=True,
                )

        if user_.manga_stats.chapters_read:
            add_favourite(embed, user=user_, type=FavouriteTypes.ANIME, empty=True)

            s = user_.manga_stats
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
                    inline=True,
                )

        else:
            add_favourite(embed, user=user_, type=FavouriteTypes.ANIME)

        add_favourite(embed, user=user_, type=FavouriteTypes.MANGA)
        add_favourite(embed, user=user_, type=FavouriteTypes.CHARACTERS)
        add_favourite(embed, user=user_, type=FavouriteTypes.STAFF)
        add_favourite(embed, user=user_, type=FavouriteTypes.STUDIOS)

        await ctx.send(embed=embed)

    @anilist.command(aliases=["auth"])
    async def login(self, ctx: Context):
        query = "SELECT expires_in FROM anilist_codes WHERE user_id = $1"
        expiry: Optional[datetime.datetime] = await self.bot.pool.fetchval(
            query,
            ctx.author.id,
        )

        if expiry and expiry > datetime.datetime.now():
            embed = SuccessEmbed(description="You are already logged in. Log out and back in to re-new the session.")
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
