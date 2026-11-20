"""Состояние партии и применение ходов."""

from __future__ import annotations

from dataclasses import dataclass, field

from chess.core.board import Board
from chess.core.coords import Square
from chess.core.moves import Move, Turn
from chess.core.notation import format_turn
from chess.core.pieces import Color, PieceType

INITIAL_CASTLING_RIGHTS = frozenset({"K", "Q", "k", "q"})


@dataclass(frozen=True)
class GameResult:
    """Итог партии: мат или пат."""

    kind: str  # "checkmate" | "stalemate"
    winner: Color | None = None

    @property
    def title(self) -> str:
        if self.kind == "checkmate":
            if self.winner is Color.WHITE:
                return "Мат! Победа белых"
            if self.winner is Color.BLACK:
                return "Мат! Победа чёрных"
            return "Мат!"
        return "Пат — ничья"

    @property
    def subtitle(self) -> str:
        if self.kind == "checkmate":
            return "Король не может уйти из-под шаха. Партия завершена."
        return "У стороны нет легальных ходов, но шаха нет. Партия завершена."


@dataclass
class GameState:
    board: Board
    side_to_move: Color = Color.WHITE
    castling_rights: frozenset[str] = INITIAL_CASTLING_RIGHTS
    en_passant_target: Square | None = None
    halfmove_clock: int = 0
    turn_number: int = 1
    history: list[str] = field(default_factory=list)
    last_move: Move | None = None
    _result: GameResult | None = field(default=None, init=False, repr=False)
    _result_known: bool = field(default=False, init=False, repr=False)

    @property
    def result(self) -> GameResult | None:
        """Результат партии.

        Вычисляется лениво при первом обращении. Это важно для perft: при
        переборе результат не запрашивается, поэтому лишняя генерация ходов
        не выполняется.
        """

        if not self._result_known:
            self._result = self.evaluate_result()
            self._result_known = True
        return self._result

    @result.setter
    def result(self, value: GameResult | None) -> None:
        self._result = value
        self._result_known = True

    # ------------------------------------------------------------------
    # Создание и клонирование
    # ------------------------------------------------------------------

    @classmethod
    def initial(cls) -> "GameState":
        return cls(board=Board.initial())

    def copy(self) -> "GameState":
        copy = GameState(
            board=self.board.copy(),
            side_to_move=self.side_to_move,
            castling_rights=self.castling_rights,
            en_passant_target=self.en_passant_target,
            halfmove_clock=self.halfmove_clock,
            turn_number=self.turn_number,
            history=list(self.history),
            last_move=self.last_move,
        )
        copy._result = self._result
        copy._result_known = self._result_known
        return copy

    # ------------------------------------------------------------------
    # Применение хода
    # ------------------------------------------------------------------

    def apply_move(
        self,
        move: Move,
        *,
        detect_result: bool = False,
        record_history: bool = True,
    ) -> "GameState":
        return self.apply_turn(
            Turn.single(move),
            detect_result=detect_result,
            record_history=record_history,
        )

    def apply_turn(
        self,
        turn: Turn,
        *,
        detect_result: bool = False,
        record_history: bool = True,
    ) -> "GameState":
        """Возвращает новое состояние после действия.

        Результат по умолчанию вычисляется лениво при обращении к
        :attr:`result`. ``detect_result=True`` заставляет вычислить его сразу.
        ``record_history=False`` отключает запись нотации — это используется в
        perft-тестах вместе с ленивым результатом.
        """

        if self._result_known and self._result is not None:
            raise ValueError("Партия уже завершена")
        if not turn.moves:
            raise ValueError("Пустой Turn")

        state = self.copy()
        rights = set(state.castling_rights)

        for move in turn.moves:
            piece = state.board.piece_at(move.from_square)
            if piece is None:
                raise ValueError(f"На клетке {move.from_square.name} нет фигуры")

            captured_square: Square | None = None
            if move.en_passant:
                captured_square = Square(move.to_square.file, move.from_square.rank)
            elif move.capture is not None:
                captured_square = move.to_square

            if captured_square is not None:
                captured = state.board.piece_at(captured_square)
                if captured is not None and captured.type is PieceType.ROOK:
                    _drop_rook_right(rights, captured.color, captured.square)
                state.board.remove_piece(captured_square)

            if piece.type is PieceType.KING:
                _drop_king_rights(rights, piece.color)
            elif piece.type is PieceType.ROOK:
                _drop_rook_right(rights, piece.color, piece.square)

            moved = state.board.move_piece(move.from_square, move.to_square)

            if move.castle is not None:
                rank = move.from_square.rank
                if move.castle == "K":
                    rook_from, rook_to = Square(7, rank), Square(5, rank)
                else:
                    rook_from, rook_to = Square(0, rank), Square(3, rank)
                state.board.move_piece(rook_from, rook_to)

            if move.promotion is not None:
                moved = moved.promoted_to(move.promotion)
                state.board.replace_piece(moved)

            if (
                piece.type is PieceType.PAWN
                and abs(move.to_square.rank - move.from_square.rank) == 2
            ):
                state.en_passant_target = Square(
                    move.from_square.file,
                    (move.from_square.rank + move.to_square.rank) // 2,
                )
            else:
                state.en_passant_target = None

            is_capture = move.capture is not None or move.en_passant
            state.halfmove_clock = 0 if (piece.type is PieceType.PAWN or is_capture) else state.halfmove_clock + 1
            state.last_move = move

        state.castling_rights = frozenset(rights)
        state.side_to_move = self.side_to_move.opposite
        if self.side_to_move is Color.BLACK:
            state.turn_number = self.turn_number + 1

        if record_history:
            state.history.append(format_turn(self, turn, state))

        state._result = None
        state._result_known = False
        if detect_result:
            state.result = state.evaluate_result()

        return state

    # ------------------------------------------------------------------
    # Результат и удобные запросы
    # ------------------------------------------------------------------

    def evaluate_result(self) -> GameResult | None:
        """Возвращает мат/пат для стороны, которой принадлежит очередь."""

        from chess.core.rules import generate_legal_moves, is_in_check

        if generate_legal_moves(self):
            return None
        if is_in_check(self, self.side_to_move):
            return GameResult("checkmate", winner=self.side_to_move.opposite)
        return GameResult("stalemate")

    def piece_at(self, square: Square):
        return self.board.piece_at(square)


def _drop_king_rights(rights: set[str], color: Color) -> None:
    if color is Color.WHITE:
        rights.discard("K")
        rights.discard("Q")
    else:
        rights.discard("k")
        rights.discard("q")


def _drop_rook_right(rights: set[str], color: Color, square: Square) -> None:
    if color is Color.WHITE:
        if square == Square.from_name("h1"):
            rights.discard("K")
        elif square == Square.from_name("a1"):
            rights.discard("Q")
    else:
        if square == Square.from_name("h8"):
            rights.discard("k")
        elif square == Square.from_name("a8"):
            rights.discard("q")
