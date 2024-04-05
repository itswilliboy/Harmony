import logging
from datetime import datetime
import re
import traceback
from typing import TYPE_CHECKING, Any

import discord
from aiohttp import ClientSession
from asyncpg import Pool, Record, create_pool
from discord.ext import commands, ipc

from config import DEFAULT_PREFIX, POSTGRES_CREDENTIALS
from utils import Context


class Harmony(commands.Bot):
    """Bot class for Harmony"""

    session: ClientSession
    log: logging.Logger
    ipc: ipc.Server  # type: ignore

    if TYPE_CHECKING:
        pool: Pool[Record]

    user: discord.User

    def __init__(self, intents: discord.Intents, initial_extensions: list[str], *args: Any, **kwargs: Any) -> None:
        super().__init__(command_prefix=self.get_prefix, intents=intents, help_command=None, *args, **kwargs)  # type: ignore
        self._BotBase__cogs = commands.core._CaseInsensitiveDict()  # Hacky way for lowercase cog arguments in help command

        self.initial_extensions = initial_extensions
        self.started_at = datetime.now()

        self.prefix_cache: dict[int, list[str]] = {}

    async def get_prefix(self, message: discord.Message) -> list[str]:
        if message.guild is None:
            return commands.when_mentioned_or(DEFAULT_PREFIX)(self, message)

        prefixes = self.prefix_cache.get(message.guild.id)
        if prefixes is not None:
            return commands.when_mentioned_or(*prefixes)(self, message)

        else:
            self.log.warning("Prefix not found for guild with ID %s, using default prefix", message.guild.id)
            return commands.when_mentioned_or(DEFAULT_PREFIX)(self, message)

    async def populate_prefix_cache(self) -> None:
        resp = await self.pool.fetch("SELECT * FROM prefixes")

        for guild_id, prefix in resp:
            guild_id: int
            prefix: list[str]

            self.prefix_cache[guild_id] = prefix

    async def populate_command_permissions(self) -> None:
        pattern = re.compile(r"<function has_(guild_)?permissions\.<locals>.predicate at 0x\w+>")
        for cmd in self.commands:
            for _, check in enumerate(cmd.checks):
                if not pattern.fullmatch(str(check)):
                    continue

                try:
                    check(0)  # type: ignore  # 0 is passed to force an exception

                except Exception as exc:
                    *_, last = traceback.walk_tb(exc.__traceback__)
                    frame = last[0]
                    cmd.extras["perms"] = frame.f_locals["perms"]

    async def get_context(self, message, *, cls=Context) -> Context:
        return await super().get_context(message, cls=cls)

    async def setup_hook(self) -> None:
        discord.utils.setup_logging(level=logging.INFO)
        logging.getLogger("discord.gateway").setLevel(logging.WARNING)

        pool = await create_pool(**POSTGRES_CREDENTIALS)
        if not pool or pool and pool._closed:
            raise RuntimeError("Pool is closed")

        self.pool = pool

        # Run schema
        with open("schema.sql", "r", encoding="utf-8") as f:
            schema = f.read()
            await pool.execute(schema)

        self.session = ClientSession()
        self.log = logging.getLogger("Harmony")

        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                self.log.info("Loading extension: %s", ext)

            except Exception as exc:
                self.log.error("Failed to load extension: %s", ext, exc_info=exc)

        await self.populate_prefix_cache()
        await self.populate_command_permissions()

    async def on_ready(self) -> None:
        self.log.info("Logged in as %s on discord.py version %s", self.user, discord.__version__)

    async def close(self) -> None:
        await self.pool.close()
        await self.session.close()
        await super().close()
