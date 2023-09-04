from discord.ext import commands

from utils import PrimaryEmbed


class HelpCommand(commands.MinimalHelpCommand):
    async def send_pages(self) -> None:
        destination = self.get_destination()
        for page in self.paginator.pages:
            embed = PrimaryEmbed(description=page)
            await destination.send(embed=embed)
