import datetime
import re
from enum import StrEnum
from typing import ClassVar, TypedDict

import discord
from discord.ext import commands

from utils import BaseCog, Context


class MediaType(StrEnum):
    ANIME = "ANIME"
    MANGA = "MANGA"

class MediaStatus(StrEnum):
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

TAG_REGEX = re.compile("<.+>")
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
        studio: Studio,
        episodes: int,
        duration: int
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

    @staticmethod
    def _to_date(date: FuzzyDate) -> datetime.date:
        """Converts the date-type given by the API to a `datetime.date` object. """
        return datetime.date(year=date["year"] or 0, month=date["month"] or 0, day=date["day"]or 0)

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
        return discord.Colour.from_str(self.cover_image["color"])

    @property
    def description(self) -> str:
        """Returns a cleaned version of the description."""
        desc = TAG_REGEX.sub('', self._description)
        desc = SOURCE_REGEX.sub('', desc)
        desc = desc.replace("\N{HORIZONTAL ELLIPSIS}", "").replace("...", "").rstrip()

        if not desc.endswith((".", "!", "?")):
            desc += "."

        if len(desc) > 2048:
            desc = desc[:2038]
            desc += " **[...]**"

        return desc

    @property
    def hashtags(self) -> list[str]:
        return self._hashtags.split() if self._hashtags else []


class AniList(BaseCog):
    URL: ClassVar[str] = "https://graphql.anilist.co"

    async def search_media(self, search: str, *, type: MediaType) -> Media:
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

        variables = {
            "search": search,
            "type": type
        }

        async with self.bot.session.post(self.URL, json={"query": query, "variables": variables}) as resp:
            json = await resp.json()
            data = json["data"]["Media"]

        title = MediaTitle(data["title"])
        start_date = FuzzyDate(data["startDate"])
        end_date = FuzzyDate(data["endDate"])
        cover_image = MediaCoverImage(data["coverImage"])

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
            data["studios"]["nodes"][0],
            data["episodes"],
            data["duration"]
        )


    @commands.command()
    async def anime(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific anime media."""

        anime = await self.search_media(search, type=MediaType.ANIME)

        url = f"https://anilist.co/anime/{anime.id}"
        embed = discord.Embed(
            title=anime.title["english"],
            description=anime.description,
            color=anime.colour,
            url=url
        )

        embed.set_author(name=anime.title["romaji"])
        embed.set_thumbnail(url=anime.cover_image["extraLarge"])
        embed.set_image(url=anime.banner_image)

        if title := anime.title["native"]:
            embed.add_field(name="Native Title", value=f"**{title}**")

        embed.add_field(name="Studio", value=f"**[{anime.studio['name']}]({anime.studio['siteUrl']})**")

        if anime.hashtags:
            embed.add_field(
                name="Hashtags",
                value=" ".join(f"**[{tag}](https://twitter.com/hashtag/{tag.replace('#', '')})**" for tag in anime.hashtags)
            )

        time = anime.episodes * anime.duration / 60
        embed.add_field(
            name="Episodes | Time to Watch",
            value=f"**{anime.episodes} | ~{time:.1f} hours**",
        )

        await ctx.send(embed=embed)
