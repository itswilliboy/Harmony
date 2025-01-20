from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

import discord
from aiohttp import ClientSession
from asyncache import cachedmethod  # pyright: ignore[reportMissingTypeStubs]
from asyncpg import Pool, Record, create_pool
from discord.ext import commands
from discord.ext.commands.core import (  # pyright: ignore[reportMissingTypeStubs]
    _CaseInsensitiveDict,
)

from config import DEFAULT_PREFIX, OWNER_IDS, POSTGRES_CONNECTION_URI
from utils import Context

if TYPE_CHECKING:
    from cogs.developer.blacklist import BlacklistItem, GuildBlacklistItem


__all__ = ("Harmony",)


class Harmony(commands.Bot):
    """Bot class for Harmony"""

    session: ClientSession
    log: logging.Logger

    if TYPE_CHECKING:
        pool: Pool[Record]

    user: discord.User

    blacklist: dict[int, BlacklistItem]
    guild_blacklist: dict[int, GuildBlacklistItem]

    def __init__(self, intents: discord.Intents, initial_extensions: list[str], *args: Any, **kwargs: Any) -> None:
        super().__init__(
            *args,
            **kwargs,
            command_prefix=self.get_prefix,  # type: ignore
            intents=intents,
            help_command=None,
            activity=discord.CustomActivity(f"{DEFAULT_PREFIX}help"),
            allowed_mentions=discord.AllowedMentions.none(),
            case_insensitive=True,
        )
        self._BotBase__cogs = _CaseInsensitiveDict()  # Hacky way to allow lowercase cog arguments in help command

        self.initial_extensions = initial_extensions
        self.started_at = datetime.now()

        self.prefix_cache: dict[int, list[str]] = {}

    def _key(self, message: discord.Message) -> int:
        if message.guild is None:
            return 0
        return message.guild.id

    @cachedmethod(lambda self: self.prefix_cache, key=_key)
    async def get_prefix(self, message: discord.Message) -> list[str]:
        if message.guild is None:
            return commands.when_mentioned_or(DEFAULT_PREFIX)(self, message)

        prefixes = await self.pool.fetchval("SELECT prefixes FROM prefixes WHERE guild_id = $1", message.guild.id)
        if prefixes is not None:
            return commands.when_mentioned_or(*prefixes)(self, message)

        else:
            self.log.warning("Prefix not found for guild with ID %s, using default prefix", message.guild.id)
            return commands.when_mentioned_or(DEFAULT_PREFIX)(self, message)

    async def get_context(self, origin: discord.Message | discord.Interaction, *, cls: Any = Context) -> Context:
        return await super().get_context(origin, cls=cls)

    async def setup_hook(self) -> None:
        discord.utils.setup_logging(level=logging.INFO)
        logging.getLogger("discord.gateway").setLevel(logging.WARNING)

        pool: Optional[Pool[Record]] = await create_pool(POSTGRES_CONNECTION_URI, timeout=30)
        if not pool or pool and pool._closed:
            raise RuntimeError("Pool is closed")

        self.pool = pool

        # Run schema
        with open("schema.sql", "r", encoding="utf-8") as f:
            schema = f.read()
            await pool.execute(schema)

        headers = {"User-Agent": "Harmony Discord Bot (https://github.com/itswilliboy/Harmony)"}
        self.session = ClientSession(headers=headers)
        self.log = logging.getLogger("Harmony")

        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                self.log.info("Loading extension: %s", ext)

            except Exception as exc:
                self.log.error("Failed to load extension: %s", ext, exc_info=exc)

    async def on_ready(self) -> None:
        self.log.info("Logged in as %s on discord.py version %s", self.user, discord.__version__)

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content != after.content and before.created_at + timedelta(minutes=5) > discord.utils.utcnow():
            return await self.process_commands(after)

    async def is_owner(self, user: discord.abc.User) -> bool:
        if user.id in OWNER_IDS:
            return True
        return await super().is_owner(user)

    async def close(self) -> None:
        if hasattr(self, "pool"):
            await self.pool.close()

        if hasattr(self, "session"):
            await self.session.close()

        await super().close()
