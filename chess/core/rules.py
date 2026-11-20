"""Генерация ходов и проверка шахматных правил.

Модуль работает только с доской, фигурами и состоянием игры. Он не знает о
pygame. Основная точка входа — :func:`generate_legal_moves` и
:func:`generate_legal_turns`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from chess.core.board import Board
from chess.core.coords import Square
from chess.core.moves import Move, Turn, make_move
from chess.core.pieces import Color, Piece, PieceType

if TYPE_CHECKING:  # pragma: no cover - только для аннотаций
    from chess.core.game_state import GameState

KNIGHT_OFFSETS = (
    (1, 2),
    (2, 1),
    (2, -1),
    (1, -2),
    (-1, -2),
    (-2, -1),
    (-2, 1),
    (-1, 2),
)
KING_OFFSETS = (
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
    (0, -1),
    (1, -1),
)
DIAGONAL_DIRECTIONS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ORTHOGONAL_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))
QUEEN_DIRECTIONS = DIAGONAL_DIRECTIONS + ORTHOGONAL_DIRECTIONS

_CASTLE_RIGHT = {
    (Color.WHITE, "K"): "K",
    (Color.WHITE, "Q"): "Q",
    (Color.BLACK, "K"): "k",
    (Color.BLACK, "Q"): "q",
}


# ---------------------------------------------------------------------------
# Атаки
# ---------------------------------------------------------------------------


def is_square_attacked(board: Board, square: Square, by_color: Color) -> bool:
    """Атакована ли клетка фигурами указанного цвета."""

    # Пешки атакуют по диагонали вперёд.
    pawn_rank_delta = -1 if by_color is Color.WHITE else 1
    for file_delta in (-1, 1):
        attacker_square = square.offset(file_delta, pawn_rank_delta)
        if attacker_square is None or not board.is_on_board(attacker_square):
            continue
        attacker = board.piece_at(attacker_square)
        if (
            attacker is not None
            and attacker.color is by_color
            and attacker.type is PieceType.PAWN
        ):
            return True

    for file_delta, rank_delta in KNIGHT_OFFSETS:
        attacker_square = square.offset(file_delta, rank_delta)
        if attacker_square is None or not board.is_on_board(attacker_square):
            continue
        attacker = board.piece_at(attacker_square)
        if (
            attacker is not None
            and attacker.color is by_color
            and attacker.type is PieceType.KNIGHT
        ):
            return True

    for file_delta, rank_delta in KING_OFFSETS:
        attacker_square = square.offset(file_delta, rank_delta)
        if attacker_square is None or not board.is_on_board(attacker_square):
            continue
        attacker = board.piece_at(attacker_square)
        if (
            attacker is not None
            and attacker.color is by_color
            and attacker.type is PieceType.KING
        ):
            return True

    for directions, slider_types in (
        (DIAGONAL_DIRECTIONS, (PieceType.BISHOP, PieceType.QUEEN)),
        (ORTHOGONAL_DIRECTIONS, (PieceType.ROOK, PieceType.QUEEN)),
    ):
        for file_delta, rank_delta in directions:
            current = square
            while True:
                current = current.offset(file_delta, rank_delta)
                if current is None or not board.is_on_board(current):
                    break
                attacker = board.piece_at(current)
                if attacker is None:
                    continue
                if attacker.color is by_color and attacker.type in slider_types:
                    return True
                break

    return False


def _pinned_squares(board: Board, king_square: Square, color: Color) -> set[Square]:
    """Клетки своих фигур, удерживающих короля на линии атаки."""

    pinned: set[Square] = set()
    for directions, slider_types in (
        (DIAGONAL_DIRECTIONS, (PieceType.BISHOP, PieceType.QUEEN)),
        (ORTHOGONAL_DIRECTIONS, (PieceType.ROOK, PieceType.QUEEN)),
    ):
        for file_delta, rank_delta in directions:
            blocker: Piece | None = None
            current = king_square
            while True:
                current = current.offset(file_delta, rank_delta)
                if current is None or not board.is_on_board(current):
                    break
                piece = board.piece_at(current)
                if piece is None:
                    continue
                if piece.color is color:
                    if blocker is None:
                        blocker = piece
                        continue
                    break
                if blocker is not None and piece.type in slider_types:
                    pinned.add(blocker.square)
                break
    return pinned


# ---------------------------------------------------------------------------
# Псевдолегальные ходы
# ---------------------------------------------------------------------------


def _pawn_moves(board: Board, state: "GameState", piece: Piece) -> Iterable[Move]:
    color = piece.color
    board_config = state.config.board
    direction = 1 if color is Color.WHITE else -1
    start_rank = (
        board_config.white_pawn_rank
        if color is Color.WHITE
        else board_config.black_pawn_rank
    )
    last_rank = (
        board_config.white_promotion_rank
        if color is Color.WHITE
        else board_config.black_promotion_rank
    )

    one_step = piece.square.offset(0, direction)
    if one_step is not None and board.is_on_board(one_step) and board.is_empty(one_step):
        yield from _pawn_destination_moves(piece, one_step, None, last_rank)
        two_steps = piece.square.offset(0, direction * 2)
        if (
            not piece.has_moved
            and piece.square.rank == start_rank
            and two_steps is not None
            and board.is_on_board(two_steps)
            and board.is_empty(two_steps)
        ):
            yield make_move(piece, two_steps, is_double=True)

    for file_delta in (-1, 1):
        target = piece.square.offset(file_delta, direction)
        if target is None or not board.is_on_board(target):
            continue
        victim = board.piece_at(target)
        if victim is not None and victim.color is not color:
            yield from _pawn_destination_moves(piece, target, victim, last_rank)
        elif victim is None and state.en_passant_target == target:
            adjacent = board.piece_at(Square(target.file, piece.square.rank))
            if (
                adjacent is not None
                and adjacent.color is not color
                and adjacent.type is PieceType.PAWN
            ):
                yield make_move(piece, target, capture=adjacent, en_passant=True)


def _pawn_destination_moves(
    piece: Piece,
    target: Square,
    victim: Piece | None,
    last_rank: int,
) -> Iterable[Move]:
    if target.rank != last_rank:
        yield make_move(piece, target, capture=victim)
        return
    for promotion in (
        PieceType.QUEEN,
        PieceType.ROOK,
        PieceType.BISHOP,
        PieceType.KNIGHT,
    ):
        yield make_move(piece, target, capture=victim, promotion=promotion)


def _sliding_moves(board: Board, piece: Piece, directions: Iterable[tuple[int, int]]) -> Iterable[Move]:
    for file_delta, rank_delta in directions:
        current = piece.square
        while True:
            current = current.offset(file_delta, rank_delta)
            if current is None or not board.is_on_board(current):
                break
            occupant = board.piece_at(current)
            if occupant is None:
                yield make_move(piece, current)
                continue
            if occupant.color is not piece.color:
                yield make_move(piece, current, capture=occupant)
            break


def _step_moves(
    board: Board,
    piece: Piece,
    offsets: Iterable[tuple[int, int]],
) -> Iterable[Move]:
    for file_delta, rank_delta in offsets:
        target = piece.square.offset(file_delta, rank_delta)
        if target is None or not board.is_on_board(target):
            continue
        occupant = board.piece_at(target)
        if occupant is None:
            yield make_move(piece, target)
        elif occupant.color is not piece.color:
            yield make_move(piece, target, capture=occupant)


def _castle_moves(board: Board, state: "GameState", piece: Piece) -> Iterable[Move]:
    if piece.type is not PieceType.KING or piece.has_moved:
        return
    castling = state.config.board.castling_for(piece.color is Color.WHITE)
    if castling is None or piece.square != castling.king_from:
        return

    opponent = piece.color.opposite
    for side, rook_from, king_to, empty_squares, safe_squares in (
        (
            "K",
            castling.king_side_rook_from,
            castling.king_side_king_to,
            castling.king_side_empty,
            castling.king_side_safe,
        ),
        (
            "Q",
            castling.queen_side_rook_from,
            castling.queen_side_king_to,
            castling.queen_side_empty,
            castling.queen_side_safe,
        ),
    ):
        right = _CASTLE_RIGHT[(piece.color, side)]
        if right not in state.castling_rights:
            continue
        rook = board.piece_at(rook_from)
        if (
            rook is None
            or rook.color is not piece.color
            or rook.type is not PieceType.ROOK
            or rook.has_moved
        ):
            continue
        if any(not board.is_empty(square) for square in empty_squares):
            continue
        if any(is_square_attacked(board, square, opponent) for square in safe_squares):
            continue
        yield Move(
            piece_id=piece.id,
            from_square=piece.square,
            to_square=king_to,
            castle=side,
        )


def generate_pseudo_moves(state: "GameState", piece: Piece) -> list[Move]:
    """Все ходы фигуры без фильтрации по безопасности короля."""

    board = state.board
    if piece.type is PieceType.PAWN:
        return list(_pawn_moves(board, state, piece))
    if piece.type is PieceType.KNIGHT:
        return list(_step_moves(board, piece, KNIGHT_OFFSETS))
    if piece.type is PieceType.BISHOP:
        return list(_sliding_moves(board, piece, DIAGONAL_DIRECTIONS))
    if piece.type is PieceType.ROOK:
        return list(_sliding_moves(board, piece, ORTHOGONAL_DIRECTIONS))
    if piece.type is PieceType.QUEEN:
        return list(_sliding_moves(board, piece, QUEEN_DIRECTIONS))
    if piece.type is PieceType.KING:
        return list(_step_moves(board, piece, KING_OFFSETS)) + list(
            _castle_moves(board, state, piece)
        )
    return []


# ---------------------------------------------------------------------------
# Легальные ходы
# ---------------------------------------------------------------------------


def _apply_move_to_board(board: Board, move: Move) -> Piece:
    """Применяет ход к уже скопированной доске (без счётчиков состояния)."""

    piece = board.piece_at(move.from_square)
    if piece is None:
        raise ValueError(f"На клетке {move.from_square.name} нет фигуры")

    if move.en_passant:
        board.remove_piece(Square(move.to_square.file, move.from_square.rank))
    elif move.capture is not None:
        board.remove_piece(move.to_square)

    moved = board.move_piece(move.from_square, move.to_square)

    if move.castle is not None:
        castling = board.config.castling_for(piece.color is Color.WHITE)
        if castling is not None:
            if move.castle == "K":
                rook_from, rook_to = (
                    castling.king_side_rook_from,
                    castling.king_side_rook_to,
                )
            else:
                rook_from, rook_to = (
                    castling.queen_side_rook_from,
                    castling.queen_side_rook_to,
                )
            board.move_piece(rook_from, rook_to)

    if move.promotion is not None:
        moved = moved.promoted_to(move.promotion)
        board.replace_piece(moved)

    return moved


def _keeps_king_safe(board: Board, move: Move, color: Color) -> bool:
    trial = board.copy()
    moved = _apply_move_to_board(trial, move)
    king_square = moved.square if moved.type is PieceType.KING else trial.king_square(color)
    if king_square is None:
        return False
    return not is_square_attacked(trial, king_square, color.opposite)


def generate_legal_moves(state: "GameState") -> list[Move]:
    """Легальные ходы стороны, которой принадлежит очередь."""

    color = state.side_to_move
    board = state.board
    king_square = board.king_square(color)
    if king_square is None:
        return []

    in_check = is_square_attacked(board, king_square, color.opposite)
    pinned = set() if in_check else _pinned_squares(board, king_square, color)

    legal: list[Move] = []
    for piece in board.pieces_of(color):
        for move in generate_pseudo_moves(state, piece):
            if move.castle is not None:
                # Путь и конечная клетка уже проверены при генерации.
                legal.append(move)
                continue
            needs_test = (
                in_check
                or piece.type is PieceType.KING
                or move.en_passant
                or piece.square in pinned
            )
            if not needs_test or _keeps_king_safe(board, move, color):
                legal.append(move)
    return legal


def generate_legal_turns(state: "GameState") -> list[Turn]:
    return [Turn.single(move) for move in generate_legal_moves(state)]


# ---------------------------------------------------------------------------
# Шах, мат, пат
# ---------------------------------------------------------------------------


def is_in_check(state: "GameState", color: Color) -> bool:
    king_square = state.board.king_square(color)
    if king_square is None:
        return False
    return is_square_attacked(state.board, king_square, color.opposite)


def _state_for_color(state: "GameState", color: Color) -> "GameState":
    if state.side_to_move is color:
        return state
    copy = state.copy()
    copy.side_to_move = color
    return copy


def is_checkmate(state: "GameState", color: Color) -> bool:
    local = _state_for_color(state, color)
    return is_in_check(local, color) and not generate_legal_moves(local)


def is_stalemate(state: "GameState", color: Color) -> bool:
    local = _state_for_color(state, color)
    return not is_in_check(local, color) and not generate_legal_moves(local)
