"""Состояние партии, применение ходов и определение результата.

Модуль чистый: pygame здесь не используется. Все особенности конкретного
размера доски берутся из :class:`chess.core.board_config.GameConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from chess.core.board import Board
from chess.core.board_config import BoardConfig, GameConfig
from chess.core.coords import Square
from chess.core.moves import Move, Turn
from chess.core.notation import format_turn
from chess.core.pieces import Color, Piece, PieceType
from chess.core.portals import PortalActivation, PortalPair, generate_portals


class GameStatus(Enum):
    """Все возможные состояния партии."""

    ONGOING = "ongoing"
    WHITE_WIN = "white_win"
    BLACK_WIN = "black_win"
    DRAW_STALEMATE = "draw_stalemate"
    DRAW_50_MOVES = "draw_50_moves"
    DRAW_REPETITION = "draw_repetition"
    DRAW_INSUFFICIENT_MATERIAL = "draw_insufficient_material"
    DRAW_AGREEMENT = "draw_agreement"
    RESIGN_WHITE = "resign_white"
    RESIGN_BLACK = "resign_black"

    @property
    def is_finished(self) -> bool:
        return self is not GameStatus.ONGOING

    @property
    def is_draw(self) -> bool:
        return self in {
            GameStatus.DRAW_STALEMATE,
            GameStatus.DRAW_50_MOVES,
            GameStatus.DRAW_REPETITION,
            GameStatus.DRAW_INSUFFICIENT_MATERIAL,
            GameStatus.DRAW_AGREEMENT,
        }


@dataclass(frozen=True)
class GameResult:
    """Итог партии.

    ``status`` различает победу, все виды ничьих и сдачу. ``winner`` заполнен
    только для побед (в том числе для сдачи одной из сторон).
    """

    status: GameStatus
    winner: Color | None = None

    @property
    def is_draw(self) -> bool:
        return self.status.is_draw

    @property
    def kind(self) -> str:
        """Совместимый строковый вид результата для UI и старых тестов."""

        return {
            GameStatus.ONGOING: "ongoing",
            GameStatus.WHITE_WIN: "checkmate",
            GameStatus.BLACK_WIN: "checkmate",
            GameStatus.DRAW_STALEMATE: "stalemate",
            GameStatus.DRAW_50_MOVES: "draw_50_moves",
            GameStatus.DRAW_REPETITION: "draw_repetition",
            GameStatus.DRAW_INSUFFICIENT_MATERIAL: "draw_insufficient_material",
            GameStatus.DRAW_AGREEMENT: "draw_agreement",
            GameStatus.RESIGN_WHITE: "resign_white",
            GameStatus.RESIGN_BLACK: "resign_black",
        }[self.status]

    @property
    def title(self) -> str:
        if self.status is GameStatus.WHITE_WIN:
            return "Мат! Победа белых"
        if self.status is GameStatus.BLACK_WIN:
            return "Мат! Победа чёрных"
        if self.status is GameStatus.DRAW_STALEMATE:
            return "Пат — ничья"
        if self.status is GameStatus.DRAW_50_MOVES:
            return "Ничья по 50 ходам"
        if self.status is GameStatus.DRAW_REPETITION:
            return "Троекратное повторение"
        if self.status is GameStatus.DRAW_INSUFFICIENT_MATERIAL:
            return "Недостаточный материал"
        if self.status is GameStatus.DRAW_AGREEMENT:
            return "Ничья по соглашению"
        if self.status is GameStatus.RESIGN_WHITE:
            return "Белые сдались"
        if self.status is GameStatus.RESIGN_BLACK:
            return "Чёрные сдались"
        return "Партия продолжается"

    @property
    def subtitle(self) -> str:
        if self.status is GameStatus.WHITE_WIN:
            return "Король чёрных не может уйти из-под шаха. Победа белых."
        if self.status is GameStatus.BLACK_WIN:
            return "Король белых не может уйти из-под шаха. Победа чёрных."
        if self.status is GameStatus.DRAW_STALEMATE:
            return "У стороны нет легальных ходов, но шаха нет."
        if self.status is GameStatus.DRAW_50_MOVES:
            return (
                "Прошло 100 полуходов без хода пешкой и без взятия. "
                "Партия завершена вничью."
            )
        if self.status is GameStatus.DRAW_REPETITION:
            return "Одна и та же позиция возникла три раза. Партия завершена вничью."
        if self.status is GameStatus.DRAW_INSUFFICIENT_MATERIAL:
            return (
                "У сторон недостаточно материала, чтобы поставить мат. "
                "Партия завершена вничью."
            )
        if self.status is GameStatus.DRAW_AGREEMENT:
            return "Игроки согласились на ничью."
        if self.status is GameStatus.RESIGN_WHITE:
            return "Белые признали поражение. Победа чёрных."
        if self.status is GameStatus.RESIGN_BLACK:
            return "Чёрные признали поражение. Победа белых."
        return "Партия продолжается."


@dataclass
class GameState:
    """Полное состояние партии.

    ``config`` описывает размер доски и параметры партии. Раскладка порталов
    ``portals`` создаётся после начальной расстановки и входит в хеш позиции,
    чтобы троекратное повторение учитывало пары клеток.
    """

    board: Board
    side_to_move: Color = Color.WHITE
    castling_rights: frozenset[str] | None = None
    en_passant_target: Square | None = None
    halfmove_clock: int = 0
    turn_number: int = 1
    history: list[str] = field(default_factory=list)
    last_move: Move | None = None
    config: GameConfig | None = None
    history_hashes: list[tuple] = field(default_factory=list)
    pending_resurrections: tuple = ()
    frozen: frozenset[str] = frozenset()
    portals: list[PortalPair] = field(default_factory=list)
    _result: GameResult | None = field(default=None, init=False, repr=False)
    _result_known: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = GameConfig(board=self.board.config)
        elif self.board.config is not self.config.board:
            # Состояние и доска должны описывать одну и ту же доску.
            self.board.config = self.config.board
        if not isinstance(self.portals, list):
            self.portals = list(self.portals)
        if self.castling_rights is None:
            self.castling_rights = self.config.board.initial_castling_rights
        if not self.history_hashes:
            self.history_hashes.append(self.position_hash)

    # ------------------------------------------------------------------
    # Создание и клонирование
    # ------------------------------------------------------------------

    @classmethod
    def initial(
        cls,
        config: GameConfig | BoardConfig | int | None = None,
        rng=None,
    ) -> "GameState":
        """Начальная позиция выбранного размера (по умолчанию 8×8).

        Порталы генерируются после расстановки фигур. ``rng`` принимает
        ``random.Random``, целочисленный seed или ``None``; количество пар
        берётся из :class:`GameConfig`.
        """

        game_config = _resolve_game_config(config)
        board = Board.initial(game_config.board)
        portals = generate_portals(board, game_config.portal_count, rng)
        return cls(
            board=board,
            config=game_config,
            castling_rights=game_config.board.initial_castling_rights,
            portals=portals,
        )

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
            config=self.config,
            history_hashes=list(self.history_hashes),
            pending_resurrections=self.pending_resurrections,
            frozen=self.frozen,
            portals=list(self.portals),
        )
        copy._result = self._result
        copy._result_known = self._result_known
        return copy

    # ------------------------------------------------------------------
    # Порталы
    # ------------------------------------------------------------------

    def _validate_activation(self, activation: PortalActivation) -> PortalPair:
        """Проверяет, что активация ссылается на существующую пару."""

        pair = next(
            (item for item in self.portals if item.id == activation.pair_id),
            None,
        )
        if pair is None:
            raise ValueError(f"Портал с id={activation.pair_id} отсутствует")
        if pair.other(activation.entry) != activation.exit:
            raise ValueError(
                "Вход и выход активации не соответствуют выбранной паре"
            )
        return pair

    def _apply_free_teleport(self, state: "GameState", activation: PortalActivation) -> None:
        """Переносит фигуру на выход портала в начале хода."""

        self._validate_activation(activation)
        piece = state.board.piece_at(activation.entry)
        if piece is None:
            raise ValueError(f"На клетке {activation.entry.name} нет фигуры")
        if piece.color is not state.side_to_move:
            raise ValueError("Свободный выход доступен только фигуре стороны хода")
        if not state.board.is_empty(activation.exit):
            raise ValueError("Выход портала занят")
        state.board.move_piece(activation.entry, activation.exit)

    def preview_free_exit(self, activation: PortalActivation) -> "GameState":
        """Копия состояния после свободного выхода без смены стороны.

        Используется генерацией ходов и интерфейсом для предпросмотра. Права
        на рокировку снимаются так же, как при применении хода: фигура считается
        двигавшейся, поэтому рокировка после выхода невозможна.
        """

        piece = self.board.piece_at(activation.entry)
        state = self.copy()
        self._apply_free_teleport(state, activation)
        if piece is not None:
            rights = set(state.castling_rights or ())
            _drop_piece_rights(rights, state.config.board, piece, activation.entry)
            state.castling_rights = frozenset(rights)
        return state

    def free_exit_activation(self, square: Square) -> PortalActivation | None:
        """Активация свободного выхода с клетки ``square``, если она возможна."""

        piece = self.board.piece_at(square)
        if piece is None or piece.color is not self.side_to_move:
            return None
        pair = next((item for item in self.portals if item.contains(square)), None)
        if pair is None:
            return None
        exit_square = pair.other(square)
        if exit_square is None or not self.board.is_empty(exit_square):
            return None
        return PortalActivation(pair.id, square, exit_square)

    # ------------------------------------------------------------------
    # Повторения и хеш позиции
    # ------------------------------------------------------------------

    @property
    def position_hash(self) -> tuple:
        """Хеш позиции для правила троекратного повторения.

        Включает расстановку с id фигур, сторону хода, права рокировки, поле
        взятия на проходе, отложенные возрождения, замороженные фигуры и
        раскладку порталов. Поля будущих благословений уже участвуют в хеше.
        """

        pieces = tuple(
            sorted(
                (
                    piece.square.rank,
                    piece.square.file,
                    piece.type.value,
                    piece.color.value,
                    piece.id,
                )
                for piece in self.board.pieces.values()
            )
        )
        return (
            pieces,
            self.side_to_move.value,
            tuple(sorted(self.castling_rights or ())),
            self.en_passant_target.name if self.en_passant_target is not None else None,
            _stable_tuple(self.pending_resurrections),
            tuple(sorted(self.frozen)),
            _stable_tuple(self.portals),
        )

    def _repetition_count(self) -> int:
        current = self.position_hash
        return sum(1 for item in self.history_hashes if item == current)

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

        if self._result_known and self._result is not None and self._result.status.is_finished:
            raise ValueError("Партия уже завершена")
        if not turn.moves:
            raise ValueError("Пустой Turn")
        if turn.portal_activation_count > 1:
            raise ValueError("За ход разрешена не более одной активации портала")
        if turn.free_teleport is not None and any(
            move.teleport is not None for move in turn.moves
        ):
            raise ValueError(
                "Свободный выход и телепортация в ходе взаимоисключающи"
            )

        state = self.copy()
        rights = set(state.castling_rights or ())
        board_config = state.config.board

        if turn.free_teleport is not None:
            activation = turn.free_teleport
            piece = state.board.piece_at(activation.entry)
            if piece is not None:
                _drop_piece_rights(rights, board_config, piece, activation.entry)
            self._apply_free_teleport(state, activation)
            state.en_passant_target = None

        for move in turn.moves:
            piece = state.board.piece_at(move.from_square)
            if piece is None:
                raise ValueError(f"На клетке {move.from_square.name} нет фигуры")

            if move.teleport is not None:
                self._validate_activation(move.teleport)
                _drop_piece_rights(rights, board_config, piece, move.from_square)
                if move.capture is not None:
                    captured = state.board.piece_at(move.to_square)
                    if captured is None:
                        raise ValueError("На конечной клетке нет фигуры для взятия")
                    _drop_piece_rights(
                        rights,
                        board_config,
                        captured,
                        move.to_square,
                    )

                from chess.core.rules import _apply_teleport_to_board

                moved = _apply_teleport_to_board(state.board, piece, move)
                state.en_passant_target = None
                is_capture = move.capture is not None
                state.halfmove_clock = (
                    0
                    if (piece.type is PieceType.PAWN or is_capture)
                    else state.halfmove_clock + 1
                )
                state.last_move = move
                continue

            captured_square: Square | None = None
            if move.en_passant:
                captured_square = Square(move.to_square.file, move.from_square.rank)
            elif move.capture is not None:
                captured_square = move.to_square

            if captured_square is not None:
                captured = state.board.piece_at(captured_square)
                if captured is not None and captured.type is PieceType.ROOK:
                    _drop_rook_right(rights, board_config, captured.color, captured.square)
                state.board.remove_piece(captured_square)

            _drop_piece_rights(rights, board_config, piece, move.from_square)

            moved = state.board.move_piece(move.from_square, move.to_square)

            if move.castle is not None:
                castling = board_config.castling_for(piece.color is Color.WHITE)
                if castling is None:
                    raise ValueError("Рокировка недоступна на этой доске")
                if move.castle == "K":
                    rook_from = castling.king_side_rook_from
                    rook_to = castling.king_side_rook_to
                else:
                    rook_from = castling.queen_side_rook_from
                    rook_to = castling.queen_side_rook_to
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
            state.halfmove_clock = (
                0
                if (piece.type is PieceType.PAWN or is_capture)
                else state.halfmove_clock + 1
            )
            state.last_move = move

        state.castling_rights = frozenset(rights)
        state.side_to_move = self.side_to_move.opposite
        if self.side_to_move is Color.BLACK:
            state.turn_number = self.turn_number + 1

        if record_history:
            state.history.append(format_turn(self, turn, state))

        # Хеш нужен для повторений, но в perft он не запрашивается.
        if record_history or detect_result:
            state.history_hashes.append(state.position_hash)

        state._result = None
        state._result_known = False
        if detect_result:
            state.result = state.evaluate_result()

        return state

    # ------------------------------------------------------------------
    # Результат и удобные запросы
    # ------------------------------------------------------------------

    @property
    def result(self) -> GameResult | None:
        """Результат партии или ``None``, пока партия продолжается.

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

    @property
    def status(self) -> GameStatus:
        """Текущий статус, включая ``ONGOING`` для незавершённой партии."""

        result = self.result
        return GameStatus.ONGOING if result is None else result.status

    def evaluate_result(self) -> GameResult | None:
        """Определяет мат, пат и все автоматические ничьи."""

        from chess.core.rules import generate_legal_turns, is_in_check

        if not generate_legal_turns(self):
            if is_in_check(self, self.side_to_move):
                status = (
                    GameStatus.WHITE_WIN
                    if self.side_to_move is Color.BLACK
                    else GameStatus.BLACK_WIN
                )
                return GameResult(status, winner=self.side_to_move.opposite)
            return GameResult(GameStatus.DRAW_STALEMATE)

        if self.halfmove_clock >= 100:
            return GameResult(GameStatus.DRAW_50_MOVES)

        if self._repetition_count() >= 3:
            return GameResult(GameStatus.DRAW_REPETITION)

        if self._has_insufficient_material():
            return GameResult(GameStatus.DRAW_INSUFFICIENT_MATERIAL)

        return None

    def resign(self, color: Color) -> "GameState":
        """Возвращает состояние с зафиксированной сдачей указанной стороны."""

        state = self.copy()
        status = (
            GameStatus.RESIGN_WHITE
            if color is Color.WHITE
            else GameStatus.RESIGN_BLACK
        )
        state.result = GameResult(status, winner=color.opposite)
        return state

    def agree_draw(self) -> "GameState":
        """Возвращает состояние с ничьей по соглашению сторон."""

        state = self.copy()
        state.result = GameResult(GameStatus.DRAW_AGREEMENT)
        return state

    def _has_insufficient_material(self) -> bool:
        """Проверяет автоматические ничьи по недостаточному материалу."""

        if self.pending_resurrections:
            return False

        minor_pieces: dict[Color, list] = {Color.WHITE: [], Color.BLACK: []}
        for piece in self.board.pieces.values():
            if piece.type is PieceType.KING:
                continue
            if piece.type in (PieceType.PAWN, PieceType.ROOK, PieceType.QUEEN):
                return False
            minor_pieces[piece.color].append(piece)

        white = minor_pieces[Color.WHITE]
        black = minor_pieces[Color.BLACK]
        # Только короли.
        if not white and not black:
            return True
        # K+B vs K и K+N vs K.
        if len(white) == 1 and not black:
            return white[0].type in (PieceType.BISHOP, PieceType.KNIGHT)
        if len(black) == 1 and not white:
            return black[0].type in (PieceType.BISHOP, PieceType.KNIGHT)
        # K+B vs K+B с одноцветными слонами.
        if (
            len(white) == 1
            and len(black) == 1
            and white[0].type is PieceType.BISHOP
            and black[0].type is PieceType.BISHOP
        ):
            return white[0].square.is_light == black[0].square.is_light
        return False

    def piece_at(self, square: Square):
        return self.board.piece_at(square)


def _resolve_game_config(config: GameConfig | BoardConfig | int | None) -> GameConfig:
    if config is None:
        return GameConfig.for_size(8)
    if isinstance(config, int):
        return GameConfig.for_size(config)
    if isinstance(config, BoardConfig):
        return GameConfig(board=config)
    return config


def _stable_tuple(value: tuple) -> tuple:
    """Приводит задел будущих механик к стабильному хешируемому виду."""

    return tuple(sorted(repr(item) for item in value))


def _drop_piece_rights(
    rights: set[str],
    board_config: BoardConfig,
    piece: Piece,
    square: Square,
) -> None:
    """Снимает права на рокировку после ухода фигуры с клетки."""

    if piece.type is PieceType.KING:
        _drop_king_rights(rights, piece.color)
    elif piece.type is PieceType.ROOK:
        _drop_rook_right(rights, board_config, piece.color, square)


def _drop_king_rights(rights: set[str], color: Color) -> None:
    if color is Color.WHITE:
        rights.discard("K")
        rights.discard("Q")
    else:
        rights.discard("k")
        rights.discard("q")


def _drop_rook_right(
    rights: set[str],
    board_config: BoardConfig,
    color: Color,
    square: Square,
) -> None:
    castling = board_config.castling_for(color is Color.WHITE)
    if castling is None:
        return
    king_side, queen_side = ("K", "Q") if color is Color.WHITE else ("k", "q")
    if square == castling.king_side_rook_from:
        rights.discard(king_side)
    elif square == castling.queen_side_rook_from:
        rights.discard(queen_side)
