from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from config import DEFAULT_PREFIX
from utils import BaseCog, ErrorEmbed, PrimaryEmbed, SuccessEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class Prefix(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        bot.loop.create_task(self.check_prefixes())

    async def check_prefixes(self) -> None:
        await self.bot.wait_until_ready()
        prefixes = await self.bot.pool.fetch("SELECT * FROM prefixes")
        guild_ids = set([i.id for i in self.bot.guilds])
        db_ids = set([i["guild_id"] for i in prefixes])

        if len(guild_ids) > len(db_ids):
            for id in guild_ids:
                await self.bot.pool.execute(
                    "INSERT INTO prefixes VALUES ($1, $2) ON CONFLICT DO NOTHING", id, DEFAULT_PREFIX
                )

        else:
            for id in db_ids:
                if id in db_ids and id not in guild_ids:
                    await self.bot.pool.execute("DELETE FROM prefixes WHERE guild_id = $1", id)

    async def get_custom_prefix(self, message: discord.Message) -> str:
        prefixes = await self.bot.get_prefix(message)
        if isinstance(prefixes, list):
            del prefixes[0]  # Delete mention prefixes
            del prefixes[0]

        return prefixes[0]

    async def set_custom_prefix(self, guild: discord.abc.Snowflake, prefix: str) -> None:
        query = """
            UPDATE prefixes
            SET prefix = $1
            WHERE
                guild_id = $2
        """
        await self.bot.pool.execute(query, prefix, guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.bot.pool.execute("INSERT INTO prefixes VALUES ($1, $2)", guild.id, DEFAULT_PREFIX)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.bot.pool.execute("DELETE FROM prefixes WHERE guild_id = $1", guild.id)

    @commands.group(invoke_without_command=True)
    async def prefix(self, ctx: Context):
        """Displays the server's prefix."""
        embed = PrimaryEmbed(description=f"The current prefix is: `{await self.get_custom_prefix(ctx.message)}`")
        embed.set_footer(text=f"You can set a new one with '{ctx.clean_prefix}prefix set <prefix>'")
        await ctx.send(embed=embed)

    @commands.has_guild_permissions(manage_guild=True)
    @prefix.command()
    async def set(self, ctx: Context, prefix: str):
        """Updates the server's prefix."""
        if len(prefix) > 5:
            embed = ErrorEmbed(description="The prefix needs to be shorter than 5 characters.")
            return await ctx.send(embed=embed)

        await self.set_custom_prefix(ctx.guild, prefix)
        embed = SuccessEmbed(description=f"Successfully updated the prefix to: `{prefix}`")
        await ctx.send(embed=embed)

    @commands.has_guild_permissions(manage_guild=True)
    @prefix.command()
    async def reset(self, ctx: Context):
        """Resets the server's prefix to the default prefix."""
        await self.set_custom_prefix(ctx.guild, DEFAULT_PREFIX)
        embed = SuccessEmbed(description=f"Successfully reset the prefix to: `{DEFAULT_PREFIX}`")
        await ctx.send(embed=embed)
