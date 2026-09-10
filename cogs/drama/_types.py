from enum import IntEnum
from typing import Optional, TypedDict

#! Apparently unused outside of Advanced Search; avoid unless making command


#! Media
class MDLCountries(IntEnum):
    JAPAN = 1
    CHINA = 2
    SOUTH_KOREA = 3
    HONG_KONG = 4
    TAIWAN = 5
    THAILAND = 6
    PHILIPPINES = 140
    SINGAPORE = 157


class MDLGenres(IntEnum):
    ACTION = 1
    FOOD = 2
    MILITARY = 3
    SUSPENSE = 4
    ADVENTURE = 5
    FRIENDSHIP = 6
    MUSIC = 7
    THRILLER = 8
    ANIMALS = 9
    HISTORICAL = 10
    MYSTERY = 11
    TOKUSATSU = 12
    BUSINESS = 13
    HORROR = 14
    PSYCHOLOGICAL = 15
    VAMPIRE = 16
    COMEDY = 17
    LAW = 18
    ROMANCE = 19
    WUXIA = 20
    CRIME = 21
    LIFE = 22
    SCHOOL = 23
    YOUTH = 24
    DRAMA = 25
    MARTIAL_ARTS = 26
    SCI_FI = 27
    ZOMBIES = 28
    FAMILY = 29
    MEDICAL = 30
    SPORTS = 31
    FANTASY = 32
    MELODRAMA = 33
    SUPERNATURAL = 34
    DOCUMENTARY = 35
    SITCOM = 36
    WAR = 37
    DETECTIVE = 38
    TRAGEDY = 39
    MATURE = 40
    POLITICAL = 41
    INVESTIGATION = 42
    MANGA = 44
    WESTERN = 45


class MDLStatus(IntEnum):
    ONGOING = 1
    UPCOMING = 2
    COMPLETED = 3


class MDLTypes(IntEnum):
    DRAMA = 68
    MOVIE = 77
    SHOW = 86


class DramaFormats(IntEnum):
    STANDARD = 7
    WEB = 8
    VERTICAL = 10
    SPECIAL = 14


class MovieFormats(IntEnum):
    FEATURE = 24
    SHORT = 26
    INDEPENDENT = 28
    MADEFORTV = 30
    DOCUMENTARY = 32
    ANIMATED = 34
    OTHER = 36


class ShowFormats(IntEnum):
    TALK = 5
    VARIETY = 6
    DOCUMENTARY = 16
    MUSIC = 18
    REALITY = 20
    OTHER = 22
    ANIMATED = 38


#! People
class MDLGenders(IntEnum):  # * These are the only 2 genders MyDramaList currently supports.
    FEMALE = 70
    MALE = 77


class MDLNationalities(IntEnum):
    JAPANESE = 1
    CHINESE = 2
    SOUTH_KOREAN = 3
    HONGKONGER = 4
    TAIWANESE = 5
    THAI = 6
    FILIPINO = 140
    SINGAPOREAN = 157


#! Return Types
class MDLSearchPeople(TypedDict):
    id: str
    title: str
    uri: str
    nationality: str
    short_desc: str


class MDLMedia(TypedDict):
    title: str
    native_title: str
    description: str
    url: str
    image_uri: str
    genres: list[str]
    tags: list[str]
    country: str
    rating: float
    rating_users: int
    original_network: Optional[str]
    screenwriter: list[str]
    director: list[str]
    type: str
    release_date: Optional[str]
    duration: str
    ranked: str
    content_rating: str
    daysofweek: Optional[list[str]]
    episodes: Optional[int]
    aired: Optional[str]

class MDLSearchMedia(TypedDict):
    id: str
    title: str
    uri: str
    image_uri: str
    score: str
    ranking: str
    type: str
    year: str
    amt_episodes: int
    short_desc: str
