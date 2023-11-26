from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from discord.ext import commands

if TYPE_CHECKING:
    from bot import Harmony

    from . import Context


class BaseCogMeta(commands.CogMeta):
    hidden: bool
    owner_only: bool

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        hidden = kwargs.pop("hidden", False)
        owner_only = kwargs.pop("owner_only", False)

        if hidden:
            kwargs["command_attrs"] = dict(hidden=True)

        inst = super().__new__(cls, *args, **kwargs)

        inst.hidden = hidden
        inst.owner_only = owner_only

        return inst


class BaseCog(commands.Cog, metaclass=BaseCogMeta):
    """Base class used in the creation of cogs."""

    def __init__(self, bot: Harmony, *args, **kwargs) -> None:
        self.bot = bot
        super().__init__(*args, **kwargs)

        if self.owner_only:
            self.cog_check = self.owner_only_check  # type: ignore

    async def owner_only_check(self, ctx: Context) -> bool:
        predicate = await ctx.bot.is_owner(ctx.author)

        if predicate is False:
            raise commands.NotOwner()
        return predicate

    def is_hidden(self) -> bool:
        """Returns `True` if the cog is hidden."""
        return self.hidden or all([cmd.hidden for cmd in self.get_commands()])
