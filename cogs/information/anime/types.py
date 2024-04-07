from enum import StrEnum
from typing import NamedTuple, Optional, TypedDict


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
    color: Optional[str]


class Edge(NamedTuple):
    id: int
    title: str
    type: MediaRelation


class Object(TypedDict):
    name: str
    siteUrl: str


class PartialMedia(TypedDict):
    episodes: int | None
    chapters: int | None


class FollowingStatus(TypedDict):
    status: MediaListStatus
    score: int
    progress: int
    media: PartialMedia
    user: Object


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
