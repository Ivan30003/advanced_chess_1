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
) -> bool:
    """Атаки с одной активацией портала."""

    for pair in portals:
        for entry, exit_square in ((pair.a, pair.b), (pair.b, pair.a)):
            if not board.is_empty(exit_square):
                continue

            # Фигура на входе свободно выходит на выход и атакует оттуда.
            occupant = board.piece_at(entry)
            if occupant is not None and occupant.color is by_color:
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
                        ) and _attacks_from_square(
                            trial,
                            occupant.type,
                            by_color,
                            exit_square,
                            square,
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
                if slider.square == entry:
                    continue
                if not _path_is_clear(
                    board,
                    slider.square,
                    entry,
                    slider.type,
                ):
                    continue
                if _attacks_from_square(
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
) -> bool:
    """Атакована ли клетка с учётом порталов."""

    if _is_square_attacked_basic(board, square, by_color):
        return True
    if not portals:
        return False
    return _portal_attacks(
        board,
        square,
        by_color,
        portals,
        include_king_free_exit=include_king_free_exit,
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

    board = state.board
    if piece.type is PieceType.PAWN:
        return list(_pawn_moves(board, state, piece))
    if piece.type is PieceType.KNIGHT:
        return list(_step_moves(board, piece, KNIGHT_OFFSETS))
    if piece.type is PieceType.BISHOP:
        return list(
            _sliding_moves(
                board,
                state,
                piece,
                DIAGONAL_DIRECTIONS,
                allow_portal_teleport=allow_portal_teleport,
            )
        )
    if piece.type is PieceType.ROOK:
        return list(
            _sliding_moves(
                board,
                state,
                piece,
                ORTHOGONAL_DIRECTIONS,
                allow_portal_teleport=allow_portal_teleport,
            )
        )
    if piece.type is PieceType.QUEEN:
        return list(
            _sliding_moves(
                board,
                state,
                piece,
                QUEEN_DIRECTIONS,
                allow_portal_teleport=allow_portal_teleport,
            )
        )
    if piece.type is PieceType.KING:
        return list(_step_moves(board, piece, KING_OFFSETS)) + list(
            _castle_moves(board, state, piece)
        )
    return []


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
    if not _path_is_clear(board, move.from_square, entry, piece.type):
        raise ValueError("Путь до входа портала заблокирован")

    if move.to_square != exit_square:
        if not _path_is_clear(
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
    )


# ---------------------------------------------------------------------------
# Легальные ходы и действия
# ---------------------------------------------------------------------------


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
    )
    # При порталах обычная эвристика связок может пропустить линию атаки
    # через портал, поэтому проверяем безопасность каждого хода.
    pinned = (
        set()
        if in_check or has_portals
        else _pinned_squares(board, king_square, color)
    )

    legal: list[Move] = []
    for piece in board.pieces_of(color):
        for move in generate_pseudo_moves(state, piece):
            if move.castle is not None and not has_portals:
                # Путь и конечная клетка уже проверены при генерации.
                legal.append(move)
                continue
            needs_test = (
                has_portals
                or in_check
                or piece.type is PieceType.KING
                or move.en_passant
                or move.teleport is not None
                or piece.square in pinned
            )
            if not needs_test or _keeps_king_safe(
                board,
                move,
                color,
                state.portals,
            ):
                legal.append(move)
    return legal


def _free_exit_turns(state: "GameState") -> list[Turn]:
    """Действия со свободным выходом в начале хода."""

    color = state.side_to_move
    board = state.board
    turns: list[Turn] = []

    for pair in state.portals:
        for entry, exit_square in ((pair.a, pair.b), (pair.b, pair.a)):
            piece = board.piece_at(entry)
            if piece is None or piece.color is not color:
                continue
            if not board.is_empty(exit_square):
                continue

            activation = PortalActivation(pair.id, entry, exit_square)
            preview = state.preview_free_exit(activation)

            if piece.type is PieceType.KING and is_square_attacked(
                preview.board,
                exit_square,
                color.opposite,
                preview.portals,
            ):
                # Король не может выйти на атакованную клетку.
                continue

            moved_piece = preview.board.piece_at(exit_square)
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
                if not _keeps_king_safe(
                    preview.board,
                    move,
                    color,
                    preview.portals,
                ):
                    continue
                turns.append(
                    Turn(free_teleport=activation, moves=[move])
                )
    return turns


def generate_legal_turns(state: "GameState") -> list[Turn]:
    """Все легальные действия стороны, включая свободный выход из портала."""

    turns = [Turn.single(move) for move in generate_legal_moves(state)]
    turns.extend(_free_exit_turns(state))
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
