from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Optional, Self

import discord

from utils import plural, progress_bar

from .types import (
    Edge,
    FollowingStatus,
    FuzzyDate,
    MediaCoverImage,
    MediaFormat,
    MediaList,
    MediaListStatus,
    MediaSeason,
    MediaStatus,
    MediaTitle,
    MediaType,
    Object,
    Regex,
)

if TYPE_CHECKING:
    from bot import Harmony

    from . import User

    Interaction = discord.Interaction[Harmony]


class MinifiedMedia:
    def __init__(
        self,
        id: int,
        id_mal: int,
        is_adult: bool,
        type: MediaType,
        title: MediaTitle,
        season: Optional[MediaSeason],
        season_year: Optional[int],
        mean_score: Optional[int],
        status: MediaStatus,
        episodes: int,
        chapters: int,
        volumes: int,
        genres: list[str],
        format: MediaFormat,
        cover: MediaCoverImage,
    ) -> None:
        self.id = id
        self.id_mal = id_mal
        self.is_adult = is_adult
        self.type = type
        self.title = title
        self.season = season
        self.season_year = season_year
        self.mean_score = mean_score
        self.status = status
        self.episodes = episodes
        self.chapters = chapters
        self.volumes = volumes
        self.genres = genres
        self.format = format
        self.cover = cover

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and other.id == self.id

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        type_ = MediaType(data["type"])
        title = MediaTitle(data["title"])
        season = MediaSeason(data["season"]) if data["season"] else None
        format = MediaFormat(data["format"])
        cover = MediaCoverImage(data["coverImage"])

        return cls(
            data["id"],
            data["idMal"],
            data["isAdult"],
            type_,
            title,
            season,
            data["seasonYear"],
            data["meanScore"],
            data["status"],
            data["episodes"],
            data["chapters"],
            data["volumes"],
            data["genres"],
            format,
            cover,
        )

    @property
    def name(self) -> str:
        """Returns the name of the media."""
        if self.is_adult:
            return f"\N{NO ONE UNDER EIGHTEEN SYMBOL} {self.title['romaji']}"
        else:
            return self.title["romaji"]

    @property
    def small_info(self) -> str:
        """Return a string with some information about the media."""
        fmt: list[str] = []

        if self.format:
            fmt.append(f"{str(self.format).replace('_', ' ').title()}")

        if self.season and self.season_year:
            fmt.append(f"{str(self.season).title()} {self.season_year}")

        if self.status:
            fmt.append(str(self.status).title())

        if self.episodes:
            fmt.append(f"{self.episodes} episode{'' if self.episodes == 1 else 's'}")

        if self.chapters and self.volumes:
            fmt.append(
                f"{self.volumes} volume{'' if self.volumes == 1 else 's'} ({self.chapters} chapter{'' if self.chapters == 1 else 's'})"
            )

        fmt.append(f"[AL](<https://anilist.co/{self.type.lower()}/{self.id}>)")
        if self.id_mal:
            fmt.append(f"[MAL](<https://myanimelist.net/{self.type.lower()}/{self.id_mal}>)")

        genres = ""
        if self.genres:
            genres = f"\nGenre{'' if len(self.genres) == 1 else 's'}: " + (", ".join(self.genres))

        return " \N{EM DASH} ".join(fmt) + genres


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

        self._data: dict[str, Any]  # Raw json data

    def __repr__(self) -> str:
        title = self.title["english"] or self.title["romaji"]
        return f"<Media id={self.id} name={title} type={self.type}>"

    def __str__(self) -> str:
        return self.title["english"] or self.title["romaji"] or self.title["native"] or "<No Title>"

    @classmethod
    def from_json(cls, data: dict[str, Any], following_status: dict[str, Any]) -> Self:
        type_ = MediaType(data["type"])
        title = MediaTitle(data["title"])
        start_date = FuzzyDate(data["startDate"])
        end_date = FuzzyDate(data["endDate"])
        season = MediaSeason(data["season"]) if data["season"] else None
        cover_image = MediaCoverImage(data["coverImage"])
        studio = data["studios"]["nodes"][0] if data["studios"]["nodes"] else None

        following_statuses: list[FollowingStatus] = cls.parse_following_statuses(following_status)

        relations: list[Edge] = []
        if edges := data["relations"]["edges"]:
            for edge in edges:
                node = edge["node"]
                title_ = MediaTitle(node["title"])
                list_entry_ = MediaList(node["mediaListEntry"]) if node.get("mediaListEntry") else None
                relations.append(
                    Edge(node["id"], title_["romaji"], edge["relationType"], list_entry_, node["format"], node["status"])
                )

        list_entry = MediaList(data["mediaListEntry"]) if data.get("mediaListEntry") else None

        inst = cls(
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

        inst._data = data
        return inst

    @staticmethod
    def parse_following_statuses(data: dict[str, Any]) -> list[FollowingStatus]:
        following_statuses: list[FollowingStatus] = []
        following_users = data.get("data", {}).get("Page", {}).get("mediaList", [])
        for user in following_users:
            following_statuses.append(FollowingStatus(user))

        return following_statuses

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

        desc = Regex.TAG_REGEX.sub("", self._description)
        split = Regex.SOURCE_REGEX.split(desc)
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
        """Returns a list of hashtags that are linked with the media."""
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
    def url(self) -> str:
        """Returns the site url of the media."""
        return f"https://anilist.co/{str(self.type.lower())}/{self.id}"

    @property
    def embed(self) -> discord.Embed:
        """Returns the main informational embed of the media."""
        title = str(self)

        embed = discord.Embed(title=title, description=self.description, color=self.colour, url=self.url)

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

        if not self.list_entry:
            embed.set_footer(
                text="Tip: Log in with `anilist login` to see your own- and your friends' progress on this media."
            )

        return embed

    def _get_wording(self, status: MediaListStatus) -> str:
        if status == MediaListStatus.CURRENT:
            return "watching" if self.type == MediaType.ANIME else "reading"
        return str(status)

    def status_embed(self, user: Optional[User] = None) -> Optional[discord.Embed]:
        """Returns the embed giving information about watching/reading status."""
        status = self.following_statuses
        entry = self.list_entry

        embed = discord.Embed(title=self.title["english"], url=self.url, colour=self.colour)
        embed.set_thumbnail(url=self.cover_image["extraLarge"])

        if entry and not entry["private"]:
            desc = [
                f"↪ Status: **{self._get_wording(entry["status"]).title()}**",
                f"↪ Volumes: **{entry['progressVolumes']} / {self.volumes or "TBA"}**"
                if self.type == MediaType.MANGA
                else "",
                f"↪ Progress: **{entry['progress']}"
                + " / "
                + str(self.episodes or self.chapters or "TBA")
                + (
                    f" {plural(self.episodes or 0):episode}"
                    if self.type == MediaType.ANIME
                    else f" {plural(self.chapters or 0):chapter}"
                )
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

                if entry["repeat"]:
                    wording = "Rewatches" if self.type == MediaType.ANIME else "Rereads"
                    desc.append(f"↪ {wording}: **{entry['repeat']}**")

            desc = [i for i in desc if i != ""]

            embed.description = "\n".join(desc)

        if status:
            information: list[str] = []
            status.sort(key=lambda st: st["status"])

            length = 0
            for st in status:
                user_: Any = st["user"]

                if user is not None:
                    if user_["id"] == user.id:
                        continue

                total_progress = st["media"]["episodes"] or st["media"]["chapters"]

                desc = (
                    f"↪ **[{user_['name']}]({user_['siteUrl']}) - "
                    f"{st['score']} / 10**\n"
                    f"╰ `{self._get_wording(st["status"]).title()}:` "
                    f"{st['progress']} / {total_progress} "
                    f"{f'{plural(self.chapters or 0):chapter}' if self.type == MediaType.MANGA else f'{plural(self.episodes or 0):episode}'}"
                )

                length += len(desc)
                if length > 1000:  # Make sure we don't exceed the embed-field value limit.
                    break

                information.append(desc)

            if information:
                embed.add_field(name="Followed Users", value="\n".join(information))

        if user:
            embed.set_author(name=user.name, url=user.url, icon_url=user.avatar_url)

        if embed.description or embed.fields:
            return embed
