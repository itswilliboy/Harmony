from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utils import BaseCog, Context, Paginator, PrimaryEmbed

if TYPE_CHECKING:
    from bot import Harmony


class Statistics(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: Context):
        if ctx.guild is None:  # type: ignore
            return

        await ctx.pool.execute(
            """
            INSERT INTO command_statistics
                VALUES ($1, 1)
            ON CONFLICT (guild_id)
                DO UPDATE
                SET count = (
                    SELECT count FROM command_statistics
                    WHERE guild_id = $1
                ) + 1
            """,
            ctx.guild.id
        )

    @commands.Cog.listener("on_message")
    async def message_listener(self, message: discord.Message):
        if message.guild is None:
            return

        if message.webhook_id is not None:
            return

        await self.bot.pool.execute(
            """
            INSERT INTO message_statistics
                VALUES ($1, $2, 1, $3)
            ON CONFLICT (guild_id, user_id)
                DO UPDATE
                SET count = (
                    SELECT count FROM message_statistics
                    WHERE guild_id = $1
                    AND user_id = $2
                ) + 1
            """,
            message.guild.id,
            message.author.id,
            message.author.bot,
        )

    @commands.group(aliases=["msgs"], invoke_without_command=True)
    async def messages(self, ctx: Context, member: discord.Member = commands.Author):
        res: int = await ctx.pool.fetchval(
            "SELECT count FROM message_statistics WHERE user_id = $1 AND guild_id = $2", member.id, ctx.guild.id
        )

        is_author = ctx.author == member
        apos = "'"  # :^)
        await ctx.send(
            embed=PrimaryEmbed(
                description=f"{f'{member.mention} has' if not is_author else f'You{apos}ve'} sent **{res}** messages in *{ctx.guild.name}*"
            )
        )

    @messages.command(aliases=["lb"])
    async def leaderboard(self, ctx: Context, with_bots: bool = False):
        res = await ctx.pool.fetch(
            """
            SELECT user_id, count FROM message_statistics
                WHERE guild_id = $1 AND bot = $2
            ORDER BY count DESC
            """,
            ctx.guild.id,
            with_bots,
        )

        embeds: list[discord.Embed] = []
        for chunk in discord.utils.as_chunks(res, 10):
            embed = PrimaryEmbed(title="Message Leaderboard")

            for chnk in chunk:
                member = ctx.guild.get_member(chnk["user_id"])
                name = None

                if member:
                    name = member.global_name if member.global_name not in (None, member.name) else None

                embed.add_field(
                    name=member
                    and f"{member.display_name} {f'({name})' if name else ''}"
                    or f"Unknown User ({chnk['user_id']})",
                    value=f"**{chnk['count']}** message{'s' if chnk['count'] != 1 else ''}",
                    inline=False,
                )

            embeds.append(embed)

        await Paginator(embeds, ctx.author).start(ctx)
