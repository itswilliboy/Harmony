from __future__ import annotations

import datetime
from traceback import format_exception
from typing import TYPE_CHECKING, Annotated, Callable, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils import BannedMember, BaseCog, ErrorEmbed, GenericError, SuccessEmbed, plural
from utils.autocomplete import ban_entry_autocomplete

if TYPE_CHECKING:
    from utils import Context


class BanFlags(commands.FlagConverter):
    reason: str = commands.flag(description="The reason for the ban.", default="No reason given.")
    days: int = commands.flag(description="The amount of days to delete messages for", default=0)


class ClearFlags(commands.FlagConverter):
    after: Optional[int] = commands.flag(description="The ID of the message to delete messages after", default=None)
    before: Optional[int] = commands.flag(description="The ID of the message to delete messages before", default=None)
    user: Optional[int] = commands.flag(description="The ID of the user to delete messages from", default=None)


class General(BaseCog):
    @commands.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    @commands.guild_only()
    @commands.hybrid_command()
    @app_commands.default_permissions(kick_members=True)
    @app_commands.describe(member="The member to kick", reason="The reason for the kick")
    async def kick(self, ctx: Context, member: discord.Member, *, reason: Optional[str] = None):
        """Kicks a user."""

        assert isinstance(ctx.author, discord.Member)

        if member.id == ctx.guild.owner_id:
            raise GenericError("I can't kick the server owner.")

        elif member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
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
    @commands.hybrid_command()
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(user="The member to ban", reason="The reason for the ban")
    async def ban(self, ctx: Context, user: discord.Member | discord.User, *, flags: BanFlags):
        """Bans a user that is either in the server or not."""

        to_ban: discord.abc.Snowflake
        if isinstance(user, discord.User) and ctx.guild.get_member(user.id) is None:
            to_ban = discord.Object(user.id)

        else:
            assert isinstance(ctx.author, discord.Member) and isinstance(user, discord.Member)

            if user == ctx.guild.owner:
                raise GenericError("I can't ban the server owner.")

            elif user.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
                raise GenericError(f"Your top role needs to be higher than {user.mention}'s top role to ban them.")

            elif ctx.guild.me.top_role <= user.top_role:
                raise GenericError(f"My top role is not high enough to ban {user.mention}.")

            to_ban = user

        reason = flags.reason
        try:
            await ctx.guild.ban(to_ban, reason=reason, delete_message_days=flags.days)
        except discord.HTTPException as exc:
            self.bot.log.error(format_exception(exc), exc_info=exc)
            raise GenericError("Something went wrong when trying to ban, maybe try again?", True) from exc

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
            raise GenericError("Something went wrong when trying to unban that user.") from None

    @app_commands.guild_only()
    @app_commands.command(name="unban")
    @app_commands.autocomplete(user=ban_entry_autocomplete)
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        user="The user to unban, use the autocomplete or input a user id", reason="The reason for the unban"
    )
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def slash_unban(self, interaction: discord.Interaction, user: str, reason: Optional[str] = None):
        """Unbans a banned user."""

        if not user.isnumeric():
            return await interaction.response.send_message(
                embed=ErrorEmbed(description="Please use the autocomplete or input a valid user ID."), ephemeral=True
            )

        assert interaction.guild

        try:
            reason = reason or "No reason given."
            await interaction.guild.unban(discord.Object(user))
            embed = SuccessEmbed(description=f"Sucessfully unbanned <@{user}>.\nReason: `{reason}`")
            await interaction.response.send_message(embed=embed)

        except discord.NotFound:
            await interaction.response.send_message(
                embed=ErrorEmbed(description="Couldn't find that banned user."), ephemeral=True
            )

    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_guild_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.hybrid_command(aliases=["purge"])
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(amount="Amount of messages to clear")
    async def clear(self, ctx: Context, amount: commands.Range[int, 1, 500], *, flags: ClearFlags):
        """Clears up to 500 messages from the current channel."""
        before = None
        after = None
        if flags.before:
            before = discord.Object(flags.before)

        if flags.after:
            after = discord.Object(flags.after)

        check: Optional[Callable[[discord.Message], bool]] = None
        if flags.user:

            def actual_check(message: discord.Message) -> bool:
                return bool(message.author.id == flags.user)

            check = actual_check

        assert not isinstance(ctx.channel, (discord.DMChannel, discord.PartialMessageable, discord.GroupChannel))
        await ctx.channel.purge(
            limit=amount, before=before or ctx.message, after=after, check=check or discord.utils.MISSING
        )

        try:
            await ctx.message.add_reaction("\N{OK HAND SIGN}")
        except Exception:
            pass

    @commands.bot_has_permissions(read_message_history=True)
    @commands.guild_only()
    @commands.hybrid_command()
    @app_commands.describe(amount="Amount of messages to clean up")
    async def cleanup(self, ctx: Context, amount: int = 25):
        """Removes the bot's messages, and command invocations in the current channel."""

        assert isinstance(ctx.author, discord.Member)
        if ctx.channel.permissions_for(ctx.author).is_superset(discord.Permissions(manage_messages=True)):
            limit = min(max(2, amount), 100)

        else:
            limit = min(max(2, amount), 25)

        prefixes = await ctx.bot.get_prefix(ctx.message)

        assert isinstance(ctx.me, discord.Member)
        has_perms = ctx.channel.permissions_for(ctx.me).is_superset(discord.Permissions(manage_messages=True))

        def check(msg: discord.Message) -> bool:
            recent = msg.created_at.replace(tzinfo=None) > datetime.datetime.now() - datetime.timedelta(weeks=2)
            is_bot = msg.author == ctx.bot.user

            if has_perms:
                return is_bot or msg.content.startswith(tuple(prefixes)) and recent

            else:
                return is_bot and recent

        if TYPE_CHECKING:
            assert isinstance(ctx.channel, discord.TextChannel)

        if has_perms:
            deleted = len(await ctx.channel.purge(limit=limit, check=check, before=ctx.message))

        else:
            deleted = 0
            async for message in ctx.channel.history(limit=limit, before=ctx.message):
                if not check(message):
                    continue
                await message.delete()
                deleted += 1

        await ctx.send(f"Deleted **{deleted}** {plural(deleted):message}", delete_after=5.0)

    @commands.has_guild_permissions(ban_members=True, manage_guild=True)
    @commands.bot_has_guild_permissions(ban_members=True, manage_guild=True)
    @commands.guild_only()
    @commands.command(aliases=["mban", "multiban", "bban"])
    async def bulkban(self, ctx: Context, users: commands.Greedy[discord.Object], flags: BanFlags):
        """Bans up to 200 users at the same time, that are either in the server or not."""

        if len(users) > 200:
            raise GenericError("Can only ban up to 200 users at a time.")

        async with ctx.typing():
            reason = flags.reason

            try:
                result = await ctx.guild.bulk_ban(set(users), reason=reason, delete_message_seconds=flags.days * 24 * 3600)

                banned = result.banned
                failed = result.failed
                failed_ids = [str(user.id) for user in failed]

                embed = SuccessEmbed(
                    description=f"Sucessfully banned {len(banned)} users.\nReason: `{reason}`"
                    + f"\nFailed to ban users: `{', '.join(failed_ids)}`"
                    if failed_ids
                    else ""
                )
                embed.timestamp = discord.utils.utcnow()

                await ctx.send(embed=embed)

            except discord.HTTPException as exc:
                raise GenericError("According to Discord, no users were banned (unlikely), check audit logs.") from exc
