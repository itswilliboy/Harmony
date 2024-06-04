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
    ANIME = "anime"
    MANGA = "manga"
    CHARACTERS = "characters"
    STAFF = "staff"
    STUDIOS = "studios"


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


class Object(TypedDict):
    name: str
    siteUrl: str


class PartialMedia(TypedDict):
    episodes: Optional[int]
    chapters: Optional[int]


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
    repeat: int
    private: bool
    startedAt: FuzzyDate
    completedAt: FuzzyDate
    updatedAt: int
    createdAt: int
    repeat: int
