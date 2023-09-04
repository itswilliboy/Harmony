from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord.ext import commands

from utils import BaseCog, ErrorEmbed

from ..developer import NotOwner

if TYPE_CHECKING:
    from bot import Harmony
    from utils import Context


class ErrorHandler(BaseCog, command_attrs=dict(hidden=True)):
    def __init__(self, bot: Harmony) -> None:
        super().__init__(bot)
        self.bot = bot

    @staticmethod
    def underline(text: str, target: str) -> str:
        words = text.split()
        underline = ""

        for word in words:
            if word == target:
                position = text.find(word)
                underline += " " * position + "^" * len(word)

        return f"{text}\n{underline}"

    @staticmethod
    def get_signature(ctx: Context) -> str:
        base = f"{ctx.clean_prefix}{ctx.command.name}"
        if usage := ctx.command.usage:
            return f"{base} {usage}"
        return f"{base} {ctx.command.signature}"

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error: Any):
        command = ctx.command

        if isinstance(error, commands.CommandNotFound):
            return await ctx.message.add_reaction("\u2753")

        elif isinstance(error, commands.MissingPermissions):
            missing = error.missing_permissions
            to_list = [f"`{i.replace('_', ' ').title()}`" for i in missing]
            nl = "\n"
            description = f"""
                You are missing the following permissions to use this commands:
                * {f' {nl}* '.join(to_list)}
            """

            embed = ErrorEmbed(title="Missing Permissions", description=description)

        elif isinstance(error, commands.MissingRequiredArgument):
            underlined = self.underline(f"{ctx.clean_prefix}{command.name} {command.signature}", f"<{error.param.name}>")
            embed = ErrorEmbed(
                title="Missing a Required Argument",
                description=f"`{error.param.name}` is a required argument that is missing.\n```\n{underlined}\n```",
            )
            embed.set_footer(text="'<>' = required | '[]' = optional")

        elif isinstance(error, commands.BadArgument):
            usage = self.get_signature(ctx)
            embed = ErrorEmbed(title="Bad Argument", description=f"Correct usage:\n```\n{usage}\n```")

        elif isinstance(error, (commands.NotOwner, NotOwner)):
            embed = ErrorEmbed(title="Owner Only", description="Only bot developers can use this command.")

        else:
            embed = ErrorEmbed(description="An unknown error occured")
            raise error

        embed.set_footer(text=f"If this was unexpected, please contact the developer ({ctx.clean_prefix}support).")
        await ctx.send(embed=embed)
