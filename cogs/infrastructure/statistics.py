from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utils import BaseCog, Context

if TYPE_CHECKING:
    from bot import Harmony


class Statistics(BaseCog, command_attrs=dict(hidden=True)):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot
        bot.loop.create_task(self.check_statistics())

    async def check_statistics(self) -> None:
        bot = self.bot
        await bot.wait_until_ready()

        for guild in bot.guilds:
            if not await bot.pool.fetch("SELECT guild_id FROM statistics WHERE guild_id = $1", guild.id):
                await bot.pool.execute("INSERT INTO statistics (guild_id) VALUES ($1)", guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.bot.pool.execute("INSERT INTO statistics (guild_id) VALUES ($1) ON CONFLICT DO NOTHING", guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await self.bot.pool.execute("DELETE FROM statistics WHERE guild_id = $1", guild.id)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: Context):
        if ctx.guild is None:
            return

        await self.bot.pool.execute(
            """
            UPDATE statistics
            SET command_runs = command_runs + 1
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )
