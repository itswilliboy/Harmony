import discord
from asyncache import cached  # pyright: ignore[reportMissingTypeStubs]
from cachetools import TTLCache
from discord import app_commands

__all__ = ("ban_entry_autocomplete",)


@cached(TTLCache(1000, 60))
async def get_ban_entries(guild: discord.Guild) -> list[discord.BanEntry]:
    return [ban async for ban in guild.bans(limit=None)]


async def ban_entry_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    assert interaction.guild
    entries = await get_ban_entries(interaction.guild)

    return [
        app_commands.Choice(name=entry.user.name, value=str(entry.user.id))
        for entry in entries
        if current.lower() in entry.user.name.lower()
    ][:25]
