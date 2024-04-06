from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, NamedTuple

from discord import Embed
from discord.ext import commands

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

    Command = commands.Command[Any, Any, Any]
    Group = commands.Group[Any, Any, Any]
    Cog = commands.Cog


class Category(NamedTuple):
    cog: str
    commands: str


class HelpCommand(commands.HelpCommand):
    context: Context

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(verify_checks=False, *args, **kwargs)
        self.verify_checks = False

    async def send_bot_help(self, mapping: Mapping[BaseCog | None, list[Command]]) -> None:
        embed = PrimaryEmbed(title="Help")
        embed.description = (
            f"Use `{self.context.clean_prefix}help [command]` for more information on a command.\n"
            f"You can also use `{self.context.clean_prefix}help [category]` for more infomation on a category."
        )

        categories: list[Category] = []

        for cog, cmds in mapping.items():
            if cog is None or cog.qualified_name == "Jishaku" or cog.is_hidden():
                continue

            cmds_ = await self.filter_commands(cmds, sort=True)
            category = Category(
                cog.qualified_name, ", ".join([f"`{cmd.name}`" if cmd.enabled else f"~~`{cmd.name}`~~" for cmd in cmds_])
            )
            categories.append(category)

        for category in categories:
            embed.add_field(name=category.cog, value=category.commands, inline=False)

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: Command) -> None:
        embed = PrimaryEmbed(title=command.name.title())
        embed.description = command.short_doc

        embed.add_field(name="Usage", value=f"```\n{get_command_signature((self.context.clean_prefix, command))}\n```")
        if aliases := command.aliases:
            embed.add_field(name="Aliases", value=", ".join([f"`{alias}`" for alias in aliases]), inline=False)

        if perms := command.extras.get("perms"):
            nl = "\n"
            keys = [key.replace("_", " ").title() for key in list(perms.keys())]
            embed.add_field(name="Required Permissions", value=f"* {f' {nl}* '.join(keys)}", inline=False)

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group: Group) -> None:
        embed = PrimaryEmbed(title=group.name.title())
        embed.description = group.short_doc

        formatted: list[str] = []
        formatted.append(get_command_signature((self.context.clean_prefix, group)))
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
                if cmd.hidden:
                    continue

                embed.add_field(
                    name=f"`{cmd.qualified_name}`",
                    value=f"{cmd.short_doc}\n`{get_command_signature((self.context.clean_prefix, cmd))}`\n\u200b",
                    inline=False,
                )

            embeds.append(embed)

        await Paginator(embeds, self.context.author).start(self.get_destination())

    async def send_error_message(self, error: str) -> None:
        await self.get_destination().send(embed=ErrorEmbed(description=error))


class Help(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        bot.help_command = HelpCommand()
        bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = commands.MinimalHelpCommand()
        self.bot.help_command.cog = None
