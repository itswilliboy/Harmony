from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Optional

from .anime import Media, MinifiedMedia
from .oauth import AccessToken, OAuth, User
from .types import MediaListCollection, MediaType

if TYPE_CHECKING:
    from bot import Harmony


class InvalidToken(Exception): ...


MINIFIED_SEARCH_QUERY = """
    query ($search: String, $type: MediaType) {
        Media (search: $search, type: $type, sort: POPULARITY_DESC) {
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
        Media (search: $search, id: $id, type: $type, sort: POPULARITY_DESC) {
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

        }
    }

    fragment listEntry on Media {
        mediaListEntry {
                score(format: POINT_10)
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
    query ($userName: String, $userId: Int $type: MediaType) {
        MediaListCollection(userName: $userName, userId: $userId, type: $type, sort: SCORE_DESC) {
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
                        type
                        episodes
                        status
                        duration
                        chapters
                        volumes
                        title {
                            english
                            romaji
                            native
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
            hasNextChunk
        }
    }
"""

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


class AniListClient:
    URL: ClassVar[str] = "https://graphql.anilist.co"

    def __init__(self, bot: Harmony) -> None:
        self.bot = bot
        self.oauth = OAuth(bot.session)

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

        return Media.from_json(data, following_status or {}), user

    async def search_minified_media(self, search: str, *, type: MediaType) -> Optional[MinifiedMedia]:
        """Searchs and returns a "minified" media via a search query."""

        variables = {"search": search, "type": type}

        async with self.bot.session.post(
            self.URL,
            json={"query": MINIFIED_SEARCH_QUERY, "variables": variables},
        ) as resp:
            json = await resp.json()

            if not json:
                return None

            try:
                data_ = json["data"]
                data = data_["Media"]
            except KeyError:
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
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data

    async def fetch_media_collection(self, user: int | str, type: MediaType) -> MediaListCollection:
        """Fetches a user's anime- or manga list via their user ID."""

        variables: dict[str, Any] = {"type": type}
        if isinstance(user, int):
            variables["userId"] = user

        else:
            variables["userName"] = user

        async with self.bot.session.post(self.URL, json={"query": MEDIA_LIST_QUERY, "variables": variables}) as resp:
            data = (await resp.json())["data"]["MediaListCollection"]
            collection: MediaListCollection = data
            return collection

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
