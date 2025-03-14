from __future__ import annotations

from inspect import getsourcefile, getsourcelines
from os import path
from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast
from urllib.parse import urljoin, urlparse

import discord
from aiohttp import ClientConnectionError, InvalidURL
from discord.app_commands import describe
from discord.ext import commands

from utils import BaseCog, ErrorEmbed, GenericError, SuccessEmbed, argument_or_reference

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class Utilities(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.command(aliases=["steal", "stealemoji"])
    async def addemoji(
        self, ctx: Context, emoji: discord.PartialEmoji | str, name: Optional[str] = None, server_id: Optional[int] = None
    ):
        """Add an emoji via an image URL or steal one from another server :^)"""
        if name and len(name) < 2:
            return await ctx.send(embed=ErrorEmbed(description="The emoji name needs to be at least 2 characters long."))

        reason = f"Added with `addemoji` command by {ctx.author}"

        guild = self.bot.get_guild(server_id) if server_id else None
        if guild is None:
            guild = ctx.guild
            author = ctx.author

        else:
            author = guild.get_member(ctx.author.id)

        perm = discord.Permissions(manage_expressions=True)

        if guild != ctx.guild and ctx.author not in guild.members:
            raise GenericError("You aren't in that server.")

        if not author.guild_permissions.is_superset(perm):  # type: ignore
            raise commands.MissingPermissions(missing_permissions=["Manage Expressions"])

        if not guild.me.guild_permissions.is_superset(perm):
            raise commands.BotMissingPermissions(missing_permissions=["Manage Expressions"])

        if isinstance(emoji, discord.PartialEmoji):
            name_ = name or emoji.name
            created = await guild.create_custom_emoji(name=name_, image=await emoji.read(), reason=reason)

            embed = SuccessEmbed(description=f"Successfully added {created} as `{created.name}`")
            embed.set_footer(text=f"Server: {guild}")
            return await ctx.send(str(created), embed=embed)

        try:
            async with ctx.session.get(emoji) as resp:
                if not resp.ok:
                    raise GenericError("Something went wrong when trying to download the image, make sure it exists.", True)

                if resp.content_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
                    raise GenericError("Unsupported format, must be: `PNG`, `JPEG`, `WEBP`, or `GIF`.")

                image = await resp.read()

        except InvalidURL:
            raise GenericError("The URL is invalid, make sure it's valid.") from None

        except ClientConnectionError:
            raise GenericError(
                "Something went wrong when to trying to resolve the URL, make sure it exists.", True
            ) from None

        parsed = urljoin(emoji, urlparse(emoji).path)
        try:
            name_ = name or parsed.split("/")[-1]
            name_ = Path(name_).stem

        except IndexError:
            raise GenericError(
                "Needs to be a valid file URL (eg. `https://cdn.discordapp.com/emojis/744346239075877518.gif`)",
                True,
            ) from None

        try:
            created = await guild.create_custom_emoji(name=name_, image=image, reason=reason)

            embed = SuccessEmbed(description=f"Successfully added {created} as `{created.name}`")
            embed.set_footer(text=f"Server: {guild}")
            return await ctx.send(str(created), embed=embed)

        except discord.HTTPException:
            raise GenericError(
                "Something went wrong when trying to create the emoji. Make sure the file is less than 256 kB in size.",
                True,
            ) from None

    @commands.hybrid_command()
    @describe(text="The text to view raw")
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

    # Some code from https://github.com/Rapptz/RoboDanny
    @describe(command="Command to view source for")
    @commands.hybrid_command(aliases=["src"])
    async def source(self, ctx: Context, *, command: Optional[str] = None):
        """Gets the source code of a specific command."""

        REPO_URL = "https://github.com/itswilliboy/Harmony"
        BRANCH = "master"

        if command is None:
            return await ctx.send(REPO_URL)

        if command == "help":
            source = type(self.bot.help_command)
            module = source.__module__
            file = getsourcefile(source)
            file = cast("str", file)

        else:
            cmd = self.bot.get_command(command)
            if cmd is None:
                raise GenericError("Couldn't find that command.")

            source = cmd.callback.__code__
            file = source.co_filename
            module = cmd.callback.__module__

        if not module.startswith("cogs"):
            raise GenericError("Coulnd't find the source for that command.")

        lines, first = getsourcelines(source)
        loc = path.relpath(file).replace("\\", "/")

        url = f"<{REPO_URL}/blob/{BRANCH}/{loc}#L{first}-L{first + len(lines) - 1}>"
        await ctx.send(url)
