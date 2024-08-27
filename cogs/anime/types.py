from __future__ import annotations

from enum import StrEnum
from typing import Any, NamedTuple, Optional, TypedDict


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


class FavouriteTypes(StrEnum):
    ANIME = "ANIME"
    MANGA = "MANGA"
    CHARACTERS = "CHARACTERS"
    STAFF = "STAFF"
    STUDIOS = "STUDIOS"


class ActivityType(StrEnum):
    TEXT = "TEXT"
    ANIME_LIST = "ANIME_LIST"
    MANGA_LIST = "MANGA_LIST"
    MESSAGE = "MESSAGE"
    MEDIA_LIST = "MEDIA_LIST"


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
    id: int
    title: str
    type: MediaRelation
    list_entry: Optional[MediaList]


class Object(TypedDict):
    name: str
    siteUrl: str


class TResponse(TypedDict):
    episodes: Optional[int]
    chapters: Optional[int]


class FollowingStatus(TypedDict):
    status: MediaListStatus
    score: int
    progress: int
    media: TResponse
    user: Object


class AiringSchedule(TypedDict):
    episode: int


class MediaList(TypedDict):
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


class _Media(TypedDict):
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
    media: _Media


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
