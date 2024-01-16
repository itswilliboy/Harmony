import datetime
import re
from enum import StrEnum
from typing import ClassVar, TypedDict

import discord
from discord.ext import commands

from utils import BaseCog, Context, GenericError


class MediaType(StrEnum):
    ANIME = "ANIME"
    MANGA = "MANGA"


class MediaStatus(StrEnum):
    """ "The current publishing status of the media."""

    FINISHED = "FINISHED"
    RELEASING = "RELEASING"
    NOT_YET_RELEASED = "NOT_YET_RELEASED"
    CANCELLED = "CANCELLED"
    HIATUS = "HIATUS"


class MediaTitle(TypedDict):
    """The official titles of the media in various languages."""

    romaji: str
    english: str
    native: str


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


class Studio(TypedDict):
    name: str
    siteUrl: str


TAG_REGEX = re.compile(r"</?\w+/?>")
SOURCE_REGEX = re.compile(r"\(Source: .+\)")


class Media:
    def __init__(
        self,
        id: int,
        id_mal: int,
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
    ) -> None:
        self.id = id
        self.id_mal = id_mal
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
        self.genres = genres

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
        desc = TAG_REGEX.sub("", self._description)
        desc = SOURCE_REGEX.sub("", desc)
        desc = desc.replace("\N{HORIZONTAL ELLIPSIS}", "").replace("...", "").rstrip()

        if not desc.endswith((".", "!", "?")):
            desc += "."

        if len(desc) > 2048:
            desc = desc[:2038]
            desc += " **[...]**"

        desc += "\n\u200b"

        return desc

    @property
    def hashtags(self) -> list[str]:
        return self._hashtags.split() if self._hashtags else []


class MediaView(discord.ui.View):
    ...


class AniList(BaseCog):
    URL: ClassVar[str] = "https://graphql.anilist.co"

    async def search_media(self, search: str, *, type: MediaType) -> Media | None:
        """Searchs and returns a media via a search query."""
        query = """
            query ($search: String, $type: MediaType) {
                Media (search: $search, type: $type) {
                    id
                    idMal
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
                }
            }
        """

        variables = {"search": search, "type": type}

        async with self.bot.session.post(self.URL, json={"query": query, "variables": variables}) as resp:
            json = await resp.json()
            data = json["data"]["Media"]
            print(data)

            if data is None:
                return None

        title = MediaTitle(data["title"])
        start_date = FuzzyDate(data["startDate"])
        end_date = FuzzyDate(data["endDate"])
        cover_image = MediaCoverImage(data["coverImage"])
        studio = data["studios"]["nodes"][0] if data["studios"]["nodes"] else None

        return Media(
            data["id"],
            data["idMal"],
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
        )

    @commands.command()
    async def anime(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific anime."""

        anime = await self.search_media(search, type=MediaType.ANIME)

        if anime is None:
            raise GenericError("Couldn't find any anime with that name.")

        url = f"https://anilist.co/anime/{anime.id}"

        title = ""
        if t := anime.title["english"]:
            title = t

        elif t := anime.title["romaji"]:
            title = t

        elif t := anime.title["native"]:
            title = t

        embed = discord.Embed(title=title, description=anime.description, color=anime.colour, url=url)

        if title != anime.title["romaji"]:
            embed.set_author(name=anime.title["romaji"])
        embed.set_thumbnail(url=anime.cover_image["extraLarge"])
        embed.set_image(url=anime.banner_image)

        if title := anime.title["native"]:
            embed.add_field(name="Native Title", value=f"**{title}**")

        if studio := anime.studio:
            embed.add_field(name="Studio", value=f"**[{studio['name']}]({studio['siteUrl']})**")

        if genres := anime.genres:
            embed.add_field(name="Genres", value=", ".join(f"**{genre}**" for genre in genres), inline=False)

        if hashtags := anime.hashtags:
            embed.add_field(
                name="Hashtags",
                value=" ".join(f"**[{tag}](https://twitter.com/hashtag/{tag.replace('#', '')})**" for tag in hashtags),
            )

        time = anime.episodes * anime.duration / 60
        embed.add_field(
            name="Episodes | Time to Watch",
            value=f"**{anime.episodes} | ~{time:.1f} hours**",
        )

        await ctx.send(embed=embed)

    @commands.command()
    async def manga(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific manga."""

        manga = await self.search_media(search, type=MediaType.MANGA)

        if manga is None:
            raise GenericError("Couldn't find any manga with that name.")

        url = f"https://anilist.co/manga/{manga.id}"

        title = ""
        if t := manga.title["english"]:
            title = t

        elif t := manga.title["romaji"]:
            title = t

        elif t := manga.title["native"]:
            title = t

        embed = discord.Embed(title=title, description=manga.description, color=manga.colour, url=url)

        if title != manga.title["romaji"]:
            embed.set_author(name=manga.title["romaji"])
        embed.set_thumbnail(url=manga.cover_image["extraLarge"])
        embed.set_image(url=manga.banner_image)

        if title := manga.title["native"]:
            embed.add_field(name="Native Title", value=f"**{title}**")

        if genres := manga.genres:
            embed.add_field(name="Genres", value=", ".join(f"**{genre}**" for genre in genres), inline=False)

        if hashtags := manga.hashtags:
            embed.add_field(
                name="Hashtags",
                value=" ".join(f"**[{tag}](https://twitter.com/hashtag/{tag.replace('#', '')})**" for tag in hashtags),
            )

        await ctx.send(embed=embed)
