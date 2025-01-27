from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from textwrap import dedent
from traceback import format_exception
from typing import TYPE_CHECKING, Literal, Optional, Self

import discord
from asyncpg import Record
from discord import ui
from discord.ext import commands

from utils import BaseCog, BaseView, Context, GenericError, Paginator

if TYPE_CHECKING:
    from bot import Harmony

    Interaction = discord.Interaction[Harmony]


class Status(Enum):
    IDLE = False
    IN_PROGRESS = None
    DONE = True


@dataclass
class ErrorReport:
    id: int
    guild_id: Optional[int]
    channel_id: int
    message_id: int
    message_content: str
    author_id: int
    traceback: str
    timestamp: datetime.datetime
    _status: Optional[bool]

    bot: Harmony

    @classmethod
    def from_record(cls, bot: Harmony, record: Record) -> Self:
        return cls(
            record["id"],
            record.get("guild_id"),
            record["channel_id"],
            record["message_id"],
            record["message_content"],
            record["author_id"],
            record["traceback"],
            record["timestamp"],
            record["status"],
            bot,
        )

    @property
    def status(self) -> Status:
        return Status(self._status)

    async def set_status(self, status: Status) -> None:
        await self.bot.pool.execute("UPDATE error_reports SET status = $1 WHERE id = $2", status.value, self.id)
        self._status = status.value

    def get_colour(self) -> discord.Colour:
        """Returns an embed colour based on the current status."""

        if self.status == Status.IDLE:
            return discord.Colour.from_str("#FF0000")

        elif self.status == Status.IN_PROGRESS:
            return discord.Colour.yellow()

        else:
            return discord.Colour.from_str("#1db954")

    def embed(self) -> discord.Embed:
        bot = self.bot
        embed = discord.Embed(colour=self.get_colour(), timestamp=self.timestamp)
        embed.set_footer(text=f"ID: {self.id}")

        channel = bot.get_channel(self.channel_id)

        message: Optional[discord.PartialMessage] = None
        if channel is not None:
            assert not isinstance(
                channel, discord.DMChannel | discord.ForumChannel | discord.CategoryChannel | discord.abc.PrivateChannel
            )
            message = channel.get_partial_message(self.message_id)

        desc = f"""
            Author: <@{self.author_id}>
            Guild: {self.bot.get_guild(self.guild_id) if self.guild_id else None}
            Channel: {channel.jump_url if (channel and not isinstance(channel, discord.abc.PrivateChannel)) else None}
            Message: {message.jump_url if message else None}

            Traceback:
            ```py\n{self.traceback}\n```
        """

        embed.description = dedent(desc)
        return embed


class StatusView(BaseView):
    def __init__(self, report: ErrorReport, author: discord.abc.Snowflake) -> None:
        super().__init__(author)

        self.report = report
        self.update_state()

    def update_state(self) -> None:
        report = self.report

        self.idle.disabled = False
        self.in_progress.disabled = False
        self.done.disabled = False

        if report.status == Status.IDLE:
            self.idle.disabled = True

        elif report.status == Status.IN_PROGRESS:
            self.in_progress.disabled = True

        elif report.status == Status.DONE:
            self.done.disabled = True

    async def set_status(self, status: Status, interaction: Interaction) -> None:
        await self.report.set_status(status)
        self.update_state()
        await interaction.response.edit_message(embed=self.report.embed(), view=self)

    @ui.button(label="Idle", style=discord.ButtonStyle.red)
    async def idle(self, interaction: Interaction, _):
        await self.set_status(Status.IDLE, interaction)

    @ui.button(label="In Progress", style=discord.ButtonStyle.blurple)
    async def in_progress(self, interaction: Interaction, _):
        await self.set_status(Status.IN_PROGRESS, interaction)

    @ui.button(label="Done", style=discord.ButtonStyle.green)
    async def done(self, interaction: Interaction, _):
        await self.set_status(Status.DONE, interaction)


class ReportPaginator(Paginator[discord.Embed], StatusView):
    def __init__(self, reports: list[ErrorReport], embeds: list[discord.Embed], author: discord.abc.Snowflake) -> None:
        self.reports = reports
        self.author = author

        StatusView.__init__(self, reports[0], author)
        Paginator.__init__(self, embeds, author)  # type: ignore

        self.position_items()

    async def on_page_switch(self):
        StatusView.__init__(self, self.reports[self.page], self.author)
        self.position_items()

    def position_items(self) -> None:
        for i, item in enumerate(self.children):
            if i < 3:
                item._row = 4
                item._rendered_row = 4

            else:
                item._row = 0
                item._rendered_row = 0


class Reporting(BaseCog):
    async def create_report(self, ctx: Context, error: Exception) -> int:
        query = """
            INSERT INTO error_reports
                (guild_id, channel_id, message_id, message_content, author_id, traceback, status)
            VALUES
                ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """

        return await self.bot.pool.fetchval(
            query,
            ctx.guild and ctx.guild.id,
            ctx.channel.id,
            ctx.message.id,
            ctx.message.content,
            ctx.author.id,
            "".join(format_exception(error)),
            Status.IDLE.value,
        )

    async def get_report(self, id: int) -> Optional[ErrorReport]:
        record = await self.bot.pool.fetchrow("SELECT * FROM error_reports WHERE id = $1", id)
        return ErrorReport.from_record(self.bot, record) if record else None

    async def get_reports(self, *, status: Optional[Status] = None) -> list[ErrorReport]:
        if status is None:
            records = await self.bot.pool.fetch("SELECT * FROM error_reports ORDER BY id ASC")
            return [ErrorReport.from_record(self.bot, record) for record in records]

        else:
            records = await self.bot.pool.fetch(
                "SELECT * FROM error_reports WHERE status = $1 ORDER BY id ASC", status.value
            )
            return [ErrorReport.from_record(self.bot, record) for record in records]

    async def get_next(self, status: Literal[Status.IDLE, Status.IN_PROGRESS]) -> Optional[ErrorReport]:
        query = f"""
            SELECT * FROM error_reports
            WHERE
                status {"= false" if status == Status.IDLE else "IS NULL"}
            ORDER BY id ASC
            LIMIT 1
        """

        record = await self.bot.pool.fetchrow(query)
        return ErrorReport.from_record(self.bot, record) if record else None

    @commands.is_owner()
    @commands.group(hidden=True, aliases=["er"])
    async def error(self, _: Context):
        pass

    @error.command(aliases=["s"])
    async def show(self, ctx: Context, id: int):
        report = await self.get_report(id)

        if report is None:
            raise GenericError("No report with that ID.")

        view = StatusView(report, ctx.author)
        view.message = await ctx.send(embed=report.embed(), view=view)

    @error.command(aliases=["l"])
    async def list(self, ctx: Context):
        await ctx.typing()
        reports = await self.get_reports()

        embeds = [report.embed() for report in reports]

        if not embeds:
            raise GenericError("There aren't any reports to display.")

        await ReportPaginator(reports, embeds, ctx.author).start(ctx)

    @error.command()
    async def next(self, ctx: Context, in_progress: bool = False):
        report = await self.get_next(Status.IN_PROGRESS if in_progress else Status.IDLE)

        if report is None:
            raise GenericError("Couldn't find any reports with that criteria.")

        view = StatusView(report, ctx.author)
        view.message = await ctx.send(embed=report.embed(), view=view)
