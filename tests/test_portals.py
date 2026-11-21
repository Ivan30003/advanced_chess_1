"""Тесты порталов: генерация, свободный выход, телепортация и шах."""

from __future__ import annotations

import random

import pytest

from chess.core.board import Board
from chess.core.board_config import BoardConfig, GameConfig
from chess.core.coords import Square
from chess.core.game_state import GameState, GameStatus
from chess.core.moves import Turn, make_move
from chess.core.pieces import Color, Piece, PieceType
from chess.core.portals import (
    PortalActivation,
    PortalPair,
    PortalSet,
    generate_portals,
    paired_square,
    portal_at,
)
from chess.core.rules import (
    generate_legal_moves,
    generate_legal_turns,
    is_checkmate,
    is_in_check,
)

S = Square.from_name
WHITE = Color.WHITE
BLACK = Color.BLACK
KING = PieceType.KING
ROOK = PieceType.ROOK
KNIGHT = PieceType.KNIGHT
PAWN = PieceType.PAWN


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def make_state(
    pieces: list[tuple[PieceType, Color, str]],
    portals: tuple[PortalPair, ...] = (),
    *,
    side: Color = WHITE,
    size: int = 8,
    en_passant: str | None = None,
    castling_rights: frozenset[str] = frozenset(),
) -> GameState:
    board = Board.empty(BoardConfig.for_size(size))
    for piece_type, color, name in pieces:
        board.add_piece(
            Piece(
                id=f"{color.value[0]}{piece_type.letter}-{name}",
                type=piece_type,
                color=color,
                square=S(name),
                original_square=S(name),
            )
        )
    return GameState(
        board=board,
        config=GameConfig.for_size(size),
        side_to_move=side,
        castling_rights=castling_rights,
        en_passant_target=S(en_passant) if en_passant is not None else None,
        portals=portals,
    )


def pair(
    pair_id: int = 0,
    a: str = "a4",
    b: str = "h4",
    color_index: int | None = None,
    symbol_index: int | None = None,
) -> PortalPair:
    return PortalPair(
        id=pair_id,
        color_index=pair_id if color_index is None else color_index,
        symbol_index=pair_id if symbol_index is None else symbol_index,
        a=S(a),
        b=S(b),
    )


def kings() -> list[tuple[PieceType, Color, str]]:
    return [(KING, WHITE, "e1"), (KING, BLACK, "e8")]


def free_exit_turns(state: GameState) -> list[Turn]:
    return [turn for turn in generate_legal_turns(state) if turn.free_teleport]


def teleport_moves(
    state: GameState,
    *,
    to: str | None = None,
    from_name: str | None = None,
) -> list:
    moves = [move for move in generate_legal_moves(state) if move.teleport is not None]
    if to is not None:
        moves = [move for move in moves if move.to_square == S(to)]
    if from_name is not None:
        moves = [move for move in moves if move.from_square == S(from_name)]
    return moves


def perft(state: GameState, depth: int) -> int:
    if depth == 0:
        return 1
    total = 0
    for move in generate_legal_moves(state):
        child = state.apply_move(move, detect_result=False, record_history=False)
        total += perft(child, depth - 1)
    return total


# ---------------------------------------------------------------------------
# Генерация и модель
# ---------------------------------------------------------------------------


def test_generate_portals_counts_and_constraints() -> None:
    for size in (6, 8, 10):
        board = Board.initial(BoardConfig.for_size(size))
        for count in range(4):
            paths = generate_portals(board, count, rng=100 + count)
            assert len(paths) == count
            cells = [square for item in paths for square in item.squares]
            assert len(cells) == len(set(cells)) == count * 2
            for square in cells:
                assert board.is_empty(square)
                assert 0 < square.rank < size - 1
            for index, item in enumerate(paths):
                for other in paths[index + 1 :]:
                    assert item.color_index != other.color_index
                    assert item.symbol_index != other.symbol_index


def test_generate_portals_is_seed_deterministic() -> None:
    board = Board.initial(BoardConfig.for_size(8))
    first = generate_portals(board, 3, rng=random.Random(1234))
    second = generate_portals(board, 3, rng=1234)
    assert first == second
    third = generate_portals(board, 3, rng=99)
    assert first != third


def test_generate_portals_rejects_bad_count() -> None:
    board = Board.initial(BoardConfig.for_size(8))
    with pytest.raises(ValueError):
        generate_portals(board, 4, rng=1)
    with pytest.raises(ValueError):
        generate_portals(board, -1, rng=1)


def test_portal_lookup_helpers() -> None:
    first = pair(0, "a4", "h4", 0, 0)
    second = pair(1, "b3", "g6", 1, 1)
    portal_set = PortalSet([first, second])
    assert portal_set.portal_at(S("a4")) is first
    assert portal_set.portal_at(S("g6")) is second
    assert portal_set.portal_at(S("e5")) is None
    assert portal_set.paired_square(S("a4")) == S("h4")
    assert portal_set.paired_square(S("e5")) is None
    assert portal_at([first, second], S("b3")) is second
    assert paired_square([first, second], S("h4")) == S("a4")
    with pytest.raises(ValueError):
        PortalPair(9, 0, 0, S("a4"), S("a4"))
    with pytest.raises(ValueError):
        PortalSet([first, pair(2, "h4", "d5")])


def test_initial_state_generates_and_copies_portals() -> None:
    state = GameState.initial(GameConfig.for_size(8, portal_count=3), rng=7)
    assert len(state.portals) == 3
    assert state.config.portal_count == 3
    clone = state.copy()
    assert clone.portals == state.portals
    assert clone.position_hash == state.position_hash
    another = GameState.initial(GameConfig.for_size(8, portal_count=3), rng=8)
    assert another.position_hash != state.position_hash


# ---------------------------------------------------------------------------
# Свободный выход
# ---------------------------------------------------------------------------


def test_free_exit_then_normal_move() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a4")],
        (pair(0, "a4", "h4"),),
    )
    turns = free_exit_turns(state)
    assert turns
    turn = next(item for item in turns if item.move.to_square == S("h8"))
    assert turn.portal_activation_count == 1

    after = state.apply_turn(turn)
    assert after.board.piece_at(S("h8")).id == "wR-a4"
    assert after.board.is_empty(S("a4"))
    assert after.history[-1] == "a4~h4-h8"


def test_occupied_exit_blocks_free_exit() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a4"), (PAWN, BLACK, "h4")],
        (pair(0, "a4", "h4"),),
    )
    assert state.free_exit_activation(S("a4")) is None
    assert free_exit_turns(state) == []


def test_preview_free_exit_does_not_change_state() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a4")],
        (pair(0, "a4", "h4"),),
    )
    activation = state.free_exit_activation(S("a4"))
    assert activation is not None
    preview = state.preview_free_exit(activation)
    assert state.board.piece_at(S("a4")) is not None
    assert state.board.is_empty(S("h4"))
    assert preview.board.piece_at(S("h4")) is not None
    assert preview.board.is_empty(S("a4"))
    assert preview.side_to_move is state.side_to_move


# ---------------------------------------------------------------------------
# Телепортация скользящих фигур
# ---------------------------------------------------------------------------


def test_rook_teleports_and_continues() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1")],
        (pair(0, "a4", "h4"),),
    )
    move = next(
        item for item in teleport_moves(state, to="h5") if item.from_square == S("a1")
    )
    assert move.teleport.entry == S("a4")
    assert move.teleport.exit == S("h4")

    after = state.apply_move(move)
    assert after.board.piece_at(S("h5")).id == "wR-a1"
    assert after.board.is_empty(S("a1"))
    assert after.board.is_empty(S("a4"))
    assert after.history[-1] == "a1-a4~h4-h5"


def test_rook_may_stop_on_exit() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1")],
        (pair(0, "a4", "h4"),),
    )
    move = next(item for item in teleport_moves(state, to="h4"))
    after = state.apply_move(move)
    assert after.board.piece_at(S("h4")).id == "wR-a1"
    assert after.history[-1] == "a1-a4~h4"


def test_teleport_continues_in_any_direction() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1")],
        (pair(0, "a4", "h4"),),
    )
    # Вход найден по вертикали, а продолжение — по горизонтали.
    assert teleport_moves(state, to="d4")


def test_teleport_capture_only_on_final_square() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1"), (PAWN, BLACK, "h7")],
        (pair(0, "a4", "h4"),),
    )
    capture = next(item for item in teleport_moves(state, to="h7"))
    assert capture.capture is not None
    assert capture.capture.type is PAWN
    peaceful = next(item for item in teleport_moves(state, to="h6"))
    assert peaceful.capture is None

    after = state.apply_move(capture)
    assert after.board.piece_at(S("h7")).id == "wR-a1"
    assert after.history[-1] == "a1-a4~h4xh7"


def test_occupied_exit_blocks_teleport() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1"), (PAWN, BLACK, "h4")],
        (pair(0, "a4", "h4"),),
    )
    assert teleport_moves(state) == []
    # Обычная остановка на входе остаётся доступной.
    assert any(
        move.from_square == S("a1") and move.to_square == S("a4")
        for move in generate_legal_moves(state)
    )


def test_enemy_on_entry_is_normal_capture() -> None:
    state = make_state(
        [(KING, WHITE, "h1"), (KING, BLACK, "e8"), (ROOK, WHITE, "a1"), (PAWN, BLACK, "a4")],
        (pair(0, "a4", "h4"),),
    )
    moves = [
        move
        for move in generate_legal_moves(state)
        if move.from_square == S("a1") and move.to_square == S("a4")
    ]
    assert len(moves) == 1
    assert moves[0].capture is not None
    assert moves[0].teleport is None

    after = state.apply_move(moves[0])
    assert after.board.piece_at(S("a4")).id == "wR-a1"
    assert after.board.is_empty(S("a1"))


def test_can_stop_on_second_portal_without_second_activation() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1")],
        (pair(0, "a4", "h4"), pair(1, "h3", "b5")),
    )
    move = next(
        item
        for item in teleport_moves(state, to="h3")
        if item.teleport is not None
    )
    assert move.teleport.pair_id == 0
    after = state.apply_move(move)
    assert after.board.piece_at(S("h3")).id == "wR-a1"
    # На следующем ходу белых с h3 уже возможен свободный выход.
    after.side_to_move = WHITE
    assert after.free_exit_activation(S("h3")) is not None


def test_teleport_cannot_land_on_uncaptured_piece() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1"), (PAWN, BLACK, "h5")],
        (pair(0, "a4", "h4"),),
    )
    piece = state.board.piece_at(S("a1"))
    move = make_move(piece, S("h5"), teleport=PortalActivation(0, S("a4"), S("h4")))
    assert move.capture is None
    with pytest.raises(ValueError):
        state.apply_move(move)


def test_short_pieces_do_not_teleport_midmove() -> None:
    for piece_type, name in ((KNIGHT, "d4"), (KING, "d4"), (PAWN, "d4")):
        state = make_state(
            [(KING, WHITE, "a1"), (KING, BLACK, "a8"), (piece_type, WHITE, name)],
            (pair(0, "d5", "f5"),),
        )
        assert teleport_moves(state) == []


def test_short_piece_can_use_free_exit_next_turn() -> None:
    state = make_state(
        [(KING, WHITE, "a1"), (KING, BLACK, "a8"), (KNIGHT, WHITE, "d5")],
        (pair(0, "d5", "f5"),),
    )
    turns = free_exit_turns(state)
    assert turns
    turn = next(item for item in turns if item.move.to_square == S("g7"))
    after = state.apply_turn(turn)
    assert after.board.piece_at(S("g7")).id == "wN-d5"
    assert after.history[-1] == "d5~f5-g7"


# ---------------------------------------------------------------------------
# Пешка после свободного выхода
# ---------------------------------------------------------------------------


def test_pawn_after_free_exit_cannot_double_move() -> None:
    state = make_state(
        [(KING, WHITE, "a1"), (KING, BLACK, "a8"), (PAWN, WHITE, "e2")],
        (pair(0, "e2", "g3"),),
    )
    turns = free_exit_turns(state)
    assert turns
    assert not any(item.move.is_double for item in turns)
    assert any(item.move.to_square == S("g4") for item in turns)

    turn = next(item for item in turns if item.move.to_square == S("g4"))
    after = state.apply_turn(turn)
    assert after.board.piece_at(S("g4")).id == "wP-e2"
    assert after.board.piece_at(S("g4")).has_moved
    assert after.history[-1] == "e2~g3-g4"


def test_pawn_after_free_exit_can_capture_en_passant() -> None:
    state = make_state(
        [
            (KING, WHITE, "a1"),
            (KING, BLACK, "a8"),
            (PAWN, WHITE, "e2"),
            (PAWN, BLACK, "f5"),
        ],
        (pair(0, "e2", "g5"),),
        en_passant="f6",
    )
    turn = next(item for item in free_exit_turns(state) if item.move.en_passant)
    after = state.apply_turn(turn)
    assert after.board.is_empty(S("f5"))
    assert after.board.piece_at(S("f6")).id == "wP-e2"
    assert after.history[-1] == "e2~g5xf6"


def test_pawn_after_free_exit_can_promote() -> None:
    state = make_state(
        [(KING, WHITE, "a1"), (KING, BLACK, "a8"), (PAWN, WHITE, "g7")],
        (pair(0, "g7", "h7"),),
    )
    turns = [
        item
        for item in free_exit_turns(state)
        if item.move.promotion is PieceType.QUEEN
    ]
    assert turns
    after = state.apply_turn(turns[0])
    assert after.board.piece_at(S("h8")).type is PieceType.QUEEN
    assert after.history[-1] == "g7~h7-h8=Q"


# ---------------------------------------------------------------------------
# Король, рокировка и права
# ---------------------------------------------------------------------------


def test_king_cannot_free_exit_to_attacked_square() -> None:
    state = make_state(
        [(KING, WHITE, "e2"), (KING, BLACK, "a8"), (ROOK, BLACK, "e8")],
        (pair(0, "e2", "e4"),),
    )
    assert state.free_exit_activation(S("e2")) is not None
    assert free_exit_turns(state) == []


def test_king_final_position_must_be_safe() -> None:
    state = make_state(
        [(KING, WHITE, "e2"), (KING, BLACK, "a8"), (ROOK, BLACK, "h5")],
        (pair(0, "e2", "e4"),),
    )
    turns = free_exit_turns(state)
    assert turns
    assert not any(item.move.to_square == S("e5") for item in turns)


def test_castling_does_not_activate_portals() -> None:
    state = make_state(
        [
            (KING, WHITE, "e1"),
            (ROOK, WHITE, "h1"),
            (KING, BLACK, "e8"),
        ],
        (pair(0, "a4", "h4"),),
        castling_rights=frozenset({"K"}),
    )
    castle = next(move for move in generate_legal_moves(state) if move.castle == "K")
    assert castle.teleport is None
    after = state.apply_move(castle)
    assert after.board.piece_at(S("g1")).id == "wK-e1"
    assert after.board.piece_at(S("f1")).id == "wR-h1"
    assert after.portals == state.portals


def test_castling_rights_lost_after_free_exit_of_rook() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1")],
        (pair(0, "a1", "a4"),),
        castling_rights=frozenset({"K", "Q", "k", "q"}),
    )
    turn = next(item for item in free_exit_turns(state) if item.move.to_square == S("a5"))
    after = state.apply_turn(turn)
    assert "Q" not in after.castling_rights
    assert "K" in after.castling_rights


def test_castling_rights_lost_after_midmove_rook_teleport() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a1")],
        (pair(0, "a4", "h4"),),
        castling_rights=frozenset({"K", "Q", "k", "q"}),
    )
    move = next(item for item in teleport_moves(state, to="h5"))
    after = state.apply_move(move)
    assert "Q" not in after.castling_rights
    assert "K" in after.castling_rights


def test_king_cannot_castle_after_free_exit_to_castling_square() -> None:
    state = make_state(
        [
            (KING, WHITE, "a4"),
            (ROOK, WHITE, "h1"),
            (KING, BLACK, "a8"),
        ],
        (pair(0, "a4", "e1"),),
        castling_rights=frozenset({"K"}),
    )
    preview = state.preview_free_exit(state.free_exit_activation(S("a4")))
    assert "K" not in preview.castling_rights
    assert not any(move.castle for move in generate_legal_moves(preview))

    turns = free_exit_turns(state)
    assert turns
    assert not any(turn.move.castle for turn in turns)


def test_castling_rights_lost_after_king_free_exit() -> None:
    state = make_state(
        kings(),
        (pair(0, "e1", "e3"),),
        castling_rights=frozenset({"K", "Q", "k", "q"}),
    )
    preview = state.preview_free_exit(state.free_exit_activation(S("e1")))
    assert not any(move.castle for move in generate_legal_moves(preview))

    turn = next(item for item in free_exit_turns(state) if item.move.to_square == S("e4"))
    after = state.apply_turn(turn)
    assert "K" not in after.castling_rights and "Q" not in after.castling_rights


# ---------------------------------------------------------------------------
# Одна активация, шах, мат и perft
# ---------------------------------------------------------------------------


def test_only_one_activation_per_turn() -> None:
    state = make_state(
        kings() + [(ROOK, WHITE, "a4")],
        (pair(0, "a4", "h4"), pair(1, "h5", "b5")),
    )
    activation = state.free_exit_activation(S("a4"))
    assert activation is not None
    second = PortalActivation(1, S("h5"), S("b5"))
    move = make_move(state.board.piece_at(S("a4")), S("b6"), teleport=second)
    turn = Turn(free_teleport=activation, moves=[move])
    assert turn.portal_activation_count == 2
    with pytest.raises(ValueError):
        state.apply_turn(turn)


def test_check_through_slider_portal() -> None:
    state = make_state(
        [(KING, WHITE, "h1"), (KING, BLACK, "h8"), (ROOK, WHITE, "a1")],
        (pair(0, "a4", "h4"),),
    )
    assert is_in_check(state, BLACK)


def test_blocking_piece_still_stops_portal_attack() -> None:
    state = make_state(
        [
            (KING, WHITE, "h1"),
            (KING, BLACK, "h8"),
            (ROOK, WHITE, "a1"),
            (PAWN, BLACK, "h6"),
        ],
        (pair(0, "a4", "h4"),),
    )
    assert not is_in_check(state, BLACK)


def test_check_after_free_exit_of_rook() -> None:
    state = make_state(
        [(KING, WHITE, "e1"), (KING, BLACK, "h8"), (ROOK, WHITE, "a4")],
        (pair(0, "a4", "h4"),),
    )
    assert is_in_check(state, BLACK)


def test_check_after_free_exit_of_knight() -> None:
    state = make_state(
        [(KING, WHITE, "a1"), (KING, BLACK, "g6"), (KNIGHT, WHITE, "a4")],
        (pair(0, "a4", "h4"),),
    )
    assert is_in_check(state, BLACK)


def test_mate_through_portal() -> None:
    state = make_state(
        [
            (KING, WHITE, "h1"),
            (KING, BLACK, "h8"),
            (ROOK, WHITE, "a1"),
            (PAWN, BLACK, "g7"),
            (PAWN, BLACK, "h7"),
        ],
        (pair(0, "a4", "e8"),),
    )
    move = next(item for item in teleport_moves(state, to="e8"))
    after = state.apply_move(move)
    assert is_in_check(after, BLACK)
    assert is_checkmate(after, BLACK)
    assert after.status is GameStatus.WHITE_WIN
    assert after.history[-1] == "a1-a4~e8"


def test_portals_do_not_break_perft_without_portals() -> None:
    state = GameState.initial()
    assert not state.portals
    assert perft(state, 1) == 20
    assert perft(state, 2) == 400
    assert perft(state, 3) == 8902
