from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional, Self, cast

import discord
from discord import ui

from utils import Paginator, PrimaryEmbed, get_score

from .types import MediaFormat, MediaListCollection, MediaListStatus, MediaType, ScoreFormat
from .utils import get_title

if TYPE_CHECKING:
    from bot import Harmony

    from . import AniListClient

    Interaction = discord.Interaction[Harmony]


def field(*args: str | Literal[0]) -> str:
    return "\n".join(line for line in args if line)


class MediaList(Paginator[discord.Embed]):
    def __init__(self, client: AniListClient, collection: MediaListCollection, aniuser_id: int, user_id: int) -> None:
        self.anime: MediaListCollection = collection
        self.manga: Optional[MediaListCollection] = None

        self.client = client
        self.collection = collection
        self.aniuser_id = aniuser_id

        self.current_status: MediaListStatus = MediaListStatus.COMPLETED
        super().__init__(self.embeds(MediaListStatus.COMPLETED), discord.Object(user_id))

        self._anime.label = f"Anime ({self.get_length(self.anime)})"
        self.update_status_buttons()

    @staticmethod
    def get_length(seq: MediaListCollection, status: Optional[MediaListStatus] = None) -> int:
        if status is None:
            return sum(len(i["entries"]) for i in seq["lists"])
        return sum(len(i["entries"]) for i in seq["lists"] if i["entries"][0]["status"] == status)

    async def fetch_manga(self) -> MediaListCollection:
        return await self.client.fetch_media_collection(self.aniuser_id, MediaType.MANGA)

    def update_collection(self, collection: MediaListCollection) -> None:
        self.collection = collection
        embeds = self.embeds(self.current_status)

        self.page = 0
        self.items = embeds
        self.count = len(self.items)
        self.current = self.items[0]

        self.update_buttons()

    def enable_status_buttons(self) -> None:
        self.completed.disabled = False
        self.watching.disabled = False
        self.paused.disabled = False
        self.dropped.disabled = False
        self.planning.disabled = False

    def update_status_buttons(self) -> None:
        self.completed.label = f"Completed ({self.get_length(self.collection, MediaListStatus.COMPLETED)})"
        self.paused.label = f"Paused ({self.get_length(self.collection, MediaListStatus.PAUSED)})"
        self.dropped.label = f"Dropped ({self.get_length(self.collection, MediaListStatus.DROPPED)})"
        self.planning.label = f"Planning ({self.get_length(self.collection, MediaListStatus.PLANNING)})"

        if self.collection["lists"][0]["entries"][0]["media"]["type"] == MediaFormat.MANGA:
            self.watching.label = f"Reading ({self.get_length(self.collection, MediaListStatus.CURRENT)})"

        else:
            self.watching.label = f"Watching ({self.get_length(self.collection, MediaListStatus.CURRENT)})"

    async def status_callback(self, status: MediaListStatus, interaction: Interaction, button: ui.Button[Self]) -> None:
        self.current_status = status
        self.update_collection(self.collection)

        self.enable_status_buttons()
        self.update_status_buttons()
        button.disabled = True

        await self.update(interaction)

    async def update(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(embed=self.current, view=self)

    def embeds(self, type: MediaListStatus) -> list[discord.Embed]:
        score_format = cast(ScoreFormat, self.collection["user"]["mediaListOptions"]["scoreFormat"])  # type: ignore

        try:
            list_ = [i for i in self.collection["lists"] if i["status"] == type][0]

        except IndexError:
            return [PrimaryEmbed(description="Pretty empty here...")]

        embeds: list[discord.Embed] = []
        for chunk in discord.utils.as_chunks(list_["entries"], 5):
            format = list_["entries"][0]["media"]["type"]
            type_ = str(type).title().replace("Current", "Watching")

            if type == MediaListStatus.CURRENT and format == MediaType.MANGA:
                type_ = "Reading"

            list_url = f"https://anilist.co/user/{self.collection['user']['name']}/{str(format).lower()}list/{type_}"

            embed = PrimaryEmbed(title=f"{self.collection['user']['name']}'s {type_} {format.title()}", url=list_url)
            desc: list[str] = []

            for entry in chunk:
                media = entry["media"]
                title = get_title(media["title"])

                total = media["episodes"] or media["chapters"] or "TBA"

                url = f"https://anilist.co/{(media['type']).lower()}/{media['id']}"

                backlog_text = ""
                if (next_episode := media["nextAiringEpisode"]) and next_episode and entry["progress"]:
                    current_ep = next_episode["episode"] - 1
                    episode_backlog = current_ep - entry["progress"]

                    plural = "s" if episode_backlog > 1 else ""

                    backlog_text = (
                        (f"`({episode_backlog} episode{plural} behind)`")
                        if episode_backlog and (entry["status"] in (MediaListStatus.CURRENT, MediaListStatus.REPEATING))
                        else ""
                    )

                    backlog_text += (
                        f"\n-# ╰ Next episode <t:{next_episode['airingAt']}:R> (<t:{next_episode['airingAt']}:f>)"
                    )

                wording = "Rewatches" if format == MediaType.ANIME else "Rereads"

                info = field(
                    f"### [{title}]({url})",
                    f"↪ Score: **{get_score(entry['score'], score_format)}**",
                    f"↪ Progress: **{entry['progress']} / {total}** {backlog_text}",
                    entry["repeat"] and f"╰ {wording}: **{entry['repeat']}**",
                )

                desc.append(info)

            embed.description = "\n".join(desc)
            embeds.append(embed)

        return embeds

    @ui.button(emoji="\N{VIDEO CAMERA}", label="Anime", row=2, disabled=True, style=discord.ButtonStyle.green)
    async def _anime(self, interaction: Interaction, button: ui.Button[Self]):
        if self.manga is not None:
            self._manga.disabled = False
        button.disabled = True

        self.collection = self.anime
        self.update_collection(self.anime)
        self.update_status_buttons()

        await self.update(interaction)

    @ui.button(emoji="\N{OPEN BOOK}", label="Manga", row=2, style=discord.ButtonStyle.green)
    async def _manga(self, interaction: Interaction, button: ui.Button[Self]):
        self._anime.disabled = False
        button.disabled = True

        if self.manga is None:
            self.manga = await self.fetch_manga()
            if not self.manga["lists"]:
                self._anime.disabled = True
                return await self.update(interaction)

            button.label = f"Manga ({self.get_length(self.manga)})"

        self.collection = self.manga
        self.update_collection(self.manga)
        self.update_status_buttons()

        await self.update(interaction)

    @ui.button(label="Sorted By: Score Descending", row=2, disabled=True)
    async def _sorted(self, *_): ...

    @ui.button(label="Completed", row=3, disabled=True, style=discord.ButtonStyle.blurple)
    async def completed(self, interaction: Interaction, button: ui.Button[Self]):
        await self.status_callback(MediaListStatus.COMPLETED, interaction, button)

    @ui.button(label="Watching", row=3, style=discord.ButtonStyle.blurple)
    async def watching(self, interaction: Interaction, button: ui.Button[Self]):
        await self.status_callback(MediaListStatus.CURRENT, interaction, button)

    @ui.button(label="Paused", row=3, style=discord.ButtonStyle.blurple)
    async def paused(self, interaction: Interaction, button: ui.Button[Self]):
        await self.status_callback(MediaListStatus.PAUSED, interaction, button)

    @ui.button(label="Dropped", row=3, style=discord.ButtonStyle.blurple)
    async def dropped(self, interaction: Interaction, button: ui.Button[Self]):
        await self.status_callback(MediaListStatus.DROPPED, interaction, button)

    @ui.button(label="Planning", row=3, style=discord.ButtonStyle.blurple)
    async def planning(self, interaction: Interaction, button: ui.Button[Self]):
        await self.status_callback(MediaListStatus.PLANNING, interaction, button)
