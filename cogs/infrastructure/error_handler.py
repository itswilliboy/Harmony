from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utils import BaseCog, ErrorEmbed, GenericError, get_command_signature

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class ErrorHandler(BaseCog):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)

    @staticmethod
    def underline(text: str, target: str) -> str:
        words = text.split()
        underline = ""

        for word in words:
            if word == target:
                position = text.find(word)
                underline += " " * position + "^" * len(word)

        return f"{text}\n{underline}"

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error: Exception):
        if ctx.is_blacklisted():
            return

        command = ctx.command

        try:
            error = error.original  # type: ignore
        except AttributeError:
            pass

        if isinstance(error, commands.CommandNotFound):
            return await ctx.message.add_reaction("\N{BLACK QUESTION MARK ORNAMENT}")

        elif isinstance(error, commands.MissingPermissions):
            missing = error.missing_permissions
            to_list = [f"`{i.replace('_', ' ').title()}`" for i in missing]
            nl = "\n"
            description = f"""
                You are missing the following permissions to use this command:
                * {f' {nl}* '.join(to_list)}
            """

            embed = ErrorEmbed(title="Missing Permissions", description=description)

        elif isinstance(error, commands.BotMissingPermissions):
            missing = error.missing_permissions
            to_list = [f"`{i.replace('_', ' ').title()}`" for i in missing]
            nl = "\n"
            description = f"""
                I am missing the following permissions:
                * {f' {nl}* '.join(to_list)}
            """

            embed = ErrorEmbed(title="Bot Missing Permissions", description=description)

        elif isinstance(error, discord.Forbidden):
            embed = ErrorEmbed(
                title="Forbidden",
                description=(
                    "I'm missing permissions to perform this action, \
                              please make sure I have the correct permissions."
                ),
            )

        elif isinstance(error, commands.MissingRequiredArgument):
            underlined = self.underline(f"{ctx.clean_prefix}{command.name} {command.signature}", f"<{error.param.name}>")
            embed = ErrorEmbed(
                title="Missing a Required Argument",
                description=f"`{error.param.name}` is a required argument that is missing.\n```\n{underlined}\n```",
            )
            embed.set_footer(text="< > = required | [ ] = optional")

        elif isinstance(error, commands.BadUnionArgument):
            usage = get_command_signature(ctx)
            embed = ErrorEmbed(
                title="Bad Argument", description=f"Correct usage:\n```\n{usage}\n```\n`{str(error.errors[-1])}`"
            )
            embed.set_footer(text="< > = required | [ ] = optional")

        elif isinstance(error, commands.BadArgument):
            usage = get_command_signature(ctx)
            embed = ErrorEmbed(title="Bad Argument", description=f"Correct usage:\n```\n{usage}\n```")  # type: ignore
            embed.set_footer(text="< > = required | [ ] = optional")

            if msgs := error.args:
                embed.description += f"\n`{msgs[0]}`"  # type: ignore

        elif isinstance(error, commands.NotOwner):
            embed = ErrorEmbed(title="Owner Only", description="Only bot developers can use this command.")

        elif isinstance(error, GenericError):
            embed = ErrorEmbed(description=f"{error!s}")

        elif isinstance(error, commands.NoPrivateMessage):
            embed = ErrorEmbed(description="This command can only be used inside of a server.")

        elif isinstance(error, commands.CheckFailure) and str(error) == "The global check once functions failed.":
            return

        elif isinstance(error, commands.RangeError):
            embed = ErrorEmbed(
                description=f"The value (`{error.value}`) needs to between `{error.minimum}`-`{error.maximum}`"
            )

        elif isinstance(error, commands.DisabledCommand):
            embed = ErrorEmbed(description="This command is currently disabled.")

        else:
            embed = ErrorEmbed(description="An unknown error occurred")
            self.bot.log.error("In %s: %s", ctx.command, error, exc_info=error)

        if not embed.footer:
            if isinstance(error, GenericError) and error.footer:
                embed.set_footer(text=f"If this was unexpected, please contact the developer ({ctx.clean_prefix}support).")

        await ctx.send(embed=embed)
