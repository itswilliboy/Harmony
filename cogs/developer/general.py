from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Optional

from discord.ext import commands
from jishaku.codeblocks import Codeblock
from jishaku.codeblocks import codeblock_converter as CodeblockConverter

from utils import BaseCog

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class General(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @commands.command(aliases=["e"])
    async def eval(self, ctx: Context, *, code: Annotated[Codeblock, CodeblockConverter]):
        await ctx.invoke(self.bot.get_command("jishaku python"), argument=code)  # type: ignore

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
