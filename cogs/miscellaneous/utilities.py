from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from aiohttp import InvalidURL
from pathlib import Path

from utils import ErrorEmbed, SuccessEmbed
from utils.cog import BaseCog

if TYPE_CHECKING:
    from bot import Harmony
    from utils.context import Context


class Utilities(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot

    @commands.has_guild_permissions(manage_emojis=True)
    @commands.bot_has_guild_permissions(manage_emojis=True)
    @commands.command(aliases=["steal", "stealemoji"])
    async def addemoji(self, ctx: Context, emoji: discord.PartialEmoji | str, name: str | None = None):
        """Add an emoji via an image URL or steal one from another server :^)"""
        if name and len(name) < 2:
            return await ctx.send(embed=ErrorEmbed(description="The emoji name needs to be at least 2 characters long."))

        reason = f"Added with `addemoji` command by {ctx.author}"

        if isinstance(emoji, discord.PartialEmoji):
            name_ = name or emoji.name
            created = await ctx.guild.create_custom_emoji(name=name_, image=await emoji.read(), reason=reason)

            embed = SuccessEmbed(description=f"Successfully added {created} as `{created.name}`")
            return await ctx.send(str(created), embed=embed)

        else:
            if not emoji.endswith((".png", ".jpg", ".jpeg", ".gif")):
                embed = ErrorEmbed(description="ONLY `JPEG`, `PNG` and `GIF` file formats are supported.")
                await ctx.send(embed=embed)
            
            try:
                async with self.bot.session.get(emoji) as resp:
                    if not resp.ok:
                        embed = ErrorEmbed(
                            description="Something went wrong when trying to download the image, please make sure it exists."
                        )
                        return await ctx.send(embed=embed)

                    image = await resp.read()
            
            except InvalidURL:
                embed = ErrorEmbed(description="The URL is invalid, make sure it's valid.")
                return await ctx.send(embed=embed)

            split = emoji.split("/")
            try:
                name_ = name or split[-1]
                name_ = Path(name_).stem

            except IndexError:
                embed = ErrorEmbed(description="Needs to be a valid file URL (eg. `https://cdn.discordapp.com/emojis/884506546787188826.png`)")
                return await ctx.send(embed=embed)

            try:
                created = await ctx.guild.create_custom_emoji(name=name_, image=image, reason=reason)

                embed = SuccessEmbed(description=f"Successfully added {created} as `{created.name}`")
                return await ctx.send(str(created), embed=embed)

            except discord.HTTPException:
                embed = ErrorEmbed(
                    description="""
                    Something went wrong when trying to create the emoji.
                    Make sure the file is less than 256 kB in size.
                    """
                )
                await ctx.send(embed=embed)
