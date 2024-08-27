from typing import Any

from discord import Colour, Embed

__all__ = ("PrimaryEmbed", "SuccessEmbed", "ErrorEmbed")

class PrimaryEmbed(Embed):
    """Primary embed with a purple colour."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        colour = Colour.from_str("#6441A5")
        super().__init__(colour=colour, *args, **kwargs)


class SuccessEmbed(Embed):
    """Success embed with a green colour."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        colour = Colour.from_str("#1DB954")
        super().__init__(colour=colour, *args, **kwargs)


class ErrorEmbed(Embed):
    """Error (fail) embed with a red colour."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        colour = Colour.from_str("#FF0000")
        super().__init__(colour=colour, *args, **kwargs)
