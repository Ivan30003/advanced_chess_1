"""Игровой экран: партия на доске 6×6, 8×8 или 10×10 с hot-seat управлением."""

from __future__ import annotations

import pygame

from chess.core.blessings import BlessingType
from chess.core.coords import Square
from chess.core.game_state import GameResult, GameState
from chess.core.moves import Move, Turn
from chess.core.pieces import (
    BLESSING_INFO,
    PROMOTION_LETTERS,
    PROMOTION_PIECES,
    Color,
    PieceType,
)
from chess.core.portals import PortalActivation, PortalPair, portal_at
from chess.core.rules import (
    generate_legal_moves,
    generate_legal_turns,
    is_in_check,
    legal_bless_targets,
)
from chess.ui import piece_art, theme
from chess.ui.app import Scene
from chess.ui.board_view import BoardView, DisplayPiece, PortalMarker
from chess.ui.setup_config import SetupConfig
from chess.ui.widgets import Button


def _ui_square(square: Square) -> tuple[int, int]:
    return square.file, square.rank


class GameScene(Scene):
    """Полноценная партия на выбранной доске.

    Состояние хранится в :class:`GameState`; сцена только преобразует клики и
    рисует данные. Вся проверка легальности выполняется в ``chess.core``.
    """

    def __init__(self, app, config: SetupConfig) -> None:
        super().__init__(app)
        self.config = config.normalized()
        self.game_config = self.config.to_game_config()
        self.board_view = BoardView(self.game_config.size)
        self.state = self._initial_state()
        self.selected: Square | None = None
        self.legal_by_target: dict[Square, list[Move]] = {}
        self.free_exit: PortalActivation | None = None
        self.free_exit_target: PortalActivation | None = None
        self.hover_portal: tuple[PortalPair, Square] | None = None
        self.hover_capture: tuple[int, int] | None = None
        self.pending_promotion: list[Move] | None = None
        self.promotion_hover: PieceType | None = None
        self.promotion_rects: dict[PieceType, pygame.Rect] = {}
        self.teleport_flash: tuple[Square, Square, int, float] | None = None
        self.log_scroll = 0.0
        self.log_follow = True
        self.blessing_mode = False
        self.blessing_targets: dict[Square, str] = {}
        self.double_mode = False
        self.double_turns: list[Turn] = []
        self.double_by_first: dict[Square, list[Turn]] = {}
        self.double_second_by_target: dict[Square, list[Turn]] = {}
        self.double_first: Move | None = None
        self.pass_through_mode = False
        self.ability_message = ""
        self.hover_piece: tuple[Square, object] | None = None

        self.buttons: dict[str, Button] = {
            "new": Button("Новая партия", self.new_game, accent=True, font_size=19),
            "rules": Button("Правила", self.app.show_rules, font_size=18),
            "menu": Button("В меню", self.app.show_menu, font_size=18),
        }
        self.bless_button = Button(
            "Благословить",
            self._start_blessing,
            accent=True,
            font_size=14,
            tooltip="Потратить ход короля на благословение соседней фигуры",
        )
        self.ability_button = Button(
            "",
            self._use_ability,
            font_size=14,
            tooltip="Активировать способность выбранной фигуры",
        )
        self.context_buttons = (self.bless_button, self.ability_button)

        self.result_buttons: dict[str, Button] = {
            "new": Button("Новая партия", self.new_game, accent=True, font_size=20),
            "menu": Button("В меню", self.app.show_menu, font_size=20),
        }
        self._background: pygame.Surface | None = None
        self._background_size = (0, 0)
        self._last_size = (0, 0)
        self._layout()

    # ------------------------------------------------------------------
    # Управление партией
    # ------------------------------------------------------------------

    def new_game(self) -> None:
        self.state = self._initial_state()
        self._clear_selection()
        self.pending_promotion = None
        self.hover_portal = None
        self.hover_piece = None
        self.teleport_flash = None
        self.log_scroll = 0.0
        self.log_follow = True
        self.ability_message = ""

    def _initial_state(self) -> GameState:
        choices = {
            Color.WHITE: self.config.white_ability,
            Color.BLACK: self.config.black_ability,
        }
        return GameState.initial(self.game_config, blessing_choice=choices)

    def _clear_selection(self) -> None:
        self.selected = None
        self.legal_by_target = {}
        self.hover_capture = None
        self.free_exit = None
        self.free_exit_target = None
        self._clear_action_modes()
        self._position_context_buttons()

    def _clear_action_modes(self) -> None:
        self.blessing_mode = False
        self.blessing_targets = {}
        self.double_mode = False
        self.double_turns = []
        self.double_by_first = {}
        self.double_second_by_target = {}
        self.double_first = None
        self.pass_through_mode = False

    def _cancel_action_mode(self) -> None:
        self._clear_action_modes()
        if self.selected is not None:
            self._fill_targets(self._active_state(), self.selected)
        self._show_message("Действие отменено.")
        self._position_context_buttons()

    def _show_message(self, text: str) -> None:
        self.ability_message = text

    def _active_state(self) -> GameState:
        """Состояние для показа ходов: с учётом ещё не применённого выхода."""

        if self.free_exit is None:
            return self.state
        return self.state.preview_free_exit(self.free_exit)

    def _generated_turns(self) -> list[Turn]:
        """Действия из текущей (возможно, предварительной) позиции."""

        return generate_legal_turns(self._active_state())

    def _fill_targets(self, state: GameState, square: Square) -> None:
        moves = [
            move
            for move in generate_legal_moves(state)
            if move.from_square == square
        ]
        # Обычные ходы и проход сквозь фигуры не смешиваются: режим прохода
        # явно включается кнопкой способности.
        if self.pass_through_mode:
            moves = [move for move in moves if move.pass_through]
        else:
            moves = [move for move in moves if not move.pass_through]
        self.legal_by_target = {}
        for move in moves:
            self.legal_by_target.setdefault(move.to_square, []).append(move)

    def _select(self, square: Square) -> None:
        state = self._active_state()
        self._clear_action_modes()
        self.selected = square
        self._fill_targets(state, square)
        self.free_exit_target = (
            None if self.free_exit is not None else self.state.free_exit_activation(square)
        )
        self._position_context_buttons()

    def _activate_free_exit(self) -> None:
        if self.free_exit_target is None:
            return
        self.free_exit = self.free_exit_target
        # Выход временно становится позицией фигуры; сам ход ещё не применён.
        self._select(self.free_exit.exit)

    def _portal_pair_by_id(self, pair_id: int) -> PortalPair | None:
        return next((pair for pair in self.state.portals if pair.id == pair_id), None)

    # ------------------------------------------------------------------
    # Благословения и активные способности
    # ------------------------------------------------------------------

    def _selected_piece(self):
        if self.selected is None:
            return None
        return self._active_state().board.piece_at(self.selected)

    def _blessing_turns(self) -> list[Turn]:
        return [turn for turn in self._generated_turns() if turn.is_bless]

    def _bless_turn_for(self, square: Square) -> Turn | None:
        for turn in self._blessing_turns():
            if turn.bless is not None and turn.bless.target_square == square:
                return turn
        return None

    def _ability_turns_for(self, piece) -> list[Turn]:
        turns = self._generated_turns()
        if piece.blessing is BlessingType.FREEZE:
            return [
                turn
                for turn in turns
                if turn.is_freeze
                and turn.freeze is not None
                and turn.freeze.source_piece_id == piece.id
            ]
        if piece.blessing is BlessingType.DOUBLE_MOVE:
            return [
                turn
                for turn in turns
                if turn.is_double_move
                and turn.moves
                and turn.moves[0].piece_id == piece.id
            ]
        return []

    def _start_blessing(self) -> None:
        piece = self._selected_piece()
        if piece is None or piece.type is not PieceType.KING:
            return
        turns = self._blessing_turns()
        if not turns:
            self._show_message(
                "Благословение недоступно: кулдаун, шах или нет целей."
            )
            return
        self.blessing_mode = True
        self.double_mode = False
        self.pass_through_mode = False
        self.legal_by_target = {}
        self.blessing_targets = {
            turn.bless.target_square: "bless"
            for turn in turns
            if turn.bless is not None
        }
        self._show_message("Выберите фигуру, которую нужно благословить.")

    def _use_ability(self) -> None:
        piece = self._selected_piece()
        if piece is None or self.selected is None:
            return
        if piece.id in self.state.frozen:
            self._show_message("Фигура заморожена до конца хода противника.")
            return
        if piece.blessing is BlessingType.PASS_THROUGH:
            if piece.type is PieceType.KNIGHT:
                self._show_message("Коню проход сквозь фигуры не нужен.")
                return
            self.pass_through_mode = not self.pass_through_mode
            self._fill_targets(self._active_state(), self.selected)
            self._show_message(
                "Режим прохода включён: выберите клетку за фигурами."
                if self.pass_through_mode
                else "Режим прохода выключен."
            )
            self._position_context_buttons()
            return

        if piece.blessing is BlessingType.DOUBLE_MOVE:
            turns = self._ability_turns_for(piece)
            if not turns:
                self._show_message("Двойной ход сейчас недоступен.")
                return
            self._start_double_move(piece, turns)
            return

        if piece.blessing is BlessingType.FREEZE:
            turns = self._ability_turns_for(piece)
            if not turns:
                self._show_message(
                    "Заморозка недоступна: рядом нет врагов или ваш король под шахом."
                )
                return
            self._commit_turn(turns[0])
            return

    def _start_double_move(self, piece, turns: list[Turn]) -> None:
        self.double_mode = True
        self.pass_through_mode = False
        self.blessing_mode = False
        self.blessing_targets = {}
        self.double_turns = turns
        self.double_first = None
        self.double_by_first = {}
        for turn in turns:
            self.double_by_first.setdefault(turn.moves[0].to_square, []).append(turn)
        self.double_second_by_target = {}
        self.legal_by_target = {
            square: [items[0].moves[0]]
            for square, items in self.double_by_first.items()
        }
        self._show_message(
            f"Двойной ход «{piece.type.display_name.lower()}»: выберите первый ход."
        )
        self._position_context_buttons()

    def _handle_double_click(self, square: Square) -> bool:
        if self.double_first is None:
            turns = self.double_by_first.get(square)
            if not turns:
                return True
            self.double_first = turns[0].moves[0]
            for turn in turns:
                self.double_second_by_target.setdefault(
                    turn.moves[1].to_square, []
                ).append(turn)
            self.legal_by_target = {
                target: [items[0].moves[1]]
                for target, items in self.double_second_by_target.items()
            }
            self._show_message("Двойной ход: выберите второй ход.")
            return True

        turns = self.double_second_by_target.get(square)
        if not turns:
            return True
        # Если на клетке возможно превращение, разворачиваем выбор ферзя.
        promoted = [
            turn
            for turn in turns
            if turn.moves[1].promotion is PieceType.QUEEN
        ]
        self._commit_turn(promoted[0] if promoted else turns[0])
        return True

    def _commit_turn(self, turn: Turn) -> None:
        """Применяет действие с учётом уже выбранного свободного выхода."""

        activation = turn.free_teleport
        if activation is None:
            activation = self.free_exit
        if activation is None:
            activation = next(
                (move.teleport for move in turn.moves if move.teleport is not None),
                None,
            )
        if activation is not None:
            pair = self._portal_pair_by_id(activation.pair_id)
            if pair is not None:
                self.teleport_flash = (
                    activation.entry,
                    activation.exit,
                    pair.color_index,
                    0.0,
                )
        if self.free_exit is not None:
            turn = Turn(
                moves=list(turn.moves),
                free_teleport=self.free_exit,
                bless=turn.bless,
                freeze=turn.freeze,
            )
        self.state = self.state.apply_turn(turn)
        self.pending_promotion = None
        self._clear_selection()
        self.log_follow = True

    def _execute(self, move: Move) -> None:
        self._commit_turn(Turn(moves=[move]))

    def _position_context_buttons(self) -> None:
        """Раскладывает кнопки благословения и способности над фигурой."""

        for button in self.context_buttons:
            button.visible = False
            button.enabled = False
        if (
            self.selected is None
            or self.state.result is not None
            or self.pending_promotion is not None
        ):
            return

        piece = self._selected_piece()
        if piece is None:
            return
        rect = self.board_view.square_rect(*_ui_square(self.selected))
        button_w = max(132, min(190, int(self.board_view.square_size * 2.3)))
        button_h = 30
        slots = 0

        if piece.type is PieceType.KING and self.state.config.abilities_enabled:
            targets = legal_bless_targets(self._active_state())
            self.bless_button.visible = True
            self.bless_button.enabled = bool(targets) and piece.id not in self.state.frozen
            if self.state.bless_cooldown.get(self.state.side_to_move, 0) > 0:
                self.bless_button.tooltip = (
                    f"Кулдаун: ещё {self.state.bless_cooldown[self.state.side_to_move]} "
                    "ход(а) стороны"
                )
            elif is_in_check(self.state, self.state.side_to_move):
                self.bless_button.tooltip = "Нельзя благословлять под шахом"
            elif not targets:
                self.bless_button.tooltip = "Рядом нет допустимых целей"
            elif piece.id in self.state.frozen:
                self.bless_button.tooltip = "Замороженный король не может благословлять"
            else:
                self.bless_button.tooltip = (
                    "Потратить ход короля на благословение соседней фигуры"
                )
            self._place_context_button(self.bless_button, rect, slots, button_w, button_h)
            slots += 1

        choice = self.state.blessing_choice.get(self.state.side_to_move)
        if (
            choice is not None
            and piece.blessing is choice
            and not piece.blessing_used
            and piece.id not in self.state.frozen
        ):
            if choice is BlessingType.PASS_THROUGH and piece.type is not PieceType.KNIGHT:
                moves = [
                    move
                    for move in generate_legal_moves(self._active_state())
                    if move.piece_id == piece.id and move.pass_through
                ]
                self.ability_button.visible = True
                self.ability_button.enabled = bool(moves)
                self.ability_button.text = (
                    "Проход: вкл" if self.pass_through_mode else "Проход сквозь"
                )
                self.ability_button.tooltip = (
                    "Показать клетки за фигурами. Способность расходуется "
                    "только при проходе сквозь занятую клетку."
                )
            elif choice is BlessingType.DOUBLE_MOVE:
                turns = self._ability_turns_for(piece)
                self.ability_button.visible = True
                self.ability_button.enabled = bool(turns) and not self.double_mode
                self.ability_button.text = "Двойной ход"
                self.ability_button.tooltip = (
                    "Сделать два хода этой фигурой. Мат запрещён."
                )
            elif choice is BlessingType.FREEZE:
                turns = self._ability_turns_for(piece)
                self.ability_button.visible = True
                self.ability_button.enabled = bool(turns)
                self.ability_button.text = "Заморозка"
                self.ability_button.tooltip = (
                    "Обездвижить ортогонально соседних врагов на их ход."
                )
            if self.ability_button.visible:
                self._place_context_button(
                    self.ability_button, rect, slots, button_w, button_h
                )
                slots += 1

    def _place_context_button(
        self,
        button: Button,
        square_rect: pygame.Rect,
        slot: int,
        width: int,
        height: int,
    ) -> None:
        board = self.board_view.board_rect
        x = square_rect.centerx - width // 2
        x = max(board.left + 4, min(x, board.right - width - 4))
        y = square_rect.top - height - 6 - slot * (height + 4)
        if y < board.top + 4:
            y = square_rect.bottom + 6 + slot * (height + 4)
        button.set_rect(pygame.Rect(x, y, width, height))

    def _draw_context_buttons(self, surface: pygame.Surface) -> None:
        for button in self.context_buttons:
            button.draw(surface)
        for button in self.context_buttons:
            if button.visible and button.hovered and button.tooltip:
                self._draw_tooltip_text(surface, button.tooltip)
                break

    def _handle_board_click(self, square: Square) -> None:
        if self.state.result is not None:
            return

        if self.blessing_mode:
            turn = self._bless_turn_for(square)
            if turn is not None:
                self._commit_turn(turn)
            return

        if self.double_mode:
            if self._handle_double_click(square):
                return

        piece = self._active_state().board.piece_at(square)

        if self.selected is None:
            if piece is not None and piece.color is self.state.side_to_move:
                if piece.id in self.state.frozen:
                    self._show_message(
                        f"{piece.type.display_name} заморожена до конца хода противника."
                    )
                    return
                self._select(square)
            return

        if square == self.selected:
            if self.pass_through_mode:
                self.pass_through_mode = False
                self._fill_targets(self._active_state(), self.selected)
                self._position_context_buttons()
                self._show_message("Режим прохода выключен.")
                return
            self._clear_selection()
            return

        # Клик по свободному выходу — это не обычный ход, а начало действия.
        if (
            self.free_exit is None
            and self.free_exit_target is not None
            and square == self.free_exit_target.exit
        ):
            self._activate_free_exit()
            return

        candidates = self.legal_by_target.get(square)
        if candidates:
            promotions = [move for move in candidates if move.promotion is not None]
            if promotions:
                # Превращение обязательно завершить выбором фигуры.
                self.pending_promotion = promotions
                self.promotion_hover = None
                return
            self._execute(candidates[0])
            return

        # Клик по своей фигуре переключает выбор, по нелегальной клетке —
        # снимает его. После свободного выхода выбор начинается заново.
        if piece is not None and piece.color is self.state.side_to_move:
            if piece.id in self.state.frozen:
                self._show_message(
                    f"{piece.type.display_name} заморожена до конца хода противника."
                )
                return
            if self.free_exit is not None:
                self.free_exit = None
                self.free_exit_target = None
                self._select(square)
            else:
                self._select(square)
        else:
            self._clear_selection()

    def _complete_promotion(self, piece_type: PieceType) -> None:
        if not self.pending_promotion:
            return
        for move in self.pending_promotion:
            if move.promotion is piece_type:
                self._execute(move)
                return

    # ------------------------------------------------------------------
    # Компоновка
    # ------------------------------------------------------------------

    def _layout(self) -> None:
        width, height = self.app.screen.get_size()
        self._last_size = (width, height)
        margin = 28
        header_h = 72
        self.margin = margin
        self.header_h = header_h

        panel_w = min(380, max(300, int(width * 0.29)))
        self.panel_rect = pygame.Rect(
            width - margin - panel_w,
            header_h + 16,
            panel_w,
            height - header_h - 48,
        )
        board_rect = pygame.Rect(
            margin,
            header_h + 16,
            self.panel_rect.left - margin - 24,
            height - header_h - 48,
        )
        self.board_view.set_rect(board_rect)

        px = self.panel_rect.left + 18
        inner_w = self.panel_rect.w - 36
        self.ability_rect = pygame.Rect(
            px, self.panel_rect.top + 64, inner_w, 50
        )
        self.status_rect = pygame.Rect(
            px, self.panel_rect.top + 122, inner_w, 64
        )

        button_h = 40
        gap = 8
        y = self.panel_rect.bottom - (button_h * 3 + gap * 2) - 16
        self.buttons_top = y
        for key in ("new", "rules", "menu"):
            self.buttons[key].set_rect(pygame.Rect(px, y, inner_w, button_h))
            y += button_h + gap

        journal_top = self.status_rect.bottom + 34
        journal_bottom = self.buttons_top - 16
        self.journal_rect = pygame.Rect(
            px,
            journal_top,
            inner_w,
            max(80, journal_bottom - journal_top),
        )
        self._layout_overlays()
        self._position_context_buttons()

    def _layout_overlays(self) -> None:
        width, height = self.app.screen.get_size()

        dialog_w = min(560, max(460, width - 160))
        dialog_h = 230
        self.promotion_rect = pygame.Rect(0, 0, dialog_w, dialog_h)
        self.promotion_rect.center = (width // 2, height // 2)
        cell_size = 92
        gap = 14
        total = cell_size * 4 + gap * 3
        left = self.promotion_rect.centerx - total // 2
        top = self.promotion_rect.top + 82
        self.promotion_rects = {}
        for index, piece_type in enumerate(PROMOTION_PIECES):
            self.promotion_rects[piece_type] = pygame.Rect(
                left + index * (cell_size + gap),
                top,
                cell_size,
                cell_size,
            )

        result_w = min(520, max(420, width - 180))
        result_h = 290
        self.result_rect = pygame.Rect(0, 0, result_w, result_h)
        self.result_rect.center = (width // 2, height // 2)
        button_w = 170
        button_h = 46
        gap = 16
        total = button_w * 2 + gap
        left = self.result_rect.centerx - total // 2
        y = self.result_rect.bottom - button_h - 24
        self.result_buttons["new"].set_rect(pygame.Rect(left, y, button_w, button_h))
        self.result_buttons["menu"].set_rect(
            pygame.Rect(left + button_w + gap, y, button_w, button_h)
        )

    def _ensure_background(self, size: tuple[int, int]) -> pygame.Surface:
        if self._background is not None and self._background_size == size:
            return self._background
        width, height = size
        background = theme.vertical_gradient(size, theme.BACKGROUND_TOP, theme.BACKGROUND_BOTTOM)
        theme.draw_checker_pattern(
            background,
            pygame.Rect(0, 0, width, height),
            cell=max(52, width // 20),
            color=theme.ACCENT,
            alpha=4,
        )
        self._background = background
        self._background_size = size
        return background

    # ------------------------------------------------------------------
    # События
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.app.screen.get_size() != self._last_size:
            self._layout()

        if self.pending_promotion:
            self._handle_promotion_event(event)
            return

        if self.state.result is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            for button in self.result_buttons.values():
                if button.handle_event(event):
                    return
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.blessing_mode or self.double_mode or self.pass_through_mode:
                self._cancel_action_mode()
            else:
                self._clear_selection()
            return

        for button in self.context_buttons:
            if button.handle_event(event):
                return

        for button in self.buttons.values():
            if button.handle_event(event):
                return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.blessing_mode or self.double_mode or self.pass_through_mode:
                self._cancel_action_mode()
            else:
                self._clear_selection()
            return

        if event.type == pygame.MOUSEWHEEL and self.journal_rect.collidepoint(
            pygame.mouse.get_pos()
        ):
            self.log_follow = False
            max_scroll = self._journal_max_scroll()
            self.log_scroll = max(0.0, min(self.log_scroll - event.y * 42, max_scroll))
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            square = self.board_view.square_at(event.pos)
            if square is not None:
                self._handle_board_click(Square(*square))

    def _handle_promotion_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.promotion_hover = None
            for piece_type, rect in self.promotion_rects.items():
                if rect.collidepoint(event.pos):
                    self.promotion_hover = piece_type
                    break
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for piece_type, rect in self.promotion_rects.items():
                if rect.collidepoint(event.pos):
                    self._complete_promotion(piece_type)
                    return
        # Esc и правый клик не отменяют начатое превращение.

    def update(self, dt: float) -> None:
        if self.app.screen.get_size() != self._last_size:
            self._layout()
        self.board_view.update(dt)

        if self.teleport_flash is not None:
            entry, exit_square, color_index, progress = self.teleport_flash
            progress += dt * 2.4
            if progress >= 1.0:
                self.teleport_flash = None
            else:
                self.teleport_flash = (entry, exit_square, color_index, progress)

        self.hover_capture = None
        self.hover_portal = None
        self.hover_piece = None
        mouse = pygame.mouse.get_pos()
        square = self.board_view.square_at(mouse)
        if square is not None:
            core_square = Square(*square)
            pair = portal_at(self.state.portals, core_square)
            if pair is not None and self.pending_promotion is None:
                self.hover_portal = (pair, core_square)
            board_piece = self._active_state().board.piece_at(core_square)
            if board_piece is not None:
                self.hover_piece = (core_square, board_piece)
            if (
                self.selected is not None
                and self.pending_promotion is None
                and self.state.result is None
            ):
                candidates = self.legal_by_target.get(core_square, [])
                if any(move.is_capture for move in candidates):
                    self.hover_capture = square

        for button in self.context_buttons:
            button.hovered = button.visible and button.contains(mouse)
        if self.state.result is not None:
            for button in self.result_buttons.values():
                button.hovered = button.contains(mouse)
        else:
            for button in self.buttons.values():
                button.hovered = button.contains(mouse)

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        if (width, height) != self._last_size:
            self._layout()
        surface.blit(self._ensure_background((width, height)), (0, 0))

        theme.draw_text(
            surface,
            "Партия",
            32,
            theme.TEXT,
            (self.margin, 22),
            bold=True,
        )
        theme.draw_text(
            surface,
            f"Доска {self.game_config.size}×{self.game_config.size} · "
            f"порталов: {len(self.state.portals)} · hot-seat · клик-клик",
            16,
            theme.TEXT_MUTED,
            (self.margin, 58),
        )

        self._draw_board(surface)
        self._draw_panel(surface)
        self._draw_context_buttons(surface)
        self._draw_piece_tooltip(surface)
        self._draw_portal_tooltip(surface)

        if self.pending_promotion:
            self._draw_promotion(surface)
        elif self.state.result is not None:
            self._draw_result(surface)

    def _display_pieces(self) -> list[DisplayPiece]:
        state = self.state
        display_board = self._active_state().board
        return [
            DisplayPiece(
                piece_type=piece.type,
                color=piece.color,
                square=_ui_square(piece.square),
                blessing=piece.blessing,
                blessing_used=piece.blessing_used,
                frozen=piece.id in state.frozen,
            )
            for piece in display_board.pieces.values()
        ]

    def _draw_board(self, surface: pygame.Surface) -> None:
        state = self.state
        # В режиме предпросмотра свободного выхода фигура уже показывается
        # на выходе, хотя сам ход ещё не применён.
        pieces = self._display_pieces()

        selected = _ui_square(self.selected) if self.selected is not None else None
        last_move = None
        if state.last_move is not None:
            last_move = (
                _ui_square(state.last_move.from_square),
                _ui_square(state.last_move.to_square),
            )

        check_square = None
        if state.result is None and is_in_check(state, state.side_to_move):
            king_square = state.board.king_square(state.side_to_move)
            if king_square is not None:
                check_square = _ui_square(king_square)

        legal_targets: dict[tuple[int, int], str] = {}
        portal_targets: dict[tuple[int, int], int] = {}
        if self.blessing_mode:
            legal_targets = {
                _ui_square(square): kind
                for square, kind in self.blessing_targets.items()
            }
        elif self.config.show_legal_hints and self.selected is not None:
            for target, moves in self.legal_by_target.items():
                if any(move.pass_through for move in moves):
                    kind = "pass"
                else:
                    kind = "capture" if any(move.is_capture for move in moves) else "move"
                legal_targets[_ui_square(target)] = kind
                activation = next(
                    (move.teleport for move in moves if move.teleport is not None),
                    None,
                )
                if activation is not None:
                    pair = self._portal_pair_by_id(activation.pair_id)
                    if pair is not None:
                        portal_targets[_ui_square(target)] = pair.color_index

        free_exit_target = None
        free_exit_color = 0
        if self.free_exit_target is not None:
            pair = self._portal_pair_by_id(self.free_exit_target.pair_id)
            if pair is not None:
                free_exit_target = _ui_square(self.free_exit_target.exit)
                free_exit_color = pair.color_index

        portal_markers = [
            PortalMarker(
                square=_ui_square(pair.a),
                color_index=pair.color_index,
                symbol_index=pair.symbol_index,
            )
            for pair in state.portals
        ] + [
            PortalMarker(
                square=_ui_square(pair.b),
                color_index=pair.color_index,
                symbol_index=pair.symbol_index,
            )
            for pair in state.portals
        ]

        self.board_view.draw(
            surface,
            pieces=pieces,
            selected=selected,
            last_move=last_move,
            check_square=check_square,
            legal_targets=legal_targets,
            portal_targets=portal_targets,
            free_exit_target=free_exit_target,
            free_exit_color_index=free_exit_color,
            hover_capture=self.hover_capture,
            portals=portal_markers,
            show_coordinates=True,
        )

        if self.teleport_flash is not None:
            entry, exit_square, color_index, progress = self.teleport_flash
            self.board_view.draw_portal_flash(
                surface,
                _ui_square(entry),
                _ui_square(exit_square),
                color_index,
                progress,
            )

    def _draw_panel(self, surface: pygame.Surface) -> None:
        theme.draw_panel(
            surface,
            self.panel_rect,
            theme.PANEL,
            radius=theme.RADIUS,
            border=theme.BORDER_SOFT,
            shadow=True,
        )
        x = self.panel_rect.left + 18
        theme.draw_text(
            surface,
            "Ход партии",
            20,
            theme.TEXT,
            (x, self.panel_rect.top + 18),
            bold=True,
        )
        theme.draw_text(
            surface,
            self.config.summary,
            12,
            theme.TEXT_DIM,
            (x, self.panel_rect.top + 46),
            max_width=self.panel_rect.w - 36,
        )
        self._draw_ability_status(surface)

        is_result = self.state.result is not None
        in_check = not is_result and is_in_check(self.state, self.state.side_to_move)

        if is_result:
            status_text = self.state.result.title
            status_color = theme.ACCENT
        else:
            status_text = f"Ход {self.state.side_to_move.display_name.lower()}"
            status_color = (
                theme.TEXT if self.state.side_to_move is Color.WHITE else theme.ICE
            )

        theme.draw_panel(
            surface,
            self.status_rect,
            theme.PANEL_DARK,
            radius=theme.RADIUS_SMALL,
            border=theme.ACCENT if not is_result else theme.DANGER,
        )
        theme.draw_text(
            surface,
            status_text,
            22,
            status_color,
            (self.status_rect.left + 14, self.status_rect.top + 12),
            bold=True,
        )
        detail = f"Ход №{self.state.turn_number}"
        if in_check:
            detail += " · шах!"
        elif self.free_exit is not None:
            detail += " · свободный выход: выберите ход"
        elif self.blessing_mode:
            detail += " · выберите цель благословения"
        elif self.double_mode:
            detail += " · двойной ход: выберите клетку"
        elif self.pass_through_mode:
            detail += " · режим прохода включён"
        elif self.ability_message:
            detail += " · " + self.ability_message
        elif not is_result:
            detail += " · выберите фигуру"
        theme.draw_text(
            surface,
            detail,
            14,
            theme.DANGER if in_check else theme.TEXT_MUTED,
            (self.status_rect.left + 14, self.status_rect.top + 40),
            max_width=self.status_rect.w - 28,
        )

        theme.draw_text(
            surface,
            "Журнал ходов",
            16,
            theme.TEXT_MUTED,
            (x, self.status_rect.bottom + 18),
            bold=True,
        )
        self._draw_journal(surface)
        for button in self.buttons.values():
            button.draw(surface)

    def _draw_ability_status(self, surface: pygame.Surface) -> None:
        """Строки о выбранных способностях, кулдауне и заморозке."""

        lines: list[str] = []
        if self.state.portals:
            lines.append(
                f"Порталов: {len(self.state.portals)} пар · 1 активация за ход"
            )
        if self.state.config.abilities_enabled:
            for color in (Color.WHITE, Color.BLACK):
                choice = self.state.blessing_choice.get(color)
                info = BLESSING_INFO.get(choice) if choice is not None else None
                name = info.name if info is not None else "не выбрана"
                parts = [f"{color.display_name}: {name}"]
                cooldown = self.state.bless_cooldown.get(color, 0)
                if cooldown:
                    parts.append(f"кулдаун {cooldown}")
                else:
                    parts.append("готово")
                blessed = sum(
                    1
                    for piece in self.state.board.pieces_of(color)
                    if piece.blessing is not None
                )
                if blessed:
                    parts.append(f"благословений: {blessed}")
                frozen = sum(
                    1
                    for piece in self.state.board.pieces_of(color)
                    if piece.id in self.state.frozen
                )
                if frozen:
                    parts.append(f"заморожено: {frozen}")
                lines.append(" · ".join(parts))
        else:
            lines.append("Способности короля выключены")

        y = self.ability_rect.top
        for index, line in enumerate(lines[:3]):
            theme.draw_text(
                surface,
                line,
                11,
                theme.ACCENT if "готово" in line else theme.TEXT_DIM,
                (self.ability_rect.left, y + index * 15),
                max_width=self.ability_rect.w,
            )

    def _journal_lines(self) -> list[str]:
        history = self.state.history
        lines: list[str] = []
        for index in range(0, len(history), 2):
            number = index // 2 + 1
            white = history[index]
            black = history[index + 1] if index + 1 < len(history) else ""
            if black:
                lines.append(f"{number:>2}. {white}    {black}")
            else:
                lines.append(f"{number:>2}. {white}")
        return lines

    def _journal_max_scroll(self) -> float:
        lines = max(1, len(self._journal_lines()))
        content_h = lines * 23 + 16
        return max(0.0, content_h - self.journal_rect.h)

    def _draw_journal(self, surface: pygame.Surface) -> None:
        theme.draw_panel(
            surface,
            self.journal_rect,
            theme.PANEL_DARK,
            radius=theme.RADIUS_SMALL,
            border=theme.BORDER_SOFT,
        )
        lines = self._journal_lines()
        if not lines:
            theme.draw_text(
                surface,
                "Ходов пока нет. Начните с фигуры белых.",
                14,
                theme.TEXT_DIM,
                (self.journal_rect.left + 12, self.journal_rect.top + 12),
                max_width=self.journal_rect.w - 24,
            )
            return

        max_scroll = self._journal_max_scroll()
        if self.log_follow:
            self.log_scroll = max_scroll
        self.log_scroll = max(0.0, min(self.log_scroll, max_scroll))

        clip = surface.get_clip()
        inner = self.journal_rect.inflate(-16, -12)
        surface.set_clip(inner)
        y = inner.top - self.log_scroll
        for line in lines:
            if y + 23 >= inner.top and y <= inner.bottom:
                theme.draw_text(surface, line, 15, theme.TEXT_MUTED, (inner.left, y))
            y += 23
        surface.set_clip(clip)

        if max_scroll > 0:
            track = pygame.Rect(
                self.journal_rect.right - 8,
                self.journal_rect.top + 8,
                3,
                self.journal_rect.h - 16,
            )
            pygame.draw.rect(surface, theme.BUTTON_BG, track, border_radius=2)
            thumb_h = max(24, int(track.h * (self.journal_rect.h / (self.journal_rect.h + max_scroll))))
            thumb_y = track.top + int((track.h - thumb_h) * (self.log_scroll / max_scroll))
            pygame.draw.rect(
                surface,
                theme.ACCENT,
                pygame.Rect(track.left, thumb_y, track.w, thumb_h),
                border_radius=2,
            )

    def _draw_tooltip_text(
        self,
        surface: pygame.Surface,
        text: str,
        *,
        border: tuple[int, int, int] = theme.ACCENT,
        wrap_width: int = 280,
    ) -> None:
        font = theme.get_font(13)
        lines = theme.wrap_text(text, font, wrap_width)
        line_h = font.get_linesize()
        width = max(
            [wrap_width]
            + [font.size(line)[0] for line in lines]
        ) + 24
        width = min(width, wrap_width + 24)
        height = line_h * max(1, len(lines)) + 16
        mouse = pygame.mouse.get_pos()
        rect = pygame.Rect(mouse[0] + 16, mouse[1] + 16, width, height)
        screen = surface.get_rect()
        if rect.right > screen.right - 10:
            rect.right = mouse[0] - 12
        if rect.bottom > screen.bottom - 10:
            rect.bottom = mouse[1] - 12
        rect.clamp_ip(screen.inflate(-12, -12))
        theme.draw_panel(
            surface,
            rect,
            theme.PANEL,
            radius=theme.RADIUS_SMALL,
            border=border,
            shadow=True,
        )
        theme.draw_text(
            surface,
            text,
            13,
            theme.TEXT,
            (rect.left + 12, rect.top + 8),
            max_width=wrap_width,
        )

    def _draw_piece_tooltip(self, surface: pygame.Surface) -> None:
        if self.hover_piece is None or self.pending_promotion is not None:
            return
        _, piece = self.hover_piece
        parts: list[str] = []
        if piece.id in self.state.frozen:
            parts.append("Заморожена до конца хода противника.")
        info = BLESSING_INFO.get(piece.blessing) if piece.blessing is not None else None
        if info is not None:
            parts.append(f"{info.name}: {info.description}")
        elif piece.ever_blessed and piece.id in self.state.frozen:
            parts.append("Благословение уже израсходовано.")
        if not parts:
            return
        self._draw_tooltip_text(surface, "\n".join(parts), border=theme.ICE)

    def _draw_portal_tooltip(self, surface: pygame.Surface) -> None:
        if self.hover_portal is None:
            return
        if self.hover_piece is not None:
            _, piece = self.hover_piece
            if piece.id in self.state.frozen or piece.blessing is not None:
                return
        pair, square = self.hover_portal
        partner = pair.other(square)
        if partner is None:
            return
        color = theme.portal_color(pair.color_index)
        text = (
            f"Портал {theme.portal_name(pair.color_index)}: "
            f"связан с {partner.name}"
        )
        font_size = 14
        font = theme.get_font(font_size)
        width = font.size(text)[0] + 22
        height = 30
        mouse = pygame.mouse.get_pos()
        rect = pygame.Rect(mouse[0] + 16, mouse[1] + 16, width, height)
        screen = surface.get_rect()
        if rect.right > screen.right - 10:
            rect.right = mouse[0] - 12
        if rect.bottom > screen.bottom - 10:
            rect.bottom = mouse[1] - 12
        rect.clamp_ip(screen.inflate(-12, -12))
        theme.draw_panel(
            surface,
            rect,
            theme.PANEL,
            radius=theme.RADIUS_SMALL,
            border=color,
            shadow=True,
        )
        theme.draw_text_in_rect(
            surface,
            text,
            rect,
            font_size,
            color,
            bold=True,
        )

    def _draw_promotion(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))

        theme.draw_panel(
            surface,
            self.promotion_rect,
            theme.PANEL,
            radius=theme.RADIUS,
            border=theme.ACCENT,
            shadow=True,
        )
        theme.draw_text(
            surface,
            "Превращение пешки",
            24,
            theme.TEXT,
            (self.promotion_rect.centerx, self.promotion_rect.top + 18),
            align="center",
            bold=True,
        )
        theme.draw_text(
            surface,
            "Выберите фигуру. Отмена невозможна.",
            14,
            theme.TEXT_MUTED,
            (self.promotion_rect.centerx, self.promotion_rect.top + 50),
            align="center",
        )

        mover = self.state.side_to_move
        for piece_type, rect in self.promotion_rects.items():
            hovered = self.promotion_hover is piece_type
            theme.draw_panel(
                surface,
                rect,
                theme.PANEL_LIGHT if hovered else theme.PANEL_DARK,
                radius=theme.RADIUS_SMALL,
                border=theme.ACCENT if hovered else theme.BORDER,
            )
            image_rect = rect.inflate(-34, -44)
            image_rect.top += 8
            piece_art.draw_piece(surface, piece_type, mover, image_rect)
            theme.draw_text(
                surface,
                f"{PROMOTION_LETTERS[piece_type]} · {piece_type.display_name}",
                13,
                theme.ACCENT if hovered else theme.TEXT_MUTED,
                (rect.centerx, rect.bottom - 15),
                align="center",
                valign="middle",
                bold=hovered,
            )

    def _draw_result(self, surface: pygame.Surface) -> None:
        result: GameResult = self.state.result  # type: ignore[assignment]
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        theme.draw_panel(
            surface,
            self.result_rect,
            theme.PANEL,
            radius=theme.RADIUS,
            border=theme.ACCENT,
            shadow=True,
        )
        theme.draw_text(
            surface,
            result.title,
            28,
            theme.ACCENT,
            (self.result_rect.centerx, self.result_rect.top + 34),
            align="center",
            bold=True,
        )
        theme.draw_text(
            surface,
            result.subtitle,
            16,
            theme.TEXT_MUTED,
            (self.result_rect.left + 34, self.result_rect.top + 82),
            max_width=self.result_rect.w - 68,
            line_spacing=5,
        )
        theme.draw_text(
            surface,
            "Ввод заблокирован. Начните новую партию или вернитесь в меню.",
            13,
            theme.TEXT_DIM,
            (self.result_rect.centerx, self.result_rect.top + 152),
            align="center",
        )
        for button in self.result_buttons.values():
            button.draw(surface)
