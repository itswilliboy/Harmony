# TODO: Add docstrings to all(?) class properties
from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Self

import discord

from utils import progress_bar

from .oauth import AccessToken, OAuth
from .types import (
    Edge,
    FollowingStatus,
    FuzzyDate,
    MediaCoverImage,
    MediaList,
    MediaSeason,
    MediaStatus,
    MediaTitle,
    MediaType,
    Object,
)

if TYPE_CHECKING:
    from bot import Harmony

    from .oauth import User

    Interaction = discord.Interaction[Harmony]


TAG_REGEX = re.compile(r"</?\w+/?>")
SOURCE_REGEX = re.compile(r"\(Source: .+\)")

SEARCH_QUERY = """
    query ($search: String, $type: MediaType) {
        Media (search: $search, type: $type) {
            id
            isAdult
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
            season
            seasonYear
            meanScore
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
            isAdult
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
            season
            seasonYear
            meanScore
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

# FIXME: Fix so the authenticated user doesn't appear on the following embed.
FOLLOWING_QUERY = """
    query ($id: Int, $page: Int, $perPage: Int) {
        Page(page: $page, perPage: $perPage) {
            mediaList(mediaId: $id, isFollowing: true, sort: UPDATED_TIME_DESC) {
                status
                score(format: POINT_10)
                progress
                repeat
                media {
                    episodes
                    chapters
                }
                user {
                    siteUrl
                    name
                    id
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
        is_adult: bool,
        type: MediaType,
        title: MediaTitle,
        description: Optional[str],
        start_date: FuzzyDate,
        end_date: FuzzyDate,
        season: Optional[MediaSeason],
        season_year: Optional[int],
        mean_score: Optional[int],
        status: MediaStatus,
        cover_image: MediaCoverImage,
        banner_image: str,
        hashtags: str,
        studio: Optional[Object],
        episodes: int,
        duration: int,
        chapters: int,
        volumes: int,
        genres: list[str],
        following_statuses: list[FollowingStatus],
        relations: list[Edge],
        list_entry: Optional[MediaList],
    ) -> None:
        self.id = id
        self.id_mal = id_mal
        self.is_adult = is_adult
        self.type = type
        self.title = title
        self._description = description
        self._start_date = start_date
        self._end_date = end_date
        self.season = season
        self.season_year = season_year
        self.mean_score = mean_score
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
        self.following_statuses = following_statuses
        self.relations = relations
        self.list_entry = list_entry

    @classmethod
    def from_json(cls, data: dict[str, Any], following_status: dict[str, Any]) -> Self:
        type_ = MediaType(data["type"])
        title = MediaTitle(data["title"])
        start_date = FuzzyDate(data["startDate"])
        end_date = FuzzyDate(data["endDate"])
        season = MediaSeason(data["season"]) if data["season"] else None
        cover_image = MediaCoverImage(data["coverImage"])
        studio = data["studios"]["nodes"][0] if data["studios"]["nodes"] else None

        following_statuses: list[FollowingStatus] = []
        following_users = following_status.get("data", {}).get("Page", {}).get("mediaList", [])
        for user in following_users:
            following_statuses.append(FollowingStatus(user))

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
            data["isAdult"],
            type_,
            title,
            data["description"],
            start_date,
            end_date,
            season,
            data["seasonYear"],
            data["meanScore"],
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
            following_statuses,
            relations,
            list_entry,
        )

    @staticmethod
    def _to_datetime(date: FuzzyDate) -> Optional[datetime.datetime]:
        """Converts the date-type given by the API to a `datetime.datetime` object."""
        try:
            # We could use a datetime.date instead, but since this will be used for Discord-timestamps later,
            # it will be more convenient to be able to call the .timestamp() on datetime.datetime object.
            return datetime.datetime(year=date["year"] or 0, month=date["month"] or 0, day=date["day"] or 0)
        except ValueError:
            return None

    @property
    def start_date(self) -> Optional[datetime.datetime]:
        """Returns the date when the media started."""
        return self._to_datetime(self._start_date)

    @property
    def end_date(self) -> Optional[datetime.datetime]:
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

        BASE_URL = f"https://anilist.co/search/{'manga' if self.type == MediaType.MANGA else 'anime'}/"

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

        title = self.title.get("english") or self.title.get("romaji") or self.title.get("native")

        embed = discord.Embed(title=title, description=self.description, color=self.colour, url=url)

        if title != self.title["romaji"]:
            embed.set_author(name=self.title["romaji"])

        embed.set_thumbnail(url=self.cover_image["extraLarge"])
        embed.set_image(url=self.banner_image)

        info = [
            f"↪ Native Title: **{self.title['native']}**" if self.title["native"] else "",
            f"↪ Studio: **[{self.studio['name']}]({self.studio['siteUrl']})**" if self.studio else "",
            (
                f"↪ Episodes: **{self.episodes}"
                f"{f' | {(self.episodes*self.duration)/60:.1f} hours' if self.duration else ''}**"
                if self.episodes
                else ""
            ),
            f"↪ Volumes: **{self.volumes}**" if self.volumes else "",
            f"↪ Chapters: **{self.chapters}**" if self.chapters else "",
            f"↪ Year: **{self.season_year}{f' | {(self.season or str()).title()}'}**" if self.season_year else "",
        ]

        if self.start_date:
            started_at = discord.utils.format_dt(self.start_date, "d")
            ended_at = discord.utils.format_dt(self.end_date, "d") if self.end_date else "TBA"

            info.append(f"↪ Releasing: **{started_at} ⟶ {ended_at}**")

        info = [i for i in info if i != ""]

        embed.add_field(name="Information", value="\n".join(info))

        if self.genres:
            embed.add_field(
                name="Genres",
                value=", ".join(f"**{genre}**" for genre in self.genres),
                inline=False,
            )

        if self.hashtags:
            embed.add_field(
                name="Hashtags",
                value=" ".join(f"**[{tag}](https://twitter.com/hashtag/{tag.replace('#', '')})**" for tag in self.hashtags),
            )

        if self.mean_score:
            embed.add_field(
                name="Average Score",
                value=f"**{self.mean_score} // 100**\n{progress_bar(self.mean_score)}",
            )

        return embed

    @property
    def list_embed(self) -> Optional[discord.Embed]:
        entry = self.list_entry
        if entry is None:
            return None

        # Don't wanna expose their secrets :^)
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
                started_at = discord.utils.format_dt(
                    self._to_datetime(entry["startedAt"]),  # type: ignore
                    "d",
                )

            if entry["completedAt"]["year"]:
                completed_at = discord.utils.format_dt(
                    self._to_datetime(entry["completedAt"]),  # type: ignore
                    "d",
                )

            if started_at and not completed_at:
                desc.append(f"↪ Started at: **{started_at}**")
            elif completed_at and not started_at:
                desc.append(f"↪ Completed at: **{completed_at}**")
            elif started_at and completed_at:
                desc.append(f"↪ Started / Completed: **{started_at} ⟶ {completed_at}**")

        desc = [i for i in desc if i != ""]
        embed = discord.Embed(title="Your Status", colour=self.colour, description="\n".join(desc))

        if entry["updatedAt"] and not self.following_statuses:
            embed.set_footer(text="Last Updated").timestamp = datetime.datetime.fromtimestamp(entry["updatedAt"])

        return embed

    def following_status_embed(self, user: Optional[User] = None) -> Optional[discord.Embed]:
        status_ = self.following_statuses
        if not status_:
            return

        information: list[str] = []
        for status in status_:
            user_: Any = status["user"]

            if user is not None:
                if user_["id"] == user.id:
                    continue

            TOTAL_PROGRESS = status["media"]["episodes"] or status["media"]["chapters"]

            desc = (
                f"↪ **[{user_['name']}]({user_['siteUrl']}) - "
                f"{status['score']} / 10**\n"
                f"╰ `{status['status'].title()}:` "
                f"{status['progress']} / {TOTAL_PROGRESS} "
                f"{'chapter(s)' if self.type == MediaType.MANGA else 'episode(s)'}"
            )

            information.append(desc)

        if not information:
            return None

        return discord.Embed(title="Followed Users", colour=self.colour, description="\n".join(information))


class AniListClient:
    URL: ClassVar[str] = "https://graphql.anilist.co"

    def __init__(self, bot: Harmony) -> None:
        self.bot = bot
        self.oauth = OAuth(bot.session)

    async def search_media(
        self, search: str, *, type: MediaType, user_id: Optional[int] = None
    ) -> tuple[Media, Optional[User]] | tuple[None, None]:
        """Searchs and returns a media via a search query."""

        variables = {"search": search, "type": type}
        headers = await self.get_headers(user_id) if user_id else {}

        async with self.bot.session.post(
            self.URL,
            json={"query": SEARCH_QUERY, "variables": variables},
            headers=headers,
        ) as resp:
            json = await resp.json()

            try:
                data_ = json["data"]
                data = data_["Media"]
            except KeyError:
                return (None, None)

            if data is None:
                return (None, None)

        following_status = {}
        if user_id:
            following_status = await self.fetch_following_status(
                data["id"],
                user_id,
                headers=headers,
            )

        user: Optional[User] = None
        if headers:
            user = await self.oauth.get_current_user(headers["Authorization"].split()[1])

        return (Media.from_json(data, following_status or {}), user)

    async def fetch_media(self, id: int, *, user_id: Optional[int] = None) -> Optional[Media]:
        """Fetches and returns a media via an ID."""

        variables = {"id": id}
        headers = await self.get_headers(user_id) if user_id else {}

        async with self.bot.session.post(
            self.URL,
            json={"query": FETCH_QUERY, "variables": variables},
            headers=headers,
        ) as resp:
            json = await resp.json()

            try:
                data_ = json["data"]
                data = data_["Media"]
            except KeyError:
                return None

            if data is None:
                return None

        following_status = {}
        if user_id:
            following_status = await self.fetch_following_status(
                id,
                user_id,
                headers=headers,
            )

        return Media.from_json(data, following_status or {})

    async def fetch_following_status(
        self,
        media_id: int,
        user_id: int,
        *,
        headers: Optional[dict[str, str]] = None,
        page: int = 1,
        per_page: int = 5,
    ) -> Optional[dict[str, Any]]:
        """Fetches all the ratings of the followed users."""

        variables = {"id": media_id, "page": page, "perPage": per_page}
        headers = headers or await self.get_headers(user_id)

        if not headers:
            return

        async with self.bot.session.post(
            self.URL,
            json={
                "query": FOLLOWING_QUERY,
                "variables": variables,
            },
            headers=headers,
        ) as req:
            if req.status == 200:
                data = await req.json()
                return data

    async def get_token(self, user_id: int) -> Optional[AccessToken]:
        query = "SELECT * FROM anilist_codes WHERE user_id = $1"
        resp = await self.bot.pool.fetchrow(query, user_id)

        if not resp:
            return None

        return AccessToken(
            resp["access_token"],
            resp["expires_in"],
        )

    async def get_headers(self, user_id: int) -> dict[str, str]:
        token = await self.get_token(user_id)
        if token is not None:
            return self.oauth.get_headers(token.token)

        return {}
