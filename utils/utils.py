from typing import Any, Generator, TypeVar

T = TypeVar("T")

def chunk(list: list[T], size: int) -> Generator[list[T], Any, None]:
    for i in range(0, len(list), size):
        yield list[i : i + size]