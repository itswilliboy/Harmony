from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Self, TypedDict

from config import ANILIST_ID, ANILIST_SECRET

if TYPE_CHECKING:
    from aiohttp import ClientSession

VIEWER_QUERY = """
    query {
        Viewer {
            name,
            about,
            avatar {
                large
            },
            bannerImage,
            siteUrl,
            createdAt,
            statistics {
                anime {
                    count,
                    meanScore,
                    minutesWatched,
                    episodesWatched
                }
                manga {
                    count,
                    meanScore,
                    chaptersRead,
                    volumesRead
                }
            }
            favourites {
                anime {
                    nodes {
                        title {
                            userPreferred
                        },
                        siteUrl
                    }
                }
                manga {
                    nodes {
                        title {
                            userPreferred
                        },
                        siteUrl
                    }
                }
                characters {
                    nodes {
                        name {
                            userPreferred
                        },
                        siteUrl
                    }
                }
                staff {
                    nodes {
                        name {
                            userPreferred
                        },
                        siteUrl
                    }
                }
                studios {
                    nodes {
                        name,
                        siteUrl
                    }
                }
            }
        }
    }
"""

USER_QUERY = """
    query ($name: String) {
        User (name: $name) {
            name,
            about,
            avatar {
                large
            },
            bannerImage,
            siteUrl,
            createdAt,
            statistics {
                anime {
                    count,
                    meanScore,
                    minutesWatched,
                    episodesWatched
                }
                manga {
                    count,
                    meanScore,
                    chaptersRead,
                    volumesRead
                }
            }
            favourites {
                anime {
                    nodes {
                        title {
                            userPreferred
                        },
                        siteUrl
                    }
                }
                manga {
                    nodes {
                        title {
                            userPreferred
                        },
                        siteUrl
                    }
                }
                characters {
                    nodes {
                        name {
                            userPreferred
                        },
                        siteUrl
                    }
                }
                staff {
                    nodes {
                        name {
                            userPreferred
                        },
                        siteUrl
                    }
                }
                studios {
                    nodes {
                        name,
                        siteUrl
                    }
                }
            }
        }
    }
"""

class UserStatistics(NamedTuple):
    count: int
    mean_score: float
    minutes_watched: int
    episodes_watched: int

    chapters_read: int
    volumes_read: int

class PartialNode(NamedTuple):
    name: str
    site_url: str

class Favourites(TypedDict):
    anime: PartialNode
    manga: PartialNode
    characters: PartialNode
    staff: PartialNode
    studios: PartialNode

class AccessToken(NamedTuple):
    token: str
    expiry: datetime

class User:
    def __init__(
        self,
        name: str,
        about: str | None,
        avatar_url: str | None,
        banner_url: str | None,
        url: str,
        created_at: int,
        anime_stats: UserStatistics,
        manga_stats: UserStatistics,
        favourites: Favourites
    ) -> None:
        self.name = name
        self.about = about
        self.avatar_url = avatar_url
        self.banner_url = banner_url
        self.url = url
        self._created_at = created_at
        self.anime_stats = anime_stats
        self.manga_stats = manga_stats
        self.favourites = favourites

    def __str__(self) -> str:
        return self.name

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        avatar_url = data["avatar"]["large"]

        stats = data["statistics"]
        anime_stats = UserStatistics(
            stats["anime"]["count"],
            stats["anime"]["meanScore"],
            stats["anime"]["minutesWatched"],
            stats["anime"]["episodesWatched"],
            0,
            0
        )

        manga_stats = UserStatistics(
            stats["manga"]["count"],
            stats["manga"]["meanScore"],
            0,
            0,
            stats["manga"]["chaptersRead"],
            stats["manga"]["volumesRead"]
        )

        favourites: Favourites = {}  # type: ignore
        for k, v in data["favourites"].items():
            k: str
            v: dict[str, Any]

            nodes = v["nodes"]
            if not nodes:
                continue

            first = v["nodes"][0]

            it = iter(first)
            name = next(it)
            url = next(it)

            name = first[name]
            url = first[url]

            if isinstance(name, dict):
                name = name["userPreferred"]

            favourites[k] = PartialNode(name, url)

        return cls(
            data["name"],
            data["about"],
            avatar_url,
            data["bannerImage"],
            data["siteUrl"],
            data["createdAt"],
            anime_stats,
            manga_stats,
            favourites
        )

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self._created_at)

    @staticmethod
    def _get_progress_bar(percentage: float) -> str:
        empty = "\N{LIGHT SHADE}"
        full = "\N{FULL BLOCK}"

        score = round(percentage/10)
        bar = (full*score).ljust(10, empty)
        return bar


class OAuth:
    URL: ClassVar[str] = "https://graphql.anilist.co"

    def __init__(self, session: ClientSession) -> None:
        self.session = session

    @staticmethod
    def _get_headers(token: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        return headers

    async def get_access_token(self, auth_code: str) -> AccessToken | None:
        """Converts a Authorization Code to an Access Token"""

        json = {
            "grant_type": "authorization_code",
            "client_id": ANILIST_ID,
            "client_secret": ANILIST_SECRET,
            "redirect_uri": "https://anilist.co/api/v2/oauth/pin",
            "code": auth_code
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        async with self.session.post("https://anilist.co/api/v2/oauth/token", json=json, headers=headers) as resp:
            json = await resp.json()
            token = json.get("access_token", None)

            if token is None:
                return None

            expires = datetime.now() + timedelta(seconds=json["expires_in"])

        return AccessToken(token, expires)

    async def get_current_user(self, token: str) -> User:
        """Gets the current user with the Access Token."""

        async with self.session.post(self.URL, headers=self._get_headers(token), json={"query": VIEWER_QUERY}) as resp:
            json = await resp.json()
            return User.from_json(json["data"]["Viewer"])

    async def get_user(self, username: str) -> User | None:
        """Gets a user by their username."""

        async with self.session.post(self.URL, json={"query": USER_QUERY, "variables": {"name": username}}) as resp:
            json = await resp.json()
            try:
                return User.from_json(json["data"]["User"])

            except:
                raise
