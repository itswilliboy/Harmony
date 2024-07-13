from __future__ import annotations

import asyncio
import datetime
import re
from typing import Annotated, Any, Optional

import discord
from discord.app_commands import describe
from discord.ext import commands
from jwt import decode

from bot import Harmony
from utils import (
    BaseCog,
    Context,
    GenericError,
    PrimaryEmbed,
    SuccessEmbed,
    progress_bar,
)

from .anime import MinifiedMedia
from .client import AniListClient
from .media_list import MediaList
from .oauth import User
from .types import FavouriteTypes, MediaType
from .views import PIXEL_LINE_URL, Delete, LoginView, RelationView

ANIME_REGEX = re.compile(r"\{\{(.*?)\}\}")
MANGA_REGEX = re.compile(r"\[\[(.*?)\]\]")
INLINE_CB_REGEX = re.compile(r"(?P<CB>(`{1,2})[^`^\n]+?\2)(?:$|[^`])")
CB_REGEX = re.compile(r"```[\S\s]+?```")
HL_REGEX = re.compile(r"\[.*?\]\(.*?\)")


def add_favourite(embed: discord.Embed, *, user: User, type: FavouriteTypes, maxlen: int = 1024, empty: bool = False):
    favourites = discord.utils.find(lambda f: f["_type"] == type, user.favourites)

    if favourites and favourites["items"]:
        value = ""
        for favourite in favourites["items"][:5]:
            fmt = f"\n- **[{favourite.name}]({favourite.site_url})**"
            if len(value + fmt) > maxlen:
                break
            value += fmt
    elif empty:
        value = "No Favourites Found..."
    else:
        return

    embed.add_field(name=f"Favourite {type.title()}", value=value, inline=False)


class AniUser(commands.UserConverter):
    async def convert(self, ctx: Context, argument: str) -> Optional[str | int]:
        try:
            user = await super().convert(ctx, argument)

            if jwt := await ctx.pool.fetchval("SELECT token FROM anilist_tokens WHERE user_id = $1", user.id):
                uid = decode(jwt, options={"verify_signature": False})["sub"]
                return int(uid)

        except commands.BadArgument:
            pass

        return argument


class AniList(BaseCog, name="Anime"):
    def __init__(
        self,
        bot: Harmony,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(bot, *args, **kwargs)

        self.client = AniListClient(bot)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if await self.bot.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM inline_search_optout WHERE user_id = $1)", message.author.id
        ):
            return

        content = message.content

        for match in reversed(list(INLINE_CB_REGEX.finditer(content))):
            start, end = match.span("CB")
            content = content[:start] + content[end:]

        content = CB_REGEX.sub(" ", content)
        content = HL_REGEX.sub(" ", content)

        anime = list(set(ANIME_REGEX.findall(content)))
        manga = list(set(MANGA_REGEX.findall(content)))

        if not anime and not manga:
            return

        found: list[MinifiedMedia] = []

        async with message.channel.typing():
            embed = PrimaryEmbed()

            for name in anime:
                media = await self.client.search_minified_media(name, type=MediaType.ANIME)
                if media and media not in found:
                    found.append(media)
                    embed.add_field(name=f"**__{media.name}__**", value=media.small_info, inline=False)

            for name in manga:
                media = await self.client.search_minified_media(name, type=MediaType.MANGA)
                if media and media not in found:
                    found.append(media)
                    embed.add_field(name=f"**__{media.name}__**", value=media.small_info, inline=False)

        if not embed.fields:
            try:
                await message.add_reaction("\N{BLACK QUESTION MARK ORNAMENT}")
                await asyncio.sleep(3)
                await message.remove_reaction("\N{BLACK QUESTION MARK ORNAMENT}", self.bot.user)
            except discord.HTTPException:
                pass
            return

        prefixes = await self.bot.get_prefix(message)
        prefix = next(iter(sorted(prefixes, key=len)), "ht;")

        embed.set_footer(text=f'{{{{anime}}}} \N{EM DASH} [[manga]] \N{EM DASH} Run "{prefix}optout" to disable this.')

        if len(embed.fields) == 1:
            media = found[0]
            embed.set_thumbnail(url=media.cover["extraLarge"])

            if media.cover["color"]:
                embed.color = discord.Colour.from_str(media.cover["color"])

        await message.channel.send(embed=embed, view=Delete.view(message.author))

    async def search(
        self,
        ctx: Context,
        search: str,
        search_type: MediaType,
    ) -> None:
        assert not isinstance(ctx.channel, discord.PartialMessageable | discord.GroupChannel)

        media, user = await self.client.search_media(
            search,
            type=search_type,
            user_id=ctx.author.id,
        )

        if media is None:
            raise GenericError(f"Couldn't find any {search_type.value.lower()} with that name.")

        if media.is_adult and not (
            isinstance(
                ctx.channel,
                discord.DMChannel,
            )
            or ctx.channel.is_nsfw()
        ):
            raise GenericError(
                (
                    f"This {search_type.value.lower()} was flagged as NSFW. "
                    "Please try searching in an NSFW channel or in my DMs."
                )
            )

        view = discord.utils.MISSING

        if media.relations:
            view = RelationView(self, media, user, ctx.author.id)

        embeds: list[discord.Embed] = []

        if not media.embed.image:
            em = media.embed.copy()
            em.set_image(url=PIXEL_LINE_URL)
            embeds.append(em)

        else:
            embeds.append(media.embed)

        if em := media.list_embed:
            em.set_image(url=PIXEL_LINE_URL)
            em.set_thumbnail(url=ctx.author.display_avatar.url)
            embeds.append(em)

        if em := media.following_status_embed(user):
            em.set_image(url=PIXEL_LINE_URL)
            embeds.append(em)

        await ctx.send(embeds=embeds, view=view)

    async def get_user(self, ctx: Context, user: Optional[str | int] = None) -> User:
        if user is None:
            token = await self.client.get_token(ctx.author.id)
            if token is None:
                cp = ctx.clean_prefix
                raise commands.BadArgument(
                    message=f"You need to pass an AniList username or log in with {cp}anilist login to view yourself."
                )
            elif token.expiry < datetime.datetime.now():
                raise GenericError(
                    f"Your token has expired, create a new one with {ctx.clean_prefix}anilist login.",
                )

            return await self.client.oauth.get_current_user(token.token)
        else:
            if isinstance(user, str) and user.isnumeric():
                user = int(user)
            user_ = await self.client.oauth.get_user(user)

            if user_ is None:
                raise GenericError("Couldn't find any user with that name.")

            return user_

    @commands.hybrid_command(hidden=True)
    async def optout(self, ctx: Context):
        """Opts you out (or back in) of inline search."""
        if await ctx.pool.fetchval("SELECT EXISTS(SELECT 1 FROM inline_search_optout WHERE user_id = $1)", ctx.author.id):
            await ctx.pool.execute("DELETE FROM inline_search_optout WHERE user_id = $1", ctx.author.id)
            await ctx.send("Opted back into inline search.")
        else:
            await ctx.pool.execute("INSERT INTO inline_search_optout (user_id) VALUES ($1)", ctx.author.id)
            await ctx.send("Opted out of inline search.")

    @commands.hybrid_command()
    @describe(search="The anime to search for")
    async def anime(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific anime."""
        await self.search(ctx, search, MediaType.ANIME)

    @commands.hybrid_command()
    @describe(search="The manga to search for")
    async def manga(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific manga."""
        await self.search(ctx, search, MediaType.MANGA)

    @commands.hybrid_group(invoke_without_command=True)
    async def anilist(self, ctx: Context):
        await ctx.send_help(ctx.command)

    @anilist.command()
    @describe(user="AniList username")
    async def profile(self, ctx: Context, user: Annotated[Optional[str | int], AniUser] = None):
        """View someone's AniList profile."""
        user_ = await self.get_user(ctx, user)

        embed = PrimaryEmbed(
            title=user_.name,
            url=user_.url,
            description=user_.about + "\n\u200b" if user_.about else "",
        )

        embed.set_footer(text="Account Created")
        embed.timestamp = user_.created_at

        if url := user_.banner_url:
            embed.set_image(url=url)

        if url := user_.avatar_url:
            embed.set_thumbnail(url=url)

        if user_.anime_stats.episodes_watched:
            s = user_.anime_stats
            embed.add_field(
                name="Anime Statistics",
                value=(
                    f"Anime Watched: **`{s.count:,}`**\n"
                    f"Episodes Watched: **`{s.episodes_watched:,}`**\n"
                    f"Hours Watched: **`{(s.minutes_watched / 60):.1f}` (`{(s.minutes_watched / 1440):.1f} days`)**"
                ),
                inline=True,
            )

            if s.mean_score:
                embed.add_field(
                    name="Average Anime Score",
                    value=f"**{s.mean_score} // 100**\n{progress_bar(s.mean_score)}",
                    inline=True,
                )

        if user_.manga_stats.chapters_read:
            add_favourite(embed, user=user_, type=FavouriteTypes.ANIME, empty=True)

            s = user_.manga_stats
            embed.add_field(
                name="Manga Statistics",
                value=(
                    f"Manga Read: **`{s.count:,}`**\n"
                    f"Volumes Read: **`{s.volumes_read:,}`**\n"
                    f"Chapters Read: **`{s.chapters_read:,}`**"
                ),
                inline=True,
            )

            if s.mean_score:
                embed.add_field(
                    name="Average Manga Score",
                    value=f"**{s.mean_score} // 100**\n{progress_bar(s.mean_score)}",
                    inline=True,
                )

        else:
            add_favourite(embed, user=user_, type=FavouriteTypes.ANIME)

        add_favourite(embed, user=user_, type=FavouriteTypes.MANGA)
        add_favourite(embed, user=user_, type=FavouriteTypes.CHARACTERS)
        add_favourite(embed, user=user_, type=FavouriteTypes.STAFF)
        add_favourite(embed, user=user_, type=FavouriteTypes.STUDIOS)

        await ctx.send(embed=embed)

    @describe(user="AniList username")
    @anilist.command()
    async def list(self, ctx: Context, user: Annotated[Optional[str | int], AniUser] = None):
        """View someone's anime list on AniList."""
        user_ = await self.get_user(ctx, user)

        async with ctx.typing():
            ml = MediaList(
                self.client, await self.client.fetch_media_collection(user_.id, MediaType.ANIME), user_.id, ctx.author.id
            )
            await ml.start(ctx)

    @anilist.command(aliases=["auth"])
    async def login(self, ctx: Context):
        """Log in with an AniList account."""
        query = "SELECT expiry FROM anilist_tokens WHERE user_id = $1"
        expiry: Optional[datetime.datetime] = await self.bot.pool.fetchval(
            query,
            ctx.author.id,
        )

        if expiry and expiry > datetime.datetime.now():
            embed = SuccessEmbed(description="You are already logged in. Log out and back in to renew the session.")
            embed.set_footer(text=f"Run `{ctx.clean_prefix}anilist logout` to log out.")
            return await ctx.send(embed=embed)

        embed = PrimaryEmbed(
            title="Authorise with Anilist",
            description="Copy the code from the link below, and then press the green button for the next step.",
        )

        await ctx.send(
            embed=embed,
            view=LoginView(ctx.bot, ctx.author, self.client),
        )

    @anilist.command()
    async def logout(self, ctx: Context):
        """Logs you out."""
        query = "SELECT EXISTS(SELECT 1 FROM anilist_tokens WHERE user_id = $1)"
        exists = await self.bot.pool.fetchval(query, ctx.author.id)

        if not exists:
            raise GenericError("You are not logged in.")

        query = "DELETE FROM anilist_tokens WHERE user_id = $1"
        await self.bot.pool.execute(query, ctx.author.id)

        await ctx.send(
            embed=SuccessEmbed(description="Successfully logged you out."),
        )


async def setup(bot: Harmony) -> None:
    await bot.add_cog(AniList(bot))
