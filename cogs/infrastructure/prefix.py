from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from config import DEFAULT_PREFIX
from utils import BaseCog, PrimaryEmbed, SuccessEmbed, GenericError

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context

MENTION_REGEX = re.compile(r"^<@!?([\d]+)>$")


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
                    "INSERT INTO prefixes VALUES ($1, $2) ON CONFLICT DO NOTHING", id, [DEFAULT_PREFIX]
                )

        else:
            for id in db_ids:
                if id in db_ids and id not in guild_ids:
                    await self.bot.pool.execute("DELETE FROM prefixes WHERE guild_id = $1", id)

    async def get_custom_prefixes(self, message: discord.Message) -> list[str]:
        prefixes = await self.bot.get_prefix(message)

        # Remove mention prefixes from list
        del prefixes[0]
        del prefixes[0]

        return prefixes

    async def add_custom_prefix(self, guild: discord.abc.Snowflake, prefix: str) -> None:
        query = """
            UPDATE prefixes
            SET prefixes = ARRAY_APPEND(prefixes, $1)
            WHERE
                guild_id = $2
        """
        await self.bot.pool.execute(query, prefix, guild.id)

    async def remove_custom_prefix(self, guild: discord.abc.Snowflake, prefix: str) -> None:
        query = """
            UPDATE prefixes
            SET prefixes = ARRAY_REMOVE(prefixes, $1)
            WHERE
                guild_id = $2
        """
        await self.bot.pool.execute(query, prefix, guild.id)

    async def reset_prefixes(self, guild: discord.abc.Snowflake) -> None:
        query = """
            UPDATE prefixes
            SET prefixes = $1
            WHERE 
                guild_id = $2
        """
        await self.bot.pool.execute(query, [DEFAULT_PREFIX], guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.bot.pool.execute("INSERT INTO prefixes VALUES ($1, $2)", guild.id, [DEFAULT_PREFIX])

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.bot.pool.execute("DELETE FROM prefixes WHERE guild_id = $1", guild.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if match := MENTION_REGEX.fullmatch(message.content):
            if match and match.group(1) == str(self.bot.user.id):
                ctx = await self.bot.get_context(message)
                cmd = self.bot.get_command("prefix")

                await ctx.invoke(cmd)  # type: ignore

    @commands.guild_only()
    @commands.group(invoke_without_command=True)
    async def prefix(self, ctx: Context):
        """Displays the server's prefix."""

        prefixes = await self.get_custom_prefixes(ctx.message)
        formatted = [f"`{pre}`" for pre in prefixes]
        formatted.insert(0, self.bot.user.mention)

        nl = "\n"
        embed = PrimaryEmbed(
            description=f"Here is a list of the server-prefixes:\n* {f' {nl}* '.join(formatted)}"
        )
        embed.set_author(name=f"Get started with {ctx.clean_prefix}help !")

        if ctx.author.guild_permissions.manage_guild:  # type: ignore
            embed.set_footer(text=f"You can add another prefix with '{ctx.clean_prefix}prefix add <prefix>'")
        await ctx.send(embed=embed)

    @commands.has_guild_permissions(manage_guild=True)
    @prefix.command()
    async def add(self, ctx: Context, prefix: str):
        """Adds a server-prefix."""

        if len(prefix) > 5:
            raise GenericError("The prefix needs to be shorter than 5 characters.")

        prefixes = await self.get_custom_prefixes(ctx.message)
        if len(prefixes) - 2 >= 5:
            raise GenericError("You cannot have more than 5 custom prefixes.")

        if prefix in prefixes:
            raise GenericError("That prefix already exists.")

        await self.add_custom_prefix(ctx.guild, prefix)
        embed = SuccessEmbed(description=f"Successfully added `{prefix}` as a prefix.")
        await ctx.send(embed=embed)

    @commands.has_guild_permissions(manage_guild=True)
    @prefix.command()
    async def remove(self, ctx: Context, prefix: str):
        """Removes a server-prefix."""

        if prefix == DEFAULT_PREFIX:
            raise GenericError("You can't remove the default prefix.")

        if prefix not in (await self.get_custom_prefixes(ctx.message)):
            raise GenericError("That prefix doesn't exist.")

        await self.remove_custom_prefix(ctx.guild, prefix)
        embed = SuccessEmbed(description=f"Successfully removed `{prefix}` as a prefix.")
        await ctx.send(embed=embed)

    @commands.has_guild_permissions(manage_guild=True)
    @prefix.command()
    async def reset(self, ctx: Context):
        """Resets the server's prefixes."""

        await self.reset_prefixes(ctx.guild)
        embed = SuccessEmbed(description="Successfully reset all of the prefixes")
        await ctx.send(embed=embed)
