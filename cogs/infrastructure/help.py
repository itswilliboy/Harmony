from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, NamedTuple, Optional, cast

from discord import Embed, utils
from discord.ext import commands

from utils import (
    BaseCog,
    BaseCogMeta,
    ErrorEmbed,
    Paginator,
    PrimaryEmbed,
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
        super().__init__(*args, **kwargs, verify_checks=False)
        self.verify_checks = False

    async def send_bot_help(self, mapping: Mapping[Optional[BaseCog], list[Command]]) -> None:
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

        cog = cast(BaseCogMeta, command.cog)
        ctx = self.context
        if (hasattr(cog, "owner_only") and cog.owner_only) and not await ctx.bot.is_owner(ctx.author):
            return await self.context.message.add_reaction("\N{CROSS MARK}")

        embed.add_field(name="Usage", value=f"```\n{get_command_signature((self.context.clean_prefix, command))}\n```")

        flags: list[str] = []
        for param in command.clean_params.values():
            if issubclass(param.annotation.__class__, commands.flags.FlagsMeta):
                for name, flag in param.annotation.get_flags().items():
                    flags.append(f"`{name}`: {flag.description} `(Default: {flag.default})`")

        nl = "\n"
        if flags:
            embed.add_field(name="Flags", value=f"* {f' {nl}* '.join(flags)}", inline=False)

        embed.set_footer(text="< > = required | [ ] = optional")
        if aliases := command.aliases:
            embed.add_field(name="Aliases", value=", ".join([f"`{alias}`" for alias in aliases]), inline=False)

        perms: dict[str, bool] = {}
        bot_perms: dict[str, bool] = {}
        guild_only: bool = False
        for check in command.checks:
            if "guild_only" in str(check):
                guild_only = True

            if check.__closure__:
                if "bot_has" in str(check):
                    bot_perms = check.__closure__[0].cell_contents
                else:
                    perms = check.__closure__[0].cell_contents

        if perms:
            keys = [key.replace("_", " ").title() for key in list(perms.keys())]
            embed.add_field(name="Required Permissions", value=f"* {f' {nl}* '.join(keys)}", inline=False)

        if bot_perms:
            keys = [key.replace("_", " ").title() for key in list(bot_perms.keys())]
            embed.add_field(name="Bot's Required Permissions", value=f"* {f' {nl}* '.join(keys)}", inline=False)

        if guild_only:
            assert isinstance(embed.title, str)
            embed.title += " [Server Only]"

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
        embed.set_footer(text="< > = required | [ ] = optional")

        await self.get_destination().send(embed=embed)

    async def send_cog_help(self, cog: Cog) -> None:
        embeds: list[Embed] = []

        for chnk in utils.as_chunks(cog.get_commands(), 5):
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
