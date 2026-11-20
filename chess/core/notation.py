"""Упрощённая координатная нотация журнала ходов.

На этапе 2 поддерживаются обычные ходы, взятия, рокировка и превращение:
``e2-e4``, ``e4xd5``, ``O-O``, ``O-O-O``, ``e7-e8=Q``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chess.core.moves import Move, Turn
from chess.core.pieces import PROMOTION_LETTERS

if TYPE_CHECKING:  # pragma: no cover
    from chess.core.game_state import GameState


def format_move(move: Move) -> str:
    if move.castle == "K":
        return "O-O"
    if move.castle == "Q":
        return "O-O-O"

    separator = "x" if move.is_capture else "-"
    text = f"{move.from_square.name}{separator}{move.to_square.name}"
    if move.promotion is not None:
        text += f"={PROMOTION_LETTERS[move.promotion]}"
    return text


def format_turn(state_before: "GameState", turn: Turn, state_after: "GameState") -> str:
    """Строка журнала для одного действия стороны.

    ``state_before`` и ``state_after`` оставлены в сигнатуре для будущих
    составных действий и специальных механик.
    """

    del state_before, state_after
    return ", ".join(format_move(move) for move in turn.moves)
