from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
from asyncpg import Record
from discord.ext import commands

from utils import BaseCog, GenericError, PrimaryEmbed, SuccessEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class BlacklistItem:
    """Represents an item on the blacklist."""

    def __init__(self, cog: Blacklist, record: Record) -> None:
        self.cog = cog
        self._global: bool = record["global"]
        self._guild_ids: list[int] | None = record.get("guild_ids")
        self._user_id: int = record["user_id"]
        self._reason: str = record["reason"]

    def __repr__(self) -> str:
        return f"<BlacklistItem, user_id={self.user_id}, global={self.is_global}>"

    @property
    def is_global(self) -> bool:
        """Returns `True` if the blacklist is global."""
        return self._global

    @property
    def guild_ids(self) -> list[int]:
        """Returns the ID of any guilds the user if blacklisted in."""
        return [i for i in self._guild_ids] if self._guild_ids else []

    @property
    def user_id(self) -> int:
        """Returns the ID of the blacklisted user."""
        return self._user_id

    @property
    def reason(self) -> str:
        """Returns the reason for the blacklist."""
        return self._reason

    async def add_guild(self, guild: discord.abc.Snowflake) -> Self:
        """Adds a guild to the item."""
        if guild.id in self.guild_ids:
            raise ValueError("User is already blacklisted in that guild.")

        updated = await self.cog.bot.pool.fetchrow(
            """
            UPDATE blacklist
            SET guild_ids = ARRAY_APPEND(guild_ids, $1)
            WHERE user_id = $2
            RETURNING *
            """,
            guild.id,
            self.user_id,
        )
        assert updated
        self.__init__(self.cog, updated)
        return self

    async def remove_guild(self, guild: discord.abc.Snowflake) -> Self:
        """Removes a guild from the item."""
        if self.is_global:
            raise ValueError("Can't remove guilds from a global blacklist item.")

        elif guild.id not in self.guild_ids:
            raise ValueError("User is not blacklisted in that guild.")

        await self.cog.bot.pool.execute(
            """
            UPDATE blacklist
            SET guild_ids = ARRAY_REMOVE(guild_ids, $1)
            WHERE user_id = $2
            RETURNING *
            """,
            guild.id,
            self.user_id,
        )
        assert self._guild_ids
        self._guild_ids.remove(guild.id)
        return self


class GuildBlacklistItem:
    def __init__(self, record: Record) -> None:
        self._guild_id: int = record["guild_id"]
        self._reason: str = record["reason"]
        self._timestamp: datetime.datetime = record["timestamp"]

    @property
    def guild_id(self) -> int:
        """Returns the ID of the guild that is blacklisted."""
        return self._guild_id

    @property
    def reason(self) -> str:
        """Returns the reason for the blacklist."""
        return self._reason

    @property
    def timestamp(self) -> datetime.datetime:
        """Returns the date and time of blacklisting."""
        return self._timestamp


class Flags(commands.FlagConverter, prefix="--", delimiter=" "):
    guild: discord.Guild | None = None
    reason: str | None = None


class Blacklist(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.blacklist: dict[int, BlacklistItem] = {}
        self.guild_blacklist: dict[int, GuildBlacklistItem] = {}
        bot.loop.create_task(self.fill_cache())
        bot.add_check(self.blacklist_check, call_once=True)

    @staticmethod
    def blacklist_check(ctx: Context) -> bool:
        return not ctx.is_blacklisted()

    async def fill_cache(self) -> None:
        records = await self.bot.pool.fetch("SELECT * FROM blacklist")
        for record in records:
            self.blacklist[record["user_id"]] = BlacklistItem(self, record)

        records = await self.bot.pool.fetch("SELECT * FROM guild_blacklist")
        for record in records:
            self.guild_blacklist[record["guild_id"]] = GuildBlacklistItem(record)

    async def add_blacklist(
        self, user: discord.User, *, guild: discord.Guild | None = None, reason: str | None = None
    ) -> BlacklistItem:
        """Create a blacklist for a user, optionally in a specific guild."""
        if guild:
            query = """
                INSERT INTO blacklist (user_id, guild_ids, reason, global) 
                VALUES ($1, $2, $3, $4) 
                RETURNING *
            """

            record = await self.bot.pool.fetchrow(query, user.id, [guild.id], reason, False)

        else:
            query = """
                INSERT INTO blacklist (user_id, reason, global) 
                VALUES ($1, $2, $3) 
                RETURNING *
            """

            record = await self.bot.pool.fetchrow(query, user.id, reason, True)

        assert record
        item = BlacklistItem(self, record)
        self.blacklist[user.id] = item

        return item

    async def remove_blacklist(self, user: discord.User) -> None:
        """Remove the blacklist of a user from everywhere."""
        query = "DELETE FROM blacklist WHERE user_id = $1"
        await self.bot.pool.execute(query, user.id)
        del self.blacklist[user.id]

    async def add_guild_blacklist(self, guild: discord.Guild, reason: str) -> GuildBlacklistItem:
        """Add a guild to the blacklist."""
        query = """
            INSERT INTO guild_blacklist VALUES ($1, $2, $3)
            RETURNING *
        """
        record = await self.bot.pool.fetchrow(query, guild.id, reason, datetime.datetime.now())

        assert record
        item = GuildBlacklistItem(record)
        self.guild_blacklist[guild.id] = item

        return item

    async def remove_guild_blacklist(self, guild: discord.Guild) -> None:
        """Unblacklist a guild."""
        query = """
            DELETE FROM guild_blacklist WHERE guild_id = $1
        """
        await self.bot.pool.execute(query, guild.id)
        self.guild_blacklist.pop(guild.id, None)

    @commands.group(name="blacklist", hidden=True)
    async def blacklist_(self, ctx: Context) -> None:
        if not ctx.invoked_subcommand:
            raise GenericError("Invoke a valid subcommand.")

    @blacklist_.command()
    async def add(self, ctx: Context, user: discord.User, *, flags: Flags):
        guild: discord.Guild | None = flags and flags.guild
        reason: str | None = flags and flags.reason

        if item := self.blacklist.get(user.id):
            if item.is_global:
                raise GenericError("User is globally blacklisted")

            if not guild:
                raise commands.MissingRequiredArgument(ctx.command.params["flags"])

            await item.add_guild(guild)

        else:
            await self.add_blacklist(user, guild=guild, reason=reason)

        reason = flags and f"`{flags.reason}`"
        embed = SuccessEmbed(description=f"Successfully blacklisted {user.mention}\nReason: {reason}.")
        await ctx.send(embed=embed)

    @blacklist_.command()
    async def remove(self, ctx: Context, user: discord.User, *, flags: Flags):
        guild: discord.Guild | None = flags and flags.guild

        item = self.blacklist.get(user.id, None)
        if item is None:
            raise GenericError("User isn't blacklisted.")

        elif guild and item.is_global:
            raise GenericError("This user isn't blacklisted in that server.")

        if guild is not None:
            await item.remove_guild(guild)

        else:
            await self.remove_blacklist(user)

        embed = SuccessEmbed(description=f"Successfully removed the blacklist for {user.mention}.")
        await ctx.send(embed=embed)

    @blacklist_.command()
    async def status(self, ctx: Context, user: discord.User):
        item = self.blacklist.get(user.id)
        if item is None:
            raise GenericError("User isn't blacklisted.")

        nl = "\n"
        guilds = [self.bot.get_guild(i) for i in item.guild_ids if i]
        guild_names = [i.name for i in guilds if i]
        embed = (
            PrimaryEmbed(
                title="Blacklisted",
                description=f"""
            Globally: `{item.is_global}`
            {f'Servers:{nl}* {f" {nl}* ".join(guild_names)}' if not item.is_global else ''}
            """,
            )
            .set_thumbnail(url=user.display_avatar.url)
            .set_footer(text=f"{str(user)} | {user.id}")
        )

        await ctx.send(embed=embed)

    @commands.group(name="guild_blacklist", aliases=["gblacklist"])
    async def guild_blacklist_(self, ctx: Context):
        if not ctx.invoked_subcommand:
            raise GenericError("Invoke a valid subcommand.")

    @guild_blacklist_.command(name="add")
    async def g_add(
        self,
        ctx: Context,
        guild_id: int = commands.param(default=lambda ctx: ctx.guild.id),
        *,
        reason: str = "No reason given.",
    ):
        guild = self.bot.get_guild(guild_id)

        if guild is None:
            raise GenericError("Couldn't find that guild.")

        await self.add_guild_blacklist(guild, reason)
        embed = SuccessEmbed(description=f"Successfully blacklisted `{guild.name}`.")
        await ctx.send(embed=embed)

    @guild_blacklist_.command(name="status")
    async def g_status(self, ctx: Context, guild_id: int):
        item = self.guild_blacklist.get(guild_id)

        if item is None:
            raise GenericError("That guild isn't blacklisted.")

        guild = self.bot.get_guild(guild_id)
        assert guild

        embed = PrimaryEmbed(
            title="Guild Blacklisted",
            description=f"Reason: {item.reason}\nSince: {discord.utils.format_dt(item.timestamp, 'D')}",
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon)

        await ctx.send(embed=embed)

    @guild_blacklist_.command(name="remove")
    async def g_remove(self, ctx: Context, guild_id: int):
        item = self.guild_blacklist.get(guild_id)

        if item is None:
            raise GenericError("That guild isn't blacklisted.")

        guild = self.bot.get_guild(guild_id)
        assert guild

        await self.remove_guild_blacklist(guild)

        embed = SuccessEmbed(description=f"Successfully unblacklisted `{guild.name}`.")
        await ctx.send(embed=embed)
