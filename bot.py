import logging
from typing import Any

import discord
from aiohttp import ClientSession
from asyncpg import Pool, create_pool
from discord.ext import commands

from config import POSTGRES_SETTINGS


class Harmony(commands.Bot):
    session: ClientSession
    pool: Pool
    log: logging.Logger

    user: discord.User

    def __init__(self, intents: discord.Intents, initial_extensions: list[str], *args: Any, **kwargs: Any) -> None:
        self.initial_extensions = initial_extensions
        super().__init__(command_prefix=self.get_prefix, intents=intents, help_command=None, *args, **kwargs)  # type: ignore

    async def get_prefix(self, message: discord.Message) -> str | list[str]:
        if message.guild is None:
            return commands.when_mentioned(self, message)

        resp = await self.pool.fetchrow("SELECT prefix FROM prefixes WHERE guild_id=$1", message.guild.id)
        return resp and commands.when_mentioned_or(resp["prefix"])(self, message) or commands.when_mentioned(self, message)

    async def setup_hook(self) -> None:
        discord.utils.setup_logging(level=logging.INFO)
        logging.getLogger("discord.gateway").setLevel(logging.WARNING)

        pool = await create_pool(**POSTGRES_SETTINGS)
        if not pool or pool and pool._closed:
            raise Exception("Pool is closed")

        self.pool = pool

        self.session = ClientSession()
        self.log = logging.getLogger("Harmony")

        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                self.log.info("Loading extension: %s", ext)
            except Exception as exc:
                self.log.error("Failed to load extension: %s", exc, exc_info=exc)

        # Run schema
        with open("schema.sql", "r", encoding="utf-8") as f:
            schema = f.read()
            await pool.execute(schema)

    async def on_ready(self) -> None:
        self.log.info("Logged in as %s on discord.py version %s", self.user, discord.__version__)

    async def close(self) -> None:
        await self.pool.close()
        await self.session.close()
        await super().close()
