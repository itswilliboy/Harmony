# TODO: Check if Media is NSFW, and refer to use the command in an NSFW-channel.
from __future__ import annotations

import datetime
import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Self, TypedDict

import discord
from discord.ext import commands

from config import ANILIST_URL
from utils import BaseCog, Context, ErrorEmbed, GenericError, PrimaryEmbed, SuccessEmbed

from .oauth import OAuth, AccessToken

if TYPE_CHECKING:
    from bot import Harmony

    from .oauth import PartialNode

    Interaction = discord.Interaction[Harmony]


class MediaType(StrEnum):
    ANIME = "ANIME"
    MANGA = "MANGA"


class MediaStatus(StrEnum):
    """The current publishing status of the media."""

    FINISHED = "FINISHED"
    RELEASING = "RELEASING"
    NOT_YET_RELEASED = "NOT_YET_RELEASED"
    CANCELLED = "CANCELLED"
    HIATUS = "HIATUS"


class MediaRelation(StrEnum):
    """The type of relation."""

    SOURCE = "SOURCE"
    PREQUEL = "PREQUEL"
    SEQUEL = "SEQUEL"
    SIDE_STORY = "SIDE_STORY"
    ALTERNATIVE = "ALTERNATIVE"

    ADAPTATION = "ADAPTATION"
    PARENT = "PARENT"
    CHARACTER = "CHARACTER"
    SUMMARY = "SUMMARY"
    SPIN_OFF = "SPIN_OFF"
    OTHER = "OTHER"
    COMPILATION = "COMPILATION"
    CONTAINS = "CONTAINS"


class MediaSeason(StrEnum):
    WINTER = "WINTER"
    SPRING = "SPRING"
    SUMMER = "SUMMER"
    FALL = "FALL"


class MediaListStatus(StrEnum):
    CURRENT = "CURRENT"
    PLANNING = "PLANNING"
    COMPLETED = "COMPLETED"
    DROPPED = "DROPPED"
    PAUSED = "PAUSED"
    REPEATING = "REPEATING"


class MediaTitle(TypedDict):
    """The official titles of the media in various languages."""

    romaji: str
    english: str | None
    native: str | None


class FuzzyDate(TypedDict):
    """Construct of dates provided by the API."""

    year: int | None
    month: int | None
    day: int | None


class MediaCoverImage(TypedDict):
    """A set of media images and the most prominent colour in them."""

    extraLarge: str
    large: str
    medium: str
    color: str


class Edge(NamedTuple):
    id: int
    title: str
    type: MediaRelation


class Studio(TypedDict):
    name: str
    siteUrl: str


class MediaList(TypedDict):
    score: float
    status: MediaListStatus
    progress: int
    progressVolumes: int
    private: bool
    startedAt: FuzzyDate
    completedAt: FuzzyDate
    updatedAt: int
    createdAt: int
    repeat: int


TAG_REGEX = re.compile(r"</?\w+/?>")
SOURCE_REGEX = re.compile(r"\(Source: .+\)")

SEARCH_QUERY = """
    query ($search: String, $type: MediaType) {
        Media (search: $search, type: $type) {
            id
            idMal
            type
            description(asHtml: false)
            episodes
            hashtag
            status
            bannerImage
            episodes
            duration
            chapters
            volumes
            genres
            title {
                romaji
                english
                native
            }
            startDate {
                year
                month
                day
            }
            endDate {
                year
                month
                day
            }
            season,
            seasonYear,
            coverImage {
                extraLarge
                large
                medium
                color
            }
            studios(isMain: true) {
                nodes {
                    name
                    siteUrl
                }
            }
            relations {
                edges {
                    node {
                        id
                        title {
                            romaji
                        }
                    }
                    relationType(version: 2)
                }
            }
            mediaListEntry {
                score(format: POINT_10)
                status
                progress
                progressVolumes
                private
                startedAt {
                    year
                    month
                    day
                }
                completedAt {
                    year
                    month
                    day
                }
                updatedAt
                createdAt
                repeat
            }
        }
    }
"""

FETCH_QUERY = """
    query ($id: Int) {
        Media (id: $id) {
            id
            idMal
            type
            description(asHtml: false)
            episodes
            hashtag
            status
            bannerImage
            episodes
            duration
            chapters
            volumes
            genres
            title {
                romaji
                english
                native
            }
            startDate {
                year
                month
                day
            }
            endDate {
                year
                month
                day
            }
            season,
            seasonYear,
            coverImage {
                extraLarge
                large
                medium
                color
            }
            studios(isMain: true) {
                nodes {
                    name
                    siteUrl
                }
            }
            relations {
                edges {
                    node {
                        id
                        title {
                            romaji
                        }
                    }
                    relationType(version: 2)
                }
            }
            mediaListEntry {
                score(format: POINT_10)
                status
                progress
                progressVolumes
                private
                startedAt {
                    year
                    month
                    day
                }
                completedAt {
                    year
                    month
                    day
                }
                updatedAt
                createdAt
                repeat
            }
        }
    }
"""


class Media:
    def __init__(
        self,
        id: int,
        id_mal: int,
        type: MediaType,
        title: MediaTitle,
        description: str,
        start_date: FuzzyDate,
        end_date: FuzzyDate,
        season: MediaSeason | None,
        season_year: int | None,
        status: MediaStatus,
        cover_image: MediaCoverImage,
        banner_image: str,
        hashtags: str,
        studio: Studio | None,
        episodes: int,
        duration: int,
        chapters: int,
        volumes: int,
        genres: list[str],
        relations: list[Edge],
        list_entry: MediaList | None,
    ) -> None:
        self.id = id
        self.id_mal = id_mal
        self.type = type
        self.title = title
        self._description = description
        self._start_date = start_date
        self._end_date = end_date
        self.season = season
        self.season_year = season_year
        self.status = status
        self.cover_image = cover_image
        self.banner_image = banner_image
        self._hashtags = hashtags
        self.studio = studio
        self.episodes = episodes
        self.duration = duration
        self.chapters = chapters
        self.volumes = volumes
        self._genres = genres
        self.relations = relations
        self.list_entry = list_entry

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        type_ = MediaType(data["type"])
        title = MediaTitle(data["title"])
        start_date = FuzzyDate(data["startDate"])
        end_date = FuzzyDate(data["endDate"])
        season = MediaSeason(data["season"]) if data["season"] else None
        cover_image = MediaCoverImage(data["coverImage"])
        studio = data["studios"]["nodes"][0] if data["studios"]["nodes"] else None

        relations: list[Edge] = []
        if edges := data["relations"]["edges"]:
            for edge in edges:
                node = edge["node"]
                title_ = MediaTitle(node["title"])
                relations.append(Edge(node["id"], title_["romaji"], edge["relationType"]))

        list_entry = MediaList(data["mediaListEntry"]) if data["mediaListEntry"] else None

        return cls(
            data["id"],
            data["idMal"],
            type_,
            title,
            data["description"],
            start_date,
            end_date,
            season,
            data["seasonYear"],
            data["status"],
            cover_image,
            data["bannerImage"],
            data["hashtag"],
            studio,
            data["episodes"],
            data["duration"],
            data["chapters"],
            data["volumes"],
            data["genres"],
            relations,
            list_entry,
        )

    @staticmethod
    def _to_datetime(date: FuzzyDate) -> datetime.datetime | None:
        """Converts the date-type given by the API to a `datetime.datetime` object."""
        try:
            # We could use a datetime.date instead, but since this will be used for Discord-timestamps later,
            # it will be more convenient to be able to call the .timestamp() on datetime.datetime object.
            return datetime.datetime(year=date["year"] or 0, month=date["month"] or 0, day=date["day"] or 0)
        except ValueError:
            return None

    @property
    def start_date(self) -> datetime.datetime | None:
        """Returns the date when the media started."""
        return self._to_datetime(self._start_date)

    @property
    def end_date(self) -> datetime.datetime | None:
        """Returns the date when the media ended."""
        return self._to_datetime(self._end_date)

    @property
    def colour(self) -> discord.Colour:
        """Returns the most prominent colour in the cover image."""
        if self.cover_image["color"] is None:
            return discord.Colour.dark_embed()

        return discord.Colour.from_str(self.cover_image["color"])

    @property
    def description(self) -> str:
        """Returns a cleaned version of the description."""
        if self._description is None:
            return ""

        desc = TAG_REGEX.sub("", self._description)
        split = SOURCE_REGEX.split(desc)
        desc = split[0]
        desc = desc.replace("\N{HORIZONTAL ELLIPSIS}", "").replace("...", "").rstrip()

        if not desc.endswith((".", "!", "?")):
            desc += "."

        if len(desc) > 2048:
            desc = desc[:2036]
            desc += " **[...]**"

        desc += "\n\u200b"

        return desc

    @property
    def hashtags(self) -> list[str]:
        return self._hashtags.split() if self._hashtags else []

    @property
    def genres(self) -> list[str]:
        """Returns a set of hyperlinked genres linked with the media."""

        if self.type == MediaType.MANGA:
            BASE_URL = "https://anilist.co/search/manga/"

        else:
            BASE_URL = "https://anilist.co/search/anime/"

        to_return: list[str] = []
        for genre in self._genres:
            url = (BASE_URL + genre).replace(" ", "%20")
            to_return.append(f"[{genre}]({url})")

        return to_return

    @property
    def embed(self) -> discord.Embed:
        if self.type == MediaType.MANGA:
            url = f"https://anilist.co/manga/{self.id}"

        else:
            url = f"https://anilist.co/anime/{self.id}"

        title: str = ""
        if t := self.title.get("english"):
            title = t

        elif t := self.title.get("romaji"):
            title = t

        elif t := self.title.get("native"):
            title = t

        embed = discord.Embed(title=title, description=self.description, color=self.colour, url=url)

        if title != self.title["romaji"]:
            embed.set_author(name=self.title["romaji"])

        embed.set_thumbnail(url=self.cover_image["extraLarge"])
        embed.set_image(url=self.banner_image)

        info = [
            f"↪ Native Title: **{self.title['native']}**" if self.title["native"] else "",
            f"↪ Studio: **[{self.studio['name']}]({self.studio['siteUrl']})**" if self.studio else "",
            f"↪ Episodes: **{self.episodes} \
            {f' | {(self.episodes*self.duration)/60:.1f} hours' if self.duration else ''}**"
            if self.episodes
            else "",
            f"↪ Volumes: **{self.volumes}**" if self.volumes else "",
            f"↪ Chapters: **{self.chapters}**" if self.chapters else "",
            f"↪ Year: **{self.season_year}{f' | {(self.season or str()).title()}'}**" if self.season_year else "",
        ]

        if self.start_date:
            started_at = discord.utils.format_dt(self.start_date, "d")

            ended_at = "TBA"
            if self.end_date:
                ended_at = discord.utils.format_dt(self.end_date, "d")

            info.append(f"↪ Releasing: **{started_at} ⟶ {ended_at}**")

        info = [i for i in info if i != ""]

        embed.add_field(name="Basic Information", value="\n".join(info))

        if self.genres:
            embed.add_field(name="Genres", value=", ".join(f"**{genre}**" for genre in self.genres), inline=False)

        if self.hashtags:
            embed.add_field(
                name="Hashtags",
                value=" ".join(f"**[{tag}](https://twitter.com/hashtag/{tag.replace('#', '')})**" for tag in self.hashtags),
            )

        return embed

    @property
    def list_embed(self) -> discord.Embed | None:
        entry = self.list_entry
        if entry is None:
            return None

        if entry["private"] is True:
            return None

        desc = [
            f"↪ Status: **{entry['status'].title()}**",
            f"↪ Volumes: **{entry['progressVolumes']} / {self.volumes}**" if self.type == MediaType.MANGA else "",
            f"↪ Progress: **{entry['progress']}"
            + " / "
            + (str(self.episodes) if self.type == MediaType.ANIME else str(self.chapters))
            + (" episode(s)" if self.type == MediaType.ANIME else " chapter(s)")
            + "**",
            f"↪ Score: **{entry['score']} / 10**",
        ]

        if entry["startedAt"] or entry["completedAt"]:
            started_at = completed_at = None

            if entry["startedAt"]["year"]:
                started_at = discord.utils.format_dt(self._to_datetime(entry["startedAt"]), "d")  # type: ignore

            if entry["completedAt"]["year"]:
                completed_at = discord.utils.format_dt(self._to_datetime(entry["completedAt"]), "d")  # type: ignore

            if started_at and not completed_at:
                desc.append(f"↪ Started at: **{started_at}**")

            elif completed_at and not started_at:
                desc.append(f"↪ Completed at: **{completed_at}**")

            elif started_at and completed_at:
                desc.append(f"↪ Started / Completed: **{started_at} ⟶ {completed_at}**")

        desc = [i for i in desc if i != ""]

        embed = discord.Embed(colour=self.colour, description="\n".join(desc))

        if entry["updatedAt"]:
            embed.set_footer(text="Last Updated").timestamp = datetime.datetime.fromtimestamp(entry["updatedAt"])

        return embed


async def callback(cog: AniList, id: int, interaction: Interaction):
    media = await cog.fetch_media(id)

    if media is None:
        return await interaction.response.send_message(
            "Something went wrong when trying to find that media.", ephemeral=True
        )

    view = discord.utils.MISSING
    if media.relations:
        view = RelationView(cog, media)

    await interaction.response.send_message(embed=media.embed, view=view, ephemeral=True)


class RelationButton(discord.ui.Button):
    def __init__(self, cog: AniList, edge: Edge, text: str, emoji: str, row: int | None = None) -> None:
        label = f"{text}: {edge.title}"
        if len(label) > 80:
            label = label[:77] + "..."

        super().__init__(label=label, emoji=emoji, row=row)
        self.cog = cog
        self.edge = edge
        self.text = text

    async def callback(self, interaction: Interaction) -> None:
        await callback(self.cog, self.edge.id, interaction)


class RelationSelect(discord.ui.Select):
    def __init__(self, cog: AniList, options: list[discord.SelectOption]) -> None:
        for option in options:
            if len(option.label) > 80:
                option.label = option.label[:77] + "..."

        super().__init__(placeholder="Select a relation to view", min_values=1, max_values=1, options=options[:25])
        self.cog = cog

    async def callback(self, interaction: Interaction):
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


class AdaptationSelect(discord.ui.Select):
    def __init__(self, cog: AniList, options: list[discord.SelectOption]) -> None:
        super().__init__(placeholder="Select an adaptation to view", min_values=1, max_values=1, options=options[:25])
        self.cog = cog

    async def callback(self, interaction: Interaction):
        await callback(self.cog, int(self.values[0].split("\u200b")[1]), interaction)


class RelationView(discord.ui.View):
    def __init__(self, cog: AniList, media: Media) -> None:
        super().__init__()
        self.media = media
        self.cog = cog

        relation_options = []
        adaptation_options = []
        relations = sorted(media.relations, key=self._sort_relations)
        for edge in relations:
            value = f"{edge.title}\u200b{edge.id}"
            if len(value) > 100:
                value = f"{edge.title[:100-len(value)]}\u200b{edge.id}"  # Shorten value to 100 characters, but keep ID

            if edge.type == MediaRelation.SOURCE:
                self.add_item(RelationButton(self.cog, edge, "Source", "\N{OPEN BOOK}", row=0))

            elif edge.type == MediaRelation.PREQUEL:
                self.add_item(RelationButton(self.cog, edge, "Prequel", "\N{LEFTWARDS BLACK ARROW}", row=0))

            elif edge.type == MediaRelation.SEQUEL:
                self.add_item(RelationButton(self.cog, edge, "Sequel", "\N{BLACK RIGHTWARDS ARROW}", row=0))

            elif edge.type == MediaRelation.ADAPTATION:
                adaptation_options.append(
                    discord.SelectOption(emoji="\N{MOVIE CAMERA}", label=edge.title, value=value, description="Adaptation")
                )

            elif edge.type == MediaRelation.SIDE_STORY:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{TWISTED RIGHTWARDS ARROWS}", label=edge.title, value=value, description="Side Story"
                    )
                )

            elif edge.type == MediaRelation.ALTERNATIVE:
                relation_options.append(
                    discord.SelectOption(
                        emoji="\N{TWISTED RIGHTWARDS ARROWS}", label=edge.title, value=value, description="Alternative"
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


class CodeModal(discord.ui.Modal, title="Enter OAuth Code"):
    code: str

    code_input = discord.ui.TextInput(label="OAuth Code", style=discord.TextStyle.short)

    async def on_submit(self, interaction: Interaction):
        self.code = self.code_input.value
        await interaction.response.send_message("Successfully retrieved code", ephemeral=True)
        self.stop()


class CodeView(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member) -> None:
        super().__init__(timeout=120)
        self.author = author

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("This is not your button.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Enter Code", style=discord.ButtonStyle.green)
    async def enter(self, interaction: Interaction, _):
        await interaction.response.send_modal(CodeModal())


class LoginView(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member) -> None:
        super().__init__(timeout=120)
        self.author = author

        self._children.insert(0, discord.ui.Button(url=ANILIST_URL, label="Get Code"))
        self.code: str | None = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("This is not your button.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Enter Code", style=discord.ButtonStyle.green)
    async def modal(self, interaction: Interaction, _):
        modal = CodeModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        self.code = modal.code
        self.stop()


class AniList(BaseCog):
    URL: ClassVar[str] = "https://graphql.anilist.co"

    def __init__(self, bot: Harmony):
        super().__init__(bot)
        self.oauth = OAuth(self.bot.session)

    async def search_media(self, search: str, *, type: MediaType, user_id: int | None = None) -> Media | None:
        """Searchs and returns a media via a search query."""

        variables = {"search": search, "type": type}

        headers = {}
        if user_id is not None:
            token = await self.get_token(user_id)
            if token is not None:
                headers = self.oauth._get_headers(token.token)

        async with self.bot.session.post(
            self.URL, json={"query": SEARCH_QUERY, "variables": variables}, headers=headers
        ) as resp:
            json = await resp.json()

            try:
                data_ = json["data"]
                data = data_["Media"]

            except KeyError:
                return None

            if data is None:
                return None

        return Media.from_json(data)

    async def fetch_media(self, id: int, *, user_id: int | None = None) -> Media | None:
        """Fetches and returns a media via an ID."""

        variables = {"id": id}

        headers = {}
        if user_id is not None:
            token = await self.get_token(user_id)
            if token is not None:
                headers = self.oauth._get_headers(token.token)

        async with self.bot.session.post(
            self.URL, json={"query": FETCH_QUERY, "variables": variables}, headers=headers
        ) as resp:
            json = await resp.json()

            try:
                data_ = json["data"]
                data = data_["Media"]

            except KeyError:
                return None

            if data is None:
                return None

        return Media.from_json(data)

    async def get_token(self, user_id: int) -> AccessToken | None:
        query = "SELECT * FROM anilist_codes WHERE user_id = $1"
        resp = await self.bot.pool.fetchrow(query, user_id)
        if not resp:
            return None

        return AccessToken(resp["access_token"], resp["expires_in"])

    @commands.command()
    async def anime(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific anime."""

        anime = await self.search_media(search, type=MediaType.ANIME, user_id=ctx.author.id)

        if anime is None:
            raise GenericError("Couldn't find any anime with that name.")

        view = discord.utils.MISSING
        if anime.relations:
            view = RelationView(self, anime)

        embeds = [anime.embed]
        if anime.list_embed:
            embeds.append(anime.list_embed)

        await ctx.send(embeds=embeds, view=view)

    @commands.command()
    async def manga(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific manga."""

        manga = await self.search_media(search, type=MediaType.MANGA, user_id=ctx.author.id)

        if manga is None:
            raise GenericError("Couldn't find any manga with that name.")

        view = discord.utils.MISSING
        if manga.relations:
            view = RelationView(self, manga)

        embeds = [manga.embed]
        if manga.list_embed:
            embeds.append(manga.list_embed)

        await ctx.send(embeds=embeds, view=view)

    @commands.group()
    async def anilist(self, ctx: Context, username: str | None = None):
        if username is None:
            token = await self.get_token(ctx.author.id)
            if token is None:
                cp = ctx.clean_prefix
                raise commands.BadArgument(
                    message=f"You need to pass an AniList username or log in with {cp}anilist login to view yourself."
                )

            elif token.expiry < datetime.datetime.now():
                raise GenericError(f"Your token has expired, create a new one with {ctx.clean_prefix}anilist login.")

            user = await self.oauth.get_current_user(token.token)

        else:
            user = await self.oauth.get_user(username)

            if user is None:
                raise GenericError("Couldn't find a user with that name.")

        embed = PrimaryEmbed(title=user.name, url=user.url, description=user.about + "\n\u200b" if user.about else "")

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
                    value=f"**{s.mean_score} // 100**\n{user._get_progress_bar(s.mean_score)}",
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
                    value=f"**{s.mean_score} // 100**\n{user._get_progress_bar(s.mean_score)}",
                    inline=False,
                )

        values: list[str] = []
        for k, v in user.favourites.items():  # type: ignore
            v: PartialNode
            name = k.title()
            if name[-1] == "s":
                name = name[:-1]
            values.append(f"{name}: **[{v.name}]({v.site_url})**")

        if values:
            embed.add_field(name="Favourites", value="\n".join(values), inline=False)

        await ctx.send(embed=embed)

    @anilist.command(aliases=["auth"])
    async def login(self, ctx: Context):
        query = "SELECT expires_in FROM anilist_codes WHERE user_id = $1"
        expiry: datetime.datetime = await self.bot.pool.fetchval(query, ctx.author.id)
        if expiry:
            if expiry > datetime.datetime.now():
                embed = SuccessEmbed(description="You are already logged in. Log out and back in to re-new session.")
                embed.set_footer(text=f"Run `{ctx.clean_prefix}anilist logout` to log out.")
                return await ctx.send(embed=embed)

        view = LoginView(ctx.author)
        embed = PrimaryEmbed(
            title="Authorise with Anilist",
            description="Copy the code from the link below, and then press the green button for the next step.",
        )
        message = await ctx.send(embed=embed, view=view)

        await view.wait()  # FIXME: Fix structure of callbacks, and try to remove View.wait() (s)
        if view.code is None:
            return

        resp = await self.oauth.get_access_token(view.code)
        if resp is None:
            return await message.edit(embed=ErrorEmbed(description="Invalid code, try again."))

        token, expires_in = resp

        query = "INSERT INTO anilist_codes VALUES ($1, $2, $3)"
        await self.bot.pool.execute(query, ctx.author.id, token, expires_in)

        await message.edit(embed=SuccessEmbed(description="Successfully logged you in."))

    @anilist.command()
    async def logout(self, ctx: Context):
        query = "SELECT EXISTS(SELECT 1 FROM anilist_codes WHERE user_id = $1)"
        exists = await self.bot.pool.fetchval(query, ctx.author.id)

        if not exists:
            raise GenericError("You are not logged in.")

        query = "DELETE FROM anilist_codes WHERE user_id = $1"
        await self.bot.pool.execute(query, ctx.author.id)

        await ctx.send(embed=PrimaryEmbed(description="Successfully logged you out."))
