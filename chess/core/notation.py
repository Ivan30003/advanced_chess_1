"""Упрощённая координатная нотация журнала ходов.

Поддерживаются обычные ходы, взятия, рокировка, превращение и порталы:
``e2-e4``, ``e4xd5``, ``O-O``, ``O-O-O``, ``e7-e8=Q``,
``a1-a4~h4-h8`` (телепорт с продолжением) и ``b3~g6-g7`` (свободный
выход и ход). Если ход просто заканчивается на портале без активации,
запись остаётся обычной.
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

    activation = move.teleport
    if activation is not None:
        text = (
            f"{move.from_square.name}-{activation.entry.name}"
            f"~{activation.exit.name}"
        )
        if move.to_square != activation.exit:
            separator = "x" if move.capture is not None else "-"
            text += f"{separator}{move.to_square.name}"
        if move.promotion is not None:
            text += f"={PROMOTION_LETTERS[move.promotion]}"
        return text

    separator = "x" if move.is_capture else "-"
    text = f"{move.from_square.name}{separator}{move.to_square.name}"
    if move.promotion is not None:
        text += f"={PROMOTION_LETTERS[move.promotion]}"
    return text


def _free_exit_text(move: Move, prefix: str) -> str:
    """Добавляет к записи хода префикс свободного выхода."""

    text = format_move(move)
    from_name = move.from_square.name
    if text.startswith(from_name):
        text = text[len(from_name) :]
    return prefix + text


def format_turn(state_before: "GameState", turn: Turn, state_after: "GameState") -> str:
    """Строка журнала для одного действия стороны.

    ``state_before`` и ``state_after`` оставлены в сигнатуре для будущих
    составных действий и специальных механик.
    """

    del state_before, state_after
    parts: list[str] = []
    prefix = ""
    if turn.free_teleport is not None:
        prefix = (
            f"{turn.free_teleport.entry.name}~"
            f"{turn.free_teleport.exit.name}"
        )

    for index, move in enumerate(turn.moves):
        if index == 0 and prefix:
            parts.append(_free_exit_text(move, prefix))
            prefix = ""
        else:
            parts.append(format_move(move))

    if prefix:
        parts.append(prefix)
    return ", ".join(parts)
