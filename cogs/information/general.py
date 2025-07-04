from __future__ import annotations

import datetime
import json
import time
from io import BytesIO
from os import getpid
from sys import version_info
from textwrap import dedent
from typing import TYPE_CHECKING, Any, NamedTuple, Self, cast

import aiohttp
import asyncpg
import discord
import pygit2
from cutlet import Cutlet
from discord.app_commands import describe
from discord.ext import commands
from jishaku.functools import executor_function
from langcodes import Language
from PIL import Image
from psutil import Process, cpu_percent, virtual_memory

from config import JEYY_API, OWNER_IDS
from utils import BaseCog, GenericError, PrimaryEmbed, argument_or_reference

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class AvatarView(discord.ui.View):
    def __init__(self, avatar: discord.Asset) -> None:
        super().__init__(timeout=None)
        for format in ("png", "jpeg", "webp", "gif"):
            if format == "gif" and not avatar.is_animated():
                continue

            button: discord.ui.Button[Self] = discord.ui.Button(
                label=format.upper(), url=avatar.replace(format=format, size=1024).url
            )
            self.add_item(button)


class TranslatorResponse(NamedTuple):
    translated: str
    language: str


class General(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.guild_only()
    @commands.hybrid_command(aliases=["ui", "whois", "info"])
    @describe(member="The member to view")
    async def userinfo(self, ctx: Context, member: discord.Member = commands.Author):
        """Get information about a member in the server."""

        colour = member.colour if str(member.colour) != "#000000" else discord.Colour.dark_embed()
        activity = member.activity and member.activity.name or "N/A"
        created_at = discord.utils.format_dt(member.created_at, "R")

        nick = member.nick or "N/A"
        joined_at = discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "N/A"
        top_role = member.top_role.mention if member.top_role != ctx.guild.default_role else "@everyone"
        role_count = len(member.roles)

        embed = discord.Embed(title=member.global_name or member.name, colour=colour)
        embed.set_author(name="User Information")
        embed.set_thumbnail(url=member.display_avatar.with_format("png").url)

        embed.add_field(name="Username", value=str(member))
        embed.add_field(name=f"User ID {'<:bot:1110964599349579926>' if member.bot else ''}", value=member.id, inline=False)

        # This doesn't work without the presence intent
        """ statuses = {
            discord.Status.online: "<:online:884494020443779122> Online",
            discord.Status.idle: "<:idle:884494020049518623> Idle",
            discord.Status.dnd: "<:dnd:884494020397658152> Do Not Disturb",
            discord.Status.offline: "<:offline:884494020401844325> Offline",
        }

        embed.add_field(name="Status", value=statuses.get(member.status, "N/A"), inline=False) """
        embed.add_field(name="Activity", value=activity, inline=False)
        embed.add_field(name="Created Account", value=created_at)

        embed.add_field(name="__Server Specific__", value="", inline=False)
        embed.add_field(name="Joined Server", value=joined_at, inline=False)
        embed.add_field(name="Nickname", value=nick, inline=False)

        embed.add_field(name="Amount of Roles", value=role_count - 1, inline=True)
        embed.add_field(name="Top Role", value=top_role, inline=True)

        await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["av", "pfp"])
    @describe(user="The user whose avatar to view")
    async def avatar(self, ctx: Context, user: discord.User = commands.Author):
        """Get someone's avatar."""
        view = AvatarView(user.avatar or user.default_avatar)
        embed = PrimaryEmbed(title=f"{user.name}'s Avatar").set_image(url=(user.avatar or user.default_avatar).url)
        embed.set_footer(text=f"See {ctx.prefix}serveravatar for server-avatar")
        await ctx.send(embed=embed, view=view)

    @commands.guild_only()
    @commands.hybrid_command(aliases=["aav", "spfp"])
    @describe(member="The user whose avatar to view")
    async def serveravatar(self, ctx: Context, member: discord.Member = commands.Author):
        """Get someone's server-avatar."""
        view = AvatarView(member.guild_avatar or member.display_avatar)
        embed = PrimaryEmbed(title=f"{member.name}'s Server Avatar").set_image(
            url=(member.guild_avatar or member.display_avatar).url
        )
        embed.set_footer(text=f"See {ctx.prefix}avatar for global-avatar")
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command()
    @describe(user="The user whose banner to view")
    async def banner(self, ctx: Context, user: discord.User = commands.Author):
        """Get someone's banner"""
        try:
            fetched = await self.bot.fetch_user(user.id)

        except discord.NotFound:
            raise commands.BadArgument("Couldn't find that user") from None

        if fetched.banner is None:
            raise GenericError(f"{user.mention} doesn't have a banner.")

        view = AvatarView(fetched.banner)
        embed = PrimaryEmbed(title=f"{user.name}'s Banner").set_image(url=fetched.banner.url)
        embed.set_footer(text=f"See {ctx.prefix}serverbanner for server-banner")
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(aliases=["sbanner"])
    @describe(user="The user whose banner to view")
    async def serverbanner(self, ctx: Context, user: discord.User = commands.Author):
        """Get someone's server-banner"""
        try:
            fetched = await ctx.guild.fetch_member(user.id)

        except discord.NotFound:
            raise commands.BadArgument("Couldn't find that user") from None

        if not any((fetched.banner, fetched.guild_banner)):
            raise GenericError(f"{user.mention} doesn't have a banner.")

        banner = fetched.guild_banner or fetched.display_banner
        assert banner
        view = AvatarView(banner)
        embed = PrimaryEmbed(title=f"{user.name}'s Server Banner").set_image(url=banner.url)
        embed.set_footer(text=f"See {ctx.prefix}banner for global-banner")
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command()
    async def icon(self, ctx: Context):
        """Get the server's icon."""
        if ctx.guild.icon is None:
            raise GenericError("This server doesn't have an icon")

        view = AvatarView(ctx.guild.icon)
        embed = PrimaryEmbed(title=f"{ctx.guild.name}'s Icon").set_image(url=ctx.guild.icon.url)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command()
    async def invite(self, ctx: Context):
        """Invite the bot."""
        permissions = discord.Permissions(10170482945222)
        invite = discord.utils.oauth_url(
            client_id=self.bot.user.id,
            permissions=permissions,
            scopes=("bot", "applications.commands"),
        )

        view = discord.ui.View().add_item(discord.ui.Button(label="Invite Me!", url=invite))
        await ctx.send(
            embed=PrimaryEmbed(
                title="Thanks for inviting me!",
                description=f"You can invite me using the button below or by pressing [here]({invite}).",
            ).set_thumbnail(url=self.bot.user.display_avatar.url),
            view=view,
        )

    @commands.hybrid_command()
    async def support(self, ctx: Context):
        """Join our support server."""
        invite = "https://discord.gg/P22UdJUdHk"

        view = discord.ui.View().add_item(discord.ui.Button(label="Join our Support Server!", url=invite))
        await ctx.send(
            embed=PrimaryEmbed(
                title="Join our support server!",
                description=f"You can join our server using the button below or by pressing [here]({invite}).",
            ).set_thumbnail(url=self.bot.user.display_avatar.url),
            view=view,
        )

    @commands.command(aliases=["latency"])
    async def ping(self, ctx: Context):
        """Displays the latencies of various services used by the bot."""

        def get_color(ping: int) -> str:
            if ping <= 500:
                return f"```diff\n+ {ping} ms\n```"
            else:
                return f"```diff\n- {ping} ms\n```"

        start = time.perf_counter()
        await ctx.pool.fetch("SELECT 1")
        end = time.perf_counter()
        db_latency = int((end - start) * 1000)

        latency = int(self.bot.latency * 1000)
        embed = PrimaryEmbed(title="Latency")
        embed.add_field(name="Discord Gateway Latency", value=get_color(latency), inline=False)
        embed.add_field(name="Bot Response Time", value="```Calculating...```", inline=False)
        embed.add_field(name="Database Latency", value=get_color(db_latency), inline=False)

        start = time.perf_counter()
        msg = await ctx.send(embed=embed)
        end = time.perf_counter()
        resp_time = int((end - start) * 1000)
        embed.set_field_at(1, name="Bot Response Time", value=get_color(resp_time))
        await msg.edit(embed=embed)

    @commands.command()
    async def uptime(self, ctx: Context):
        await ctx.send(discord.utils.format_dt(self.bot.started_at, "R"))

    def format(self, commit: pygit2.Commit) -> str:
        msg, *_ = commit.message.partition("\n")
        time = datetime.datetime.fromtimestamp(commit.commit_time)

        timestamp = discord.utils.format_dt(time, "R")
        partial, full = commit.short_id, commit.id
        return f"[`{partial}`](<https://github.com/itswilliboy/Harmony/commit/{full}>) {timestamp} | {msg}"

    def get_latest_commits(self, limit: int = 3) -> list[str]:
        repo = pygit2.Repository(".git")
        commits = list(repo.walk(repo.head.target))[:limit]

        return [self.format(commit) for commit in commits]

    @commands.hybrid_command(aliases=["bot", "about", "abt"])
    async def botinfo(self, ctx: Context):
        """Displays information about the bot."""

        embed = PrimaryEmbed(title="Bot Information")
        embed.set_footer(text=f"Check out `{ctx.clean_prefix}ping` for more latency information.")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        if user := self.bot.get_user(OWNER_IDS[0]):
            embed.set_author(name=f"@{user.name}", icon_url=user.display_avatar.url)

        app = await self.bot.application_info()
        embed.add_field(name="Started", value=discord.utils.format_dt(self.bot.started_at, "R"))
        embed.add_field(
            name="Installs", value=f"{len(self.bot.guilds)} servers\n╰ {app.approximate_user_install_count} individual users"
        )

        embed.add_field(name="Latest Changes", value="\n".join(self.get_latest_commits(5)), inline=False)

        process = Process(getpid())
        cpu = cpu_percent()
        server_ram = virtual_memory().used
        process_ram = process.memory_info().rss

        def formatted(bytes: int) -> str:
            def to_mebibytes(bytes_: int) -> int:
                return int(bytes_ / (1 << 20))

            return f"{to_mebibytes(bytes):,}"

        value = f"""
            `CPU (Server) `: {cpu:1}%
            `RAM (Server) `: {formatted(server_ram)} MiB
            `RAM (Process)`: {formatted(process_ram)} MiB
        """
        embed.add_field(name="Process Information", value=dedent(value), inline=False)

        command_runs: int = await ctx.pool.fetchval("SELECT SUM(count) FROM command_statistics")
        embed.add_field(name="Commands Ran", value=f"{command_runs or 0:,}")

        version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
        value = f"""
            `CPython   `: v{version}
            `discord.py`: v{discord.__version__}
            `aiohttp   `: v{aiohttp.__version__}
            `asyncpg   `: v{asyncpg.__version__}
        """
        embed.add_field(name="Version Information", value=dedent(value), inline=False)
        embed.add_field(
            name="Privacy Policy & Terms of Service",
            value=(
                "**[Privacy Policy](https://itswilli.dev/bot/privacy)**\n"
                "**[Terms of Service](https://itswilli.dev/bot/terms)**"
            ),
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @describe(text="The text to translate")
    async def translate(
        self,
        ctx: Context,
        *,
        text: str = argument_or_reference,
    ):
        """Translate a piece of text into English via Google Translate."""

        if not text:
            raise commands.MissingRequiredArgument(ctx.command.params["text"])

        await ctx.typing()

        query_ = {"client": "dict-chrome-ex", "sl": "auto", "tl": "en", "q": text}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"  # noqa: E501
        }

        async with ctx.session.get("https://clients5.google.com/translate_a/t", params=query_, headers=headers) as resp:
            json: list[Any] = (await resp.json())[0]
            data = TranslatorResponse(json[0], json[1])

        language = Language.make(data.language)

        embed = PrimaryEmbed(title="Translation")
        embed.add_field(
            name=f"Original Text ({language.display_name().title()} | {language.display_name(data.language).title()})",
            value=text,
        )
        embed.add_field(name="Translated Text", value=data.translated, inline=False)

        if data.language == "ja":
            cutlet = Cutlet()
            embed.insert_field_at(1, name="Romaji", value=cutlet.romaji(text), inline=False)

        await ctx.send(embed=embed)

    @executor_function
    def get_image_colour(self, buffer: BytesIO) -> discord.Colour:
        """Gets the colour of the image by reading a specific pixel."""

        with Image.open(buffer) as image:
            pixels = image.load()
            colour = cast(tuple[int, int], pixels[255, 0])
            colour = list(colour)
            del colour[3]  # Delete the alpha value

        buffer.seek(0)
        return discord.Colour.from_rgb(*colour)

    # Doesn't work without presence intent
    @commands.command(hidden=True)
    async def spotify(self, ctx: Context, user: discord.Member = commands.Author):
        """Shows the current Spotify status of a user."""

        spotify = discord.utils.find(lambda a: isinstance(a, discord.Spotify), user.activities)
        if spotify is None:
            raise GenericError(f"{user.mention} isn't currently listening to anything on Spotify.")

        assert isinstance(spotify, discord.Spotify)
        params = {
            "title": spotify.title,
            "cover_url": spotify.album_cover_url,
            "duration_seconds": spotify.duration.seconds,
            "start_timestamp": int((spotify.created_at or discord.utils.utcnow()).timestamp()),
            "artists": spotify.artists,
        }
        headers = {"Authorization": f"Bearer {JEYY_API}"}

        await ctx.typing()

        params = json.dumps(params)
        async with ctx.session.get("https://api.jeyy.xyz/v2/discord/spotify", params=params, headers=headers) as resp:
            buffer = BytesIO(await resp.read())

        colour = await self.get_image_colour(buffer)
        file = discord.File(buffer, "spotify.png")
        embed = discord.Embed(colour=colour)
        embed.set_image(url="attachment://spotify.png")
        await ctx.send(embed=embed, file=file)

    @commands.command()
    async def hello(self, ctx: Context):
        """Says hello!"""
        await ctx.send("Hello!")
