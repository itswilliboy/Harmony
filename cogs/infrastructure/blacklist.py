from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from asyncpg import Record
from discord.ext import commands

from utils import BaseCog, GenericError, SuccessEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class BlacklistItem:
    """Represents an item on the blacklist"""

    def __init__(self, cog: Blacklist, record: Record) -> None:
        self.cog = cog

        self._guild_id = record.get("guild_id", None)
        self._user_id = record["user_id"]
        self._reason = record["reason"]

    def __repr__(self) -> str:
        return f"<BlacklistItem guild_id={self.guild_id}, user_id={self.user_id}, global={self.is_global}>"

    @property
    def is_global(self) -> bool:
        """Returns `True` if the blacklist is global."""
        return self._guild_id is None

    @property
    def guild_id(self) -> int | None:
        """Returns the guild ID the user is blacklisted in, if any."""
        return self._guild_id

    @property
    def user_id(self) -> int:
        """Returns the user ID of the blacklisted user."""
        return self._user_id

    @property
    def reason(self) -> str:
        """Returns the reason for the blacklist, if any."""
        return self._reason


class Flags(commands.FlagConverter, prefix="--", delimiter=" "):
    guild: discord.Guild | None = None
    reason: str | None = None


class Blacklist(BaseCog, command_attrs=dict(hidden=True)):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot

        self.blacklist: dict[int, BlacklistItem] = {}
        bot.loop.create_task(self.fill_cache())
        bot.add_check(self.blacklist_check, call_once=True)

    async def cog_check(self, ctx: Context) -> bool:
        predicate = await self.bot.is_owner(ctx.author)

        if predicate is False:
            raise commands.NotOwner()
        return predicate

    async def fill_cache(self) -> None:
        records = await self.bot.pool.fetch("SELECT * FROM blacklist")
        for record in records:
            self.blacklist[record["user_id"]] = BlacklistItem(self, record)

    def blacklist_check(self, ctx: Context) -> bool:
        if ctx.author.id in self.blacklist.keys():
            item = self.blacklist[ctx.author.id]
            if item.is_global:
                return False
            else:
                if ctx.guild.id == item.guild_id:
                    return False
        return True

    async def add_blacklist(
        self, user: discord.User, guild: discord.Guild | None, *, reason: str | None = None
    ) -> BlacklistItem:
        query = "INSERT INTO blacklist (user_id, guild_id, reason) VALUES ($1, $2, $3) RETURNING *"

        record = await self.bot.pool.fetchrow(query, user.id, guild and guild.id, reason)

        assert record
        item = BlacklistItem(self, record)
        self.blacklist[user.id] = item

        return item

    async def remove_blacklist(self, user: discord.User, guild: discord.Guild | None) -> None:
        query = "DELETE FROM blacklist WHERE user_id = $1"
        if guild is not None:
            query = "DELETE FROM blacklist WHERE user_id = $1 AND guild_id = $2"
            await self.bot.pool.execute(query, user.id, guild.id)
            return

        await self.bot.pool.execute(query, user.id)
        del self.blacklist[user.id]

    @commands.group(name="blacklist")
    async def blacklist_(self, ctx: Context) -> None:
        if not ctx.invoked_subcommand:
            raise GenericError("Invoke a valid subcommand.")

    @blacklist_.command()
    async def add(self, ctx: Context, user: discord.User, *, flags: Flags):
        guild: discord.Guild | None = flags and flags.guild
        reason: str | None = flags and flags.reason

        if item := self.blacklist.get(user.id, None):
            if guild and not item.is_global:
                if item.guild_id == guild.id:
                    raise GenericError("That user is already blacklisted in this guild.")

            elif not guild and item.is_global:
                raise GenericError("That user is already globally blacklisted.")

        await self.add_blacklist(user, guild, reason=reason)

        reason = flags and f"`{flags.reason}`"
        embed = SuccessEmbed(description=f"Successfully blacklisted {user.mention}\nReason: {reason}.")
        await ctx.send(embed=embed)

    @blacklist_.command()
    async def remove(self, ctx: Context, user: discord.User, *, flags: Flags):
        guild: discord.Guild | None = flags and flags.guild

        item = self.blacklist.get(user.id, None)
        if item is None:
            raise GenericError("That user isn't blacklisted.")

        elif guild and item.is_global:
            raise GenericError("This user isn't blacklisted in this server.")

        elif not guild and not item.is_global:
            raise GenericError("This user isn't blacklisted globally.")

        await self.remove_blacklist(user, guild)
        embed = SuccessEmbed(description=f"Successfully removed the blacklist for {user.mention}.")
        await ctx.send(embed=embed)
