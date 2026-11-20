"""Координаты клеток доски.

Поддерживаются доски 6×6, 8×8 и 10×10. Файлы нумеруются слева направо от
``a`` (0) до ``j`` (9), ранги — снизу вверх от 1 (0) до 10 (9). Белые всегда
находятся снизу. Модуль не зависит от pygame и не знает о правилах игры.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_BOARD_SIZE = 10
FILES = "abcdefghij"


@dataclass(frozen=True)
class Square:
    """Клетка доски.

    ``file`` и ``rank`` — целые индексы от 0 до 9. Класс неизменяемый и
    хешируемый, поэтому его можно использовать как ключ словаря. Принадлежность
    конкретной доске проверяется через :class:`BoardConfig`.
    """

    file: int
    rank: int

    def __post_init__(self) -> None:
        if not (0 <= self.file < MAX_BOARD_SIZE and 0 <= self.rank < MAX_BOARD_SIZE):
            raise ValueError(f"Клетка вне допустимого диапазона: file={self.file}, rank={self.rank}")

    @property
    def name(self) -> str:
        """Координатное имя клетки, например ``e2`` или ``j10``."""

        return f"{FILES[self.file]}{self.rank + 1}"

    @property
    def is_light(self) -> bool:
        """Светлая ли клетка (a1 — тёмная)."""

        return (self.file + self.rank) % 2 == 1

    def offset(self, file_delta: int, rank_delta: int) -> "Square | None":
        """Возвращает соседнюю клетку или ``None``, если вышли за доску."""

        file = self.file + file_delta
        rank = self.rank + rank_delta
        if 0 <= file < MAX_BOARD_SIZE and 0 <= rank < MAX_BOARD_SIZE:
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
        """Разбирает координату вида ``e2`` или ``j10``."""

        text = name.strip().lower()
        if len(text) < 2 or text[0] not in FILES or not text[1:].isdigit():
            raise ValueError(f"Некорректная координата: {name!r}")
        rank_number = int(text[1:])
        if not 1 <= rank_number <= MAX_BOARD_SIZE:
            raise ValueError(f"Некорректная координата: {name!r}")
        return cls(FILES.index(text[0]), rank_number - 1)

    @classmethod
    def from_indices(cls, file: int, rank: int) -> "Square":
        return cls(file, rank)

    def __str__(self) -> str:  # pragma: no cover - тривиальный вывод
        return self.name


def squares_for_size(size: int) -> tuple[Square, ...]:
    if not 1 <= size <= MAX_BOARD_SIZE:
        raise ValueError(f"Недопустимый размер доски: {size}")
    return tuple(Square(file, rank) for rank in range(size) for file in range(size))


# Исторический набор 64 клеток: используется тестами и кодом по умолчанию.
ALL_SQUARES: tuple[Square, ...] = squares_for_size(8)


def parse_square(name: str) -> Square:
    """Функциональная обёртка над :meth:`Square.from_name`."""

    return Square.from_name(name)


def is_valid_square(file: int, rank: int, size: int = MAX_BOARD_SIZE) -> bool:
    return 0 <= file < size and 0 <= rank < size
