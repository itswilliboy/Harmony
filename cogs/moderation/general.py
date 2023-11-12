from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utils import BaseCog, GenericError, SuccessEmbed

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class BannedMember(commands.Converter):
    async def convert(self, ctx: Context, argument: str):
        if argument.isdigit():
            id = int(argument)

            try:
                return await ctx.guild.fetch_ban(discord.Object(id))

            except discord.NotFound:
                raise commands.BadArgument("That member is not banned.")

        user = await discord.utils.find(lambda u: str(u.user) == argument, ctx.guild.bans(limit=None))
        if user is None:
            raise commands.BadArgument("That member is not banned.")
        return user


class General(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot

    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    @commands.guild_only()
    @commands.command()
    async def ban(self, ctx: Context, member: discord.Member | int, *, reason: str | None = None):
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
    async def unban(self, ctx: Context, user: discord.BanEntry | BannedMember, *, reason: str | None = None):
        try:
            to_unban: discord.abc.Snowflake
            if isinstance(user, discord.BanEntry):
                to_unban = user.user
            else:
                to_unban = user  # type: ignore

            reason = reason or "No reason given."
            await ctx.guild.unban(to_unban, reason=reason)
            embed = SuccessEmbed(description=f"Sucessfully unbanned <@{to_unban.id}>.\nReason: `{reason}`")
            await ctx.send(embed=embed)

        except discord.HTTPException:
            GenericError("Something went wrong when trying to unban that user.")

    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_guild_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command(aliases=["purge"])
    async def clear(self, ctx: Context, amount: commands.Range[int, 1, 250]):
        assert not isinstance(ctx.channel, (discord.DMChannel, discord.PartialMessageable, discord.GroupChannel))
        await ctx.channel.purge(limit=amount, before=ctx.message)
        await ctx.message.add_reaction("\N{OK HAND SIGN}")
