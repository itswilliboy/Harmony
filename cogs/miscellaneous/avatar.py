from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any, Self, Sequence

import discord
from asyncpg import Pool, Record
from discord.ext import commands

from utils import BaseCog, DynamicPaginator, GenericError, PrimaryEmbed
from utils.paginator import Page

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class AvatarPage(Page):
    bytes: BytesIO

    @classmethod
    def from_record(cls, record: Record, user: discord.abc.User) -> Self:
        embed = PrimaryEmbed(title=f"Avatar History for {user}", timestamp=record["timestamp"])
        embed.set_footer(text=f"ID: {record['id']}")

        bytes = BytesIO(record["image_data"])
        embed.set_image(url="attachment://av.png")

        inst = cls(embed=embed)
        inst.bytes = bytes

        return inst

    @property
    def file(self) -> discord.File:
        return discord.File(self.bytes, filename="av.png")

    @file.setter
    def file(self, *_): ...

class AvatarPaginator(DynamicPaginator[Page]):
    user: discord.abc.User

    @classmethod
    async def populate(cls, pool: Pool[Record], count: int, user: discord.abc.User, *args: Any, **kwargs: Any) -> Self:
        inst = cls(*args, **kwargs)
        inst.user = user
        inst = await super().populate(pool, count, user=user, *args, **kwargs)
        return inst

    async def fetch_chunk(self, chunk: int) -> Sequence[Page]:
        query = """
            SELECT * FROM avatar_history
                WHERE user_id = $1
            ORDER BY
                timestamp ASC
            LIMIT $2 OFFSET $3
        """
        res = await self.pool.fetch(query, self.kwargs["user"].id, self.PER_CHUNK, chunk)

        return [AvatarPage.from_record(rec, self.kwargs["user"]) for rec in res]


class Avatar(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_user_update(self, _, after: discord.User):
        if after.avatar is None:
            return

        query = """
            INSERT INTO avatar_history (user_id, image_data)
            VALUES ($1, $2)
        """
        try:
            await self.bot.pool.execute(query, after.id, await after.avatar.read())

        except discord.NotFound:
            return

    @commands.command(aliases=["ah", "history", "pfps"])
    async def avatar_history(self, ctx: Context, member: discord.Member = commands.Author):
        count = await ctx.pool.fetchval("SELECT COUNT(*) FROM avatar_history WHERE user_id = $1", member.id)

        if not count:
            raise GenericError(f"There are no avatars stored for {member.mention}.")

        async with ctx.typing():
            await (await AvatarPaginator.populate(ctx.pool, count, member)).start(ctx)
