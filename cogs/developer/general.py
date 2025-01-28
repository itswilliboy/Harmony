from __future__ import annotations

import importlib
from contextlib import redirect_stdout
from inspect import getsource
from io import BytesIO, StringIO
from traceback import format_exception
from typing import TYPE_CHECKING, Annotated, Literal, Optional

import discord
import jishaku
import jishaku.codeblocks
import jishaku.repl
from discord.ext import commands

from config import TOP_GG
from utils import BaseCog, GenericError

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class General(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.command(aliases=["e"])
    async def eval(
        self, ctx: Context, *, code: Annotated[jishaku.codeblocks.Codeblock, jishaku.codeblocks.codeblock_converter]
    ):
        buf = StringIO()
        with redirect_stdout(buf) as out:
            await ctx.invoke(self.bot.get_command("jishaku python"), argument=code)  # type: ignore

        if value := out.getvalue():
            await ctx.send(value)

    @commands.command(aliases=["ee"])
    async def eval2(
        self, ctx: Context, *, code: Annotated[jishaku.codeblocks.Codeblock, jishaku.codeblocks.codeblock_converter]
    ):
        args: dict[str, object] = {
            "ctx": ctx,
            "bot": ctx.bot,
            "client": ctx.bot.cogs["anime"].client,  # type: ignore
            "author": ctx.author,
            "me": ctx.guild.me,
            "channel": ctx.channel,
            "guild": ctx.guild,
            "ref": ctx.message.reference and ctx.message.reference.resolved,
        }

        try:
            async for x in jishaku.repl.AsyncCodeExecutor(code.content, arg_dict=args):
                if x is not None:
                    return await ctx.send(x)
                await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

        except Exception as exc:
            await ctx.author.send(f"You fucked up: ```py\n{'\n'.join(format_exception(exc))}\n```")

    @commands.command(aliases=["r"])
    async def reload(self, ctx: Context, extension: Optional[str] = None):
        """Reloads one or more extensions."""
        ext = None
        try:
            if extension is None:
                for ext in list(self.bot.extensions).copy():
                    if ext in ("jishaku",):
                        continue
                    await self.bot.reload_extension(ext)

            else:
                await self.bot.reload_extension(extension)

        except Exception as exc:
            await ctx.message.add_reaction("\N{CROSS MARK}")
            return self.bot.log.error(f"Something went wrong when trying to reload {ext or extension}: ", exc_info=exc)

        await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @commands.command(aliases=["d"])
    async def delete(self, ctx: Context, message_id: Optional[int] = None):
        if message_id is not None:
            try:
                msg = await ctx.fetch_message(message_id)
                await msg.delete()

            except Exception:
                pass

        else:
            async for msg in ctx.history():
                if msg.author == ctx.bot.user:
                    await msg.delete()
                    break

    @commands.command()
    async def sync(self, ctx: Context):
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"Synced {len(synced)} commands.")
        except Exception:
            await ctx.message.add_reaction("\N{CROSS MARK}")
            raise

    @staticmethod
    def _resolve(name: str):
        n, *parts = name.split(".")
        module = importlib.import_module(n)

        current_module = f"{n}"
        for part in parts:
            current_module += f".{part}"

            obj = getattr(module, part, None)
            if obj is None:
                module = importlib.import_module(current_module)
            else:
                module = obj

        return module

    @commands.command(aliases=["gs"])
    async def getsource(self, ctx: Context, path: str):
        try:
            func = self._resolve(path)

        except ModuleNotFoundError as exc:
            raise GenericError(f"Module not found: `{exc.name}`") from exc

        try:
            source = getsource(func)

        except TypeError as exc:
            raise GenericError(f"Unexpected Type: `{exc.args[0]}`") from exc

        if len(source) > 2000:
            buf = BytesIO(source.encode())

            return await ctx.send(file=discord.File(buf, filename="source.py"))

        await ctx.send(f"```py\n{source}\n```")

    @commands.command()
    async def postservers(self, ctx: Context, site: Literal["topgg", "dbl"] ) -> None:
        if self.bot.user.id != 741592089342640198:
            raise GenericError("Inapplicable bot ID.")

        match site:
            case "topgg":
                url = "https://top.gg/api/bots/741592089342640198/stats"
                json = {"server_count": len(self.bot.guilds)}
                headers = {"Authorization": TOP_GG or ""}  # for typing

            case _:
                raise GenericError("Site not found.")

        async with self.bot.session.post(url, json=json, headers=headers) as resp:
            if not resp.ok:
                raise Exception(await resp.text())

        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")