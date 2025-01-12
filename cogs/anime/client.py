from __future__ import annotations

from json import JSONDecodeError
from typing import TYPE_CHECKING, Any, ClassVar, Optional

from aiohttp import ContentTypeError
from cachetools import TTLCache

from .anime import Media, MinifiedMedia
from .oauth import AccessToken, ApiExecption, OAuth, User
from .types import ActivityType, ListActivity, MediaListCollection, MediaListStatus, MediaType, SearchMedia

if TYPE_CHECKING:
    from bot import Harmony


class InvalidToken(Exception): ...


MINIFIED_SEARCH_QUERY = """
    query ($search: String, $type: MediaType) {
        Media(search: $search, type: $type, sort: POPULARITY_DESC) {
            id
            isAdult
            idMal
            type
            episodes
            status
            chapters
            volumes
            genres
            title {
                romaji
                english
                native
            }
            season
            seasonYear
            meanScore
            format
            coverImage {
                extraLarge
                color
            }
        }
    }
"""

MEDIA_QUERY = """
    query ($search: String, $id: Int, $type: MediaType) {
        Media(search: $search, id: $id, type: $type, sort: POPULARITY_DESC) {
            id
            isAdult
            idMal
            type
            description(asHtml: false)
            episodes
            hashtag
            status
            bannerImage
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
                        format
                        status
                        seasonYear
                        startDate {
                            year
                        }
                        title {
                            romaji
                        }
                        ...listEntry
                    }
                    relationType(version: 2)
                }
            }
            ...listEntry
        }
    }

    fragment listEntry on Media {
        mediaListEntry {
            score(format: POINT_10_DECIMAL)
            status
            progress
            progressVolumes
            repeat
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
        }
    }
"""

SEARCH_QUERY = """
    query ($search: String) {
        Page(perPage: 25) {
            media (search: $search, sort: POPULARITY_DESC) {
                id
                type
                title {
                    romaji
                }
            }
        }
    }
"""

MEDIA_LIST_FRAGMENT = """
    fragment mediaListFragment on MediaListCollection {
        lists {
            entries {
                score(format: POINT_10_DECIMAL)
                status
                progress
                progressVolumes
                repeat
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
                media {
                    id
                    isAdult
                    idMal
                    type
                    description(asHtml: false)
                    episodes
                    hashtag
                    status
                    bannerImage
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
                        ...listEntry
                        }
                        relationType(version: 2)
                    }
                    }
                    ...listEntry
                    nextAiringEpisode {
                    episode
                    }
                }
            }
            name
            isCustomList
            isSplitCompletedList
            status
        }
        user {
            name
            id
        }
    }

    fragment listEntry on Media {
        mediaListEntry {
            score(format: POINT_10_DECIMAL)
            status
            progress
            progressVolumes
            repeat
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
"""

MEDIA_LIST_QUERY = """
    query ($userName: String, $userId: Int $type: MediaType) {{
        MediaListCollection(userName: $userName, userId: $userId, type: $type, sort: SCORE_DESC) {{
            ...mediaListFragment
        }}
    }}

    {}
""".format(MEDIA_LIST_FRAGMENT)

COMPARISON_LIST_SUBQUERY = """
    q{n}: MediaListCollection (userName: $u{n}, userId: $i{n}, type: $type, status: $status) {{
        ...mediaListFragment
    }}
"""

COMPARISON_LIST_QUERY = """
    query ({params}) {{
        {queries}
    }}

    {fragment}
"""

FOLLOWING_QUERY = """
    query ($id: Int, $page: Int, $perPage: Int) {
        Page(page: $page, perPage: $perPage) {
            mediaList(mediaId: $id, isFollowing: true, sort: UPDATED_TIME_DESC) {
                status
                score(format: POINT_10_DECIMAL)
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

ACTIVITY_QUERY = """
    query ($id: Int, $type: ActivityType) {
        Page(perPage: 25) {
            activities(userId: $id, type: $type, sort: [PINNED, ID_DESC]) {
                ... on ListActivity {
                    id
                    type
                    replyCount
                    status
                    progress
                    isLocked
                    isSubscribed
                    isLiked
                    isPinned
                    likeCount
                    createdAt
                    siteUrl
                    user {
                        id
                        name
                        avatar {
                            large
                        }
                    }
                    media {
                        id
                        type
                        status(version: 2)
                        isAdult
                        bannerImage
                        siteUrl
                        title {
                            english
                            romaji
                        }
                        coverImage {
                            large
                        }
                    }
                }
            }
        }
    }
"""


class AniListClient:
    URL: ClassVar[str] = "https://graphql.anilist.co"

    def __init__(self, bot: Harmony) -> None:
        self.bot = bot
        self.oauth = OAuth(bot.session, self)
        self.user_cache: TTLCache[str | int, User] = TTLCache(maxsize=100, ttl=600)

    async def search_media(
        self, search: str, *, type: MediaType, user_id: Optional[int] = None
    ) -> tuple[Media, Optional[User]] | tuple[None, None]:
        """Searches and returns a media via a search query."""

        variables = {"search": search, "type": type}
        headers = await self.get_headers(user_id) if user_id else {}

        async with self.bot.session.post(
            self.URL,
            json={"query": MEDIA_QUERY, "variables": variables},
            headers=headers,
        ) as resp:
            if resp.status == 400:
                raise InvalidToken("The token has either expired or been revoked.")

            try:
                json = await resp.json()

            except (ContentTypeError, JSONDecodeError) as exc:
                raise ApiExecption() from exc

            try:
                data_ = json["data"]
                data = data_["Media"]
            except (KeyError, TypeError):
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

        media = Media.from_json(data, following_status or {}), user
        return media

    async def search_many(self, search: str) -> list[SearchMedia]:
        """Searches for media and returns the first 25 results."""

        variables = {"search": search}

        async with self.bot.session.post(self.URL, json={"query": SEARCH_QUERY, "variables": variables}) as resp:
            try:
                json = await resp.json()

            except (ContentTypeError, JSONDecodeError) as exc:
                raise ApiExecption() from exc

            if not json:
                return []

            data_ = json["data"]
            media: list[SearchMedia] = data_["Page"]["media"]

        return media

    async def search_minified_media(self, search: str, *, type: MediaType) -> Optional[MinifiedMedia]:
        """Searchs and returns a "minified" media via a search query."""

        variables = {"search": search, "type": type}

        async with self.bot.session.post(
            self.URL,
            json={"query": MINIFIED_SEARCH_QUERY, "variables": variables},
        ) as resp:
            try:
                json = await resp.json()

            except (ContentTypeError, JSONDecodeError):
                return None  # Not sending error messages if it's a minified media

            if not json:
                return None

            try:
                data_ = json["data"]
                data = data_["Media"]
            except (KeyError, TypeError):
                return None

            if data is None:
                return None

        return MinifiedMedia.from_json(data)

    async def fetch_media(self, id: int, *, user_id: Optional[int] = None) -> Optional[Media]:
        """Fetches and returns a media via an ID."""

        variables = {"id": id}
        headers = await self.get_headers(user_id) if user_id else {}

        async with self.bot.session.post(
            self.URL,
            json={"query": MEDIA_QUERY, "variables": variables},
            headers=headers,
        ) as resp:
            json = await resp.json()

            try:
                data_ = json["data"]
                data = data_["Media"]
            except (KeyError, TypeError):
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
        per_page: int = 15,
    ) -> Optional[dict[str, Any]]:
        """Fetches all the ratings of the followed users."""

        variables = {"id": media_id, "page": page, "perPage": per_page}
        headers = headers or await self.get_headers(user_id)

        if not headers:
            return None

        async with self.bot.session.post(
            self.URL,
            json={
                "query": FOLLOWING_QUERY,
                "variables": variables,
            },
            headers=headers,
        ) as resp:
            if resp.status == 200:
                try:
                    json = await resp.json()

                except (ContentTypeError, JSONDecodeError) as exc:
                    raise ApiExecption() from exc

                return json

    async def fetch_media_collection(self, user: int | str, type: MediaType) -> MediaListCollection:
        """Fetches a user's anime- or manga list via their user ID or username."""

        variables: dict[str, str | int] = {"type": type}
        if isinstance(user, int):
            variables["userId"] = user

        else:
            variables["userName"] = user

        async with self.bot.session.post(self.URL, json={"query": MEDIA_LIST_QUERY, "variables": variables}) as resp:
            try:
                json = await resp.json()

            except (ContentTypeError, JSONDecodeError) as exc:
                raise ApiExecption() from exc

            data = json["data"]["MediaListCollection"]
            collection: MediaListCollection = data
            return collection

    async def fetch_media_collections(
        self, *users: str | int, type: MediaType, status: MediaListStatus, user_id: Optional[int] = None
    ) -> dict[str, MediaListCollection]:
        """Fetches multiple users' anime- or manga lists via their user ID or username."""

        variables: dict[str, str | int] = {"type": type, "status": status}
        for c, user in enumerate(users):
            if isinstance(user, str):
                variables[f"u{c}"] = user

            else:
                variables[f"i{c}"] = user

        amount = len(users)
        params = ", ".join(f"$u{n}: String, $i{n}: Int" for n in range(amount))
        params += ", $type: MediaType, $status: MediaListStatus"

        queries = "".join(COMPARISON_LIST_SUBQUERY.format(n=n) for n in range(amount))

        query = COMPARISON_LIST_QUERY.format(params=params, queries=queries, fragment=MEDIA_LIST_FRAGMENT)

        headers = {}
        if user_id is not None:
            headers = await self.get_headers(user_id)

        async with self.bot.session.post(self.URL, json={"query": query, "variables": variables}, headers=headers) as resp:
            if resp.status == 200:
                try:
                    json = await resp.json()

                except (ContentTypeError, JSONDecodeError) as exc:
                    raise ApiExecption() from exc

                data = json["data"]

                return data
            return {}

    async def fetch_user_activity(self, user_id: int, *, type: ActivityType = ActivityType.MEDIA_LIST) -> list[ListActivity]:
        variables: dict[str, str | int] = {"type": type, "id": user_id}
        async with self.bot.session.post(self.URL, json={"query": ACTIVITY_QUERY, "variables": variables}) as resp:
            if resp.status == 200:
                data = await resp.json()
                activities: list[ListActivity] = data["data"]["Page"]["activities"]
                return activities

            return []

    async def get_token(self, user_id: int) -> Optional[AccessToken]:
        query = "SELECT * FROM anilist_tokens WHERE user_id = $1"
        resp = await self.bot.pool.fetchrow(query, user_id)

        if not resp:
            return None

        return AccessToken(
            resp["token"],
            resp["refresh"],
            resp["expiry"],
        )

    async def get_headers(self, user_id: int) -> dict[str, str]:
        token = await self.get_token(user_id)
        if token is not None:
            return self.oauth.get_headers(token.token)

        return {}
