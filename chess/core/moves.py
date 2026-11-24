"""Объекты ходов и составного действия (Turn).

Turn описывает одно действие стороны: обычный ход, свободный выход из
портала, двойной ход благословлённой фигуры, благословение или заморозку.
Благословение и заморозка не содержат ходов фигур и выполняются вместо хода.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chess.core.blessings import BlessAction, FreezeAction
from chess.core.coords import Square
from chess.core.pieces import Piece, PieceType
from chess.core.portals import PortalActivation


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
    teleport: PortalActivation | None = None
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

    @property
    def is_teleport(self) -> bool:
        return self.teleport is not None


@dataclass
class Turn:
    """Действие стороны.

    ``free_teleport`` — необязательный свободный выход в начале хода. Он
    выполняется до основного действия и расходует единственную активацию
    портала за ход, поэтому не может сочетаться с ``Move.teleport``.
    """

    moves: list[Move] = field(default_factory=list)
    free_teleport: PortalActivation | None = None
    bless: BlessAction | None = None
    freeze: FreezeAction | None = None

    @classmethod
    def single(cls, move: Move) -> "Turn":
        return cls(moves=[move])

    @property
    def move(self) -> Move:
        if len(self.moves) != 1:
            raise ValueError("Turn должен содержать ровно один основной ход")
        return self.moves[0]

    @property
    def is_bless(self) -> bool:
        return self.bless is not None

    @property
    def is_freeze(self) -> bool:
        return self.freeze is not None

    @property
    def is_double_move(self) -> bool:
        return len(self.moves) == 2

    @property
    def portal_activation_count(self) -> int:
        return int(self.free_teleport is not None) + sum(
            1 for move in self.moves if move.teleport is not None
        )


def make_move(
    piece: Piece,
    to_square: Square,
    *,
    capture: Piece | None = None,
    promotion: PieceType | None = None,
    castle: str | None = None,
    en_passant: bool = False,
    is_double: bool = False,
    teleport: PortalActivation | None = None,
    pass_through: bool = False,
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
        teleport=teleport,
        pass_through=pass_through,
    )


def make_turn(move: Move) -> Turn:
    return Turn.single(move)
