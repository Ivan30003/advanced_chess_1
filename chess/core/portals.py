"""Порталы: пары клеток, активации и генерация раскладки.

Модуль чистый и не импортирует pygame. Порталы описываются неизменяемыми
парами клеток; активация — это переход с входа пары на её выход. За один ход
разрешена не более одной активации, поэтому активация хранится прямо в
объектах :class:`chess.core.moves.Move` и :class:`chess.core.moves.Turn`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Sequence

from chess.core.board import Board
from chess.core.coords import Square

MAX_PORTAL_PAIRS = 3
PORTAL_COLOR_COUNT = 3
PORTAL_SYMBOL_COUNT = 3


@dataclass(frozen=True)
class PortalPair:
    """Пара связанных клеток.

    ``color_index`` и ``symbol_index`` задают визуальный стиль пары. Клетки
    ``a`` и ``b`` различны и не могут одновременно принадлежать другой паре.
    """

    id: int
    color_index: int
    symbol_index: int
    a: Square
    b: Square

    def __post_init__(self) -> None:
        if self.a == self.b:
            raise ValueError("Клетки портала должны быть различны")

    def contains(self, square: Square) -> bool:
        return square == self.a or square == self.b

    def other(self, square: Square) -> Square | None:
        """Парная клетка или ``None``, если клетка не принадлежит паре."""

        if square == self.a:
            return self.b
        if square == self.b:
            return self.a
        return None

    @property
    def squares(self) -> tuple[Square, Square]:
        return self.a, self.b


@dataclass(frozen=True)
class PortalActivation:
    """Одна активация портала: вход и выход конкретной пары."""

    pair_id: int
    entry: Square
    exit: Square

    def __post_init__(self) -> None:
        if self.entry == self.exit:
            raise ValueError("Вход и выход портала должны быть различны")


class PortalSet:
    """Упорядоченный набор пар с быстрым поиском по клетке."""

    def __init__(self, pairs: Iterable[PortalPair] = ()) -> None:
        self.pairs: tuple[PortalPair, ...] = tuple(pairs)
        self._by_square: dict[Square, PortalPair] = {}
        self._by_id: dict[int, PortalPair] = {}
        for pair in self.pairs:
            if pair.id in self._by_id:
                raise ValueError(f"Повторяющийся id портала: {pair.id}")
            self._by_id[pair.id] = pair
            for square in pair.squares:
                if square in self._by_square:
                    raise ValueError(
                        f"Клетка {square.name} входит в две пары порталов"
                    )
                self._by_square[square] = pair

    def portal_at(self, square: Square) -> PortalPair | None:
        return self._by_square.get(square)

    def paired_square(self, square: Square) -> Square | None:
        pair = self.portal_at(square)
        return pair.other(square) if pair is not None else None

    def pair_by_id(self, pair_id: int) -> PortalPair | None:
        return self._by_id.get(pair_id)

    def activation_from(self, entry: Square) -> PortalActivation | None:
        pair = self.portal_at(entry)
        if pair is None:
            return None
        return PortalActivation(pair.id, entry, pair.other(entry))  # type: ignore[arg-type]

    def __iter__(self):
        return iter(self.pairs)

    def __len__(self) -> int:
        return len(self.pairs)

    def __bool__(self) -> bool:
        return bool(self.pairs)

    def __contains__(self, square: Square) -> bool:
        return square in self._by_square


def portal_at(
    portals: PortalSet | Sequence[PortalPair],
    square: Square,
) -> PortalPair | None:
    """Возвращает пару, которой принадлежит клетка."""

    if isinstance(portals, PortalSet):
        return portals.portal_at(square)
    for pair in portals:
        if pair.contains(square):
            return pair
    return None


def paired_square(
    portals: PortalSet | Sequence[PortalPair],
    square: Square,
) -> Square | None:
    """Возвращает парную клетку или ``None``."""

    pair = portal_at(portals, square)
    return pair.other(square) if pair is not None else None


def coerce_rng(rng: random.Random | int | None) -> random.Random:
    """Приводит seed/``random.Random``/``None`` к генератору."""

    if rng is None:
        return random.Random()
    if isinstance(rng, random.Random):
        return rng
    if isinstance(rng, int):
        return random.Random(rng)
    raise TypeError("rng должен быть random.Random, int или None")


def generate_portals(
    board: Board,
    count: int,
    rng: random.Random | int | None = None,
) -> list[PortalPair]:
    """Случайно размещает ``count`` пар порталов на свободных клетках.

    Клетки выбираются только из внутренних рядов (не первый и не последний
    ранг), не занятые фигурами на момент генерации. Пары не пересекаются и
    получают разные индексы цвета и символа. Одинаковый seed даёт одинаковую
    раскладку.
    """

    if not isinstance(count, int) or not 0 <= count <= MAX_PORTAL_PAIRS:
        raise ValueError("Количество пар порталов должно быть от 0 до 3")
    if count == 0:
        return []

    size = board.config.size
    candidates = [
        square
        for square in board.config.squares()
        if 0 < square.rank < size - 1 and board.is_empty(square)
    ]
    needed = count * 2
    if len(candidates) < needed:
        raise ValueError(
            "Недостаточно свободных внутренних клеток для выбранного "
            "количества порталов"
        )

    source = coerce_rng(rng)
    chosen = source.sample(candidates, needed)
    pairs: list[PortalPair] = []
    for index in range(count):
        pairs.append(
            PortalPair(
                id=index,
                color_index=index % PORTAL_COLOR_COUNT,
                symbol_index=index % PORTAL_SYMBOL_COUNT,
                a=chosen[index * 2],
                b=chosen[index * 2 + 1],
            )
        )
    return pairs
