from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any, NamedTuple, Optional, TypedDict

if TYPE_CHECKING:
    from datetime import datetime


class MediaType(StrEnum):
    """The type of media."""

    ANIME = "ANIME"
    MANGA = "MANGA"


class MediaStatus(StrEnum):
    """The current publishing status of the media."""

    FINISHED = "FINISHED"
    RELEASING = "RELEASING"
    NOT_YET_RELEASED = "NOT_YET_RELEASED"
    CANCELLED = "CANCELLED"
    HIATUS = "HIATUS"


class MediaFormat(StrEnum):
    """The publishing format of the media."""

    TV = "TV"
    TV_SHORT = "TV_SHORT"
    MOVIE = "MOVIE"
    SPECIAL = "SPECIAL"
    OVA = "OVA"
    ONA = "ONA"
    MUSIC = "MUSIC"
    MANGA = "MANGA"
    NOVEL = "NOVEL"
    ONE_SHOT = "ONE_SHOT"


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
    """The releasing season of the media."""

    WINTER = "WINTER"
    SPRING = "SPRING"
    SUMMER = "SUMMER"
    FALL = "FALL"


class MediaListStatus(StrEnum):
    """The status of the media on the user's list."""

    CURRENT = "CURRENT"
    PLANNING = "PLANNING"
    COMPLETED = "COMPLETED"
    DROPPED = "DROPPED"
    PAUSED = "PAUSED"
    REPEATING = "REPEATING"


class FavouriteType(StrEnum):
    """The type of favourite."""

    ANIME = "ANIME"
    MANGA = "MANGA"
    CHARACTERS = "CHARACTERS"
    STAFF = "STAFF"
    STUDIOS = "STUDIOS"


class ActivityType(StrEnum):
    """The type of activity."""

    TEXT = "TEXT"
    ANIME_LIST = "ANIME_LIST"
    MANGA_LIST = "MANGA_LIST"
    MESSAGE = "MESSAGE"
    MEDIA_LIST = "MEDIA_LIST"


class ScoreFormat(StrEnum):
    """The user's preferred scoring system."""

    POINT_100 = "POINT_100"
    POINT_10_DECIMAL = "POINT_10_DECIMAL"
    POINT_10 = "POINT_10"
    POINT_5 = "POINT_5"
    POINT_3 = "POINT_3"


class MediaTitle(TypedDict):
    """The official titles of the media in various languages."""

    romaji: str
    english: Optional[str]
    native: Optional[str]


class FuzzyDate(TypedDict):
    """Construct of dates provided by the API."""

    year: Optional[int]
    month: Optional[int]
    day: Optional[int]


class MediaCoverImage(TypedDict):
    """A set of media images and the most prominent colour in them."""

    extraLarge: str
    large: str
    medium: str
    color: Optional[str]


class Edge(NamedTuple):
    """A media connection edge."""

    id: int
    title: str
    type: MediaRelation
    list_entry: Optional[MediaList]
    format: MediaFormat
    status: MediaStatus
    year: Optional[int]


class Object(TypedDict):
    name: str
    siteUrl: str


class FollowingStatusUser(TypedDict):
    siteUrl: str
    name: str
    id: int
    mediaListOptions: MediaListOptions


class TResponse(TypedDict):
    episodes: Optional[int]
    chapters: Optional[int]


class FollowingStatus(TypedDict):
    status: MediaListStatus
    score: int
    progress: int
    media: TResponse
    user: FollowingStatusUser


class AiringSchedule(TypedDict):
    episode: int
    airingAt: int


class MediaList(TypedDict):
    """A user's media list."""

    score: float
    status: MediaListStatus
    progress: int
    progressVolumes: int
    repeat: int
    private: bool
    startedAt: FuzzyDate
    completedAt: FuzzyDate
    updatedAt: int
    createdAt: int
    user: FollowingStatusUser


class MediaT(TypedDict):
    """A media (anime or manga)."""

    id: int
    idMal: Optional[int]
    type: MediaType
    description: str
    episodes: int
    hashtag: str
    status: MediaStatus
    bannerImage: str
    duration: int
    chapters: Optional[int]
    volumes: Optional[int]
    genres: list[str]
    title: MediaTitle
    startDate: FuzzyDate
    endDate: FuzzyDate
    season: MediaSeason
    seasonYear: int
    meanScore: int
    coverImage: MediaCoverImage
    studios: dict[str, list[dict[str, str]]]
    nextAiringEpisode: Optional[AiringSchedule]


class MediaListEntry(TypedDict):
    score: int
    status: MediaListStatus
    progress: int
    progressVolumes: Optional[int]
    repeat: int
    private: bool
    startedAt: FuzzyDate
    completedat: FuzzyDate
    updatedAt: int  # timestamp
    createdAt: int  # timestamp
    media: MediaT
    user: FollowingStatusUser


class _MediaList(TypedDict):
    entries: list[MediaListEntry]
    name: str
    isCustomList: bool
    isSplitCompletedList: bool
    status: MediaListStatus


class PartialUser(TypedDict):
    name: str
    id: int


class MediaListCollection(TypedDict):
    lists: list[_MediaList]
    user: PartialUser
    hasNextChunk: bool


class ListActivity(TypedDict):
    id: int
    userId: int
    type: ActivityType
    replyCount: int
    status: str
    progress: str
    likeCount: int
    siteUrl: str
    createdAt: int  # timestamp
    user: dict[str, Any]  # TODO: Fix types
    media: dict[str, Any]  # --
    likes: list[dict[str, Any]]  # --


class SearchMedia(TypedDict):
    """A dumbed down versionb of Media used for searching."""

    id: int
    type: MediaType
    format: MediaFormat
    seasonYear: int
    title: MediaTitle
    isAdult: bool


class MediaListOptions(TypedDict):
    """The user's options for their media list."""

    scoreFormat: ScoreFormat


class ListActivityMessage(NamedTuple):
    message: str
    timestamp: datetime
    likes: int
    replies: int
    link: str


class Regex:
    ANIME_REGEX = re.compile(r"\{\{(.*?)\}\}")
    MANGA_REGEX = re.compile(r"\[\[(.*?)\]\]")
    INLINE_CB_REGEX = re.compile(r"(?P<CB>(`{1,2})[^`^\n]+?\2)(?:$|[^`])")
    CB_REGEX = re.compile(r"```[\S\s]+?```")
    HL_REGEX = re.compile(r"\[.*?\]\(.*?\)")
    TAG_REGEX = re.compile(r"</?\w+/?>")
    SOURCE_REGEX = re.compile(r"\(Source: .+\)")
