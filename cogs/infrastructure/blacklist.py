from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from asyncpg import Record
from discord.ext import commands
from typing_extensions import Self

from utils import BaseCog, GenericError, PrimaryEmbed, SuccessEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class BlacklistItem:
    """Represents an item on the blacklist"""

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
    def guild_ids(self) -> list[int | None]:
        """Returns the guild ID the user is blacklisted in, if any."""
        return [i for i in self._guild_ids] if self._guild_ids else []

    @property
    def user_id(self) -> int:
        """Returns the user ID of the blacklisted user."""
        return self._user_id

    @property
    def reason(self) -> str:
        """Returns the reason for the blacklist, if any."""
        return self._reason

    async def add_guild(self, guild: discord.abc.Snowflake) -> Self:
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
        self.__init__(self.cog, updated)  # type: ignore
        return self

    async def remove_guild(self, guild: discord.abc.Snowflake) -> Self:
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
                if ctx.guild.id in item.guild_ids:
                    return False
        return True

    async def add_blacklist(
        self, user: discord.User, *, guild: discord.Guild | None = None, reason: str | None = None
    ) -> BlacklistItem:
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
        query = "DELETE FROM blacklist WHERE user_id = $1"
        await self.bot.pool.execute(query, user.id)
        self.blacklist.pop(user.id)

    @commands.group(name="blacklist")
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
            item = await self.add_blacklist(user, guild=guild, reason=reason)

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
        guilds = [self.bot.get_guild(i) for i in item.guild_ids]  # type: ignore
        guild_names = [i.name for i in guilds]  # type: ignore
        embed = (
            PrimaryEmbed(
                title="Blacklisted",
                description=f"""
            Globally: `{item.is_global}`
            {f'Servers{nl}* {f" {nl}* ".join(guild_names)}' if not item.is_global else ''}
            """,
            )
            .set_thumbnail(url=user.display_avatar.url)
            .set_footer(text=f"{str(user)} | {user.id}")
        )

        await ctx.send(embed=embed)
