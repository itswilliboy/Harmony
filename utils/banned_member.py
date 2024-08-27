"""
This file was sourced from [RoboDanny](https://github.com/Rapptz/RoboDanny).
"""

from typing import Any

import discord
from discord.ext import commands

from .context import Context

__all__ = ("BannedMember",)

class BannedMember(commands.Converter[Any]):
    async def convert(self, ctx: Context, argument: str) -> discord.BanEntry:
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
