import discord
from discord.ext import commands
from discord.ext.commands import Context as DiscordContext

from bot import Harmony


class Context(DiscordContext[Harmony]):
    guild: discord.Guild
    command: commands.Command
