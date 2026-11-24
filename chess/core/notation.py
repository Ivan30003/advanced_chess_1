"""Упрощённая координатная нотация журнала ходов.

Поддерживаются обычные ходы, взятия, рокировка, превращение, порталы,
проход сквозь фигуры, благословения, заморозка и двойной ход:
``e2-e4``, ``e4xd5``, ``O-O``, ``e7-e8=Q``, ``a1-a4~h4-h8``,
``b3~g6-g7``, ``e2-e6*`` (проход), ``b1: благословение d2``,
``Заморозка: d4, e5`` и ``g1-f3 + f3xd4``. Отменённое щитом взятие
помечается отдельно.
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

    suffix = "*" if move.pass_through else ""
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
        return text + suffix

    separator = "x" if move.is_capture else "-"
    text = f"{move.from_square.name}{separator}{move.to_square.name}"
    if move.promotion is not None:
        text += f"={PROMOTION_LETTERS[move.promotion]}"
    return text + suffix


def _free_exit_text(move: Move, prefix: str) -> str:
    """Добавляет к записи хода префикс свободного выхода."""

    text = format_move(move)
    from_name = move.from_square.name
    if text.startswith(from_name):
        text = text[len(from_name) :]
    return prefix + text


def _free_prefix(turn: Turn) -> str:
    if turn.free_teleport is None:
        return ""
    return f"{turn.free_teleport.entry.name}~{turn.free_teleport.exit.name}"


def _free_action_prefix(turn: Turn) -> str:
    prefix = _free_prefix(turn)
    return f"{prefix}: " if prefix else ""


def _bless_text(state_after: "GameState", turn: Turn) -> str:
    action = turn.bless
    if action is None:  # pragma: no cover - защита
        return "Благословение"
    piece = state_after.board.find_piece(action.target_piece_id)
    if piece is not None:
        return f"Благословение: {action.target_square.name} ({piece.type.display_name.lower()})"
    return f"Благословение: {action.target_square.name}"


def _freeze_text(turn: Turn) -> str:
    action = turn.freeze
    if action is None:  # pragma: no cover - защита
        return "Заморозка"
    targets = ", ".join(square.name for square in action.targets)
    return f"Заморозка: {targets}"


def format_turn(state_before: "GameState", turn: Turn, state_after: "GameState") -> str:
    """Строка журнала для одного действия стороны."""

    del state_before
    parts: list[str] = []
    prefix = _free_prefix(turn)

    if turn.bless is not None:
        text = _free_action_prefix(turn) + _bless_text(state_after, turn)
        if state_after.last_cancelled:
            text += " — отменено щитом"
        return text

    if turn.freeze is not None:
        text = _free_action_prefix(turn) + _freeze_text(turn)
        if state_after.last_cancelled:
            text += " — отменено щитом"
        return text

    if len(turn.moves) == 2:
        first, second = turn.moves
        parts.append(
            _free_exit_text(first, prefix) if prefix else format_move(first)
        )
        parts.append(format_move(second))
        text = " + ".join(parts)
    else:
        for index, move in enumerate(turn.moves):
            if index == 0 and prefix:
                parts.append(_free_exit_text(move, prefix))
                prefix = ""
            else:
                parts.append(format_move(move))
        text = ", ".join(parts)

    if prefix:
        text = prefix.rstrip(": ") if text else prefix
    if state_after.last_cancelled:
        if text:
            text += " — отменено щитом (щит снят)"
        else:  # pragma: no cover - защита
            text = "Взятие отменено щитом"
    return text
