from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .anime import Media, MinifiedMedia
    from .oauth import Favourites, User
    from .types import FavouriteType, ListActivity


def add_favourite(embed: discord.Embed, *, user: User, type: FavouriteType, maxlen: int = 1024, empty: bool = False) -> None:
    favourites = discord.utils.find(lambda f: f["_type"] == type.lower(), user.favourites)

    if favourites and favourites["items"]:
        value = ""
        for favourite in favourites["items"][:5]:
            fmt = f"\n- **[{favourite.name}]({favourite.site_url})**"
            if len(value + fmt) > maxlen:
                break
            value += fmt
    elif empty:
        value = "No Favourites Found..."
    else:
        return

    embed.add_field(name=f"Favourite {type.title()}", value=value, inline=False)


def get_favourites(favourites: list[Favourites], type: FavouriteType) -> list[tuple[str, str]]:
    favs = discord.utils.find(lambda f: f["_type"] == type.lower(), favourites)

    if favs is None:
        return []

    to_return: list[tuple[str, str]] = []
    for fav in favs["items"]:
        to_return.append((fav.name, fav.site_url))

    return to_return


def get_activity_message(activity: ListActivity) -> tuple[str, datetime.datetime]:
    act = activity

    to_add: list[str] = []

    def add_item(item: str, timestamp: datetime.datetime) -> None:
        w_timestamp = discord.utils.format_dt(timestamp, "R") + f"\n{item}"
        to_add.append(w_timestamp)

    media = act["media"]
    timestamp = datetime.datetime.fromtimestamp(act["createdAt"])

    t = media["title"]
    title = t["english"] or t["romaji"] or t["native"]
    linked = f"**[{title}]({media['siteUrl']})**"

    status = act["status"]

    value = f"{status} | {linked}"
    match status:
        case "watched episode":
            ep = act["progress"]
            value = f"Watched episode **{ep}** of {linked}"
            add_item(value, timestamp)

        case "rewatched episode":
            ep = act["progress"]
            value = f"Rewatched episode **{ep}** of {linked}"
            add_item(value, timestamp)

        case "read chapter":
            ch = act["progress"]
            value = f"Read chapter **{ch}** of {linked}"
            add_item(value, timestamp)

        case "plans to watch":
            value = f"Plans to watch {linked}"
            add_item(value, timestamp)

        case "plans to read":
            value = f"Plans to read {linked}"
            add_item(value, timestamp)

        case "completed":
            value = f"Completed {linked}"
            add_item(value, timestamp)

        case "paused watching":
            value = f"Paused watching of {linked}"
            add_item(value, timestamp)

        case "paused reading":
            value = f"Paused reading of {linked}"
            add_item(value, timestamp)

        case "dropped":
            value = f"Dropped {linked}"
            add_item(value, timestamp)

        case "rewatched":
            value = f"Rewatched {linked}"
            add_item(value, timestamp)

        case _:
            print(status)
            add_item(f"{status.title()} | {linked}", timestamp)

    return value, timestamp


def get_title(media: Media | MinifiedMedia) -> str:
    """Gets the title of a media (english > romaji > native)."""
    return (
        media.title["english"] or media.title["romaji"] or media.title["native"] or "<No Title>"
    )  # Title should never not exist
