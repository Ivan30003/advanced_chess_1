"""Генерация ходов и проверка шахматных правил.

Модуль работает только с доской, фигурами и состоянием игры. Он не знает о
pygame. Основные точки входа — :func:`generate_legal_moves` (основные ходы,
включая телепортацию скользящих фигур) и :func:`generate_legal_turns`
(действия стороны, включая свободный выход из портала в начале хода).

Порталы учитываются и при проверке шаха: скользящая фигура может атаковать
короля через портал, а фигура, стоящая на портале, — свободно выйти и затем
атаковать. За один ход допускается не более одной активации, поэтому
рекурсивных активаций при проверке атак нет.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from chess.core.blessings import BlessAction, BlessingType, FreezeAction
from chess.core.board import Board
from chess.core.coords import Square
from chess.core.moves import Move, Turn, make_move
from chess.core.pieces import Color, Piece, PieceType
from chess.core.portals import (
    PortalActivation,
    PortalPair,
    PortalSet,
    portal_at,
)

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

SLIDER_TYPES = (PieceType.BISHOP, PieceType.ROOK, PieceType.QUEEN)

_CASTLE_RIGHT = {
    (Color.WHITE, "K"): "K",
    (Color.WHITE, "Q"): "Q",
    (Color.BLACK, "K"): "k",
    (Color.BLACK, "Q"): "q",
}


# ---------------------------------------------------------------------------
# Геометрия линий
# ---------------------------------------------------------------------------


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _is_slider(piece_type: PieceType) -> bool:
    return piece_type in SLIDER_TYPES


def _has_pass_through(piece: Piece) -> bool:
    return (
        piece.blessing is BlessingType.PASS_THROUGH
        and not piece.blessing_used
    )


def _pass_through_slider_attacks(
    board: Board,
    square: Square,
    by_color: Color,
    frozen: frozenset[str],
) -> bool:
    """Атакует ли слон/ладья/ферзь сквозь фигуры благодаря способности."""

    for piece in board.pieces_of(by_color):
        if piece.id in frozen or not _is_slider(piece.type):
            continue
        if not _has_pass_through(piece):
            continue
        if _line_is_valid(
            piece.type,
            square.file - piece.square.file,
            square.rank - piece.square.rank,
        ):
            return True
    return False


def _directions_for(piece_type: PieceType) -> tuple[tuple[int, int], ...]:
    if piece_type is PieceType.BISHOP:
        return DIAGONAL_DIRECTIONS
    if piece_type is PieceType.ROOK:
        return ORTHOGONAL_DIRECTIONS
    if piece_type is PieceType.QUEEN:
        return QUEEN_DIRECTIONS
    return ()


def _line_is_valid(piece_type: PieceType, file_delta: int, rank_delta: int) -> bool:
    """Лежит ли вектор на линии, доступной типу фигуры."""

    if file_delta == 0 and rank_delta == 0:
        return False
    if piece_type is PieceType.BISHOP:
        return abs(file_delta) == abs(rank_delta)
    if piece_type is PieceType.ROOK:
        return file_delta == 0 or rank_delta == 0
    if piece_type is PieceType.QUEEN:
        return (
            file_delta == 0
            or rank_delta == 0
            or abs(file_delta) == abs(rank_delta)
        )
    return False


def _path_is_clear(
    board: Board,
    origin: Square,
    target: Square,
    piece_type: PieceType,
    *,
    ignore: Iterable[Square] = (),
) -> bool:
    """Свободен ли путь между клетками по линии фигуры.

    Клетка ``target`` не проверяется на занятость: решение о взятии принимает
    вызывающий код. Клетки из ``ignore`` считаются пустыми (например, фигура,
    которая только что ушла с исходной клетки).
    """

    file_delta = target.file - origin.file
    rank_delta = target.rank - origin.rank
    if not _line_is_valid(piece_type, file_delta, rank_delta):
        return False
    ignored = set(ignore)
    step_file = _sign(file_delta)
    step_rank = _sign(rank_delta)
    current = origin
    while True:
        current = current.offset(step_file, step_rank)
        if current is None or not board.is_on_board(current):
            return False
        if current == target:
            return True
        if current in ignored:
            continue
        if not board.is_empty(current):
            return False


# ---------------------------------------------------------------------------
# Атаки
# ---------------------------------------------------------------------------


def _is_square_attacked_basic(
    board: Board,
    square: Square,
    by_color: Color,
) -> bool:
    """Атаки без учёта порталов."""

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


def _attacks_from_square(
    board: Board,
    piece_type: PieceType,
    color: Color,
    origin: Square,
    target: Square,
    *,
    ignore: Iterable[Square] = (),
) -> bool:
    """Атакует ли фигура данного типа клетку ``target`` из ``origin``.

    Используется для проверки атак после телепортации. ``origin`` — клетка
    выхода портала (фигура мысленно уже стоит там).
    """

    if origin == target:
        return False

    if piece_type is PieceType.PAWN:
        direction = 1 if color is Color.WHITE else -1
        return target in (
            origin.offset(-1, direction),
            origin.offset(1, direction),
        )
    if piece_type is PieceType.KNIGHT:
        return (
            target.file - origin.file,
            target.rank - origin.rank,
        ) in KNIGHT_OFFSETS
    if piece_type is PieceType.KING:
        return max(
            abs(target.file - origin.file),
            abs(target.rank - origin.rank),
        ) == 1
    if _is_slider(piece_type):
        return _path_is_clear(
            board,
            origin,
            target,
            piece_type,
            ignore=ignore,
        )
    return False


def _portal_attacks(
    board: Board,
    square: Square,
    by_color: Color,
    portals: Sequence[PortalPair] | PortalSet,
    *,
    include_king_free_exit: bool = True,
    frozen: frozenset[str] = frozenset(),
) -> bool:
    """Атаки с одной активацией портала."""

    for pair in portals:
        for entry, exit_square in ((pair.a, pair.b), (pair.b, pair.a)):
            if not board.is_empty(exit_square):
                continue

            # Фигура на входе свободно выходит на выход и атакует оттуда.
            occupant = board.piece_at(entry)
            if (
                occupant is not None
                and occupant.color is by_color
                and occupant.id not in frozen
            ):
                if occupant.type is PieceType.KING:
                    if include_king_free_exit:
                        trial = board.copy()
                        trial.move_piece(entry, exit_square)
                        # Король не может выйти на атакованную клетку.
                        if not is_square_attacked(
                            trial,
                            exit_square,
                            by_color.opposite,
                            portals,
                            include_king_free_exit=False,
                            frozen=frozen,
                        ) and _attacks_from_square(
                            trial,
                            occupant.type,
                            by_color,
                            exit_square,
                            square,
                        ):
                            return True
                elif _has_pass_through(occupant) and _is_slider(occupant.type):
                    if _line_is_valid(
                        occupant.type,
                        square.file - exit_square.file,
                        square.rank - exit_square.rank,
                    ):
                        return True
                elif _attacks_from_square(
                    board,
                    occupant.type,
                    by_color,
                    exit_square,
                    square,
                    ignore=(entry,),
                ):
                    return True

            # Скользящая фигура доходит до пустого входа и телепортируется.
            if not board.is_empty(entry):
                continue
            for slider in board.pieces_of(by_color):
                if not _is_slider(slider.type):
                    continue
                if slider.id in frozen:
                    continue
                if slider.square == entry:
                    continue
                pass_through = _has_pass_through(slider)
                if not pass_through and not _path_is_clear(
                    board,
                    slider.square,
                    entry,
                    slider.type,
                ):
                    continue
                if pass_through and not _line_is_valid(
                    slider.type,
                    entry.file - slider.square.file,
                    entry.rank - slider.square.rank,
                ):
                    continue
                if pass_through:
                    if _line_is_valid(
                        slider.type,
                        square.file - exit_square.file,
                        square.rank - exit_square.rank,
                    ):
                        return True
                elif _attacks_from_square(
                    board,
                    slider.type,
                    by_color,
                    exit_square,
                    square,
                    ignore=(slider.square,),
                ):
                    return True

    return False


def is_square_attacked(
    board: Board,
    square: Square,
    by_color: Color,
    portals: Sequence[PortalPair] | PortalSet = (),
    *,
    include_king_free_exit: bool = True,
    frozen: frozenset[str] = frozenset(),
) -> bool:
    """Атакована ли клетка с учётом порталов и прохода сквозь фигуры."""

    if _is_square_attacked_basic(board, square, by_color):
        return True
    if _pass_through_slider_attacks(board, square, by_color, frozen):
        return True
    if not portals:
        return False
    return _portal_attacks(
        board,
        square,
        by_color,
        portals,
        include_king_free_exit=include_king_free_exit,
        frozen=frozen,
    )


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


def _activation_at(
    state: "GameState",
    square: Square,
) -> PortalActivation | None:
    pair = portal_at(state.portals, square)
    if pair is None:
        return None
    partner = pair.other(square)
    if partner is None:  # pragma: no cover - защита от некорректной пары
        return None
    return PortalActivation(pair.id, square, partner)


def _teleport_continuations(
    board: Board,
    piece: Piece,
    activation: PortalActivation,
) -> Iterable[Move]:
    """Ходы после телепортации скользящей фигуры.

    Фигура может остановиться на выходе или продолжить движение из выхода в
    любом направлении, доступном её типу. Возврат на исходную клетку не
    генерируется, чтобы не создавать пустой ход; проходить через неё можно.
    """

    exit_square = activation.exit
    yield make_move(piece, exit_square, teleport=activation)

    start_square = piece.square
    for file_delta, rank_delta in _directions_for(piece.type):
        current = exit_square
        while True:
            current = current.offset(file_delta, rank_delta)
            if current is None or not board.is_on_board(current):
                break
            occupant = board.piece_at(current)
            if current == start_square:
                # Фигура уже ушла с исходной клетки — она пуста.
                occupant = None
            if occupant is None:
                if current != start_square:
                    yield make_move(piece, current, teleport=activation)
                continue
            if occupant.color is not piece.color and current != start_square:
                yield make_move(
                    piece,
                    current,
                    capture=occupant,
                    teleport=activation,
                )
            break


def _sliding_moves(
    board: Board,
    state: "GameState",
    piece: Piece,
    directions: Iterable[tuple[int, int]],
    *,
    allow_portal_teleport: bool = True,
) -> Iterable[Move]:
    for file_delta, rank_delta in directions:
        current = piece.square
        while True:
            current = current.offset(file_delta, rank_delta)
            if current is None or not board.is_on_board(current):
                break
            occupant = board.piece_at(current)
            if occupant is None:
                yield make_move(piece, current)
                if allow_portal_teleport:
                    activation = _activation_at(state, current)
                    if (
                        activation is not None
                        and board.is_empty(activation.exit)
                    ):
                        yield from _teleport_continuations(
                            board,
                            piece,
                            activation,
                        )
                continue
            if occupant.color is not piece.color:
                # Взятие на входе портала завершает ход без телепортации.
                yield make_move(piece, current, capture=occupant)
            break


def _pass_through_teleport_continuations(
    board: Board,
    piece: Piece,
    activation: PortalActivation,
    *,
    crossed_before: bool,
) -> Iterable[Move]:
    """Продолжения телепорта, если фигура может проходить сквозь фигуры."""

    exit_square = activation.exit
    start_square = piece.square
    if crossed_before:
        yield make_move(
            piece,
            exit_square,
            teleport=activation,
            pass_through=True,
        )

    for file_delta, rank_delta in _directions_for(piece.type):
        current = exit_square
        crossed = crossed_before
        while True:
            current = current.offset(file_delta, rank_delta)
            if current is None or not board.is_on_board(current):
                break
            occupant = board.piece_at(current)
            if current == start_square:
                occupant = None
            if occupant is None:
                if crossed:
                    yield make_move(
                        piece,
                        current,
                        teleport=activation,
                        pass_through=True,
                    )
                continue
            if occupant.color is not piece.color:
                if crossed:
                    yield make_move(
                        piece,
                        current,
                        capture=occupant,
                        teleport=activation,
                        pass_through=True,
                    )
            crossed = True


def _pass_through_sliding_moves(
    board: Board,
    state: "GameState",
    piece: Piece,
    *,
    allow_portal_teleport: bool = True,
) -> Iterable[Move]:
    """Ходы сквозь фигуры; обычные пути уже сгенерированы отдельно."""

    for file_delta, rank_delta in _directions_for(piece.type):
        current = piece.square
        crossed = False
        while True:
            current = current.offset(file_delta, rank_delta)
            if current is None or not board.is_on_board(current):
                break
            occupant = board.piece_at(current)
            if occupant is None:
                if crossed:
                    yield make_move(piece, current, pass_through=True)
                activation = _activation_at(state, current)
                if (
                    allow_portal_teleport
                    and activation is not None
                    and board.is_empty(activation.exit)
                ):
                    yield from _pass_through_teleport_continuations(
                        board,
                        piece,
                        activation,
                        crossed_before=crossed,
                    )
                continue
            if occupant.color is not piece.color and crossed:
                yield make_move(
                    piece,
                    current,
                    capture=occupant,
                    pass_through=True,
                )
            crossed = True


def _pass_through_pawn_moves(
    board: Board,
    state: "GameState",
    piece: Piece,
) -> Iterable[Move]:
    board_config = state.config.board
    start_rank = (
        board_config.white_pawn_rank
        if piece.color is Color.WHITE
        else board_config.black_pawn_rank
    )
    if piece.has_moved or piece.square.rank != start_rank:
        return
    direction = 1 if piece.color is Color.WHITE else -1
    middle = piece.square.offset(0, direction)
    target = piece.square.offset(0, direction * 2)
    if (
        middle is not None
        and target is not None
        and board.is_on_board(target)
        and board.piece_at(middle) is not None
        and board.is_empty(target)
    ):
        yield make_move(piece, target, is_double=True, pass_through=True)


def _pass_through_moves(
    state: "GameState",
    piece: Piece,
    *,
    allow_portal_teleport: bool = True,
) -> Iterable[Move]:
    if not _has_pass_through(piece) or piece.id in state.frozen:
        return
    if piece.type is PieceType.PAWN:
        yield from _pass_through_pawn_moves(state.board, state, piece)
    elif _is_slider(piece.type):
        yield from _pass_through_sliding_moves(
            state.board,
            state,
            piece,
            allow_portal_teleport=allow_portal_teleport,
        )


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
        if any(
            is_square_attacked(
                board,
                square,
                opponent,
                state.portals,
                frozen=state.frozen,
            )
            for square in safe_squares
        ):
            continue
        yield Move(
            piece_id=piece.id,
            from_square=piece.square,
            to_square=king_to,
            castle=side,
        )


def generate_pseudo_moves(
    state: "GameState",
    piece: Piece,
    *,
    allow_portal_teleport: bool = True,
) -> list[Move]:
    """Все ходы фигуры без фильтрации по безопасности короля."""

    if piece.id in state.frozen:
        return []

    board = state.board
    if piece.type is PieceType.PAWN:
        moves = list(_pawn_moves(board, state, piece))
    elif piece.type is PieceType.KNIGHT:
        moves = list(_step_moves(board, piece, KNIGHT_OFFSETS))
    elif piece.type is PieceType.BISHOP:
        moves = list(
            _sliding_moves(
                board,
                state,
                piece,
                DIAGONAL_DIRECTIONS,
                allow_portal_teleport=allow_portal_teleport,
            )
        )
    elif piece.type is PieceType.ROOK:
        moves = list(
            _sliding_moves(
                board,
                state,
                piece,
                ORTHOGONAL_DIRECTIONS,
                allow_portal_teleport=allow_portal_teleport,
            )
        )
    elif piece.type is PieceType.QUEEN:
        moves = list(
            _sliding_moves(
                board,
                state,
                piece,
                QUEEN_DIRECTIONS,
                allow_portal_teleport=allow_portal_teleport,
            )
        )
    elif piece.type is PieceType.KING:
        moves = list(_step_moves(board, piece, KING_OFFSETS)) + list(
            _castle_moves(board, state, piece)
        )
    else:
        moves = []

    moves.extend(
        _pass_through_moves(
            state,
            piece,
            allow_portal_teleport=allow_portal_teleport,
        )
    )
    return moves


# ---------------------------------------------------------------------------
# Применение хода к копии доски
# ---------------------------------------------------------------------------


def _apply_teleport_to_board(board: Board, piece: Piece, move: Move) -> Piece:
    """Применяет телепортацию скользящей фигуры к копии доски."""

    activation = move.teleport
    if activation is None:  # pragma: no cover - защита от вызова
        raise ValueError("Ход не содержит телепортации")
    entry = activation.entry
    exit_square = activation.exit

    if not _is_slider(piece.type):
        raise ValueError("Телепортироваться в середине хода могут только слон, ладья и ферзь")
    if move.castle is not None or move.en_passant or move.promotion is not None:
        raise ValueError("Телепортация не сочетается с рокировкой, en passant и превращением")
    if move.to_square == move.from_square:
        raise ValueError("Телепортация не может завершиться на исходной клетке")
    if entry == move.from_square:
        raise ValueError("Для выхода с портала в начале хода используйте free_teleport")
    if not board.is_empty(entry):
        raise ValueError("Вход портала должен быть пустым")
    if not board.is_empty(exit_square):
        raise ValueError("Выход портала должен быть пустым")
    if not move.pass_through and not _path_is_clear(
        board,
        move.from_square,
        entry,
        piece.type,
    ):
        raise ValueError("Путь до входа портала заблокирован")

    if move.to_square != exit_square:
        if not move.pass_through and not _path_is_clear(
            board,
            exit_square,
            move.to_square,
            piece.type,
            ignore=(move.from_square,),
        ):
            raise ValueError("Путь от выхода портала заблокирован")
        victim = board.piece_at(move.to_square)
        if victim is not None and victim.color is piece.color:
            raise ValueError("Нельзя завершить телепортацию на своей фигуре")
        if victim is not None and move.capture is None:
            raise ValueError("Конечная клетка телепортации занята фигурой")
        if move.capture is not None and victim is None:
            raise ValueError("На конечной клетке нет фигуры для взятия")
    elif move.capture is not None:
        raise ValueError("Нельзя взять фигуру на выходе портала")

    if move.capture is not None:
        board.remove_piece(move.to_square)

    board.remove_piece(move.from_square)
    moved = piece.moved_to(exit_square)
    board.add_piece(moved)
    if move.to_square != exit_square:
        moved = board.move_piece(exit_square, move.to_square)
    return moved


def _apply_move_to_board(board: Board, move: Move) -> Piece:
    """Применяет ход к уже скопированной доске (без счётчиков состояния)."""

    piece = board.piece_at(move.from_square)
    if piece is None:
        raise ValueError(f"На клетке {move.from_square.name} нет фигуры")

    if move.teleport is not None:
        return _apply_teleport_to_board(board, piece, move)

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


def _keeps_king_safe(
    board: Board,
    move: Move,
    color: Color,
    portals: Sequence[PortalPair] | PortalSet = (),
    frozen: frozenset[str] = frozenset(),
) -> bool:
    trial = board.copy()
    moved = _apply_move_to_board(trial, move)
    king_square = moved.square if moved.type is PieceType.KING else trial.king_square(color)
    if king_square is None:
        return False
    return not is_square_attacked(
        trial,
        king_square,
        color.opposite,
        portals,
        frozen=frozen,
    )


# ---------------------------------------------------------------------------
# Легальные ходы и действия
# ---------------------------------------------------------------------------


def _captured_piece(board: Board, move: Move) -> Piece | None:
    """Фигура, которую берёт ход (с учётом взятия на проходе)."""

    if move.en_passant:
        return board.piece_at(Square(move.to_square.file, move.from_square.rank))
    if move.capture is not None:
        return board.piece_at(move.to_square)
    return None


def _is_shielded_capture(board: Board, move: Move) -> bool:
    """Приводит ли ход к срабатыванию чужой неуязвимости."""

    victim = _captured_piece(board, move)
    return (
        victim is not None
        and victim.blessing is BlessingType.INVULNERABILITY
    )


def _move_keeps_king_safe(
    state: "GameState",
    move: Move,
    color: Color,
) -> bool:
    """Легален ли ход с учётом возможной отмены неуязвимостью."""

    if _is_shielded_capture(state.board, move):
        # Взятие отменяется целиком, поэтому позиция остаётся исходной.
        # Ход допустим, только если король и так не под шахом.
        return not is_in_check(state, color)
    return _keeps_king_safe(
        state.board,
        move,
        color,
        state.portals,
        state.frozen,
    )


def generate_legal_moves(state: "GameState") -> list[Move]:
    """Легальные основные ходы стороны, которой принадлежит очередь.

    Свободный выход из портала не является отдельным :class:`Move`; такие
    действия возвращает :func:`generate_legal_turns`.
    """

    color = state.side_to_move
    board = state.board
    king_square = board.king_square(color)
    if king_square is None:
        return []

    has_portals = bool(state.portals)
    in_check = is_square_attacked(
        board,
        king_square,
        color.opposite,
        state.portals,
        frozen=state.frozen,
    )
    # Порталы и проход сквозь фигуры ломают обычную эвристику связок,
    # поэтому в таких позициях проверяем безопасность каждого хода.
    enemy_pass_through = any(
        piece.color is color.opposite
        and piece.id not in state.frozen
        and _has_pass_through(piece)
        for piece in board.pieces_of(color.opposite)
    )
    pinned = (
        set()
        if in_check or has_portals or enemy_pass_through
        else _pinned_squares(board, king_square, color)
    )

    legal: list[Move] = []
    for piece in board.pieces_of(color):
        if piece.id in state.frozen:
            continue
        for move in generate_pseudo_moves(state, piece):
            if (
                move.castle is not None
                and not has_portals
                and not enemy_pass_through
                and not in_check
            ):
                # Путь и конечная клетка уже проверены при генерации.
                legal.append(move)
                continue
            needs_test = (
                has_portals
                or enemy_pass_through
                or in_check
                or piece.type is PieceType.KING
                or move.en_passant
                or move.teleport is not None
                or move.pass_through
                or piece.square in pinned
                or _is_shielded_capture(board, move)
            )
            if not needs_test or _move_keeps_king_safe(state, move, color):
                legal.append(move)
    return legal


def _free_exit_previews(
    state: "GameState",
) -> list[tuple[PortalActivation, "GameState"]]:
    """Допустимые свободные выходы и состояния после них."""

    color = state.side_to_move
    result: list[tuple[PortalActivation, "GameState"]] = []
    for pair in state.portals:
        for entry in (pair.a, pair.b):
            activation = state.free_exit_activation(entry)
            if activation is None:
                continue
            piece = state.board.piece_at(entry)
            if piece is None:  # pragma: no cover - защита
                continue
            if (
                piece.type is PieceType.KING
                and is_square_attacked(
                    state.board,
                    activation.exit,
                    color.opposite,
                    state.portals,
                    frozen=state.frozen,
                )
            ):
                continue
            result.append((activation, state.preview_free_exit(activation)))
    return result


def _free_exit_turns(state: "GameState") -> list[Turn]:
    """Действия со свободным выходом в начале хода."""

    color = state.side_to_move
    turns: list[Turn] = []

    for activation, preview in _free_exit_previews(state):
        moved_piece = preview.board.piece_at(activation.exit)
        if moved_piece is None:  # pragma: no cover - защита
            continue
        for move in generate_pseudo_moves(
            preview,
            moved_piece,
            allow_portal_teleport=False,
        ):
            if move.teleport is not None or move.castle is not None:
                # После выхода фигура уже считалась двигавшейся.
                continue
            if not _move_keeps_king_safe(preview, move, color):
                continue
            turns.append(Turn(free_teleport=activation, moves=[move]))
    return turns


# ---------------------------------------------------------------------------
# Действия благословений
# ---------------------------------------------------------------------------


def orthogonal_targets(
    board: Board,
    square: Square,
    color: Color,
) -> list[Piece]:
    """Вражеские фигуры, ортогонально соседние с клеткой ``square``."""

    targets: list[Piece] = []
    for file_delta, rank_delta in ORTHOGONAL_DIRECTIONS:
        current = square.offset(file_delta, rank_delta)
        if current is None or not board.is_on_board(current):
            continue
        piece = board.piece_at(current)
        if piece is not None and piece.color is color:
            targets.append(piece)
    targets.sort(key=lambda item: (item.square.file, item.square.rank))
    return targets


def legal_bless_targets(state: "GameState") -> list[Piece]:
    """Свои фигуры, которых король может благословить прямо сейчас."""

    if not state.config.abilities_enabled:
        return []
    color = state.side_to_move
    if state.blessing_choice.get(color) is None:
        return []
    if state.bless_cooldown.get(color, 0) != 0:
        return []
    king_square = state.board.king_square(color)
    if king_square is None:
        return []
    king = state.board.piece_at(king_square)
    if king is None or king.id in state.frozen:
        return []
    if is_in_check(state, color):
        return []

    targets: list[Piece] = []
    for file_delta, rank_delta in KING_OFFSETS:
        current = king_square.offset(file_delta, rank_delta)
        if current is None or not state.board.is_on_board(current):
            continue
        piece = state.board.piece_at(current)
        if (
            piece is None
            or piece.color is not color
            or piece.type is PieceType.KING
            or piece.ever_blessed
            or piece.blessing is not None
        ):
            continue
        targets.append(piece)
    targets.sort(key=lambda item: (item.square.file, item.square.rank))
    return targets


def _bless_turns(
    state: "GameState",
    free: PortalActivation | None = None,
) -> list[Turn]:
    color = state.side_to_move
    choice = state.blessing_choice.get(color)
    if choice is None or not state.config.abilities_enabled:
        return []
    if state.bless_cooldown.get(color, 0) != 0:
        return []
    king_square = state.board.king_square(color)
    if king_square is None:
        return []
    return [
        Turn(
            bless=BlessAction(king_square, target.square, target.id),
            free_teleport=free,
        )
        for target in legal_bless_targets(state)
    ]


def _freeze_turns(
    state: "GameState",
    free: PortalActivation | None = None,
) -> list[Turn]:
    color = state.side_to_move
    if (
        not state.config.abilities_enabled
        or state.blessing_choice.get(color) is not BlessingType.FREEZE
    ):
        return []
    if is_in_check(state, color):
        return []

    turns: list[Turn] = []
    for piece in state.board.pieces_of(color):
        if piece.id in state.frozen:
            continue
        if (
            piece.blessing is not BlessingType.FREEZE
            or piece.blessing_used
        ):
            continue
        targets = orthogonal_targets(
            state.board,
            piece.square,
            color.opposite,
        )
        if not targets:
            continue
        turns.append(
            Turn(
                freeze=FreezeAction(
                    piece.square,
                    piece.id,
                    tuple(target.square for target in targets),
                ),
                free_teleport=free,
            )
        )
    return turns


def _preview_after_move(state: "GameState", move: Move) -> "GameState":
    """Копия состояния после хода без смены стороны и счётчиков."""

    preview = state.copy()
    piece = preview.board.piece_at(move.from_square)
    if piece is None:  # pragma: no cover - защита
        return preview
    moved = _apply_move_to_board(preview.board, move)
    if (
        moved.type is PieceType.PAWN
        and abs(move.to_square.rank - move.from_square.rank) == 2
    ):
        preview.en_passant_target = Square(
            move.from_square.file,
            (move.from_square.rank + move.to_square.rank) // 2,
        )
    else:
        preview.en_passant_target = None
    preview.last_move = move
    return preview


def _has_any_legal_turn(state: "GameState") -> bool:
    """Есть ли у стороны хоть одно действие (без проверки мата двойным ходом)."""

    if generate_legal_moves(state):
        return True
    if _free_exit_turns(state):
        return True
    if _bless_turns(state):
        return True
    if _freeze_turns(state):
        return True
    if _double_move_turns(state, prohibit_mate=False):
        return True
    for activation, preview in _free_exit_previews(state):
        if _bless_turns(preview, activation):
            return True
        if _freeze_turns(preview, activation):
            return True
        if _double_move_turns(preview, activation, prohibit_mate=False):
            return True
    return False


def _double_move_turns(
    state: "GameState",
    free: PortalActivation | None = None,
    *,
    prohibit_mate: bool = True,
) -> list[Turn]:
    color = state.side_to_move
    if (
        not state.config.abilities_enabled
        or state.blessing_choice.get(color) is not BlessingType.DOUBLE_MOVE
    ):
        return []

    board = state.board
    candidates = [
        piece
        for piece in board.pieces_of(color)
        if piece.id not in state.frozen
        and piece.blessing is BlessingType.DOUBLE_MOVE
        and not piece.blessing_used
    ]
    if not candidates:
        return []

    legal_moves = generate_legal_moves(state)
    turns: list[Turn] = []
    for piece in candidates:
        first_moves = [
            move
            for move in legal_moves
            if move.piece_id == piece.id
            and not _is_shielded_capture(board, move)
            and not (free is not None and move.teleport is not None)
        ]
        for first in first_moves:
            preview = _preview_after_move(state, first)
            second_moves = [
                move
                for move in generate_legal_moves(preview)
                if move.piece_id == piece.id
                and move.from_square == first.to_square
                and not _is_shielded_capture(preview.board, move)
                and not (
                    (free is not None or first.teleport is not None)
                    and move.teleport is not None
                )
            ]
            for second in second_moves:
                turn = Turn(
                    free_teleport=free,
                    moves=[first, second],
                )
                if prohibit_mate:
                    final = _preview_after_move(preview, second)
                    final.side_to_move = color.opposite
                    if is_in_check(final, color.opposite) and not _has_any_legal_turn(
                        final
                    ):
                        continue
                turns.append(turn)
    return turns


def generate_legal_turns(state: "GameState") -> list[Turn]:
    """Все легальные действия стороны.

    Включает обычные ходы, свободный выход из портала, благословение,
    заморозку и двойной ход благословлённых фигур.
    """

    turns = [Turn.single(move) for move in generate_legal_moves(state)]
    turns.extend(_free_exit_turns(state))
    turns.extend(_bless_turns(state))
    turns.extend(_freeze_turns(state))
    turns.extend(_double_move_turns(state))
    for activation, preview in _free_exit_previews(state):
        turns.extend(_bless_turns(preview, activation))
        turns.extend(_freeze_turns(preview, activation))
        turns.extend(_double_move_turns(preview, activation))
    return turns


# ---------------------------------------------------------------------------
# Шах, мат, пат
# ---------------------------------------------------------------------------


def is_in_check(state: "GameState", color: Color) -> bool:
    king_square = state.board.king_square(color)
    if king_square is None:
        return False
    return is_square_attacked(
        state.board,
        king_square,
        color.opposite,
        state.portals,
        frozen=state.frozen,
    )


def _state_for_color(state: "GameState", color: Color) -> "GameState":
    if state.side_to_move is color:
        return state
    copy = state.copy()
    copy.side_to_move = color
    return copy


def is_checkmate(state: "GameState", color: Color) -> bool:
    local = _state_for_color(state, color)
    return is_in_check(local, color) and not generate_legal_turns(local)


def is_stalemate(state: "GameState", color: Color) -> bool:
    local = _state_for_color(state, color)
    return not is_in_check(local, color) and not generate_legal_turns(local)
