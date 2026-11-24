"""Тесты этапа 5: благословения короля и пять способностей."""

from __future__ import annotations

import pytest

from chess.core.blessings import (
    BlessAction,
    BlessingType,
    FreezeAction,
    PendingResurrection,
)
from chess.core.board import Board
from chess.core.board_config import BoardConfig, GameConfig
from chess.core.coords import Square
from chess.core.game_state import GameState, GameStatus
from chess.core.moves import Move, Turn
from chess.core.pieces import Color, Piece, PieceType
from chess.core.portals import PortalActivation, PortalPair
from chess.core.rules import (
    generate_legal_moves,
    generate_legal_turns,
    is_in_check,
    legal_bless_targets,
)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _piece(
    piece_id: str,
    piece_type: PieceType,
    color: Color,
    square: str,
    *,
    blessing: BlessingType | None = None,
    ever_blessed: bool = False,
    blessing_used: bool = False,
    has_moved: bool = False,
) -> Piece:
    return Piece(
        id=piece_id,
        type=piece_type,
        color=color,
        square=Square.from_name(square),
        original_square=Square.from_name(square),
        blessing=blessing,
        ever_blessed=ever_blessed,
        blessing_used=blessing_used,
        has_moved=has_moved,
    )


def _state(
    pieces: list[Piece],
    *,
    side: Color = Color.WHITE,
    white_choice: BlessingType | None = None,
    black_choice: BlessingType | None = None,
    abilities: bool = True,
    portals: tuple[PortalPair, ...] = (),
    **kwargs,
) -> GameState:
    board = Board.empty(BoardConfig.for_size(8))
    for piece in pieces:
        board.add_piece(piece)
    return GameState(
        board=board,
        config=GameConfig.for_size(8, abilities_enabled=abilities),
        side_to_move=side,
        castling_rights=frozenset(),
        portals=list(portals),
        blessing_choice={Color.WHITE: white_choice, Color.BLACK: black_choice},
        **kwargs,
    )


def _kings(*, white: str = "e1", black: str = "e8") -> list[Piece]:
    return [
        _piece("wK", PieceType.KING, Color.WHITE, white),
        _piece("bK", PieceType.KING, Color.BLACK, black),
    ]


def _find_move(
    state: GameState,
    from_name: str,
    to_name: str,
    *,
    piece_id: str | None = None,
) -> Move:
    for move in generate_legal_moves(state):
        if move.from_square.name != from_name or move.to_square.name != to_name:
            continue
        if piece_id is not None and move.piece_id != piece_id:
            continue
        return move
    raise AssertionError(f"Ход {from_name}-{to_name} не найден")


def _bless_turns(state: GameState) -> list[Turn]:
    return [turn for turn in generate_legal_turns(state) if turn.is_bless]


def _freeze_turns(state: GameState) -> list[Turn]:
    return [turn for turn in generate_legal_turns(state) if turn.is_freeze]


def _double_turns(state: GameState) -> list[Turn]:
    return [turn for turn in generate_legal_turns(state) if turn.is_double_move]


def _apply_bless(state: GameState, target_name: str) -> GameState:
    for turn in _bless_turns(state):
        if turn.bless is not None and turn.bless.target_square.name == target_name:
            return state.apply_turn(turn)
    raise AssertionError(f"Благословение {target_name} не найдено")


def _turn_number(state: GameState) -> int:
    return state.turn_number


def _apply_king_move(state: GameState, *, color: Color) -> GameState:
    for move in generate_legal_moves(state):
        piece = state.board.piece_at(move.from_square)
        if piece is not None and piece.type is PieceType.KING:
            return state.apply_turn(Turn.single(move))
    raise AssertionError(f"Нет хода королём у {color}")


# ---------------------------------------------------------------------------
# Общая механика
# ---------------------------------------------------------------------------


def test_initial_state_receives_ability_choices() -> None:
    state = GameState.initial(
        GameConfig.for_size(8, abilities_enabled=True),
        blessing_choice={
            Color.WHITE: BlessingType.FREEZE,
            Color.BLACK: BlessingType.INVULNERABILITY,
        },
    )
    assert state.blessing_choice[Color.WHITE] is BlessingType.FREEZE
    assert state.blessing_choice[Color.BLACK] is BlessingType.INVULNERABILITY
    assert state.bless_cooldown[Color.WHITE] == 0


def test_blessing_can_target_all_eight_adjacent_friendlies() -> None:
    pieces = _kings()
    pieces.extend(
        _piece(f"wR-{name}", PieceType.ROOK, Color.WHITE, name)
        for name in ("d3", "e3", "f3", "d4", "f4", "d5", "e5", "f5")
    )
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e4"),
            _piece("bK", PieceType.KING, Color.BLACK, "e8"),
            *pieces[2:],
        ],
        white_choice=BlessingType.DOUBLE_MOVE,
    )

    targets = {piece.id for piece in legal_bless_targets(state)}
    assert targets == {
        "wR-d3",
        "wR-e3",
        "wR-f3",
        "wR-d4",
        "wR-f4",
        "wR-d5",
        "wR-e5",
        "wR-f5",
    }
    assert len(_bless_turns(state)) == 8


def test_blessing_rejects_self_enemy_blessed_and_ever_blessed() -> None:
    pieces = [
        _piece("wK", PieceType.KING, Color.WHITE, "e4"),
        _piece("bK", PieceType.KING, Color.BLACK, "e8"),
        _piece("wR-d3", PieceType.ROOK, Color.WHITE, "d3"),
        _piece("bR-f5", PieceType.ROOK, Color.BLACK, "f5"),
        _piece(
            "wB-e3",
            PieceType.BISHOP,
            Color.WHITE,
            "e3",
            blessing=BlessingType.FREEZE,
            ever_blessed=True,
        ),
        _piece(
            "wN-d4",
            PieceType.KNIGHT,
            Color.WHITE,
            "d4",
            ever_blessed=True,
            blessing_used=True,
        ),
        _piece("wR-e5", PieceType.ROOK, Color.WHITE, "e5"),
    ]
    state = _state(pieces, white_choice=BlessingType.INVULNERABILITY)

    targets = {piece.id for piece in legal_bless_targets(state)}
    assert targets == {"wR-d3", "wR-e5"}

    with pytest.raises(ValueError):
        state.apply_turn(
            Turn(
                bless=BlessAction(
                    Square.from_name("e4"),
                    Square.from_name("f5"),
                    "bR-f5",
                )
            )
        )
    with pytest.raises(ValueError):
        state.apply_turn(
            Turn(
                bless=BlessAction(
                    Square.from_name("e4"),
                    Square.from_name("e3"),
                    "wB-e3",
                )
            )
        )


def test_blessing_replaces_king_move_and_starts_cooldown() -> None:
    state = _state(
        [
            *_kings(),
            _piece("wR-d1", PieceType.ROOK, Color.WHITE, "d1"),
        ],
        white_choice=BlessingType.RESURRECTION,
    )
    after = _apply_bless(state, "d1")

    assert after.side_to_move is Color.BLACK
    assert after.board.king_square(Color.WHITE) == Square.from_name("e1")
    assert after.board.piece_at(Square.from_name("d1")).blessing is BlessingType.RESURRECTION
    assert after.bless_cooldown[Color.WHITE] == 3
    assert after.halfmove_clock == state.halfmove_clock + 1
    assert after.history[-1].startswith("Благословение: d1")


def test_blessing_cooldown_is_t_plus_three() -> None:
    state = _state(
        [
            *_kings(),
            _piece("wR-d1", PieceType.ROOK, Color.WHITE, "d1"),
            _piece("wR-f1", PieceType.ROOK, Color.WHITE, "f1"),
            _piece("wN-b1", PieceType.KNIGHT, Color.WHITE, "b1"),
            _piece("bN-b8", PieceType.KNIGHT, Color.BLACK, "b8"),
        ],
        white_choice=BlessingType.INVULNERABILITY,
        black_choice=BlessingType.INVULNERABILITY,
    )
    state = _apply_bless(state, "d1")
    assert state.bless_cooldown[Color.WHITE] == 3
    assert not _bless_turns(state)

    # Один ход чёрных, затем ход белых: кулдаун 2.
    state = _apply_king_move(state, color=Color.BLACK)
    assert state.side_to_move is Color.WHITE
    assert state.bless_cooldown[Color.WHITE] == 2
    assert not _bless_turns(state)

    # Ещё один свой ход: кулдаун 1.
    state = _apply_king_move(state, color=Color.WHITE)
    state = _apply_king_move(state, color=Color.BLACK)
    assert state.side_to_move is Color.WHITE
    assert state.bless_cooldown[Color.WHITE] == 1
    assert not _bless_turns(state)

    # Следующий свой ход: способность снова доступна.
    state = _apply_king_move(state, color=Color.WHITE)
    state = _apply_king_move(state, color=Color.BLACK)
    assert state.side_to_move is Color.WHITE
    assert state.bless_cooldown[Color.WHITE] == 0
    assert any(
        turn.bless is not None
        and turn.bless.target_square.name == "f1"
        for turn in _bless_turns(state)
    )


def test_blessing_forbidden_while_in_check() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "e8"),
            _piece("bR", PieceType.ROOK, Color.BLACK, "e7"),
            _piece("wR-d1", PieceType.ROOK, Color.WHITE, "d1"),
        ],
        white_choice=BlessingType.FREEZE,
    )
    assert is_in_check(state, Color.WHITE)
    assert legal_bless_targets(state) == []
    assert not _bless_turns(state)
    with pytest.raises(ValueError):
        state.apply_turn(
            Turn(
                bless=BlessAction(
                    Square.from_name("e1"),
                    Square.from_name("d1"),
                    "wR-d1",
                )
            )
        )


def test_blessings_disabled_by_configuration() -> None:
    state = _state(
        [
            *_kings(),
            _piece("wR-d1", PieceType.ROOK, Color.WHITE, "d1"),
        ],
        abilities=False,
        white_choice=BlessingType.FREEZE,
    )
    assert legal_bless_targets(state) == []
    assert not _bless_turns(state)
    with pytest.raises(ValueError):
        state.apply_turn(
            Turn(
                bless=BlessAction(
                    Square.from_name("e1"),
                    Square.from_name("d1"),
                    "wR-d1",
                )
            )
        )


def test_each_piece_can_be_blessed_only_once() -> None:
    state = _state(
        [
            *_kings(),
            _piece("wR-d1", PieceType.ROOK, Color.WHITE, "d1"),
            _piece("wR-f1", PieceType.ROOK, Color.WHITE, "f1"),
            _piece("wN-b1", PieceType.KNIGHT, Color.WHITE, "b1"),
            _piece("bN-b8", PieceType.KNIGHT, Color.BLACK, "b8"),
        ],
        white_choice=BlessingType.INVULNERABILITY,
    )
    state = _apply_bless(state, "d1")
    # Прокручиваем три полных хода, пока кулдаун не обнулится.
    for _ in range(7):
        knight_moves = [
            move
            for move in generate_legal_moves(state)
            if move.piece_id in {"wN-b1", "bN-b8"}
        ]
        state = state.apply_turn(Turn.single(knight_moves[0]))
    assert state.side_to_move is Color.WHITE
    assert state.bless_cooldown[Color.WHITE] == 0
    targets = {piece.id for piece in legal_bless_targets(state)}
    assert "wR-d1" not in targets
    assert "wR-f1" in targets


# ---------------------------------------------------------------------------
# Неуязвимость
# ---------------------------------------------------------------------------


def test_invulnerability_cancels_capture_and_spends_shield() -> None:
    state = _state(
        [
            *_kings(),
            _piece("wR-a1", PieceType.ROOK, Color.WHITE, "a1"),
            _piece(
                "bB-a4",
                PieceType.BISHOP,
                Color.BLACK,
                "a4",
                blessing=BlessingType.INVULNERABILITY,
                ever_blessed=True,
            ),
        ],
    )
    move = _find_move(state, "a1", "a4")
    after = state.apply_turn(Turn.single(move))

    assert after.board.piece_at(Square.from_name("a1")).id == "wR-a1"
    shielded = after.board.piece_at(Square.from_name("a4"))
    assert shielded is not None and shielded.blessing is None
    assert shielded.blessing_used is True
    assert after.last_cancelled is True
    assert after.side_to_move is Color.BLACK
    assert "отменено щитом" in after.history[-1]


def test_invulnerability_cancels_en_passant() -> None:
    state = _state(
        [
            *_kings(),
            _piece("wP-e5", PieceType.PAWN, Color.WHITE, "e5"),
            _piece(
                "bP-d5",
                PieceType.PAWN,
                Color.BLACK,
                "d5",
                blessing=BlessingType.INVULNERABILITY,
                ever_blessed=True,
            ),
        ],
        en_passant_target=Square.from_name("d6"),
    )
    move = next(move for move in generate_legal_moves(state) if move.en_passant)
    after = state.apply_turn(Turn.single(move))

    assert after.board.piece_at(Square.from_name("e5")) is not None
    pawn = after.board.piece_at(Square.from_name("d5"))
    assert pawn is not None and pawn.blessing is None
    assert after.last_cancelled is True
    assert after.en_passant_target is None


def test_invulnerability_cancels_double_move_and_consumes_ability() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wR-a1",
                PieceType.ROOK,
                Color.WHITE,
                "a1",
                blessing=BlessingType.DOUBLE_MOVE,
                ever_blessed=True,
            ),
            _piece(
                "bP-a3",
                PieceType.PAWN,
                Color.BLACK,
                "a3",
                blessing=BlessingType.INVULNERABILITY,
                ever_blessed=True,
            ),
        ],
        white_choice=BlessingType.DOUBLE_MOVE,
    )
    first = _find_move(state, "a1", "a2")
    preview = state.copy()
    from chess.core.rules import _preview_after_move

    preview = _preview_after_move(state, first)
    second = _find_move(preview, "a2", "a3")
    after = state.apply_turn(Turn(moves=[first, second]))

    assert after.board.piece_at(Square.from_name("a1")).id == "wR-a1"
    assert after.board.piece_at(Square.from_name("a2")) is None
    shielded = after.board.piece_at(Square.from_name("a3"))
    assert shielded is not None and shielded.blessing is None
    rook = after.board.piece_at(Square.from_name("a1"))
    assert rook is not None and rook.blessing is None and rook.blessing_used
    assert after.last_cancelled is True
    assert after.side_to_move is Color.BLACK


def test_king_cannot_capture_shielded_piece_while_in_check() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "e8"),
            _piece(
                "bR-e2",
                PieceType.ROOK,
                Color.BLACK,
                "e2",
                blessing=BlessingType.INVULNERABILITY,
                ever_blessed=True,
            ),
        ],
    )
    assert is_in_check(state, Color.WHITE)
    moves = [
        move
        for move in generate_legal_moves(state)
        if move.from_square.name == "e1" and move.to_square.name == "e2"
    ]
    assert not moves
    move = Move(
        piece_id="wK",
        from_square=Square.from_name("e1"),
        to_square=Square.from_name("e2"),
        capture=state.board.piece_at(Square.from_name("e2")),
    )
    with pytest.raises(ValueError):
        state.apply_turn(Turn.single(move))


# ---------------------------------------------------------------------------
# Двойной ход
# ---------------------------------------------------------------------------


def test_double_move_two_moves_and_two_captures() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wR-a1",
                PieceType.ROOK,
                Color.WHITE,
                "a1",
                blessing=BlessingType.DOUBLE_MOVE,
                ever_blessed=True,
            ),
            _piece("bP-a2", PieceType.PAWN, Color.BLACK, "a2"),
            _piece("bP-a3", PieceType.PAWN, Color.BLACK, "a3"),
        ],
        white_choice=BlessingType.DOUBLE_MOVE,
    )
    turn = next(
        turn
        for turn in _double_turns(state)
        if [move.to_square.name for move in turn.moves] == ["a2", "a3"]
    )
    after = state.apply_turn(turn)

    rook = after.board.piece_at(Square.from_name("a3"))
    assert rook is not None and rook.id == "wR-a1"
    assert rook.blessing is None and rook.blessing_used
    assert after.board.piece_at(Square.from_name("a2")) is None
    assert after.side_to_move is Color.BLACK
    assert after.history[-1] == "a1xa2 + a2xa3"


def test_double_move_cannot_checkmate_but_check_is_allowed() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "g6"),
            _piece("bK", PieceType.KING, Color.BLACK, "h8"),
            _piece(
                "wQ-a1",
                PieceType.QUEEN,
                Color.WHITE,
                "a1",
                blessing=BlessingType.DOUBLE_MOVE,
                ever_blessed=True,
            ),
        ],
        white_choice=BlessingType.DOUBLE_MOVE,
    )
    first = _find_move(state, "a1", "a8", piece_id="wQ-a1")
    from chess.core.rules import _preview_after_move

    preview = _preview_after_move(state, first)
    second = _find_move(preview, "a8", "b8", piece_id="wQ-a1")

    assert not any(
        [move.to_square for move in turn.moves] == [first.to_square, second.to_square]
        for turn in _double_turns(state)
    )
    with pytest.raises(ValueError, match="мат"):
        state.apply_turn(Turn(moves=[first, second]))

    # Аналогичный шах без мата разрешён.
    check_state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "h8"),
            _piece(
                "wR-a1",
                PieceType.ROOK,
                Color.WHITE,
                "a1",
                blessing=BlessingType.DOUBLE_MOVE,
                ever_blessed=True,
            ),
        ],
        white_choice=BlessingType.DOUBLE_MOVE,
    )
    first = _find_move(check_state, "a1", "a8", piece_id="wR-a1")
    preview = _preview_after_move(check_state, first)
    second = _find_move(preview, "a8", "b8", piece_id="wR-a1")
    after = check_state.apply_turn(Turn(moves=[first, second]))

    assert after.result is None
    assert is_in_check(after, Color.BLACK)


def test_double_move_may_lead_to_stalemate() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "c7"),
            _piece("bK", PieceType.KING, Color.BLACK, "a8"),
            _piece(
                "wQ-h7",
                PieceType.QUEEN,
                Color.WHITE,
                "h7",
                blessing=BlessingType.DOUBLE_MOVE,
                ever_blessed=True,
            ),
        ],
        white_choice=BlessingType.DOUBLE_MOVE,
    )
    first = _find_move(state, "h7", "h6")
    from chess.core.rules import _preview_after_move

    preview = _preview_after_move(state, first)
    second = _find_move(preview, "h6", "b6")
    after = state.apply_turn(Turn(moves=[first, second]))

    assert not is_in_check(after, Color.BLACK)
    assert after.result is not None
    assert after.result.status is GameStatus.DRAW_STALEMATE


def test_promotion_then_second_move_uses_promoted_piece() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wP-a7",
                PieceType.PAWN,
                Color.WHITE,
                "a7",
                blessing=BlessingType.DOUBLE_MOVE,
                ever_blessed=True,
            ),
            _piece("bR-b8", PieceType.ROOK, Color.BLACK, "b8"),
        ],
        white_choice=BlessingType.DOUBLE_MOVE,
    )
    first = next(
        move
        for move in generate_legal_moves(state)
        if move.to_square.name == "a8" and move.promotion is PieceType.QUEEN
    )
    from chess.core.rules import _preview_after_move

    preview = _preview_after_move(state, first)
    second = _find_move(preview, "a8", "b8")
    after = state.apply_turn(Turn(moves=[first, second]))

    queen = after.board.piece_at(Square.from_name("b8"))
    assert queen is not None and queen.type is PieceType.QUEEN
    assert queen.blessing is None and queen.blessing_used
    assert after.history[-1] == "a7-a8=Q + a8xb8"


def test_double_move_never_activates_more_than_one_portal() -> None:
    pair = PortalPair(
        0,
        0,
        0,
        Square.from_name("a4"),
        Square.from_name("h4"),
    )
    state = _state(
        [
            *_kings(),
            _piece(
                "wR-a1",
                PieceType.ROOK,
                Color.WHITE,
                "a1",
                blessing=BlessingType.DOUBLE_MOVE,
                ever_blessed=True,
            ),
        ],
        white_choice=BlessingType.DOUBLE_MOVE,
        portals=(pair,),
    )
    for turn in _double_turns(state):
        assert turn.portal_activation_count <= 1

    teleport = PortalActivation(
        0,
        Square.from_name("a4"),
        Square.from_name("h4"),
    )
    first = Move(
        piece_id="wR-a1",
        from_square=Square.from_name("a1"),
        to_square=Square.from_name("a4"),
        teleport=teleport,
    )
    second = Move(
        piece_id="wR-a1",
        from_square=Square.from_name("a4"),
        to_square=Square.from_name("h4"),
        teleport=teleport,
    )
    with pytest.raises(ValueError, match="активац"):
        state.apply_turn(
            Turn(
                moves=[first, second],
            )
        )
    with pytest.raises(ValueError, match="активац"):
        state.apply_turn(
            Turn(
                free_teleport=teleport,
                moves=[first],
            )
        )


# ---------------------------------------------------------------------------
# Возрождение
# ---------------------------------------------------------------------------


def test_resurrection_returns_unblessed_on_original_square() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wP-d4",
                PieceType.PAWN,
                Color.WHITE,
                "d4",
                blessing=BlessingType.RESURRECTION,
                ever_blessed=True,
            ),
            _piece("bP-e4", PieceType.PAWN, Color.BLACK, "e4"),
        ],
        side=Color.BLACK,
        white_choice=BlessingType.RESURRECTION,
        en_passant_target=Square.from_name("d3"),
    )
    move = next(move for move in generate_legal_moves(state) if move.en_passant)
    after = state.apply_turn(Turn.single(move))

    revived = after.board.piece_at(Square.from_name("d4"))
    assert revived is not None and revived.type is PieceType.PAWN
    assert revived.blessing is None
    assert revived.ever_blessed is True
    assert after.pending_resurrections == []
    assert any("возрождение" in line for line in after.history)


def test_resurrection_keeps_type_at_death() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "h8"),
            _piece("bR-d8", PieceType.ROOK, Color.BLACK, "d8"),
            _piece(
                "wQ-d4",
                PieceType.QUEEN,
                Color.WHITE,
                "d4",
                blessing=BlessingType.RESURRECTION,
                ever_blessed=True,
            ),
        ],
        side=Color.BLACK,
        white_choice=BlessingType.RESURRECTION,
    )
    # Чёрная ладья делает двойной ход: берёт ферзя и уходит с клетки гибели.
    state = state.copy()
    state.blessing_choice[Color.BLACK] = BlessingType.DOUBLE_MOVE
    state.board.replace_piece(
        state.board.piece_at(Square.from_name("d8")).blessed_with(
            BlessingType.DOUBLE_MOVE
        )
    )
    first = _find_move(state, "d8", "d4")
    from chess.core.rules import _preview_after_move

    preview = _preview_after_move(state, first)
    second = _find_move(preview, "d4", "d5")
    after = state.apply_turn(Turn(moves=[first, second]))

    revived = after.board.piece_at(Square.from_name("d4"))
    assert revived is not None
    assert revived.type is PieceType.QUEEN
    assert revived.blessing is None


def test_resurrection_fails_when_square_is_occupied() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wR-d4",
                PieceType.ROOK,
                Color.WHITE,
                "d4",
                blessing=BlessingType.RESURRECTION,
                ever_blessed=True,
            ),
            _piece("bR-d8", PieceType.ROOK, Color.BLACK, "d8"),
        ],
        side=Color.BLACK,
        white_choice=BlessingType.RESURRECTION,
    )
    move = _find_move(state, "d8", "d4")
    after = state.apply_turn(Turn.single(move))

    assert after.board.piece_at(Square.from_name("d4")).id == "bR-d8"
    assert after.pending_resurrections == []
    assert any("не состоялось" in line for line in after.history)


def test_resurrection_blocks_check() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "h8"),
            _piece(
                "wR-e2",
                PieceType.ROOK,
                Color.WHITE,
                "e2",
                blessing=BlessingType.RESURRECTION,
                ever_blessed=True,
            ),
            _piece(
                "bR-e8",
                PieceType.ROOK,
                Color.BLACK,
                "e8",
                blessing=BlessingType.DOUBLE_MOVE,
                ever_blessed=True,
            ),
        ],
        side=Color.BLACK,
        white_choice=BlessingType.RESURRECTION,
        black_choice=BlessingType.DOUBLE_MOVE,
    )
    first = _find_move(state, "e8", "e2")
    from chess.core.rules import _preview_after_move

    preview = _preview_after_move(state, first)
    second = _find_move(preview, "e2", "e3")
    after = state.apply_turn(Turn(moves=[first, second]))

    assert after.board.piece_at(Square.from_name("e2")).id == "wR-e2"
    assert not is_in_check(after, Color.WHITE)


def test_resurrection_does_not_happen_after_checkmate() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "h1"),
            _piece("bK", PieceType.KING, Color.BLACK, "f2"),
            _piece("bQ-g3", PieceType.QUEEN, Color.BLACK, "g3"),
        ],
        side=Color.BLACK,
        white_choice=BlessingType.RESURRECTION,
        pending_resurrections=[
            PendingResurrection(
                piece_id="wR-b1",
                piece_type=PieceType.ROOK,
                color=Color.WHITE,
                original_square=Square.from_name("b1"),
                turn_created=1,
            )
        ],
    )
    move = _find_move(state, "g3", "g2")
    after = state.apply_turn(Turn.single(move))

    assert after.result is not None
    assert after.result.winner is Color.BLACK
    assert after.pending_resurrections == []
    assert after.board.piece_at(Square.from_name("b1")) is None


def test_multiple_resurrections_are_processed_in_order() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "h1"),
            _piece("bK", PieceType.KING, Color.BLACK, "h8"),
            _piece("bR-a8", PieceType.ROOK, Color.BLACK, "a8"),
        ],
        side=Color.BLACK,
        white_choice=BlessingType.RESURRECTION,
        pending_resurrections=[
            PendingResurrection(
                piece_id="wR-e2",
                piece_type=PieceType.ROOK,
                color=Color.WHITE,
                original_square=Square.from_name("e2"),
                turn_created=1,
            ),
            PendingResurrection(
                piece_id="wN-e2",
                piece_type=PieceType.KNIGHT,
                color=Color.WHITE,
                original_square=Square.from_name("e2"),
                turn_created=2,
            ),
        ],
    )
    after = state.apply_turn(Turn.single(_find_move(state, "a8", "a7")))

    revived = after.board.piece_at(Square.from_name("e2"))
    assert revived is not None and revived.id == "wR-e2"
    assert after.pending_resurrections == []
    assert any("не состоялось" in line for line in after.history)


# ---------------------------------------------------------------------------
# Заморозка
# ---------------------------------------------------------------------------


def _freeze_state() -> GameState:
    return _state(
        [
            *_kings(),
            _piece(
                "wR-d4",
                PieceType.ROOK,
                Color.WHITE,
                "d4",
                blessing=BlessingType.FREEZE,
                ever_blessed=True,
            ),
            _piece("bP-d5", PieceType.PAWN, Color.BLACK, "d5"),
            _piece("bP-c4", PieceType.PAWN, Color.BLACK, "c4"),
            _piece("bP-e4", PieceType.PAWN, Color.BLACK, "e4"),
            _piece("bP-d3", PieceType.PAWN, Color.BLACK, "d3"),
            _piece("bP-c5", PieceType.PAWN, Color.BLACK, "c5"),
        ],
        white_choice=BlessingType.FREEZE,
    )


def test_freeze_hits_only_orthogonal_neighbours() -> None:
    state = _freeze_state()
    turn = _freeze_turns(state)[0]
    after = state.apply_turn(turn)

    assert after.frozen == {"bP-d5", "bP-c4", "bP-e4", "bP-d3"}
    assert "bP-c5" not in after.frozen
    source = after.board.piece_at(Square.from_name("d4"))
    assert source is not None and source.blessing is None
    assert after.history[-1].startswith("Заморозка:")


def test_freeze_forbidden_under_check_and_without_targets() -> None:
    checked = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "e8"),
            _piece(
                "wR-d4",
                PieceType.ROOK,
                Color.WHITE,
                "d4",
                blessing=BlessingType.FREEZE,
                ever_blessed=True,
            ),
            _piece("bR-e7", PieceType.ROOK, Color.BLACK, "e7"),
        ],
        white_choice=BlessingType.FREEZE,
    )
    assert not _freeze_turns(checked)
    with pytest.raises(ValueError):
        checked.apply_turn(
            Turn(
                freeze=FreezeAction(
                    Square.from_name("d4"),
                    "wR-d4",
                    (),
                )
            )
        )

    lonely = _state(
        [
            *_kings(),
            _piece(
                "wR-d4",
                PieceType.ROOK,
                Color.WHITE,
                "d4",
                blessing=BlessingType.FREEZE,
                ever_blessed=True,
            ),
        ],
        white_choice=BlessingType.FREEZE,
    )
    assert not _freeze_turns(lonely)
    with pytest.raises(ValueError):
        lonely.apply_turn(
            Turn(
                freeze=FreezeAction(
                    Square.from_name("d4"),
                    "wR-d4",
                    (),
                )
            )
        )


def test_frozen_pieces_cannot_move_or_use_abilities() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece(
                "bK",
                PieceType.KING,
                Color.BLACK,
                "e8",
                blessing=BlessingType.FREEZE,
                ever_blessed=True,
            ),
            _piece(
                "bR-a8",
                PieceType.ROOK,
                Color.BLACK,
                "a8",
                blessing=BlessingType.FREEZE,
                ever_blessed=True,
            ),
            _piece("bP-c7", PieceType.PAWN, Color.BLACK, "c7"),
            _piece("bR-h8", PieceType.ROOK, Color.BLACK, "h8"),
        ],
        side=Color.BLACK,
        black_choice=BlessingType.FREEZE,
        frozen=frozenset({"bK", "bR-a8"}),
        freeze_owner=Color.WHITE,
    )
    moves = generate_legal_moves(state)
    assert all(move.piece_id != "bR-a8" for move in moves)
    turns = generate_legal_turns(state)
    assert not any(
        turn.freeze is not None and turn.freeze.source_piece_id == "bR-a8"
        for turn in turns
    )
    assert not any(turn.is_bless for turn in turns)
    frozen_move = Move(
        piece_id="bR-a8",
        from_square=Square.from_name("a8"),
        to_square=Square.from_name("a7"),
    )
    with pytest.raises(ValueError, match="Замороженная"):
        state.apply_turn(Turn.single(frozen_move))


def test_frozen_pieces_still_attack_and_give_check() -> None:
    rook_check = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "e8"),
            _piece("bR-e5", PieceType.ROOK, Color.BLACK, "e5"),
        ],
        frozen=frozenset({"bR-e5"}),
        freeze_owner=Color.BLACK,
    )
    assert is_in_check(rook_check, Color.WHITE)

    king_check = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "e2"),
        ],
        frozen=frozenset({"bK"}),
        freeze_owner=Color.BLACK,
    )
    assert is_in_check(king_check, Color.WHITE)

    capture_state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "e8"),
            _piece("wR-a1", PieceType.ROOK, Color.WHITE, "a1"),
            _piece("bR-a4", PieceType.ROOK, Color.BLACK, "a4"),
        ],
        frozen=frozenset({"bR-a4"}),
        freeze_owner=Color.BLACK,
    )
    assert _find_move(capture_state, "a1", "a4").is_capture


def test_frozen_king_clears_at_owners_next_turn() -> None:
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK-king", PieceType.KING, Color.BLACK, "e5"),
            _piece(
                "wP-e4",
                PieceType.PAWN,
                Color.WHITE,
                "e4",
                blessing=BlessingType.FREEZE,
                ever_blessed=True,
            ),
            _piece("bP-a7", PieceType.PAWN, Color.BLACK, "a7"),
        ],
        white_choice=BlessingType.FREEZE,
    )
    turn = next(
        turn
        for turn in _freeze_turns(state)
        if turn.freeze is not None
        and "bK-king" in {
            piece.id
            for piece in [
                state.board.piece_at(square) for square in turn.freeze.targets
            ]
            if piece is not None
        }
    )
    after = state.apply_turn(turn)
    assert "bK-king" in after.frozen
    assert after.freeze_owner is Color.WHITE

    black_move = _find_move(after, "a7", "a6")
    after_black = after.apply_turn(Turn.single(black_move))
    assert after_black.side_to_move is Color.WHITE
    assert after_black.frozen == frozenset()
    assert after_black.freeze_owner is None


def test_frozen_piece_cannot_use_free_exit_or_teleport() -> None:
    pair = PortalPair(
        0,
        0,
        0,
        Square.from_name("a4"),
        Square.from_name("h4"),
    )
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "e8"),
            _piece("bR-a4", PieceType.ROOK, Color.BLACK, "a4"),
            _piece("bR-a1", PieceType.ROOK, Color.BLACK, "a1"),
        ],
        side=Color.BLACK,
        portals=(pair,),
        frozen=frozenset({"bR-a4", "bR-a1"}),
        freeze_owner=Color.WHITE,
    )
    assert state.free_exit_activation(Square.from_name("a4")) is None
    moves = generate_legal_moves(state)
    assert all(move.piece_id not in {"bR-a4", "bR-a1"} for move in moves)
    activation = PortalActivation(
        0,
        Square.from_name("a4"),
        Square.from_name("h4"),
    )
    with pytest.raises(ValueError):
        state.apply_turn(Turn(free_teleport=activation))


# ---------------------------------------------------------------------------
# Проход сквозь фигуры
# ---------------------------------------------------------------------------


def test_pass_through_moves_through_pieces_and_captures_on_target() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wR-a1",
                PieceType.ROOK,
                Color.WHITE,
                "a1",
                blessing=BlessingType.PASS_THROUGH,
                ever_blessed=True,
            ),
            _piece("wP-a2", PieceType.PAWN, Color.WHITE, "a2"),
            _piece("bP-a4", PieceType.PAWN, Color.BLACK, "a4"),
            _piece("bR-a6", PieceType.ROOK, Color.BLACK, "a6"),
        ],
        white_choice=BlessingType.PASS_THROUGH,
    )
    moves = [
        move
        for move in generate_legal_moves(state)
        if move.piece_id == "wR-a1"
    ]
    assert any(move.to_square.name == "a6" and move.pass_through for move in moves)
    assert not any(move.to_square.name == "a2" for move in moves)

    capture = next(move for move in moves if move.to_square.name == "a6")
    after = state.apply_turn(Turn.single(capture))

    rook = after.board.piece_at(Square.from_name("a6"))
    assert rook is not None and rook.id == "wR-a1"
    assert rook.blessing is None and rook.blessing_used
    assert after.board.piece_at(Square.from_name("a2")) is not None
    assert after.board.piece_at(Square.from_name("a4")) is not None


def test_pass_through_not_consumed_without_crossing() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wR-a1",
                PieceType.ROOK,
                Color.WHITE,
                "a1",
                blessing=BlessingType.PASS_THROUGH,
                ever_blessed=True,
            ),
        ],
        white_choice=BlessingType.PASS_THROUGH,
    )
    normal = _find_move(state, "a1", "a3")
    assert normal.pass_through is False
    after = state.apply_turn(Turn.single(normal))

    rook = after.board.piece_at(Square.from_name("a3"))
    assert rook is not None and rook.blessing is BlessingType.PASS_THROUGH
    assert rook.blessing_used is False


def test_pawn_pass_through_only_on_initial_double_move() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wP-e2",
                PieceType.PAWN,
                Color.WHITE,
                "e2",
                blessing=BlessingType.PASS_THROUGH,
                ever_blessed=True,
            ),
            _piece("wN-e3", PieceType.KNIGHT, Color.WHITE, "e3"),
        ],
        white_choice=BlessingType.PASS_THROUGH,
    )
    moves = [
        move
        for move in generate_legal_moves(state)
        if move.piece_id == "wP-e2"
    ]
    assert any(move.to_square.name == "e4" and move.pass_through for move in moves)
    assert not any(move.to_square.name == "e3" for move in moves)

    move = next(move for move in moves if move.to_square.name == "e4")
    after = state.apply_turn(Turn.single(move))
    pawn = after.board.piece_at(Square.from_name("e4"))
    assert pawn is not None and pawn.blessing is None


def test_knight_gets_no_benefit_from_pass_through() -> None:
    state = _state(
        [
            *_kings(),
            _piece(
                "wN-g1",
                PieceType.KNIGHT,
                Color.WHITE,
                "g1",
                blessing=BlessingType.PASS_THROUGH,
                ever_blessed=True,
            ),
            _piece("wP-g2", PieceType.PAWN, Color.WHITE, "g2"),
        ],
        white_choice=BlessingType.PASS_THROUGH,
    )
    moves = [
        move
        for move in generate_legal_moves(state)
        if move.piece_id == "wN-g1"
    ]
    assert moves
    assert all(move.pass_through is False for move in moves)
    after = state.apply_turn(Turn.single(moves[0]))
    knight = after.board.find_piece("wN-g1")
    assert knight is not None and knight.blessing is BlessingType.PASS_THROUGH


def test_pass_through_attacks_count_for_check() -> None:
    blocked = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "a8"),
            _piece("wR-a1", PieceType.ROOK, Color.WHITE, "a1"),
            _piece("wP-a2", PieceType.PAWN, Color.WHITE, "a2"),
        ],
        side=Color.BLACK,
    )
    assert not is_in_check(blocked, Color.BLACK)

    through = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "e1"),
            _piece("bK", PieceType.KING, Color.BLACK, "a8"),
            _piece(
                "wR-a1",
                PieceType.ROOK,
                Color.WHITE,
                "a1",
                blessing=BlessingType.PASS_THROUGH,
                ever_blessed=True,
            ),
            _piece("wP-a2", PieceType.PAWN, Color.WHITE, "a2"),
        ],
        side=Color.BLACK,
        white_choice=BlessingType.PASS_THROUGH,
    )
    assert is_in_check(through, Color.BLACK)


def test_pass_through_combines_with_portal() -> None:
    pair = PortalPair(
        0,
        0,
        0,
        Square.from_name("a4"),
        Square.from_name("h4"),
    )
    state = _state(
        [
            *_kings(),
            _piece(
                "wR-a1",
                PieceType.ROOK,
                Color.WHITE,
                "a1",
                blessing=BlessingType.PASS_THROUGH,
                ever_blessed=True,
            ),
            _piece("wP-a2", PieceType.PAWN, Color.WHITE, "a2"),
        ],
        white_choice=BlessingType.PASS_THROUGH,
        portals=(pair,),
    )
    move = next(
        move
        for move in generate_legal_moves(state)
        if move.teleport is not None and move.pass_through
    )
    after = state.apply_turn(Turn.single(move))
    rook = after.board.find_piece("wR-a1")
    assert rook is not None and rook.blessing is None


# ---------------------------------------------------------------------------
# Взаимодействия и свободный выход
# ---------------------------------------------------------------------------


def test_invulnerability_cancels_portal_capture() -> None:
    pair = PortalPair(
        0,
        0,
        0,
        Square.from_name("a4"),
        Square.from_name("h4"),
    )
    state = _state(
        [
            *_kings(),
            _piece("wR-a1", PieceType.ROOK, Color.WHITE, "a1"),
            _piece(
                "bR-h5",
                PieceType.ROOK,
                Color.BLACK,
                "h5",
                blessing=BlessingType.INVULNERABILITY,
                ever_blessed=True,
            ),
        ],
        portals=(pair,),
    )
    move = next(
        move
        for move in generate_legal_moves(state)
        if move.teleport is not None and move.capture is not None
    )
    after = state.apply_turn(Turn.single(move))

    assert after.board.piece_at(Square.from_name("a1")).id == "wR-a1"
    shielded = after.board.piece_at(Square.from_name("h5"))
    assert shielded is not None and shielded.blessing is None
    assert after.last_cancelled is True


def test_free_exit_can_precede_blessing() -> None:
    pair = PortalPair(
        0,
        0,
        0,
        Square.from_name("a4"),
        Square.from_name("h4"),
    )
    state = _state(
        [
            _piece("wK", PieceType.KING, Color.WHITE, "a4"),
            _piece("bK", PieceType.KING, Color.BLACK, "e8"),
            _piece("wR-h3", PieceType.ROOK, Color.WHITE, "h3"),
        ],
        white_choice=BlessingType.INVULNERABILITY,
        portals=(pair,),
    )
    turn = next(
        turn
        for turn in _bless_turns(state)
        if turn.free_teleport is not None
        and turn.bless is not None
        and turn.bless.target_square.name == "h3"
    )
    after = state.apply_turn(turn)

    assert after.board.king_square(Color.WHITE) == Square.from_name("h4")
    rook = after.board.piece_at(Square.from_name("h3"))
    assert rook is not None and rook.blessing is BlessingType.INVULNERABILITY
    assert after.bless_cooldown[Color.WHITE] == 3


def test_free_exit_can_precede_freeze() -> None:
    pair = PortalPair(
        0,
        0,
        0,
        Square.from_name("a4"),
        Square.from_name("h4"),
    )
    state = _state(
        [
            *_kings(),
            _piece(
                "wR-a4",
                PieceType.ROOK,
                Color.WHITE,
                "a4",
                blessing=BlessingType.FREEZE,
                ever_blessed=True,
            ),
            _piece("bP-h5", PieceType.PAWN, Color.BLACK, "h5"),
        ],
        white_choice=BlessingType.FREEZE,
        portals=(pair,),
    )
    turn = next(
        turn for turn in _freeze_turns(state) if turn.free_teleport is not None
    )
    after = state.apply_turn(turn)

    source = after.board.piece_at(Square.from_name("h4"))
    assert source is not None and source.id == "wR-a4"
    assert source.blessing is None
    assert after.frozen == {"bP-h5"}
