from __future__ import annotations

import asyncio
import datetime
import random
from collections import ChainMap
from typing import TYPE_CHECKING, Annotated, Any, Literal, Optional, cast

import discord
from discord.app_commands import allowed_contexts, allowed_installs, describe
from discord.ext import commands

from utils import BaseCog, Context, GenericError, Page, Paginator, PrimaryEmbed, SuccessEmbed
from utils.utils import try_get_ani_id

from .anime import Media, MinifiedMedia
from .client import AniListClient
from .media_list import MediaList
from .oauth import Favourites, User
from .types import FavouriteType, ListActivity, MediaListEntry, MediaListStatus, MediaTitle, MediaType, Regex, _Media
from .views import Delete, EmbedRelationView, LoginView, ProfileManagementView, SearchView

if TYPE_CHECKING:
    from bot import Harmony


def add_favourite(embed: discord.Embed, *, user: User, type: FavouriteType, maxlen: int = 1024, empty: bool = False) -> None:
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


def get_favourites(favourites: list[Favourites], type: FavouriteType) -> list[tuple[str, str]]:
    favs = discord.utils.find(lambda f: f["_type"] == type.lower(), favourites)

    if favs is None:
        return []

    to_return: list[tuple[str, str]] = []
    for fav in favs["items"]:
        to_return.append((fav.name, fav.site_url))

    return to_return


def get_activity_message(activity: ListActivity) -> tuple[str, datetime.datetime, int, int]:
    act = activity

    to_add: list[str] = []

    def add_item(item: str, timestamp: datetime.datetime) -> None:
        w_timestamp = discord.utils.format_dt(timestamp, "R") + f"\n{item}"
        to_add.append(w_timestamp)

    media = act["media"]
    timestamp = datetime.datetime.fromtimestamp(act["createdAt"])

    t = media["title"]
    title = t["english"] or t["romaji"] or t["native"]
    linked = f"**[{title}]({media['siteUrl']})**"

    status = act["status"]

    value = f"{status} | {linked}"
    match status:
        case "watched episode":
            ep = act["progress"]
            value = f"Watched episode **{ep}** of {linked}"
            add_item(value, timestamp)

        case "rewatched episode":
            ep = act["progress"]
            value = f"Rewatched episode **{ep}** of {linked}"
            add_item(value, timestamp)

        case "read chapter":
            ch = act["progress"]
            value = f"Read chapter **{ch}** of {linked}"
            add_item(value, timestamp)

        case "plans to watch":
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

        case "paused reading":
            value = f"Paused reading of {linked}"
            add_item(value, timestamp)

        case "dropped":
            value = f"Dropped {linked}"
            add_item(value, timestamp)

        case _:
            print(status)
            add_item(f"{status.title()} | {linked}", timestamp)

    return value, timestamp, activity["likeCount"], activity["replyCount"]


class AniUser(commands.UserConverter):
    async def convert(self, ctx: Context, argument: str) -> Optional[User]:
        arg: Optional[int] = None
        try:
            user = await super().convert(ctx, argument)

            arg = await try_get_ani_id(ctx.pool, user.id)

        except commands.BadArgument:
            pass

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


class AnilistRandomFlags(commands.FlagConverter):
    type: MediaType = MediaType.ANIME
    status: MediaListStatus = MediaListStatus.PLANNING


aniuser = commands.parameter(default=_default, converter=AniUser, displayed_name="AniList user")
AniUserConv = Annotated[User, AniUser]
anilist_random_flag_converter = commands.parameter(converter=AnilistRandomFlags)


class AniList(BaseCog, name="Anime"):
    def __init__(
        self,
        bot: Harmony,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(bot, *args, **kwargs)

        self.client = AniListClient(bot)
        self.user_cache = self.client.user_cache

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.command.name != "login":
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

        for match in reversed(list(Regex.INLINE_CB_REGEX.finditer(content))):
            start, end = match.span("CB")
            content = content[:start] + content[end:]

        content = Regex.CB_REGEX.sub(" ", content)
        content = Regex.HL_REGEX.sub(" ", content)

        anime = Regex.ANIME_REGEX.findall(content)
        manga = Regex.MANGA_REGEX.findall(content)

        if not anime and not manga:
            return

        found: list[MinifiedMedia] = []

        async with message.channel.typing():
            embed = PrimaryEmbed()

            # TODO: Do one big query instead of looping through and sending multiple requests
            for name in anime:
                media = await self.client.search_minified_media(name, type=MediaType.ANIME)
                if media and media not in found:
                    found.append(media)
                    embed.add_field(
                        name=f"**__{media.name}__** (**{media.mean_score}%**)", value=media.small_info, inline=False
                    )

            for name in manga:
                media = await self.client.search_minified_media(name, type=MediaType.MANGA)
                if media and media not in found:
                    found.append(media)
                    embed.add_field(
                        name=f"**__{media.name}__** (**{media.mean_score}%**)", value=media.small_info, inline=False
                    )

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

            if not media.is_adult:
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
        media, user = await self.client.search_media(
            search,
            type=search_type,
            user_id=ctx.author.id,
        )

        if media is None:
            raise GenericError(f"Couldn't find any {search_type.value.lower()} with that name.")

        if (
            not isinstance(ctx.channel, discord.GroupChannel | discord.PartialMessageable)
            and media.is_adult
            and not (
                isinstance(
                    ctx.channel,
                    discord.DMChannel,
                )
                or ctx.channel.is_nsfw()
            )
        ):
            raise GenericError(
                (
                    f"This {search_type.value.lower()} was flagged as NSFW. "
                    "Please try searching in an NSFW channel or in my DMs."
                )
            )

        view = EmbedRelationView(self, media, user, author=ctx.author)

        view.message = await ctx.send(embed=media.embed, view=view)

    async def search_many(self, ctx: Context, search: str) -> None:
        is_nsfw = True

        if not isinstance(ctx.channel, discord.DMChannel | discord.GroupChannel | discord.PartialMessageable):
            is_nsfw = ctx.channel.is_nsfw()

        media, user = await self.client.search_many(search, ctx.author.id, include_adult=is_nsfw)

        if not media:
            raise GenericError("Couldn't find any results for this search, if it is NSFW, use an NSFW channel.")

        view = SearchView(self, media, author=ctx.author, user=user)
        view.message = await ctx.send(f"Showing results for search: `{search}`", view=view)

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

    @commands.hybrid_command(aliases=["a"])
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True, private_channels=True)
    @describe(search="The anime to search for")
    async def anime(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific anime."""
        await self.search(ctx, search, MediaType.ANIME)

    @commands.hybrid_command(aliases=["m"])
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True, private_channels=True)
    @describe(search="The manga to search for")
    async def manga(self, ctx: Context, *, search: str):
        """Searches and returns information on a specific manga."""
        await self.search(ctx, search, MediaType.MANGA)

    @commands.hybrid_command(name="search", aliases=["s"])
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def search_(self, ctx: Context, *, search: str):
        """Searches and returns the first 10 results on a media."""
        await self.search_many(ctx, search)

    @commands.hybrid_group(invoke_without_command=True, aliases=["al"])
    @allowed_installs(guilds=True, users=True)
    @allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def anilist(self, ctx: Context):
        await ctx.send_help(ctx.command)

    @describe(user="AniList username")
    @anilist.command(aliases=["p"])
    async def profile(self, ctx: Context, user: AniUserConv = aniuser):
        """Shows information about someone's profile on AniList."""
        embed = PrimaryEmbed(title=user.name, url=user.url)
        embed.set_thumbnail(url=user.avatar_url)

        astats = mstats = None
        afavs = get_favourites(user.favourites, FavouriteType.ANIME)
        mfavs = get_favourites(user.favourites, FavouriteType.MANGA)

        if s := user.anime_stats:
            items = (
                f"Anime watched: `{s.count:,}`",
                f"Episodes watched: `{s.episodes_watched:,}`",
                f"Hours watched: `{s.minutes_watched // 60:,}` (`{s.minutes_watched // 60 // 24}d`)",
                f"Favourite: [{afavs[0][0]}]({afavs[0][1]})" if afavs else (" " if mfavs else ""),
                f"-# Average score: `{s.mean_score:.1f}%`" if s.mean_score else None,
            )
            astats = [i for i in items if i]

        if s := user.manga_stats:
            items = (
                f"Manga read: `{s.count:,}`",
                f"Chapters read: `{s.chapters_read:,}`",
                f"Volumes read: `{s.volumes_read:,}`",
                f"Favourite: [{mfavs[0][0]}]({mfavs[0][1]})" if mfavs else (" " if afavs else ""),
                f"-# Average score: `{s.mean_score:.1f}%`" if s.mean_score else None,
            )
            mstats = [i for i in items if i]

        if astats:
            embed.add_field(name="Anime", value="\n".join(astats))

        if mstats:
            embed.add_field(name="Manga", value="\n".join(mstats))

        activities = await self.client.fetch_user_activity(user.id)
        first = [get_activity_message(act) for act in activities[:3]]

        if first:
            fmtd = [f"-# {discord.utils.format_dt(act[1], 'R')}\n-# {act[0]}" for act in first]
            embed.add_field(name="Recent Activity", value="\n".join(fmtd), inline=False)

        view: Optional[discord.ui.View] = None
        id = await try_get_ani_id(ctx.pool, ctx.author.id)
        if id and id == user.id and False:  # TODO: Implement.
            view = ProfileManagementView(self, user)

        await ctx.send(embed=embed, view=view or discord.utils.MISSING)

    @describe(user="AniList username")
    @anilist.command(aliases=["l"])
    async def list(self, ctx: Context, user: AniUserConv = aniuser):
        """View someone's anime list on AniList."""

        ml = MediaList(
            self.client, await self.client.fetch_media_collection(user.id, MediaType.ANIME), user.id, ctx.author.id
        )
        await ml.start(ctx)

    @anilist.command(aliases=["auth"])
    async def login(self, ctx: Context):
        """Log in with an AniList account."""
        query = "SELECT expiry FROM anilist_tokens_new WHERE user_id = $1"
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
            description="Press the button below to start the authorisation flow.",
        )

        try:
            await ctx.author.send(
                embed=embed,
                view=LoginView(ctx.bot, ctx.author, self.client),
            )
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

        except discord.Forbidden:
            await ctx.send("Couldn't send a DM, are they open?")

        except discord.NotFound:
            await ctx.send("\N{WHITE HEAVY CHECK MARK}", ephemeral=True)

    @anilist.command()
    async def logout(self, ctx: Context):
        """Logs you out."""
        query = "SELECT EXISTS(SELECT 1 FROM anilist_tokens_new WHERE user_id = $1)"
        exists = await self.bot.pool.fetchval(query, ctx.author.id)

        if not exists:
            raise GenericError("You are not logged in.")

        query = "DELETE FROM anilist_tokens_new WHERE user_id = $1"
        await self.bot.pool.execute(query, ctx.author.id)

        await ctx.send(
            embed=SuccessEmbed(description="Successlly logged you out."),
        )

    @describe(
        status="The status of the anime to compare",
        user1="The first user to compare",
        user2="The second user to compare",
        user3="The third user to compare",
        user4="The fourth user to compare",
        user5="The fifth user to compare",
    )
    @anilist.command(aliases=["c"])
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
            status=MediaListStatus[status.upper()],
            user_id=ctx.author.id,
        )

        entries: list[dict[int, _Media]] = []

        for item in cols.values():
            entries.append({i["media"]["id"]: i["media"] for i in item["lists"][0]["entries"]})

        total = ChainMap(*entries)
        shared = set(total).intersection(*entries)

        to_list = [total[i] for i in shared]

        to_list.sort(key=lambda li: li["title"]["english"] or li["title"]["romaji"])

        nl = "\n"
        pages: list[Page] = []
        for i in to_list:
            media = Media.from_json(dict(i), {})
            embeds = [media.embed]

            if emb := media.status_embed():
                embeds.append(emb)

            pages.append(Page(embeds=embeds))

        def get_title(title: MediaTitle) -> str:
            return title["english"] or title["romaji"] or title["native"] or "<No title>"

        pages.insert(
            0,
            Page(
                embed=PrimaryEmbed(
                    title=f"Common Media: {status.upper()}",
                    description=f"2. {f'{nl}2. '.join([get_title(i['title']) for i in to_list])}",
                ).set_author(name=" - ".join([str(u) for u in users]))
            ),
        )

        await Paginator(pages, ctx.author).start(ctx)

    @anilist.command(aliases=["recent", "r", "a"])
    async def activity(self, ctx: Context, user: AniUserConv = aniuser):
        """Shows somebody's recent activity on AniList."""
        activities = await self.client.fetch_user_activity(user.id)

        if not activities:
            raise GenericError("Couldn't find any recent activities for this user.")

        name = activities[0]["user"]["name"]

        messages = [get_activity_message(act) for act in activities]

        embeds: list[discord.Embed] = []
        for chunk in discord.utils.as_chunks(messages, 5):
            embed = PrimaryEmbed()
            embed.set_author(name=f"{name}'s recent activity", icon_url=activities[0]["user"]["avatar"]["large"])

            fmtd = [
                f"-# {discord.utils.format_dt(act[1], 'R')} "
                + " **|** ".join(
                    _
                    for _ in (
                        (f"\N{WHITE HEART SUIT} {act[2]}" if act[2] > 0 else None),
                        (f"\N{LOWER RIGHT PENCIL} {act[3]}" if act[3] > 0 else None),
                    )
                    if _ is not None
                )
                + f"\n{act[0]}"
                for act in chunk
            ]
            embed.description = "\n\n".join(fmtd)

            embeds.append(embed)

        await Paginator(embeds, ctx.author).start(ctx)

    @anilist.command(aliases=["ra"])
    async def random(
        self, ctx: Context, user: AniUserConv = aniuser, query_type: AnilistRandomFlags = anilist_random_flag_converter
    ):
        collection = await self.client.fetch_media_collection(user.id, type=query_type.type)

        media_list_entries: list[MediaListEntry] = []
        for medialist in collection["lists"]:
            media_list_entries.extend(medialist["entries"])

        random_media = random.choice([entry for entry in media_list_entries if entry["status"] == query_type.status])

        following_status = (
            await self.client.fetch_following_status(
                random_media["media"]["id"],
                ctx.author.id,
            )
            or {}
        )

        media = Media.from_json(dict(random_media["media"]), following_status=following_status)

        await ctx.reply(embed=media.embed, view=EmbedRelationView(self, media, user, ctx.author))


async def setup(bot: Harmony) -> None:
    await bot.add_cog(AniList(bot))
