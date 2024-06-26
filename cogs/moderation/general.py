from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Annotated, Optional

import discord
from discord.ext import commands

from utils import BannedMember, BaseCog, GenericError, PrimaryEmbed, SuccessEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class General(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        bot.loop.create_task(self.init_dict())

        self.snipes: dict[int, dict[int, tuple[Optional[discord.Message], Optional[datetime.datetime]]]]

    async def init_dict(self) -> None:
        await self.bot.wait_until_ready()

        self.snipes = {}
        for guild in self.bot.guilds:
            self.snipes[guild.id] = {}

            for channel in guild.channels:
                self.snipes[guild.id].update({channel.id: (None, None)})

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        guild = message.guild
        channel = message.channel

        assert guild, channel

        self.snipes[guild.id][channel.id] = (message, datetime.datetime.now())

    @commands.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def kick(self, ctx: Context, member: discord.Member, *, reason: Optional[str] = None):
        """Kicks a user."""

        assert isinstance(ctx.author, discord.Member)

        if member == ctx.guild.owner:
            raise GenericError("I can't kick the server owner.")

        elif member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            raise GenericError(f"Your top role needs to be higher than {member.mention}'s top role to kick them.")

        elif ctx.guild.me.top_role <= member.top_role:
            raise GenericError(f"My top role is not high enough to kick {member.mention}.")

        reason = reason or "No reason given."
        await ctx.guild.kick(member, reason=reason)
        embed = SuccessEmbed(description=f"Sucessfully kicked {member.mention}.\nReason: `{reason}`")
        embed.set_footer(text=f"ID: {member.id}").timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed)

    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    @commands.guild_only()
    @commands.command()
    async def ban(self, ctx: Context, member: discord.Member | int, *, reason: Optional[str] = None):
        """Bans a user that is either in the server or not."""
        to_ban: discord.abc.Snowflake
        if isinstance(member, int) and ctx.guild.get_member(member) is None:
            to_ban = discord.Object(member)

        else:
            assert isinstance(ctx.author, discord.Member) and isinstance(member, discord.Member)

            if member == ctx.guild.owner:
                raise GenericError("I can't ban the server owner.")

            elif member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
                raise GenericError(f"Your top role needs to be higher than {member.mention}'s top role to ban them.")

            elif ctx.guild.me.top_role <= member.top_role:
                raise GenericError(f"My top role is not high enough to ban {member.mention}.")

            to_ban = member

        reason = reason or "No reason given."
        await ctx.guild.ban(to_ban, reason=reason)
        embed = SuccessEmbed(description=f"Sucessfully banned <@{to_ban.id}>.\nReason: `{reason}`")
        embed.set_footer(text=f"ID: {to_ban.id}").timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed)

    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    @commands.guild_only()
    @commands.command()
    async def unban(
        self,
        ctx: Context,
        user: Annotated[discord.abc.Snowflake, discord.BanEntry | BannedMember],
        *,
        reason: Optional[str] = None,
    ):
        """Unbans a banned user."""
        try:
            to_unban: discord.abc.Snowflake
            if isinstance(user, discord.BanEntry):
                to_unban = user.user
            else:
                to_unban = user

            reason = reason or "No reason given."
            await ctx.guild.unban(to_unban, reason=reason)
            embed = SuccessEmbed(description=f"Sucessfully unbanned <@{to_unban.id}>.\nReason: `{reason}`")
            await ctx.send(embed=embed)

        except discord.HTTPException:
            raise GenericError("Something went wrong when trying to unban that user.")

    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_guild_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command(aliases=["purge"])
    async def clear(self, ctx: Context, amount: commands.Range[int, 1, 500]):
        """Clears up to 500 messages from the current channel."""
        assert not isinstance(ctx.channel, (discord.DMChannel, discord.PartialMessageable, discord.GroupChannel))
        await ctx.channel.purge(limit=amount, before=ctx.message)

        try:
            await ctx.message.add_reaction("\N{OK HAND SIGN}")
        except Exception:
            pass

    @commands.guild_only()
    @commands.command()
    async def snipe(self, ctx: Context):
        """Views (snipes) the most recently deleted message in the current channel."""
        exists = await ctx.pool.fetchval("SELECT EXISTS(SELECT 1 FROM snipe_optout WHERE user_id = $1)", ctx.author.id)
        if exists is True:
            raise GenericError("You are opted out from snipes.")

        snipe = self.snipes[ctx.guild.id].get(ctx.channel.id)

        assert snipe
        if snipe[0] is None:
            raise GenericError("No sniped messages in this channel.")

        message, timestamp = snipe
        assert message, timestamp

        embed = PrimaryEmbed(description=message.content or "*No Content*", timestamp=timestamp)
        embed.set_author(name=message.author, icon_url=message.author.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.command()
    async def snipe_opt_out(self, ctx: Context):
        """Toggles opt-out from snipes."""
        exists = await ctx.pool.fetchval("SELECT EXISTS(SELECT 1 FROM snipe_optout WHERE user_id = $1)", ctx.author.id)

        if exists is True:
            await ctx.pool.execute("DELETE FROM snipe_optout WHERE user_id = $1", ctx.author.id)
            await ctx.send("Successfully opted you in.")

        else:
            await ctx.pool.execute("INSERT INTO snipe_optout VALUES ($1)", ctx.author.id)
            await ctx.send("Successfully opted you out.")

    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    @commands.guild_only()
    @commands.command()
    async def cleanup(self, ctx: Context, amount: int = 25):
        """Removes the bot's messages, and command invocations in the current channel."""

        assert isinstance(ctx.author, discord.Member)
        if ctx.channel.permissions_for(ctx.author).is_superset(discord.Permissions(manage_messages=True)):
            limit = min(max(2, amount), 250)

        else:
            limit = min(max(2, amount), 25)

        prefixes = await ctx.bot.get_prefix(ctx.message)

        def check(msg: discord.Message) -> bool:
            # fmt: off
            return (msg.author == ctx.bot.user or msg.content.startswith(tuple(prefixes))) \
                and msg.created_at.replace(tzinfo=None) > datetime.datetime.now() - datetime.timedelta(weeks=2)
            # fmt: on

        if TYPE_CHECKING:
            assert isinstance(ctx.channel, discord.TextChannel)

        deleted = await ctx.channel.purge(limit=limit, check=check, before=ctx.message)
        await ctx.send(f"Deleted **{len(deleted)}** messages", delete_after=5)
