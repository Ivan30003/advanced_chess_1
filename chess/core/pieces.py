"""Базовые перечисления проекта.

Модуль намеренно не импортирует pygame: это чистые игровые типы, которые
используются и ядром, и интерфейсом.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from chess.core.blessings import (
    BLESSING_INFO,
    BlessingInfo,
    BlessingType,
    blessing_info,
)
from chess.core.coords import Square


class Color(Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def opposite(self) -> "Color":
        return Color.BLACK if self is Color.WHITE else Color.WHITE

    @property
    def display_name(self) -> str:
        return "Белые" if self is Color.WHITE else "Чёрные"


class PieceType(Enum):
    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"

    @property
    def display_name(self) -> str:
        names = {
            PieceType.PAWN: "Пешка",
            PieceType.KNIGHT: "Конь",
            PieceType.BISHOP: "Слон",
            PieceType.ROOK: "Ладья",
            PieceType.QUEEN: "Ферзь",
            PieceType.KING: "Король",
        }
        return names[self]

    @property
    def letter(self) -> str:
        """Латинская буква фигуры для нотации: K, Q, R, B, N, P."""

        return {
            PieceType.PAWN: "P",
            PieceType.KNIGHT: "N",
            PieceType.BISHOP: "B",
            PieceType.ROOK: "R",
            PieceType.QUEEN: "Q",
            PieceType.KING: "K",
        }[self]


PROMOTION_PIECES: tuple[PieceType, ...] = (
    PieceType.QUEEN,
    PieceType.ROOK,
    PieceType.BISHOP,
    PieceType.KNIGHT,
)

PROMOTION_LETTERS: dict[PieceType, str] = {
    PieceType.QUEEN: "Q",
    PieceType.ROOK: "R",
    PieceType.BISHOP: "B",
    PieceType.KNIGHT: "N",
}


@dataclass(frozen=True)
class Piece:
    """Фигура на доске.

    ``id`` стабилен на всю партию и позволяет отслеживать фигуру даже после
    превращения. ``original_square`` — клетка начальной расстановки. Объект
    неизменяемый: при ходе создаётся новая копия через :meth:`moved_to` или
    :meth:`promoted_to`.
    """

    id: str
    type: PieceType
    color: Color
    square: Square
    original_square: Square
    has_moved: bool = False
    blessing: BlessingType | None = None
    ever_blessed: bool = False
    blessing_used: bool = False

    def moved_to(self, square: Square) -> "Piece":
        return replace(self, square=square, has_moved=True)

    def promoted_to(self, piece_type: PieceType) -> "Piece":
        return replace(self, type=piece_type, has_moved=True)

    def blessed_with(self, blessing: BlessingType) -> "Piece":
        return replace(self, blessing=blessing, ever_blessed=True, blessing_used=False)

    def blessing_spent(self) -> "Piece":
        return replace(self, blessing=None, blessing_used=True)

    @property
    def is_slider(self) -> bool:
        return self.type in (PieceType.BISHOP, PieceType.ROOK, PieceType.QUEEN)

    def __str__(self) -> str:  # pragma: no cover - отладочный вывод
        color = "w" if self.color is Color.WHITE else "b"
        return f"{color}{self.type.letter}@{self.square.name}"



__all__ = [
    "BLESSING_INFO",
    "BlessingInfo",
    "BlessingType",
    "Color",
    "PROMOTION_LETTERS",
    "PROMOTION_PIECES",
    "Piece",
    "PieceType",
    "blessing_info",
]
