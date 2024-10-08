from __future__ import annotations

import asyncio
import datetime
import re
from collections import ChainMap
from typing import Annotated, Any, Literal, Optional, cast

import discord
from discord.app_commands import describe
from discord.ext import commands

from bot import Harmony
from utils import BaseCog, Context, GenericError, PrimaryEmbed, SuccessEmbed, progress_bar, try_get_ani_id
from utils.paginator import Page, Paginator

from .anime import Media, MinifiedMedia
from .client import AniListClient
from .media_list import MediaList
from .oauth import User
from .types import FavouriteType, MediaType, _Media
from .views import Delete, EmbedRelationView, LoginView

ANIME_REGEX = re.compile(r"\{\{(.*?)\}\}")
MANGA_REGEX = re.compile(r"\[\[(.*?)\]\]")
INLINE_CB_REGEX = re.compile(r"(?P<CB>(`{1,2})[^`^\n]+?\2)(?:$|[^`])")
CB_REGEX = re.compile(r"```[\S\s]+?```")
HL_REGEX = re.compile(r"\[.*?\]\(.*?\)")


def add_favourite(embed: discord.Embed, *, user: User, type: FavouriteType, maxlen: int = 1024, empty: bool = False):
    favourites = discord.utils.find(lambda f: f["_type"] == type.lower(), user.favourites)

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
    async def convert(self, ctx: Context, argument: str) -> Optional[User]:
        arg: Optional[int] = None
        try:
            user = await super().convert(ctx, argument)

            arg = await try_get_ani_id(ctx.pool, user.id)

        except commands.BadArgument:
            pass

        finally:
            cog = cast(AniList, ctx.bot.cogs["anime"])
            if u := cog.user_cache.get(arg or argument):
                return u

            user = await cog.client.oauth.get_user(arg or argument, use_cache=False)

            if not user:
                raise commands.BadArgument("Couldn't find a user with that name")

            cog.user_cache[arg or argument] = user
            return user


async def _default(ctx: Context) -> Optional[User]:
    return await AniUser().convert(ctx, str(ctx.author.id))


aniuser = commands.parameter(default=_default, converter=AniUser, displayed_name="AniList user")


AniUserConv = Annotated[User, AniUser]


class AniList(BaseCog, name="Anime"):
    def __init__(
        self,
        bot: Harmony,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(bot, *args, **kwargs)

        self.client = AniListClient(bot)
        self.user_cache = self.client.user_cache

    async def cog_check(self, ctx: Context) -> bool:
        await ctx.typing()
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        ctx = await self.bot.get_context(message)
        if ctx.is_blacklisted():
            return

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

        view = EmbedRelationView(self, media, user, author=ctx.author)

        view.message = await ctx.send(embed=media.embed, view=view)

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
    async def profile(self, ctx: Context, user: AniUserConv = aniuser):
        """View someone's AniList profile."""

        embed = PrimaryEmbed(
            title=user.name,
            url=user.url,
            description=user.about + "\n\u200b" if user.about else "",
        )

        embed.set_footer(text="Account Created")
        embed.timestamp = user.created_at

        if url := user.banner_url:
            embed.set_image(url=url)

        if url := user.avatar_url:
            embed.set_thumbnail(url=url)

        if user.anime_stats.episodes_watched:
            s = user.anime_stats
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

        if user.manga_stats.chapters_read:
            add_favourite(embed, user=user, type=FavouriteType.ANIME, empty=True)

            s = user.manga_stats
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
            add_favourite(embed, user=user, type=FavouriteType.ANIME)

        add_favourite(embed, user=user, type=FavouriteType.MANGA)
        add_favourite(embed, user=user, type=FavouriteType.CHARACTERS)
        add_favourite(embed, user=user, type=FavouriteType.STAFF)
        add_favourite(embed, user=user, type=FavouriteType.STUDIOS)

        await ctx.send(embed=embed)

    @describe(user="AniList username")
    @anilist.command()
    async def list(self, ctx: Context, user: AniUserConv = aniuser):
        """View someone's anime list on AniList."""

        ml = MediaList(
            self.client, await self.client.fetch_media_collection(user.id, MediaType.ANIME), user.id, ctx.author.id
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
            embed=SuccessEmbed(description="Success3lly logged you out."),
        )

    @describe(
        status="The status of the anime to compare",
        user1="The first user to compare",
        user2="The second user to compare",
        user3="The third user to compare",
        user4="The fourth user to compare",
        user5="The fifth user to compare",
    )
    @anilist.command()
    async def compare(
        self,
        ctx: Context,
        status: Literal["current", "paused", "completed", "dropped", "planning", "repeating"],
        user1: AniUserConv,
        user2: AniUserConv,
        user3: Optional[AniUserConv] = None,
        user4: Optional[AniUserConv] = None,
        user5: Optional[AniUserConv] = None,
    ) -> None:
        """Compares up to five different peoples' anime lists with a specific status."""
        users: list[AniUserConv] = [user1, user2]
        for u in (user3, user4, user5):
            if u:
                users.append(u)

        cols = await self.client.fetch_media_collections(
            *[u.id for u in users],
            type=MediaType.ANIME,
            status=status.upper(),  # type: ignore
            user_id=ctx.author.id,
        )

        entries: list[dict[int, _Media]] = []

        for item in cols.values():
            entries.append({i["media"]["id"]: i["media"] for i in item["lists"][0]["entries"]})

        total = ChainMap(*entries)
        shared = set(total).intersection(*entries)

        to_list = [total[i] for i in shared]

        nl = "\n"
        pages: list[Page] = []
        for i in to_list:
            media = Media.from_json(dict(i), {})
            embeds = [media.embed]

            if emb := media.status_embed():
                embeds.append(emb)

            pages.append(Page(embeds=embeds))

        pages.insert(
            0,
            Page(
                embed=PrimaryEmbed(
                    title=f"Common Media: {status.upper()}",
                    description=f"2. {f'{nl}2. '.join([str(i['title'].get('english', i['title']['romaji'])) for i in to_list])}",
                ).set_author(name=" - ".join([str(u) for u in users]))
            ),
        )

        await Paginator(pages, ctx.author).start(ctx)

    @anilist.command(aliases=["recent"])
    async def activity(self, ctx: Context, user: AniUserConv = aniuser):
        activities = await self.client.fetch_user_activity(user.id)

        if not activities:
            raise GenericError("Couldn't find any recent activities for this user.")

        name = activities[0]["user"]["name"]
        embed = PrimaryEmbed()
        embed.set_author(name=f"{name}'s recent activity", icon_url=activities[0]["user"]["avatar"]["large"])

        to_add: list[str] = []

        def add_item(item: str, timestamp: datetime.datetime) -> None:
            w_timestamp = discord.utils.format_dt(timestamp, "R") + f"\n{item}"
            to_add.append(w_timestamp)

        for act in activities[:5]:
            media = act["media"]
            timestamp = datetime.datetime.fromtimestamp(act["createdAt"])

            t = media["title"]
            title = t["english"] or t["romaji"] or t["native"]
            linked = f"**[{title}]({media['siteUrl']})**"

            status = act["status"]
            match status:
                case "watched episode":
                    ep = act["progress"]

                    value = f"Watched episode ***{ep}*** of {linked}"
                    add_item(value, timestamp)

                case "read chapter":
                    ch = act["progress"]
                    value = f"Read chapter ***{ch}*** of {linked}"
                    add_item(value, timestamp)

                case "plans to watch":
                    print(media)
                    value = f"Plans to watch {linked}"
                    add_item(value, timestamp)

                case "plans to read":
                    value = f"Plans to read {linked}"
                    add_item(value, timestamp)

                case "completed":
                    value = f"Completed {linked}"
                    add_item(value, timestamp)

                case "paused watching":
                    value = f"Paused watching of {linked}"
                    add_item(value, timestamp)

                case "paused watching":
                    value = f"Paused reading of {linked}"
                    add_item(value, timestamp)

                case _:
                    print(status)
                    pass

        embed.description = "\n\n".join(to_add)

        await ctx.send(embed=embed)


async def setup(bot: Harmony) -> None:
    await bot.add_cog(AniList(bot))
