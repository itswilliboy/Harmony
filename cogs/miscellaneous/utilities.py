from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import discord
from aiohttp import ClientConnectionError, InvalidURL
from discord.ext import commands

from utils import BaseCog, ErrorEmbed, GenericError, SuccessEmbed, argument_or_reference

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class Utilities(BaseCog, hidden=True):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.has_guild_permissions(manage_expressions=True)
    @commands.bot_has_guild_permissions(manage_expressions=True)
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
            try:
                async with self.bot.session.get(emoji) as resp:
                    if not resp.ok:
                        raise GenericError(
                            "Something went wrong when trying to download the image, make sure it exists.", True
                        )

                    if resp.content_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
                        raise GenericError("Unsupported format, must be: `PNG`, `JPEG`, `WEBP`, or `GIF`.")

                    image = await resp.read()

            except InvalidURL:
                raise GenericError("The URL is invalid, make sure it's valid.")

            except ClientConnectionError:
                raise GenericError("Something went wrong when to trying to resolve the URL, make sure it exists.", True)

            parsed = urljoin(emoji, urlparse(emoji).path)
            try:
                name_ = name or parsed.split("/")[-1]
                name_ = Path(name_).stem

            except IndexError:
                raise GenericError(
                    "Needs to be a valid file URL (eg. `https://cdn.discordapp.com/emojis/744346239075877518.gif`)",
                    True,
                )

            try:
                created = await ctx.guild.create_custom_emoji(name=name_, image=image, reason=reason)

                embed = SuccessEmbed(description=f"Successfully added {created} as `{created.name}`")
                return await ctx.send(str(created), embed=embed)

            except discord.HTTPException:
                raise GenericError(
                    "Something went wrong when trying to create the emoji. Make sure the file is less than 256 kB in size.",
                    True,
                )

    @commands.command(usage="<text or message reply>")
    async def raw(
        self,
        ctx: Context,
        *,
        text: str = argument_or_reference,
    ):
        """Displays the raw content of a message (no markdown); can be used by replying to a message."""

        if not text:
            raise commands.MissingRequiredArgument(ctx.command.params["text"])

        escaped = text.replace("```", "``\u200b`")
        await ctx.send(f"```\n{escaped}\n```")

    @commands.command()
    async def tiktok(self, ctx: Context, link: str):
        """Downloads a watermark-free TikTok video via a URL."""
        async with ctx.typing():
            URL = "http://itswilliboy.com/api/tiktok?q="
            async with self.bot.session.get(URL + link) as resp:
                if resp.content_type == "application/json":
                    json = await resp.json()
                    raise GenericError(json["message"])

                buffer = BytesIO(await resp.content.read())

            file = discord.File(fp=buffer, filename="video.mp4")
            await ctx.send("Here is your video:", file=file)
