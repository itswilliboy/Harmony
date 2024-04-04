from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands
from jishaku.codeblocks import codeblock_converter as CodeblockConverter

from utils import BaseCog

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class General(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.command(aliases=["e"])
    async def eval(self, ctx: Context, *, code: CodeblockConverter):  # type: ignore
        await ctx.invoke(self.bot.get_command("jishaku python"), argument=code)  # type: ignore

    @commands.command(aliases=["r"])
    async def reload(self, ctx: Context, extension: str | None = None):
        """Reloads one or more extensions."""
        try:
            if extension is None:
                for ext in list(self.bot.extensions).copy():
                    if ext in ("cogs.infrastructure", "jishaku"):
                        continue
                    await self.bot.reload_extension(ext)

            else:
                await self.bot.reload_extension(extension)

        except Exception as exc:
            await ctx.message.add_reaction("\N{CROSS MARK}")
            self.bot.log.error(f"Something went wrong when trying to reload {ext or extension}: ", exc_info=exc)

        await ctx.message.add_reaction("\N{OK HAND SIGN}")
