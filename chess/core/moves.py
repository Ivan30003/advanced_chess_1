"""Объекты ходов и составного действия (Turn).

На этапе 2 Turn содержит ровно один ход. Поля ``bless`` и ``freeze`` оставлены
для будущих этапов, чтобы не менять структуру данных.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chess.core.coords import Square
from chess.core.pieces import Piece, PieceType


@dataclass(frozen=True)
class Move:
    """Один ход фигуры."""

    piece_id: str
    from_square: Square
    to_square: Square
    capture: Piece | None = None
    promotion: PieceType | None = None
    castle: str | None = None  # "K" — короткая, "Q" — длинная
    en_passant: bool = False
    is_double: bool = False
    teleport: object | None = None
    pass_through: bool = False

    @property
    def is_capture(self) -> bool:
        return self.capture is not None or self.en_passant

    @property
    def is_promotion(self) -> bool:
        return self.promotion is not None

    @property
    def is_castle(self) -> bool:
        return self.castle is not None


@dataclass
class Turn:
    """Действие стороны. На этапе 2 — ровно один :class:`Move`."""

    moves: list[Move] = field(default_factory=list)
    bless: object | None = None
    freeze: object | None = None

    @classmethod
    def single(cls, move: Move) -> "Turn":
        return cls(moves=[move])

    @property
    def move(self) -> Move:
        if len(self.moves) != 1:
            raise ValueError("На этапе 2 Turn должен содержать ровно один ход")
        return self.moves[0]


def make_move(
    piece: Piece,
    to_square: Square,
    *,
    capture: Piece | None = None,
    promotion: PieceType | None = None,
    castle: str | None = None,
    en_passant: bool = False,
    is_double: bool = False,
) -> Move:
    """Удобная фабрика ходов для правил и тестов."""

    return Move(
        piece_id=piece.id,
        from_square=piece.square,
        to_square=to_square,
        capture=capture,
        promotion=promotion,
        castle=castle,
        en_passant=en_passant,
        is_double=is_double,
    )


def make_turn(move: Move) -> Turn:
    return Turn.single(move)
