from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utils import BaseCog, GenericError, Paginator, PrimaryEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


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
        await ctx.typing()
        query = """
            SELECT id, image_data, timestamp FROM avatar_history
            WHERE user_id = $1
            ORDER BY timestamp
        """
        resp = await self.bot.pool.fetch(query, member.id)

        if not resp:
            raise GenericError(f"There are no avatars stored for {member.mention}.")

        embeds = []
        files = []
        for record in resp:
            embed = PrimaryEmbed(title=f"Avatar History for {member}", timestamp=record["timestamp"])
            embed.set_footer(text=f"ID: {record['id']}")

            file = discord.File(BytesIO(record["image_data"]), filename="avatar.png")
            embed.set_image(url="attachment://avatar.png")

            embeds.append(embed)
            files.append(file)

        await Paginator(embeds, ctx.author, files=files, reversed=True).start(ctx)
