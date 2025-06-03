from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Self

import discord
from asyncache import cachedmethod  # pyright: ignore[reportMissingTypeStubs]
from asyncpg import Record
from cachetools import TTLCache
from discord.app_commands import describe
from discord.ext import commands

from utils import BaseCog, BaseView, Context, GenericError, Interaction, Paginator, PrimaryEmbed, SuccessEmbed

if TYPE_CHECKING:
    from bot import Harmony


@dataclass
class AfkRecord:
    user_id: int
    timestamp: datetime.datetime
    reason: Optional[str]
    mentioned: bool

    @classmethod
    def from_record(cls, record: Record) -> Self:
        return cls(record["user_id"], record["timestamp"], record.get("reason"), record["mentioned"])

    async def add_mention(
        self,
        bot: Harmony,
        user_id: int,
        mentioner_id: int,
        guild_id: Optional[int],
        channel_id: int,
        message_id: int,
        is_reply: bool,
    ) -> None:
        query = """
            UPDATE afk
            SET mentioned = true
                WHERE user_id = $1
        """
        await bot.pool.execute(query, self.user_id)
        self.mentioned = True

        query = """
            INSERT INTO afk_mentions
                (
                    user_id,
                    mentioner_id,
                    guild_id,
                    channel_id,
                    message_id,
                    is_reply
                )
            VALUES
                ($1, $2, $3, $4, $5, $6)
        """
        await bot.pool.execute(
            query,
            user_id,
            mentioner_id,
            guild_id,
            channel_id,
            message_id,
            is_reply,
        )


@dataclass
class AfkMention:
    user_id: int
    mentioner_id: int
    timestamp: datetime.datetime
    guild_id: int
    channel_id: int
    message_id: int
    is_reply: bool

    @classmethod
    def from_record(cls, record: Record) -> Self:
        return cls(
            record["user_id"],
            record["mentioner_id"],
            record["timestamp"],
            record["guild_id"],
            record["channel_id"],
            record["message_id"],
            record["is_reply"],
        )


class MentionPaginator(Paginator[discord.Embed]):
    def __init__(self, cog: Afk, mentions: list[AfkMention], author: discord.abc.Snowflake) -> None:
        embeds: list[discord.Embed] = []

        for i, items in enumerate(discord.utils.as_chunks(mentions, 5), start=1):
            embed = PrimaryEmbed(title="Mentions")
            for j, item in enumerate(items, start=1):
                jump_url = f"https://discord.com/channels/{item.guild_id}/{item.channel_id}/{item.message_id}"
                timestamp = discord.utils.format_dt(item.timestamp, "R")

                embed.add_field(
                    name=f"{'Reply' if item.is_reply else 'Mention'} {i}:{j}",
                    value=f"{timestamp}\nUser: <@{item.mentioner_id}>\nMessage: {jump_url}",
                    inline=False,
                )

            embeds.append(embed)
        super().__init__(embeds, author)
        self.cog = cog
        self.mentions = mentions

    @discord.ui.button(label="Clear all mentions", style=discord.ButtonStyle.red)
    async def clear(self, interaction: Interaction, _):
        await self.cog.clear_mentions(interaction.user)

        embed = SuccessEmbed(description="Successfully cleared all mentions")
        self.disable()
        await interaction.response.edit_message(embed=embed, view=self)


class MentionView(BaseView):
    def __init__(self, cog: Afk, author: Optional[discord.abc.Snowflake] = None) -> None:
        super().__init__(author=author)
        self.cog = cog

    @discord.ui.button(label="View Mentions", style=discord.ButtonStyle.green)
    async def view_mentions(self, interaction: Interaction, _):
        mentions = await self.cog.get_mentions(interaction.user)
        await MentionPaginator(self.cog, mentions, interaction.user).start_interaction(interaction, ephemeral=True)


class Afk(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot

        self.afk_cache: TTLCache[int, AfkRecord] = TTLCache(maxsize=100, ttl=600)

    async def set_afk(self, user: discord.abc.Snowflake, reason: Optional[str] = None) -> None:
        query = """
            INSERT INTO afk (user_id, reason)
                VALUES ($1, $2)
            ON CONFLICT (user_id)
                DO UPDATE
            SET reason = $2,
            timestamp = current_timestamp
        """
        await self.bot.pool.execute(query, user.id, reason)
        self.afk_cache.pop(user.id, None)

    async def unset_afk(self, user: discord.abc.Snowflake) -> None:
        query = "DELETE FROM afk WHERE user_id = $1"
        await self.bot.pool.execute(query, user.id)
        self.afk_cache.pop(user.id)

    def _key(self, snowflake: discord.abc.Snowflake) -> int:
        return snowflake.id

    @cachedmethod(lambda self: self.afk_cache, key=_key)
    async def get_afk(self, user: discord.abc.Snowflake) -> Optional[AfkRecord]:
        query = "SELECT * FROM afk WHERE user_id = $1"
        record = await self.bot.pool.fetchrow(query, user.id)

        if record is None:
            return None
        return AfkRecord.from_record(record)

    async def get_mentions(self, user: discord.abc.Snowflake) -> list[AfkMention]:
        query = "SELECT * FROM afk_mentions WHERE user_id = $1"
        records = await self.bot.pool.fetch(query, user.id)

        return [AfkMention.from_record(record) for record in records]

    async def clear_mentions(self, user: discord.abc.Snowflake) -> None:
        query = "DELETE FROM afk_mentions WHERE user_id = $1"
        await self.bot.pool.execute(query, user.id)

    @commands.Cog.listener("on_message")
    async def afk_listener(self, message: discord.Message):
        author = message.author

        ctx = await self.bot.get_context(message)
        if ctx.command or ctx.is_blacklisted() or message.author.bot:
            return

        if afk := await self.get_afk(author):
            await self.unset_afk(author)

            timestamp = discord.utils.format_dt(afk.timestamp, "R")
            embed = PrimaryEmbed()
            embed.description = f"Welcome back, {author.mention}. You were afk since {timestamp}"

            view: Optional[BaseView] = None
            if afk.mentioned:
                embed.description += "\nYou were mentioned while you were afk, check below."
                view = MentionView(self, discord.Object(afk.user_id))

            msg = await message.channel.send(embed=embed, view=view or discord.utils.MISSING)
            if view:
                view.message = msg

        if mentions := message.mentions:
            for user in mentions:
                if user == message.author:
                    continue

                if afk := await self.get_afk(user):
                    await afk.add_mention(
                        self.bot,
                        user.id,
                        message.author.id,
                        (message.guild and message.guild.id),
                        message.channel.id,
                        message.id,
                        bool(message.reference),
                    )

                    timestamp = discord.utils.format_dt(afk.timestamp, "R")
                    embed = PrimaryEmbed(description=f"{user.mention} went afk {timestamp} with reason: `{afk.reason}`")

                    await message.reply(
                        embed=embed, delete_after=30.0, allowed_mentions=discord.AllowedMentions(replied_user=True)
                    )

    @commands.group()
    @describe(reason="The reason for going AFK")
    async def afk(self, ctx: Context, *, reason: str = "AFK"):
        """Sets you ask AFK, anyone pinging you will get notified that you are afk with the reason."""
        await self.set_afk(ctx.author, reason)

        embed = SuccessEmbed(description=f"Sucessfully set {ctx.author.mention} as AFK with reason: `{reason}`")
        await ctx.send(embed=embed)

    @afk.command()
    async def mentions(self, ctx: Context):
        mentions = await self.get_mentions(ctx.author)
        if not mentions:
            raise GenericError("No mentions found")

        await MentionPaginator(self, mentions, ctx.author).start(ctx)
