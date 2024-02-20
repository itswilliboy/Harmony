from __future__ import annotations

import datetime
import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Self, TypedDict

import discord
from discord.ext import commands

from utils import BaseCog, Context, GenericError

if TYPE_CHECKING:
    from bot import Harmony


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


TAG_REGEX = re.compile(r"</?\w+/?>")
SOURCE_REGEX = re.compile(r"\(Source: .+\)")
NOTE_REGEX = re.compile(r"Note: .+")

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
        status: MediaStatus,
        cover_image: MediaCoverImage,
        banner_image: str,
        hashtags: str,
        studio: Studio | None,
        episodes: int,
        duration: int,
        genres: list[str],
        relations: list[Edge],
    ) -> None:
        self.id = id
        self.id_mal = id_mal
        self.type = type
        self.title = title
        self._description = description
        self._start_date = start_date
        self._end_date = end_date
        self.status = status
        self.cover_image = cover_image
        self.banner_image = banner_image
        self._hashtags = hashtags
        self.studio = studio
        self.episodes = episodes
        self.duration = duration
        self._genres = genres
        self.relations = relations

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        type_ = MediaType(data["type"])
        title = MediaTitle(data["title"])
        start_date = FuzzyDate(data["startDate"])
        end_date = FuzzyDate(data["endDate"])
        cover_image = MediaCoverImage(data["coverImage"])
        studio = data["studios"]["nodes"][0] if data["studios"]["nodes"] else None

        relations: list[Edge] = []
        if edges := data["relations"]["edges"]:
            for edge in edges:
                node = edge["node"]
                title_ = MediaTitle(node["title"])
                relations.append(Edge(node["id"], title_["romaji"], edge["relationType"]))

        return cls(
            data["id"],
            data["idMal"],
            type_,
            title,
            data["description"],
            start_date,
            end_date,
            data["status"],
            cover_image,
            data["bannerImage"],
            data["hashtag"],
            studio,
            data["episodes"],
            data["duration"],
            data["genres"],
            relations,
        )

    @staticmethod
    def _to_date(date: FuzzyDate) -> datetime.date:
        """Converts the date-type given by the API to a `datetime.date` object."""
        return datetime.date(year=date["year"] or 0, month=date["month"] or 0, day=date["day"] or 0)

    @property
    def start_date(self) -> datetime.date:
        """Returns the date when the media started."""
        return self._to_date(self._start_date)

    @property
    def end_date(self) -> datetime.date:
        """Returns the date when the media ended."""
        return self._to_date(self._end_date)

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
        desc = SOURCE_REGEX.sub("", desc)
        desc = NOTE_REGEX.sub("", desc)
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

        if title_ := self.title.get("native"):
            embed.add_field(name="Native Title", value=f"**{title_}**")

        if studio := self.studio:
            embed.add_field(name="Studio", value=f"**[{studio['name']}]({studio['siteUrl']})**")

        if genres := self.genres:
            embed.add_field(name="Genres", value=", ".join(f"**{genre}**" for genre in genres))

        if hashtags := self.hashtags:
            embed.add_field(
                name="Hashtags",
                value=" ".join(f"**[{tag}](https://twitter.com/hashtag/{tag.replace('#', '')})**" for tag in hashtags),
            )

        if self.episodes and self.duration:
            time = self.episodes * self.duration / 60
            embed.add_field(
                name="Episodes | Time to Watch",
                value=f"**{self.episodes} | ~{time:.1f} hours**",
            )

        elif self.episodes:
            embed.add_field(name="Episodes", value=f"**{self.episodes}**")

        if self.status:
            embed.add_field(name="Current Status", value=f"**{self.status.title()}**")

        return embed


async def callback(cog: AniList, id: int, interaction: discord.Interaction[Harmony]):
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

        super().__init__(label=label, emoji=emoji)
        self.cog = cog
        self.edge = edge
        self.text = text

    async def callback(self, interaction: discord.Interaction[Harmony]) -> None:
        await callback(self.cog, self.edge.id, interaction)


class RelationSelect(discord.ui.Select):
    def __init__(self, cog: AniList, options: list[discord.SelectOption]) -> None:
        for option in options:
            if len(option.label) > 80:
                option.label = option.label[:77] + "..."

        super().__init__(placeholder="Select a relation to view", min_values=1, max_values=1, options=options[:25])
        self.cog = cog

    async def callback(self, interaction: discord.Interaction[Harmony]):
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

    async def callback(self, interaction: discord.Interaction[Harmony]):
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
                    discord.SelectOption(
                        emoji="\N{MOVIE CAMERA}", label=edge.title, value=value, description="Adaptation"
                    )
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


class AniList(BaseCog):
    URL: ClassVar[str] = "https://graphql.anilist.co"

    async def search_media(self, search: str, *, type: MediaType) -> Media | None:
        """Searchs and returns a media via a search query."""

        variables = {"search": search, "type": type}

        async with self.bot.session.post(self.URL, json={"query": SEARCH_QUERY, "variables": variables}) as resp:
            json = await resp.json()
            print(json)

            try:
                data_ = json["data"]
                data = data_["Media"]

            except KeyError:
                return None

            if data is None:
                return None

        return Media.from_json(data)

    async def fetch_media(self, id: int) -> Media | None:
        """Fetches and returns a media via an id."""

        variables = {"id": id}

        async with self.bot.session.post(self.URL, json={"query": FETCH_QUERY, "variables": variables}) as resp:
            json = await resp.json()
            print(json)

            try:
                data_ = json["data"]
                data = data_["Media"]

            except KeyError:
                return None

            if data is None:
                return None

        return Media.from_json(data)

    @commands.command()
    async def anime(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific anime."""

        anime = await self.search_media(search, type=MediaType.ANIME)

        if anime is None:
            raise GenericError("Couldn't find any anime with that name.")

        view = discord.utils.MISSING
        if anime.relations:
            view = RelationView(self, anime)

        await ctx.send(embed=anime.embed, view=view)

    @commands.command()
    async def manga(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific manga."""

        manga = await self.search_media(search, type=MediaType.MANGA)

        if manga is None:
            raise GenericError("Couldn't find any manga with that name.")

        view = discord.utils.MISSING
        if manga.relations:
            view = RelationView(self, manga)

        await ctx.send(embed=manga.embed, view=view)
