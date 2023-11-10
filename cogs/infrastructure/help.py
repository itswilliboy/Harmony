from __future__ import annotations

from typing import TYPE_CHECKING, List, Mapping, Optional, Tuple

from discord.ext import commands
from discord.ext.commands.core import Command

from utils import BaseCog, PrimaryEmbed, get_command_signature

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class HelpCommand(commands.HelpCommand):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context: Context

    async def send_bot_help(self, mapping: Mapping[Optional[BaseCog], List[Command]]) -> None:
        embed = PrimaryEmbed(title="Help")
        embed.description = (
            f"Use `{self.context.clean_prefix}help [command]` for more information on a command.\n"
            f"You can also use `{self.context.clean_prefix}help [category]` for more information on a category."
        )
        
        categories: List[Tuple[str, str]] = []

        for cog, cmds in mapping.items():
            if cog is None or cog.qualified_name in "Jishaku" or cog.is_hidden():
                continue

            categories.append((cog.qualified_name, ", ".join([f"`{cmd.name}`" for cmd in cmds])))

        for category in categories:
            embed.add_field(name=category[0], value=category[1], inline=False)

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: Command) -> None:
        embed = PrimaryEmbed(title=command.name.title())
        embed.description = command.short_doc

        embed.add_field(name="Usage", value=f"```\n{get_command_signature((self.context.clean_prefix, command))}\n```")

        await self.get_destination().send(embed=embed)


class Help(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        bot.help_command = HelpCommand()
        bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = commands.DefaultHelpCommand()

