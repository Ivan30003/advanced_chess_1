"""Тесты ядра: расстановка, perft, рокировка, en passant, превращение."""

from __future__ import annotations

import pytest

from chess.core.board import Board
from chess.core.coords import Square
from chess.core.game_state import GameState
from chess.core.moves import Move, Turn
from chess.core.pieces import Color, Piece, PieceType, PROMOTION_PIECES
from chess.core.rules import (
    generate_legal_moves,
    generate_pseudo_moves,
    is_checkmate,
    is_in_check,
    is_stalemate,
)

_FEN_TYPES = {
    "p": PieceType.PAWN,
    "n": PieceType.KNIGHT,
    "b": PieceType.BISHOP,
    "r": PieceType.ROOK,
    "q": PieceType.QUEEN,
    "k": PieceType.KING,
}


def state_from_fen(fen: str) -> GameState:
    """Небольшой FEN-парсер для тестовых позиций."""

    board_part, turn, castling, en_passant, halfmove, fullmove = fen.split()
    board = Board.empty()
    for rank_index, row in enumerate(board_part.split("/")):
        rank = 7 - rank_index
        file = 0
        for char in row:
            if char.isdigit():
                file += int(char)
                continue
            color = Color.WHITE if char.isupper() else Color.BLACK
            piece_type = _FEN_TYPES[char.lower()]
            square = Square(file, rank)
            board.add_piece(
                Piece(
                    id=f"{color.value[0]}{piece_type.letter}-{square.name}",
                    type=piece_type,
                    color=color,
                    square=square,
                    original_square=square,
                )
            )
            file += 1
    rights = frozenset(castling) if castling != "-" else frozenset()
    target = Square.from_name(en_passant) if en_passant != "-" else None
    return GameState(
        board=board,
        side_to_move=Color.WHITE if turn == "w" else Color.BLACK,
        castling_rights=rights,
        en_passant_target=target,
        halfmove_clock=int(halfmove),
        turn_number=int(fullmove),
    )


def find_move(
    state: GameState,
    from_name: str,
    to_name: str,
    promotion: PieceType | None = None,
):
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


def perft(state: GameState, depth: int) -> int:
    if depth == 0:
        return 1
    total = 0
    for move in generate_legal_moves(state):
        child = state.apply_move(move, detect_result=False, record_history=False)
        total += perft(child, depth - 1)
    return total


# ---------------------------------------------------------------------------
# Расстановка и perft
# ---------------------------------------------------------------------------


def test_initial_setup() -> None:
    state = GameState.initial()
    assert len(state.board) == 32
    assert len(state.board.pieces_of(Color.WHITE)) == 16
    assert len(state.board.pieces_of(Color.BLACK)) == 16
    assert state.board.king_square(Color.WHITE) == Square.from_name("e1")
    assert state.board.king_square(Color.BLACK) == Square.from_name("e8")
    assert state.board.piece_at(Square.from_name("d1")).type is PieceType.QUEEN
    assert state.board.piece_at(Square.from_name("d8")).type is PieceType.QUEEN
    assert state.side_to_move is Color.WHITE
    assert state.history == []
    assert state.result is None

    ids = [piece.id for piece in state.board.iter_pieces()]
    assert len(ids) == len(set(ids))


def test_perft_initial_position() -> None:
    state = GameState.initial()
    assert perft(state, 1) == 20
    assert perft(state, 2) == 400
    assert perft(state, 3) == 8902
    assert perft(state, 4) == 197281


def test_perft_kiwipete_castling_position() -> None:
    state = state_from_fen(
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
    )
    assert perft(state, 1) == 48
    assert perft(state, 2) == 2039
    assert perft(state, 3) == 97862


def test_perft_en_passant_position() -> None:
    state = state_from_fen("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1")
    assert perft(state, 1) == 14
    assert perft(state, 2) == 191
    assert perft(state, 3) == 2812
    assert perft(state, 4) == 43238


# ---------------------------------------------------------------------------
# Рокировка
# ---------------------------------------------------------------------------


def test_white_kingside_castling_is_played() -> None:
    state = GameState.initial()
    for from_name, to_name in (
        ("e2", "e4"),
        ("e7", "e5"),
        ("g1", "f3"),
        ("b8", "c6"),
        ("f1", "c4"),
        ("f8", "c5"),
    ):
        state = play(state, from_name, to_name)

    move = find_move(state, "e1", "g1")
    assert move.castle == "K"
    state = state.apply_move(move)
    assert state.history[-1] == "O-O"
    assert state.board.piece_at(Square.from_name("g1")).type is PieceType.KING
    assert state.board.piece_at(Square.from_name("f1")).type is PieceType.ROOK
    assert state.board.piece_at(Square.from_name("h1")) is None


def test_white_queenside_castling_is_played() -> None:
    state = state_from_fen(
        "r3k2r/pppq1ppp/2npbn2/4p3/4P3/2NPBN2/PPPQ1PPP/R3K2R w KQkq - 0 1"
    )
    move = find_move(state, "e1", "c1")
    assert move.castle == "Q"
    state = state.apply_move(move)
    assert state.history[-1] == "O-O-O"
    assert state.board.piece_at(Square.from_name("c1")).type is PieceType.KING
    assert state.board.piece_at(Square.from_name("d1")).type is PieceType.ROOK
    assert state.board.piece_at(Square.from_name("a1")) is None


def test_castling_forbidden_while_in_check() -> None:
    state = state_from_fen("4r2k/8/8/8/8/8/8/4K2R w K - 0 1")
    assert is_in_check(state, Color.WHITE)
    assert not any(move.castle for move in generate_legal_moves(state))


def test_castling_forbidden_through_attacked_square() -> None:
    state = state_from_fen("5r1k/8/8/8/8/8/8/4K2R w K - 0 1")
    assert not is_in_check(state, Color.WHITE)
    # f1 пробита ладьёй по вертикали f, поэтому короткая рокировка запрещена.
    assert not any(move.castle for move in generate_legal_moves(state))


def test_castling_rights_lost_after_rook_moves() -> None:
    state = state_from_fen("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
    state = play(state, "h1", "h2")
    state = play(state, "e8", "e7")
    state = play(state, "h2", "h1")
    state = play(state, "e7", "e8")
    assert "K" not in state.castling_rights
    assert not any(move.castle for move in generate_legal_moves(state))


def test_castling_rights_lost_after_king_moves() -> None:
    state = state_from_fen("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
    state = play(state, "e1", "e2")
    state = play(state, "e8", "e7")
    state = play(state, "e2", "e1")
    state = play(state, "e7", "e8")
    assert "K" not in state.castling_rights
    assert not any(move.castle for move in generate_legal_moves(state))


# ---------------------------------------------------------------------------
# Взятие на проходе
# ---------------------------------------------------------------------------


def test_en_passant_only_immediately_after_double_push() -> None:
    state = GameState.initial()
    state = play(state, "e2", "e4")
    state = play(state, "a7", "a6")
    state = play(state, "e4", "e5")
    state = play(state, "d7", "d5")

    assert state.en_passant_target == Square.from_name("d6")
    move = find_move(state, "e5", "d6")
    assert move.en_passant
    assert move.capture is not None
    assert move.capture.type is PieceType.PAWN

    after = state.apply_move(move)
    assert after.board.piece_at(Square.from_name("d6")).color is Color.WHITE
    assert after.board.piece_at(Square.from_name("d5")) is None
    assert after.history[-1] == "e5xd6"


def test_en_passant_expires_after_another_move() -> None:
    state = GameState.initial()
    state = play(state, "e2", "e4")
    state = play(state, "a7", "a6")
    state = play(state, "e4", "e5")
    state = play(state, "d7", "d5")

    state = play(state, "g1", "f3")
    state = play(state, "a6", "a5")
    assert state.en_passant_target is None
    assert not any(
        move.from_square.name == "e5" and move.to_square.name == "d6"
        for move in generate_legal_moves(state)
    )


def test_black_en_passant() -> None:
    state = state_from_fen("4k3/8/8/8/3pP3/8/8/4K3 b - e3 0 1")
    move = find_move(state, "d4", "e3")
    assert move.en_passant
    after = state.apply_move(move)
    assert after.board.piece_at(Square.from_name("e3")).color is Color.BLACK
    assert after.board.piece_at(Square.from_name("e4")) is None


# ---------------------------------------------------------------------------
# Превращение
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("promotion", list(PROMOTION_PIECES))
def test_white_promotion_to_all_types(promotion: PieceType) -> None:
    state = state_from_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    move = find_move(state, "a7", "a8", promotion)
    after = state.apply_move(move)
    piece = after.board.piece_at(Square.from_name("a8"))
    assert piece.type is promotion
    assert piece.color is Color.WHITE
    assert after.history[-1] == f"a7-a8={promotion.letter}"


def test_black_promotion_to_queen() -> None:
    state = state_from_fen("4k3/8/8/8/8/8/p7/4K3 b - - 0 1")
    move = find_move(state, "a2", "a1", PieceType.QUEEN)
    after = state.apply_move(move)
    assert after.board.piece_at(Square.from_name("a1")).type is PieceType.QUEEN
    assert after.history[-1] == "a2-a1=Q"


def test_promotion_generates_four_choices() -> None:
    state = state_from_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    promotions = {
        move.promotion
        for move in generate_legal_moves(state)
        if move.from_square.name == "a7" and move.to_square.name == "a8"
    }
    assert promotions == {
        PieceType.QUEEN,
        PieceType.ROOK,
        PieceType.BISHOP,
        PieceType.KNIGHT,
    }


# ---------------------------------------------------------------------------
# Шах, мат, пат и безопасность короля
# ---------------------------------------------------------------------------


def test_fools_mate_detected() -> None:
    state = GameState.initial()
    for from_name, to_name in (
        ("f2", "f3"),
        ("e7", "e5"),
        ("g2", "g4"),
        ("d8", "h4"),
    ):
        state = play(state, from_name, to_name)

    assert is_in_check(state, Color.WHITE)
    assert is_checkmate(state, Color.WHITE)
    assert state.result is not None
    assert state.result.kind == "checkmate"
    assert state.result.winner is Color.BLACK
    assert state.result.title == "Мат! Победа чёрных"


def test_stalemate_detected() -> None:
    state = state_from_fen("7k/5K2/6Q1/8/8/8/8/8 b - - 0 1")
    assert not is_in_check(state, Color.BLACK)
    assert is_stalemate(state, Color.BLACK)
    assert generate_legal_moves(state) == []
    result = state.evaluate_result()
    assert result is not None
    assert result.kind == "stalemate"
    assert result.title == "Пат — ничья"


def test_move_leaving_king_in_check_is_not_generated() -> None:
    state = state_from_fen("4r2k/8/8/8/8/8/4B3/4K3 w - - 0 1")
    assert is_in_check(state, Color.WHITE) is False

    legal = generate_legal_moves(state)
    bishop_moves = [move for move in legal if move.from_square == Square.from_name("e2")]
    assert bishop_moves == []

    pseudo = generate_pseudo_moves(state, state.board.piece_at(Square.from_name("e2")))
    assert pseudo, "псевдолегальные ходы слона должны существовать"
    assert all(move.from_square.name == "e2" for move in pseudo)


def test_turn_single_move_and_history() -> None:
    state = GameState.initial()
    move = find_move(state, "e2", "e4")
    turn = Turn.single(move)
    after = state.apply_turn(turn)
    assert after.history == ["e2-e4"]
    assert state.history == []
    assert after.en_passant_target == Square.from_name("e3")
    assert after.halfmove_clock == 0
    assert after.side_to_move is Color.BLACK
    assert after.turn_number == 1


def test_turn_number_increments_after_black() -> None:
    state = GameState.initial()
    state = play(state, "e2", "e4")
    assert state.turn_number == 1
    state = play(state, "e7", "e5")
    assert state.turn_number == 2
    assert state.halfmove_clock == 0


def test_quiet_moves_increase_halfmove_clock() -> None:
    state = GameState.initial()
    state = play(state, "g1", "f3")
    assert state.halfmove_clock == 1
    state = play(state, "g8", "f6")
    assert state.halfmove_clock == 2


def test_move_object_is_immutable_and_stable() -> None:
    state = GameState.initial()
    move: Move = find_move(state, "e2", "e4")
    assert move.piece_id == "wP-e2"
    assert move.is_double
    assert move.is_capture is False
    with pytest.raises(Exception):
        move.to_square = Square.from_name("e5")  # type: ignore[misc]
