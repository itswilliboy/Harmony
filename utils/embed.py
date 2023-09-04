from discord import Colour, Embed


class PrimaryEmbed(Embed):
    def __init__(self, *args, **kwargs) -> None:
        colour = Colour.from_str("#6441A5")
        super().__init__(colour=colour, *args, **kwargs)


class SuccessEmbed(Embed):
    def __init__(self, *args, **kwargs) -> None:
        colour = Colour.from_str("#1DB954")
        super().__init__(colour=colour, *args, **kwargs)


class ErrorEmbed(Embed):
    def __init__(self, *args, **kwargs) -> None:
        colour = Colour.from_str("#FF0000")
        super().__init__(colour=colour, *args, **kwargs)
