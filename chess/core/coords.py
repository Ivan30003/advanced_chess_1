"""Координаты клеток доски 8x8.

Файлы нумеруются слева направо от ``a`` (0) до ``h`` (7), ранги — снизу
вверх от 1 (0) до 8 (7). Белые всегда находятся снизу. Модуль не зависит от
pygame и не знает о правилах игры.
"""

from __future__ import annotations

from dataclasses import dataclass

BOARD_SIZE = 8
FILES = "abcdefgh"
RANKS = "12345678"


@dataclass(frozen=True)
class Square:
    """Клетка доски.

    ``file`` и ``rank`` — целые индексы от 0 до 7. Класс неизменяемый и
    хешируемый, поэтому его можно использовать как ключ словаря.
    """

    file: int
    rank: int

    def __post_init__(self) -> None:
        if not (0 <= self.file < BOARD_SIZE and 0 <= self.rank < BOARD_SIZE):
            raise ValueError(f"Клетка вне доски: file={self.file}, rank={self.rank}")

    @property
    def name(self) -> str:
        """Координатное имя клетки, например ``e2``."""

        return f"{FILES[self.file]}{self.rank + 1}"

    @property
    def is_light(self) -> bool:
        """Светлая ли клетка (a1 — тёмная)."""

        return (self.file + self.rank) % 2 == 1

    def offset(self, file_delta: int, rank_delta: int) -> "Square | None":
        """Возвращает соседнюю клетку или ``None``, если вышли за доску."""

        file = self.file + file_delta
        rank = self.rank + rank_delta
        if 0 <= file < BOARD_SIZE and 0 <= rank < BOARD_SIZE:
            return Square(file, rank)
        return None

    def shifted(self, file_delta: int, rank_delta: int) -> "Square":
        """Как :meth:`offset`, но выбрасывает исключение за границей доски."""

        square = self.offset(file_delta, rank_delta)
        if square is None:
            raise ValueError(
                f"Смещение ({file_delta}, {rank_delta}) выводит за доску: {self.name}"
            )
        return square

    @classmethod
    def from_name(cls, name: str) -> "Square":
        """Разбирает координату вида ``e2``."""

        text = name.strip().lower()
        if len(text) != 2 or text[0] not in FILES or text[1] not in RANKS:
            raise ValueError(f"Некорректная координата: {name!r}")
        return cls(FILES.index(text[0]), RANKS.index(text[1]))

    @classmethod
    def from_indices(cls, file: int, rank: int) -> "Square":
        return cls(file, rank)

    def __str__(self) -> str:  # pragma: no cover - тривиальный вывод
        return self.name


ALL_SQUARES: tuple[Square, ...] = tuple(
    Square(file, rank) for rank in range(BOARD_SIZE) for file in range(BOARD_SIZE)
)


def parse_square(name: str) -> Square:
    """Функциональная обёртка над :meth:`Square.from_name`."""

    return Square.from_name(name)


def is_valid_square(file: int, rank: int) -> bool:
    return 0 <= file < BOARD_SIZE and 0 <= rank < BOARD_SIZE
