"""Состояние партии, применение ходов и определение результата.

Модуль чистый: pygame здесь не используется. Все особенности конкретного
размера доски берутся из :class:`chess.core.board_config.GameConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from chess.core.blessings import (
    BlessAction,
    BlessingType,
    FreezeAction,
    PendingResurrection,
)
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
    blessing_choice: dict[Color, BlessingType | None] = field(default_factory=dict)
    bless_cooldown: dict[Color, int] = field(default_factory=dict)
    pending_resurrections: list[PendingResurrection] = field(default_factory=list)
    frozen: frozenset[str] = frozenset()
    freeze_owner: Color | None = None
    last_cancelled: bool = False
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
        if not isinstance(self.pending_resurrections, list):
            self.pending_resurrections = list(self.pending_resurrections)
        if not isinstance(self.frozen, frozenset):
            self.frozen = frozenset(self.frozen)
        choices = dict(self.blessing_choice or {})
        choices.setdefault(Color.WHITE, None)
        choices.setdefault(Color.BLACK, None)
        self.blessing_choice = choices
        cooldowns = dict(self.bless_cooldown or {})
        cooldowns.setdefault(Color.WHITE, 0)
        cooldowns.setdefault(Color.BLACK, 0)
        self.bless_cooldown = cooldowns
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
        *,
        blessing_choice: dict[Color, BlessingType | None] | None = None,
    ) -> "GameState":
        """Начальная позиция выбранного размера (по умолчанию 8×8).

        Порталы генерируются после расстановки фигур. ``rng`` принимает
        ``random.Random``, целочисленный seed или ``None``; количество пар
        берётся из :class:`GameConfig`. ``blessing_choice`` переносит выбор
        способностей со экрана настройки в состояние партии.
        """

        game_config = _resolve_game_config(config)
        board = Board.initial(game_config.board)
        portals = generate_portals(board, game_config.portal_count, rng)
        chosen = {
            Color.WHITE: None,
            Color.BLACK: None,
        }
        if game_config.abilities_enabled and blessing_choice:
            for color in (Color.WHITE, Color.BLACK):
                chosen[color] = blessing_choice.get(color)
        return cls(
            board=board,
            config=game_config,
            castling_rights=game_config.board.initial_castling_rights,
            blessing_choice=chosen,
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
            blessing_choice=dict(self.blessing_choice),
            bless_cooldown=dict(self.bless_cooldown),
            pending_resurrections=list(self.pending_resurrections),
            frozen=self.frozen,
            freeze_owner=self.freeze_owner,
            last_cancelled=self.last_cancelled,
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
        if piece.id in state.frozen:
            raise ValueError("Замороженная фигура не может выйти из портала")
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
        if piece.id in self.frozen:
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
                    piece.blessing.value if piece.blessing is not None else None,
                    piece.ever_blessed,
                    piece.blessing_used,
                )
                for piece in self.board.pieces.values()
            )
        )
        choices = tuple(
            (color.value, choice.value if choice is not None else None)
            for color, choice in sorted(
                self.blessing_choice.items(), key=lambda item: item[0].value
            )
        )
        cooldowns = tuple(
            (color.value, value)
            for color, value in sorted(
                self.bless_cooldown.items(), key=lambda item: item[0].value
            )
        )
        return (
            pieces,
            self.side_to_move.value,
            tuple(sorted(self.castling_rights or ())),
            self.en_passant_target.name if self.en_passant_target is not None else None,
            _stable_tuple(self.pending_resurrections),
            tuple(sorted(self.frozen)),
            self.freeze_owner.value if self.freeze_owner is not None else None,
            choices,
            cooldowns,
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
        if not turn.moves and turn.bless is None and turn.freeze is None:
            raise ValueError("Пустой Turn")
        if turn.bless is not None and turn.freeze is not None:
            raise ValueError("Благословение и заморозка взаимоисключающи")
        if (turn.bless is not None or turn.freeze is not None) and turn.moves:
            raise ValueError("Действие способности не сочетается с ходом фигуры")
        if len(turn.moves) > 2:
            raise ValueError("За ход допускается не более двух ходов фигуры")
        if turn.portal_activation_count > 1:
            raise ValueError("За ход разрешена не более одной активации портала")
        if turn.free_teleport is not None and any(
            move.teleport is not None for move in turn.moves
        ):
            raise ValueError(
                "Свободный выход и телепортация в ходе взаимоисключающи"
            )
        if len(turn.moves) == 2:
            first, second = turn.moves
            if first.piece_id != second.piece_id:
                raise ValueError("Двойной ход должен выполняться одной фигурой")
            if first.to_square != second.from_square:
                raise ValueError("Второй ход должен начинаться с конечной клетки первого")

        if turn.bless is not None:
            return self._apply_blessing_turn(
                turn,
                record_history=record_history,
                detect_result=detect_result,
            )
        if turn.freeze is not None:
            return self._apply_freeze_turn(
                turn,
                record_history=record_history,
                detect_result=detect_result,
            )

        state = self.copy()
        state.last_cancelled = False
        rights = set(state.castling_rights or ())
        board_config = state.config.board

        double_piece_id: str | None = None
        if len(turn.moves) == 2:
            first_piece = state.board.piece_at(turn.moves[0].from_square)
            if first_piece is None:
                raise ValueError("В начале двойного хода нет фигуры")
            if first_piece.id in state.frozen:
                raise ValueError("Замороженная фигура не может ходить")
            if (
                first_piece.blessing is not BlessingType.DOUBLE_MOVE
                or first_piece.blessing_used
            ):
                raise ValueError("У фигуры нет доступного двойного хода")
            double_piece_id = first_piece.id

        if turn.free_teleport is not None:
            activation = turn.free_teleport
            piece = state.board.piece_at(activation.entry)
            if piece is not None:
                if piece.id in state.frozen:
                    raise ValueError("Замороженная фигура не может выйти из портала")
                _drop_piece_rights(rights, board_config, piece, activation.entry)
            self._apply_free_teleport(state, activation)
            state.en_passant_target = None

        pass_through_used: list[str] = []
        for index, move in enumerate(turn.moves):
            piece = state.board.piece_at(move.from_square)
            if piece is None:
                raise ValueError(f"На клетке {move.from_square.name} нет фигуры")
            if piece.id in state.frozen:
                raise ValueError("Замороженная фигура не может ходить")
            if len(turn.moves) == 2:
                # Каждый под-ход двойного хода проверяется как обычный
                # легальный ход из промежуточной позиции.
                from chess.core.rules import generate_legal_moves

                legal_now = generate_legal_moves(state)
                if not any(_same_move(move, candidate) for candidate in legal_now):
                    raise ValueError(
                        f"Под-ход {index + 1} двойного хода нелегален"
                    )

            if move.pass_through:
                if piece.blessing is not BlessingType.PASS_THROUGH:
                    raise ValueError("У фигуры нет доступного прохода сквозь фигуры")
                if _move_passes_through_piece(state.board, move):
                    pass_through_used.append(piece.id)

            captured_square = _captured_square(move)
            victim = (
                state.board.piece_at(captured_square)
                if captured_square is not None
                else None
            )
            if (
                victim is not None
                and victim.color is not piece.color
                and victim.blessing is BlessingType.INVULNERABILITY
            ):
                return self._cancel_turn_for_invulnerability(
                    turn,
                    victim,
                    record_history=record_history,
                    detect_result=detect_result,
                )

            if victim is not None:
                _note_resurrection(state, victim)

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

                _apply_teleport_to_board(state.board, piece, move)
                state.en_passant_target = None
                is_capture = move.capture is not None
                state.halfmove_clock = (
                    0
                    if (piece.type is PieceType.PAWN or is_capture)
                    else state.halfmove_clock + 1
                )
                state.last_move = move
                continue

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

        if double_piece_id is not None:
            _spend_blessing(state, double_piece_id)
        for piece_id in pass_through_used:
            _spend_blessing(state, piece_id)

        state.castling_rights = frozenset(rights)
        return self._finish_turn(
            state,
            turn,
            record_history=record_history,
            detect_result=detect_result,
            check_double_mate=double_piece_id is not None,
        )

    # ------------------------------------------------------------------
    # Действия благословений
    # ------------------------------------------------------------------

    def _apply_blessing_turn(
        self,
        turn: Turn,
        *,
        record_history: bool,
        detect_result: bool,
    ) -> "GameState":
        from chess.core.rules import is_in_check

        action: BlessAction = turn.bless  # type: ignore[assignment]
        color = self.side_to_move
        if not self.config.abilities_enabled:
            raise ValueError("Способности короля выключены")
        choice = self.blessing_choice.get(color)
        if choice is None:
            raise ValueError("Способность стороны не выбрана")

        state = self.copy()
        state.last_cancelled = False
        rights = set(state.castling_rights or ())
        if turn.free_teleport is not None:
            activation = turn.free_teleport
            piece = state.board.piece_at(activation.entry)
            if piece is not None:
                if piece.id in state.frozen:
                    raise ValueError("Замороженная фигура не может выйти из портала")
                _drop_piece_rights(rights, state.config.board, piece, activation.entry)
            self._apply_free_teleport(state, activation)
            state.en_passant_target = None

        king_square = state.board.king_square(color)
        if king_square is None:
            raise ValueError("У стороны нет короля")
        king = state.board.piece_at(king_square)
        if king is None or king.id in state.frozen:
            raise ValueError("Замороженный король не может благословлять")
        if action.king_square != king_square:
            raise ValueError("Действие указано не для текущего положения короля")
        if state.bless_cooldown.get(color, 0) != 0:
            raise ValueError("Благословение ещё на кулдауне")
        if is_in_check(state, color):
            raise ValueError("Нельзя благословлять под шахом")

        if not _is_adjacent(king_square, action.target_square):
            raise ValueError("Благословлять можно только соседнюю фигуру")
        target = state.board.piece_at(action.target_square)
        if (
            target is None
            or target.color is not color
            or target.id != action.target_piece_id
        ):
            raise ValueError("Цель благословения должна быть своей фигурой")
        if target.type is PieceType.KING:
            raise ValueError("Король не может благословить себя")
        if target.ever_blessed or target.blessing is not None:
            raise ValueError("Фигура уже была благословлена")

        state.board.replace_piece(target.blessed_with(choice))
        state.bless_cooldown[color] = 3
        state.en_passant_target = None
        state.halfmove_clock = self.halfmove_clock + 1
        state.castling_rights = frozenset(rights)
        state.last_move = None
        return self._finish_turn(
            state,
            turn,
            record_history=record_history,
            detect_result=detect_result,
        )

    def _apply_freeze_turn(
        self,
        turn: Turn,
        *,
        record_history: bool,
        detect_result: bool,
    ) -> "GameState":
        from chess.core.rules import is_in_check, orthogonal_targets

        action: FreezeAction = turn.freeze  # type: ignore[assignment]
        color = self.side_to_move
        if not self.config.abilities_enabled:
            raise ValueError("Способности короля выключены")
        if self.blessing_choice.get(color) is not BlessingType.FREEZE:
            raise ValueError("У стороны не выбрана заморозка")

        state = self.copy()
        state.last_cancelled = False
        rights = set(state.castling_rights or ())
        if turn.free_teleport is not None:
            activation = turn.free_teleport
            piece = state.board.piece_at(activation.entry)
            if piece is not None:
                if piece.id in state.frozen:
                    raise ValueError("Замороженная фигура не может выйти из портала")
                _drop_piece_rights(rights, state.config.board, piece, activation.entry)
            self._apply_free_teleport(state, activation)
            state.en_passant_target = None

        source = state.board.piece_at(action.source_square)
        if (
            source is None
            or source.color is not color
            or source.id != action.source_piece_id
        ):
            raise ValueError("Заморозку активирует своя фигура")
        if source.id in state.frozen:
            raise ValueError("Замороженная фигура не может активировать способность")
        if (
            source.blessing is not BlessingType.FREEZE
            or source.blessing_used
        ):
            raise ValueError("У фигуры нет доступной заморозки")
        if is_in_check(state, color):
            raise ValueError("Нельзя замораживать под шахом")

        targets = orthogonal_targets(state.board, source.square, color.opposite)
        if not targets:
            raise ValueError("Рядом нет вражеских фигур для заморозки")
        if action.targets and set(action.targets) != {
            piece.square for piece in targets
        }:
            raise ValueError("Список целей заморозки не соответствует позиции")

        state.frozen = frozenset(piece.id for piece in targets)
        state.freeze_owner = color
        state.board.replace_piece(source.blessing_spent())
        state.en_passant_target = None
        state.halfmove_clock = self.halfmove_clock + 1
        state.castling_rights = frozenset(rights)
        state.last_move = None
        return self._finish_turn(
            state,
            turn,
            record_history=record_history,
            detect_result=detect_result,
        )

    def _cancel_turn_for_invulnerability(
        self,
        turn: Turn,
        victim: Piece,
        *,
        record_history: bool,
        detect_result: bool,
    ) -> "GameState":
        from chess.core.rules import is_in_check

        if turn.moves and is_in_check(self, self.side_to_move):
            raise ValueError(
                "Взятие неуязвимой фигуры не может вывести из-под шаха: "
                "ход был бы отменён"
            )

        state = self.copy()
        state.last_cancelled = True
        shielded = state.board.find_piece(victim.id)
        if shielded is not None:
            state.board.replace_piece(shielded.blessing_spent())

        if len(turn.moves) == 2:
            _spend_blessing(state, turn.moves[0].piece_id)
        for move in turn.moves:
            if move.pass_through:
                piece = self.board.find_piece(move.piece_id)
                if piece is not None and _move_passes_through_piece(self.board, move):
                    _spend_blessing(state, piece.id)

        state.en_passant_target = None
        state.halfmove_clock = self.halfmove_clock + 1
        state.last_move = None
        return self._finish_turn(
            state,
            turn,
            record_history=record_history,
            detect_result=detect_result,
        )

    def _finish_turn(
        self,
        state: "GameState",
        turn: Turn,
        *,
        record_history: bool,
        detect_result: bool,
        check_double_mate: bool = False,
    ) -> "GameState":
        """Завершает ход: очередь, кулдаун, возрождения, журнал и результат."""

        state._result = None
        state._result_known = False
        state.side_to_move = self.side_to_move.opposite
        if self.side_to_move is Color.BLACK:
            state.turn_number = self.turn_number + 1

        _advance_start_of_turn(state)
        if record_history:
            state.history.append(format_turn(self, turn, state))
        _process_resurrections(state, record_history=record_history)

        # Хеш нужен для повторений, но в perft он не запрашивается.
        if record_history or detect_result:
            state.history_hashes.append(state.position_hash)

        if detect_result and not state._result_known:
            state.result = state.evaluate_result()
        if check_double_mate:
            result = state.result if state._result_known else state.evaluate_result()
            if result is not None and result.winner is self.side_to_move:
                raise ValueError("Двойной ход не может поставить мат")
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


def _is_adjacent(first: Square, second: Square) -> bool:
    return max(abs(first.file - second.file), abs(first.rank - second.rank)) == 1


def _same_move(first: Move, second: Move) -> bool:
    """Совпадают ли ходы по существенным для применения полям."""

    return (
        first.piece_id == second.piece_id
        and first.from_square == second.from_square
        and first.to_square == second.to_square
        and first.promotion == second.promotion
        and first.castle == second.castle
        and first.en_passant == second.en_passant
        and first.teleport == second.teleport
        and first.pass_through == second.pass_through
    )


def _captured_square(move: Move) -> Square | None:
    if move.en_passant:
        return Square(move.to_square.file, move.from_square.rank)
    if move.capture is not None:
        return move.to_square
    return None


def _note_resurrection(state: "GameState", victim: Piece) -> None:
    if victim.blessing is not BlessingType.RESURRECTION:
        return
    if any(item.piece_id == victim.id for item in state.pending_resurrections):
        return
    state.pending_resurrections.append(
        PendingResurrection(
            piece_id=victim.id,
            piece_type=victim.type,
            color=victim.color,
            original_square=victim.original_square,
            turn_created=state.turn_number,
        )
    )


def _spend_blessing(state: "GameState", piece_id: str) -> None:
    piece = state.board.find_piece(piece_id)
    if piece is None or piece.blessing is None:
        return
    state.board.replace_piece(piece.blessing_spent())


def _segment_crosses_piece(board: Board, origin: Square, target: Square) -> bool:
    """Есть ли фигура строго между клетками на линии."""

    file_delta = target.file - origin.file
    rank_delta = target.rank - origin.rank
    if file_delta == 0 and rank_delta == 0:
        return False
    if not (
        file_delta == 0
        or rank_delta == 0
        or abs(file_delta) == abs(rank_delta)
    ):
        return False
    step_file = (file_delta > 0) - (file_delta < 0)
    step_rank = (rank_delta > 0) - (rank_delta < 0)
    current = origin
    while True:
        current = current.offset(step_file, step_rank)
        if current is None or current == target:
            return False
        if board.piece_at(current) is not None:
            return True


def _move_passes_through_piece(board: Board, move: Move) -> bool:
    """Прошёл ли фактический путь хода сквозь занятую клетку."""

    if move.teleport is not None:
        if _segment_crosses_piece(board, move.from_square, move.teleport.entry):
            return True
        return _segment_crosses_piece(board, move.teleport.exit, move.to_square)
    return _segment_crosses_piece(board, move.from_square, move.to_square)


def _advance_start_of_turn(state: "GameState") -> None:
    """Снимает заморозку владельца и уменьшает кулдаун благословения."""

    if state.freeze_owner is not None and state.freeze_owner is state.side_to_move:
        state.frozen = frozenset()
        state.freeze_owner = None
    if state.bless_cooldown.get(state.side_to_move, 0) > 0:
        state.bless_cooldown[state.side_to_move] -= 1


def _process_resurrections(state: "GameState", *, record_history: bool) -> None:
    """Возвращает отложенные фигуры в начале хода их владельца."""

    color = state.side_to_move
    pending = [item for item in state.pending_resurrections if item.color is color]
    if not pending:
        return

    # Если партия уже завершилась матом или патом, возрождение не спасает.
    terminal = state.evaluate_result()
    if terminal is not None:
        state.pending_resurrections = [
            item for item in state.pending_resurrections if item.color is not color
        ]
        state.result = terminal
        return

    remaining = [
        item for item in state.pending_resurrections if item.color is not color
    ]
    for item in pending:
        square = item.original_square
        if state.board.is_empty(square):
            piece = Piece(
                id=item.piece_id,
                type=item.piece_type,
                color=item.color,
                square=square,
                original_square=square,
                has_moved=True,
                blessing=None,
                ever_blessed=True,
                blessing_used=False,
            )
            state.board.add_piece(piece)
            if record_history:
                state.history.append(
                    f"{item.piece_type.letter}{square.name}: возрождение."
                )
        elif record_history:
            state.history.append(
                f"Возрождение не состоялось: {square.name} занята."
            )
    state.pending_resurrections = remaining
