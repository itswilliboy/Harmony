import logging
from datetime import datetime
from typing import Any

import discord
from aiohttp import ClientSession
from asyncpg import Pool, create_pool
from discord.ext import commands, ipc

from config import DEFAULT_PREFIX, POSTGRES_SETTINGS
from utils import Context


class Harmony(commands.Bot):
    """Bot class for Harmony"""

    session: ClientSession
    pool: Pool
    log: logging.Logger
    ipc: ipc.Server  # type: ignore

    user: discord.User

    def __init__(self, intents: discord.Intents, initial_extensions: list[str], *args: Any, **kwargs: Any) -> None:
        self.initial_extensions = initial_extensions
        self.started_at = datetime.now()
        super().__init__(command_prefix=self.get_prefix, intents=intents, help_command=None, *args, **kwargs)  # type: ignore
        self._BotBase__cogs = commands.core._CaseInsensitiveDict()  # Hacky way for lowercase cog arguments in help command

    async def get_prefix(self, message: discord.Message) -> str | list[str]:
        if message.guild is None:
            return commands.when_mentioned_or(DEFAULT_PREFIX)(self, message)

        prefix = await self.pool.fetchval("SELECT prefix FROM prefixes WHERE guild_id = $1", message.guild.id)
        return prefix and commands.when_mentioned_or(prefix)(self, message) or commands.when_mentioned(self, message)

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    async def setup_hook(self) -> None:
        discord.utils.setup_logging(level=logging.INFO)
        logging.getLogger("discord.gateway").setLevel(logging.WARNING)

        pool = await create_pool(**POSTGRES_SETTINGS)
        if not pool or pool and pool._closed:
            raise Exception("Pool is closed")

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
                self.log.error("Failed to load extension: %s", exc, exc_info=exc)

    async def on_ready(self) -> None:
        self.log.info("Logged in as %s on discord.py version %s", self.user, discord.__version__)

    async def close(self) -> None:
        await self.pool.close()
        await self.session.close()
        await super().close()
