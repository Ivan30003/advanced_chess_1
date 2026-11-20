"""Тесты этапа 3: три размера доски, рокировка, пешки и ничьи."""

from __future__ import annotations

import pytest

from chess.core.board import Board
from chess.core.board_config import BoardConfig, GameConfig
from chess.core.coords import FILES, MAX_BOARD_SIZE, Square, squares_for_size
from chess.core.game_state import GameState, GameStatus
from chess.core.moves import Move
from chess.core.pieces import (
    PROMOTION_PIECES,
    Color,
    Piece,
    PieceType,
)
from chess.core.rules import (
    generate_legal_moves,
    is_checkmate,
    is_in_check,
    is_stalemate,
)

_WHITE = Color.WHITE
_BLACK = Color.BLACK
_KING = PieceType.KING
_QUEEN = PieceType.QUEEN
_ROOK = PieceType.ROOK
_BISHOP = PieceType.BISHOP
_KNIGHT = PieceType.KNIGHT
_PAWN = PieceType.PAWN


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def make_state(
    size: int,
    pieces: list[tuple[PieceType, Color, str]],
    *,
    side: Color = _WHITE,
    castling_rights: frozenset[str] | None = None,
    halfmove_clock: int = 0,
) -> GameState:
    board = Board.empty(BoardConfig.for_size(size))
    for index, (piece_type, color, name) in enumerate(pieces):
        square = Square.from_name(name)
        board.add_piece(
            Piece(
                id=f"{color.value[0]}{piece_type.letter}-{name}-{index}",
                type=piece_type,
                color=color,
                square=square,
                original_square=square,
            )
        )
    return GameState(
        board=board,
        config=GameConfig.for_size(size),
        side_to_move=side,
        castling_rights=castling_rights,
        halfmove_clock=halfmove_clock,
    )


def find_move(
    state: GameState,
    from_name: str,
    to_name: str,
    promotion: PieceType | None = None,
) -> Move:
    for move in generate_legal_moves(state):
        if move.from_square.name != from_name or move.to_square.name != to_name:
            continue
        if promotion is None or move.promotion is promotion:
            return move
    raise AssertionError(f"Легальный ход {from_name}-{to_name} не найден")


def play(
    state: GameState,
    from_name: str,
    to_name: str,
    promotion: PieceType | None = None,
) -> GameState:
    return state.apply_move(find_move(state, from_name, to_name, promotion))


def castle_moves(state: GameState) -> list[Move]:
    return [move for move in generate_legal_moves(state) if move.castle is not None]


# ---------------------------------------------------------------------------
# Конфигурация доски и начальные расстановки
# ---------------------------------------------------------------------------


def test_square_names_and_squares_for_size() -> None:
    assert FILES == "abcdefghij"
    assert Square.from_name("j10").name == "j10"
    assert Square.from_name("a1").name == "a1"
    assert len(squares_for_size(6)) == 36
    assert len(squares_for_size(8)) == 64
    assert len(squares_for_size(10)) == 100
    assert Square(9, 9).name == "j10"
    assert MAX_BOARD_SIZE == 10


@pytest.mark.parametrize("size", [6, 8, 10])
def test_board_config_files_ranks_and_positions(size: int) -> None:
    config = BoardConfig.for_size(size)
    assert config.size == size
    assert config.files == FILES[:size]
    assert config.ranks == tuple(str(index + 1) for index in range(size))
    assert len(config.squares()) == size * size
    assert config.is_on_board(Square(size - 1, size - 1))
    assert config.is_on_board(Square(0, size - 1))
    if size < MAX_BOARD_SIZE:
        assert not config.is_on_board(Square(size, 0))


def test_game_config_keeps_future_options() -> None:
    config = GameConfig.for_size(10, portal_count=2, abilities_enabled=True)
    assert config.size == 10
    assert config.board.size == 10
    assert config.portal_count == 2
    assert config.abilities_enabled is True


@pytest.mark.parametrize(
    ("size", "count", "king", "queen", "pawn_rank", "black_pawn_rank"),
    [
        (6, 24, "e1", "d1", 1, 4),
        (8, 32, "e1", "d1", 1, 6),
        (10, 36, "f1", "e1", 1, 8),
    ],
)
def test_initial_setup_common(
    size: int,
    count: int,
    king: str,
    queen: str,
    pawn_rank: int,
    black_pawn_rank: int,
) -> None:
    state = GameState.initial(size)
    assert state.config.size == size
    assert len(state.board) == count
    assert len(state.board.pieces_of(_WHITE)) == count // 2
    assert len(state.board.pieces_of(_BLACK)) == count // 2
    assert state.board.king_square(_WHITE) == Square.from_name(king)
    assert state.board.king_square(_BLACK) == Square.from_name(
        f"{king[0]}{size}"
    )
    assert state.board.piece_at(Square.from_name(queen)).type is _QUEEN
    assert state.board.piece_at(Square.from_name(f"{queen[0]}{size}")).type is _QUEEN

    white_pawns = [
        piece
        for piece in state.board.pieces_of(_WHITE)
        if piece.type is _PAWN
    ]
    black_pawns = [
        piece
        for piece in state.board.pieces_of(_BLACK)
        if piece.type is _PAWN
    ]
    assert len(white_pawns) == size
    assert len(black_pawns) == size
    assert {piece.square.rank for piece in white_pawns} == {pawn_rank}
    assert {piece.square.rank for piece in black_pawns} == {black_pawn_rank}

    ids = [piece.id for piece in state.board.iter_pieces()]
    assert len(ids) == len(set(ids))


def test_initial_setup_6x6_back_rank_and_castling() -> None:
    state = GameState.initial(6)
    white_back = [state.board.piece_at(Square(file, 0)) for file in range(6)]
    black_back = [state.board.piece_at(Square(file, 5)) for file in range(6)]
    expected = [_ROOK, _KNIGHT, _BISHOP, _QUEEN, _KING, _ROOK]
    assert [piece.type for piece in white_back] == expected
    assert [piece.type for piece in black_back] == expected
    assert all(piece.color is _WHITE for piece in white_back)
    assert all(piece.color is _BLACK for piece in black_back)
    assert state.castling_rights == frozenset()
    assert not BoardConfig.for_size(6).has_castling


def test_initial_setup_8x8_back_rank() -> None:
    state = GameState.initial(8)
    expected = [
        _ROOK,
        _KNIGHT,
        _BISHOP,
        _QUEEN,
        _KING,
        _BISHOP,
        _KNIGHT,
        _ROOK,
    ]
    assert [
        state.board.piece_at(Square(file, 0)).type for file in range(8)
    ] == expected
    assert [
        state.board.piece_at(Square(file, 7)).type for file in range(8)
    ] == expected
    assert state.castling_rights == frozenset({"K", "Q", "k", "q"})


def test_initial_setup_10x10_back_rank_and_empty_corners() -> None:
    state = GameState.initial(10)
    for corner in ("a1", "j1", "a10", "j10"):
        assert state.board.piece_at(Square.from_name(corner)) is None

    expected = [
        None,
        _ROOK,
        _KNIGHT,
        _BISHOP,
        _QUEEN,
        _KING,
        _BISHOP,
        _KNIGHT,
        _ROOK,
        None,
    ]
    assert [
        None if piece is None else piece.type
        for piece in (
            state.board.piece_at(Square(file, 0)) for file in range(10)
        )
    ] == expected
    assert [
        None if piece is None else piece.type
        for piece in (
            state.board.piece_at(Square(file, 9)) for file in range(10)
        )
    ] == expected
    assert state.castling_rights == frozenset({"K", "Q", "k", "q"})


def test_initial_move_counts_on_6x6_and_10x10() -> None:
    assert len(generate_legal_moves(GameState.initial(6))) == 14
    assert len(generate_legal_moves(GameState.initial(10))) == 26


# ---------------------------------------------------------------------------
# Рокировка
# ---------------------------------------------------------------------------


def test_castling_is_forbidden_on_6x6() -> None:
    state = make_state(
        6,
        [
            (_KING, _WHITE, "e1"),
            (_ROOK, _WHITE, "a1"),
            (_ROOK, _WHITE, "f1"),
            (_KING, _BLACK, "e6"),
        ],
        castling_rights=frozenset({"K", "Q"}),
    )
    assert castle_moves(state) == []


def test_standard_castling_on_8x8() -> None:
    state = make_state(
        8,
        [
            (_KING, _WHITE, "e1"),
            (_ROOK, _WHITE, "h1"),
            (_KING, _BLACK, "e8"),
        ],
    )
    move = find_move(state, "e1", "g1")
    assert move.castle == "K"
    after = state.apply_move(move)
    assert after.board.piece_at(Square.from_name("g1")).type is _KING
    assert after.board.piece_at(Square.from_name("f1")).type is _ROOK
    assert after.board.piece_at(Square.from_name("h1")) is None


@pytest.mark.parametrize(
    ("side", "king_to", "rook_to"),
    [("K", "h1", "g1"), ("Q", "d1", "e1")],
)
def test_generalized_castling_on_10x10(
    side: str,
    king_to: str,
    rook_to: str,
) -> None:
    state = make_state(
        10,
        [
            (_KING, _WHITE, "f1"),
            (_ROOK, _WHITE, "i1"),
            (_ROOK, _WHITE, "b1"),
            (_KING, _BLACK, "a10"),
        ],
    )
    move = find_move(state, "f1", king_to)
    assert move.castle == side
    after = state.apply_move(move)
    assert after.board.piece_at(Square.from_name(king_to)).type is _KING
    assert after.board.piece_at(Square.from_name(rook_to)).type is _ROOK


def test_castling_blocked_and_attacked_on_10x10() -> None:
    base = [
        (_KING, _WHITE, "f1"),
        (_ROOK, _WHITE, "i1"),
        (_ROOK, _WHITE, "b1"),
        (_KING, _BLACK, "a10"),
    ]

    in_check = make_state(10, base + [(_ROOK, _BLACK, "f10")])
    assert is_in_check(in_check, _WHITE)
    assert castle_moves(in_check) == []

    through_attack = make_state(10, base + [(_ROOK, _BLACK, "g10")])
    assert [move.castle for move in castle_moves(through_attack)] == ["Q"]

    destination_attack = make_state(10, base + [(_ROOK, _BLACK, "h10")])
    assert [move.castle for move in castle_moves(destination_attack)] == ["Q"]

    occupied_king_side = make_state(10, base + [(_BISHOP, _WHITE, "g1")])
    assert [move.castle for move in castle_moves(occupied_king_side)] == ["Q"]

    occupied_queen_side = make_state(10, base + [(_BISHOP, _WHITE, "c1")])
    assert [move.castle for move in castle_moves(occupied_queen_side)] == ["K"]


def test_castling_rights_lost_after_rook_move_on_10x10() -> None:
    state = make_state(
        10,
        [
            (_KING, _WHITE, "f1"),
            (_ROOK, _WHITE, "i1"),
            (_ROOK, _WHITE, "b1"),
            (_KING, _BLACK, "a10"),
        ],
    )
    for from_name, to_name in (
        ("i1", "i2"),
        ("a10", "a9"),
        ("i2", "i1"),
        ("a9", "a10"),
    ):
        state = play(state, from_name, to_name)

    assert "K" not in state.castling_rights
    assert "Q" in state.castling_rights
    assert [move.castle for move in castle_moves(state)] == ["Q"]


def test_castling_rights_lost_after_king_move_on_10x10() -> None:
    state = make_state(
        10,
        [
            (_KING, _WHITE, "f1"),
            (_ROOK, _WHITE, "i1"),
            (_ROOK, _WHITE, "b1"),
            (_KING, _BLACK, "a10"),
        ],
    )
    for from_name, to_name in (
        ("f1", "f2"),
        ("a10", "a9"),
        ("f2", "f1"),
        ("a9", "a10"),
    ):
        state = play(state, from_name, to_name)

    assert "K" not in state.castling_rights
    assert "Q" not in state.castling_rights
    assert castle_moves(state) == []


def test_castling_right_lost_when_rook_is_captured_on_10x10() -> None:
    state = make_state(
        10,
        [
            (_KING, _WHITE, "f1"),
            (_ROOK, _WHITE, "i1"),
            (_KING, _BLACK, "a10"),
            (_ROOK, _BLACK, "i10"),
        ],
        side=_BLACK,
    )
    state = play(state, "i10", "i1")

    assert "K" not in state.castling_rights
    assert "k" not in state.castling_rights


# ---------------------------------------------------------------------------
# Пешки: двойной ход, en passant и превращение
# ---------------------------------------------------------------------------


def test_double_push_only_from_start_rank_on_6x6() -> None:
    state = make_state(
        6,
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "f6"),
            (_PAWN, _WHITE, "e2"),
        ],
    )
    moves = [
        move for move in generate_legal_moves(state) if move.from_square.name == "e2"
    ]
    assert {move.to_square.name for move in moves} == {"e3", "e4"}
    assert any(move.is_double for move in moves)

    state = play(state, "e2", "e3")
    state = play(state, "f6", "f5")
    moves = [
        move for move in generate_legal_moves(state) if move.from_square.name == "e3"
    ]
    assert {move.to_square.name for move in moves} == {"e4"}
    assert not any(move.is_double for move in moves)


def test_en_passant_on_6x6_both_colors() -> None:
    white_state = make_state(
        6,
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "f6"),
            (_PAWN, _WHITE, "e3"),
            (_PAWN, _BLACK, "d5"),
        ],
        side=_BLACK,
    )
    white_state = play(white_state, "d5", "d3")
    assert white_state.en_passant_target == Square.from_name("d4")
    move = find_move(white_state, "e3", "d4")
    assert move.en_passant
    white_state = white_state.apply_move(move)
    assert white_state.board.piece_at(Square.from_name("d4")).color is _WHITE
    assert white_state.board.piece_at(Square.from_name("d3")) is None

    black_state = make_state(
        6,
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "f6"),
            (_PAWN, _WHITE, "e2"),
            (_PAWN, _BLACK, "d4"),
        ],
    )
    black_state = play(black_state, "e2", "e4")
    assert black_state.en_passant_target == Square.from_name("e3")
    move = find_move(black_state, "d4", "e3")
    assert move.en_passant
    black_state = black_state.apply_move(move)
    assert black_state.board.piece_at(Square.from_name("e3")).color is _BLACK
    assert black_state.board.piece_at(Square.from_name("e4")) is None


def test_en_passant_on_10x10_both_colors() -> None:
    white_state = make_state(
        10,
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "j10"),
            (_PAWN, _WHITE, "e7"),
            (_PAWN, _BLACK, "d9"),
        ],
        side=_BLACK,
    )
    white_state = play(white_state, "d9", "d7")
    assert white_state.en_passant_target == Square.from_name("d8")
    move = find_move(white_state, "e7", "d8")
    assert move.en_passant
    white_state = white_state.apply_move(move)
    assert white_state.board.piece_at(Square.from_name("d8")).color is _WHITE
    assert white_state.board.piece_at(Square.from_name("d7")) is None

    black_state = make_state(
        10,
        [
            (_KING, _WHITE, "j1"),
            (_KING, _BLACK, "j10"),
            (_PAWN, _WHITE, "d2"),
            (_PAWN, _BLACK, "e4"),
        ],
    )
    black_state = play(black_state, "d2", "d4")
    assert black_state.en_passant_target == Square.from_name("d3")
    move = find_move(black_state, "e4", "d3")
    assert move.en_passant
    black_state = black_state.apply_move(move)
    assert black_state.board.piece_at(Square.from_name("d3")).color is _BLACK
    assert black_state.board.piece_at(Square.from_name("d4")) is None


def test_en_passant_expires_after_another_move_on_10x10() -> None:
    state = make_state(
        10,
        [
            (_KING, _WHITE, "j1"),
            (_KING, _BLACK, "j10"),
            (_PAWN, _WHITE, "d2"),
            (_PAWN, _BLACK, "e4"),
        ],
    )
    state = play(state, "d2", "d4")
    state = play(state, "j10", "i10")
    assert state.en_passant_target is None
    assert not any(
        move.from_square.name == "e4" and move.to_square.name == "d3"
        for move in generate_legal_moves(state)
    )


@pytest.mark.parametrize("promotion", list(PROMOTION_PIECES))
@pytest.mark.parametrize(
    ("size", "pawn_from", "pawn_to", "color", "white_king", "black_king"),
    [
        (6, "e5", "e6", _WHITE, "a1", "a6"),
        (6, "e2", "e1", _BLACK, "a1", "f6"),
        (10, "e9", "e10", _WHITE, "a1", "j10"),
        (10, "e2", "e1", _BLACK, "a1", "j10"),
    ],
)
def test_promotion_on_6_and_10(
    promotion: PieceType,
    size: int,
    pawn_from: str,
    pawn_to: str,
    color: Color,
    white_king: str,
    black_king: str,
) -> None:
    state = make_state(
        size,
        [
            (_KING, _WHITE, white_king),
            (_KING, _BLACK, black_king),
            (_PAWN, color, pawn_from),
        ],
        side=color,
    )
    move = find_move(state, pawn_from, pawn_to, promotion)
    after = state.apply_move(move)
    piece = after.board.piece_at(Square.from_name(pawn_to))
    assert piece.type is promotion
    assert piece.color is color
    assert after.history[-1].endswith(f"={promotion.letter}")


# ---------------------------------------------------------------------------
# Ничьи
# ---------------------------------------------------------------------------


def test_fifty_move_draw_on_100th_halfmove() -> None:
    state = make_state(
        8,
        [
            (_KING, _WHITE, "e1"),
            (_KING, _BLACK, "e8"),
            (_ROOK, _WHITE, "a1"),
        ],
        halfmove_clock=99,
    )
    state = play(state, "a1", "a2")
    assert state.halfmove_clock == 100
    assert state.status is GameStatus.DRAW_50_MOVES
    assert state.result.title == "Ничья по 50 ходам"


def test_pawn_move_resets_fifty_move_counter() -> None:
    state = make_state(
        8,
        [
            (_KING, _WHITE, "e1"),
            (_KING, _BLACK, "e8"),
            (_PAWN, _WHITE, "a2"),
        ],
        halfmove_clock=99,
    )
    state = play(state, "a2", "a4")
    assert state.halfmove_clock == 0
    assert state.status is GameStatus.ONGOING


def test_threefold_repetition_draw() -> None:
    state = GameState.initial(8)
    moves = [
        ("g1", "f3"),
        ("g8", "f6"),
        ("f3", "g1"),
        ("f6", "g8"),
    ]
    for _ in range(2):
        for from_name, to_name in moves:
            state = play(state, from_name, to_name)

    assert state.history_hashes.count(state.position_hash) == 3
    assert state.status is GameStatus.DRAW_REPETITION
    assert state.result.title == "Троекратное повторение"


@pytest.mark.parametrize(
    "pieces",
    [
        [(_KING, _WHITE, "a1"), (_KING, _BLACK, "h8")],
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "h8"),
            (_BISHOP, _WHITE, "c1"),
        ],
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "h8"),
            (_KNIGHT, _WHITE, "b1"),
        ],
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "h8"),
            (_BISHOP, _WHITE, "b1"),
            (_BISHOP, _BLACK, "d1"),
        ],
    ],
)
def test_insufficient_material_draws(
    pieces: list[tuple[PieceType, Color, str]],
) -> None:
    state = make_state(8, pieces)
    assert state.status is GameStatus.DRAW_INSUFFICIENT_MATERIAL
    assert state.result.title == "Недостаточный материал"


@pytest.mark.parametrize(
    "pieces",
    [
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "h8"),
            (_BISHOP, _WHITE, "b1"),
            (_BISHOP, _BLACK, "c1"),
        ],
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "h8"),
            (_KNIGHT, _WHITE, "b1"),
            (_KNIGHT, _BLACK, "g1"),
        ],
        [
            (_KING, _WHITE, "a1"),
            (_KING, _BLACK, "h8"),
            (_PAWN, _WHITE, "a2"),
        ],
    ],
)
def test_sufficient_material_is_not_a_draw(
    pieces: list[tuple[PieceType, Color, str]],
) -> None:
    state = make_state(8, pieces)
    assert state.status is GameStatus.ONGOING


def test_pending_resurrection_blocks_insufficient_material() -> None:
    state = make_state(
        8,
        [(_KING, _WHITE, "a1"), (_KING, _BLACK, "h8")],
    )
    state.pending_resurrections = (("wQ", 0, "a2"),)
    assert state.evaluate_result() is None


def test_resignation_and_agreement() -> None:
    state = GameState.initial(8)

    white_resigned = state.resign(_WHITE)
    assert white_resigned.status is GameStatus.RESIGN_WHITE
    assert white_resigned.result.winner is _BLACK
    assert white_resigned.result.title == "Белые сдались"

    black_resigned = state.resign(_BLACK)
    assert black_resigned.status is GameStatus.RESIGN_BLACK
    assert black_resigned.result.winner is _WHITE
    assert black_resigned.result.title == "Чёрные сдались"

    agreed = state.agree_draw()
    assert agreed.status is GameStatus.DRAW_AGREEMENT
    assert agreed.result.is_draw
    assert agreed.result.title == "Ничья по соглашению"


def test_move_after_finished_game_is_rejected() -> None:
    state = GameState.initial(8).resign(_WHITE)
    move = find_move(GameState.initial(8), "e2", "e4")
    with pytest.raises(ValueError):
        state.apply_move(move)


# ---------------------------------------------------------------------------
# Шах, мат и пат на 6x6 и 10x10
# ---------------------------------------------------------------------------


def test_checkmate_on_6x6() -> None:
    state = make_state(
        6,
        [
            (_KING, _BLACK, "a6"),
            (_KING, _WHITE, "c5"),
            (_QUEEN, _WHITE, "b6"),
        ],
        side=_BLACK,
    )
    assert is_in_check(state, _BLACK)
    assert is_checkmate(state, _BLACK)
    assert state.status is GameStatus.WHITE_WIN
    assert state.result.winner is _WHITE
    assert state.result.title == "Мат! Победа белых"


def test_checkmate_on_10x10() -> None:
    state = make_state(
        10,
        [
            (_KING, _BLACK, "a10"),
            (_KING, _WHITE, "c9"),
            (_QUEEN, _WHITE, "b10"),
        ],
        side=_BLACK,
    )
    assert is_in_check(state, _BLACK)
    assert is_checkmate(state, _BLACK)
    assert state.status is GameStatus.WHITE_WIN


def test_stalemate_on_6x6() -> None:
    state = make_state(
        6,
        [
            (_KING, _BLACK, "a6"),
            (_KING, _WHITE, "c5"),
            (_QUEEN, _WHITE, "b4"),
        ],
        side=_BLACK,
    )
    assert not is_in_check(state, _BLACK)
    assert is_stalemate(state, _BLACK)
    assert generate_legal_moves(state) == []
    assert state.status is GameStatus.DRAW_STALEMATE
    assert state.result.title == "Пат — ничья"


def test_stalemate_on_10x10() -> None:
    state = make_state(
        10,
        [
            (_KING, _BLACK, "a10"),
            (_KING, _WHITE, "c9"),
            (_QUEEN, _WHITE, "b8"),
        ],
        side=_BLACK,
    )
    assert not is_in_check(state, _BLACK)
    assert is_stalemate(state, _BLACK)
    assert state.status is GameStatus.DRAW_STALEMATE


def test_check_is_detected_on_6x6_and_10x10() -> None:
    state_6 = make_state(
        6,
        [
            (_KING, _BLACK, "a6"),
            (_KING, _WHITE, "c5"),
            (_ROOK, _WHITE, "a1"),
        ],
        side=_BLACK,
    )
    assert is_in_check(state_6, _BLACK)

    state_10 = make_state(
        10,
        [
            (_KING, _BLACK, "a10"),
            (_KING, _WHITE, "c9"),
            (_ROOK, _WHITE, "a1"),
        ],
        side=_BLACK,
    )
    assert is_in_check(state_10, _BLACK)
