from __future__ import annotations

from datetime import datetime, timedelta
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Optional, Self, TypedDict, cast

from aiohttp import ContentTypeError

from config import ANILIST_ID, ANILIST_REDIRECT, ANILIST_SECRET
from utils import GenericError, try_get_ani_id

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from . import AniListClient
    from .types import FavouriteType, MediaListOptions


class ApiExecption(GenericError):
    def __init__(self) -> None:
        super().__init__("The AniList API is having problems and is sending invalid data, please try again later.", True)


USER_FRAGMENT = """
    fragment userFragment on User {
        name
        id
        about
        avatar {
            large
        }
        bannerImage
        siteUrl
        createdAt
        statistics {
            anime {
                count
                meanScore
                minutesWatched
                episodesWatched
            }
            manga {
                count
                meanScore
                chaptersRead
                volumesRead
            }
        }
        mediaListOptions {
            scoreFormat
        }
        favourites {
            anime {
                nodes {
                    title {
                        userPreferred
                    }
                    siteUrl
                }
            }
            manga {
                nodes {
                    title {
                        userPreferred
                    }
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
                    }
                    siteUrl
                }
            }
            studios {
                nodes {
                    name
                    siteUrl
                }
            }
        }
    }
"""

VIEWER_QUERY = """
    query {{
        Viewer {{
            ...userFragment
        }}
    }}

    {}
""".format(USER_FRAGMENT)

USER_QUERY = """
    query ($name: String, $id: Int) {{
        User (name: $name, id: $id) {{
            ...userFragment
        }}
    }}

    {}
""".format(USER_FRAGMENT)


def parse_dict_or_str(
    item: str | dict[str, str],
    key: str,
) -> str:
    if isinstance(item, str):
        return item

    return item[key]


def parse_nodes(
    node: dict[str, str | dict[str, str]],
) -> PartialNode:
    name = None
    if node.get("title"):
        name = parse_dict_or_str(node["title"], "userPreferred")
    elif node.get("name"):
        name = parse_dict_or_str(node["name"], "userPreferred")
    else:
        raise ValueError(f"Invalid node: {node}")

    return PartialNode(
        name=name,
        site_url=node["siteUrl"],  # pyright: ignore[reportArgumentType]
    )


def parse_favourites(
    node: Any,
) -> Favourites:
    items = map(parse_nodes, node[1]["nodes"])

    return {
        "_type": node[0],
        "items": list(items),
    }


class Favourites(TypedDict):
    _type: FavouriteType
    items: list[PartialNode]


class UserStatistics(NamedTuple):
    count: int
    mean_score: float
    minutes_watched: int
    episodes_watched: int

    chapters_read: int
    volumes_read: int

    def __bool__(self) -> bool:
        return any((self.count, self.episodes_watched, self.chapters_read))


class PartialNode(NamedTuple):
    name: str
    site_url: str


class AccessToken(NamedTuple):
    token: str
    refresh: str
    expiry: datetime


class User:
    def __init__(
        self,
        name: str,
        id: int,
        about: Optional[str],
        avatar_url: Optional[str],
        banner_url: Optional[str],
        url: str,
        created_at: int,
        anime_stats: UserStatistics,
        manga_stats: UserStatistics,
        favourites: list[Favourites],
        media_list_options: MediaListOptions,
    ) -> None:
        self.name = name
        self.id = id
        self._about = about
        self.avatar_url = avatar_url
        self.banner_url = banner_url
        self.url = url
        self._created_at = created_at
        self.anime_stats = anime_stats
        self.manga_stats = manga_stats
        self.favourites = favourites
        self.media_list_options = media_list_options

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name}>"

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
            0,
        )

        manga_stats = UserStatistics(
            stats["manga"]["count"],
            stats["manga"]["meanScore"],
            0,
            0,
            stats["manga"]["chaptersRead"],
            stats["manga"]["volumesRead"],
        )

        favourites: list[Favourites] = list(map(parse_favourites, data["favourites"].items()))

        return cls(
            data["name"],
            data["id"],
            data["about"],
            avatar_url,
            data["bannerImage"],
            data["siteUrl"],
            data["createdAt"],
            anime_stats,
            manga_stats,
            favourites,
            data["mediaListOptions"],
        )

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self._created_at)


class OAuth:
    URL: ClassVar[str] = "https://graphql.anilist.co"

    def __init__(self, session: ClientSession, client: AniListClient) -> None:
        self.session = session
        self.client = client

    @staticmethod
    def get_headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_access_token(self, auth_code: str) -> Optional[AccessToken]:
        """Converts an Authorisation Code to an Access Token"""

        json = {
            "grant_type": "authorization_code",
            "client_id": ANILIST_ID,
            "client_secret": ANILIST_SECRET,
            "redirect_uri": ANILIST_REDIRECT,
            "code": auth_code,
        }

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        async with self.session.post("https://anilist.co/api/v2/oauth/token", json=json, headers=headers) as resp:
            try:
                json = await resp.json()

            except (ContentTypeError, JSONDecodeError) as exc:
                raise ApiExecption() from exc

            token = json.get("access_token", None)

            if token is None:
                return None

            expires = datetime.now() + timedelta(seconds=json["expires_in"])

        return AccessToken(token, json["refresh_token"], expires)

    async def get_current_user(self, token: str) -> User:
        """Gets the current user with the Access Token."""
        id_ = cast("int", await try_get_ani_id(self.client.bot.pool, token))
        if u := self.client.user_cache.get(id_):
            return u

        async with self.session.post(self.URL, headers=self.get_headers(token), json={"query": VIEWER_QUERY}) as resp:
            try:
                json = await resp.json()

            except (ContentTypeError, JSONDecodeError):
                raise ApiExecption() from None

            user = User.from_json(json["data"]["Viewer"])
            self.client.user_cache[id_] = user

            return user

    async def get_user(self, user: str | int, *, use_cache: bool = True) -> Optional[User]:
        """Gets a user by their username or AniList ID."""
        if use_cache is True and (u := self.client.user_cache.get(user)):
            return u

        variables = {"name": user} if isinstance(user, str) else {"id": user}

        async with self.session.post(self.URL, json={"query": USER_QUERY, "variables": variables}) as resp:
            try:
                json = await resp.json()

            except (ContentTypeError, JSONDecodeError):
                raise ApiExecption() from None

            try:
                u = User.from_json(json["data"]["User"])
                if use_cache is True:
                    self.client.user_cache[user] = u

                return u
            except Exception:
                return None
