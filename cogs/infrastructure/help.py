from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

from discord import Embed
from discord.ext import commands
from discord.ext.commands import Cog, Command, Group

from utils import (
    BaseCog,
    ErrorEmbed,
    Paginator,
    PrimaryEmbed,
    chunk,
    get_command_signature,
)

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class HelpCommand(commands.HelpCommand):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context: Context

    async def send_bot_help(self, mapping: Mapping[BaseCog | None, list[Command]]) -> None:
        embed = PrimaryEmbed(title="Help")
        embed.description = (
            f"Use `{self.context.clean_prefix}help [command]` for more information on a command.\n"
            f"You can also use `{self.context.clean_prefix}help [category]` for more infomation on a category."
        )

        categories: list[tuple[str, str]] = []

        for cog, cmds in mapping.items():
            if cog is None or cog.qualified_name in "Jishaku" or cog.is_hidden():
                continue

            cmds_ = [cmd for cmd in cmds if not cmd.hidden]
            categories.append(
                (cog.qualified_name, ", ".join(sorted([f"`{cmd.name}`" for cmd in cmds_], key=lambda i: i[1])))
            )

        for category in categories:
            embed.add_field(name=category[0], value=category[1], inline=False)

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: Command) -> None:
        embed = PrimaryEmbed(title=command.name.title())
        embed.description = command.short_doc

        embed.add_field(name="Usage", value=f"```\n{get_command_signature((self.context.clean_prefix, command))}\n```")
        if aliases := command.aliases:
            embed.add_field(name="Aliases", value=", ".join([f"`{alias}`" for alias in aliases]), inline=False)

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group: Group) -> None:
        embed = PrimaryEmbed(title=group.name.title())
        embed.description = group.short_doc

        formatted = []
        for cmd in group.commands:
            formatted.append(get_command_signature((self.context.clean_prefix, cmd)))

        nl = "\n"
        embed.add_field(name="Commands", value=f"```\n{nl.join(formatted)}\n```")

        await self.get_destination().send(embed=embed)

    async def send_cog_help(self, cog: Cog) -> None:
        embeds: list[Embed] = []

        for chnk in chunk(cog.get_commands(), 5):
            embed = PrimaryEmbed(title=cog.qualified_name.title())
            for cmd in chnk:
                embed.add_field(
                    name=f"`{cmd.qualified_name}`",
                    value=f"{cmd.short_doc}\n`{get_command_signature((self.context.clean_prefix, cmd))}`\n\u200b",
                    inline=False,
                )

            embeds.append(embed)

        await Paginator(embeds).start(self.get_destination())

    async def send_error_message(self, error: str) -> None:
        await self.get_destination().send(embed=ErrorEmbed(description=error))


class Help(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        bot.help_command = HelpCommand()
        bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = commands.MinimalHelpCommand()
