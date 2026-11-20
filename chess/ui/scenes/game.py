"""Игровой экран: партия на доске 6×6, 8×8 или 10×10 с hot-seat управлением."""

from __future__ import annotations

import pygame

from chess.core.coords import Square
from chess.core.game_state import GameResult, GameState
from chess.core.moves import Move, Turn
from chess.core.pieces import (
    PROMOTION_LETTERS,
    PROMOTION_PIECES,
    Color,
    PieceType,
)
from chess.core.rules import generate_legal_moves, is_in_check
from chess.ui import piece_art, theme
from chess.ui.app import Scene
from chess.ui.board_view import BoardView, DisplayPiece
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
        self.state = GameState.initial(self.game_config)
        self.selected: Square | None = None
        self.legal_by_target: dict[Square, list[Move]] = {}
        self.hover_capture: tuple[int, int] | None = None
        self.pending_promotion: list[Move] | None = None
        self.promotion_hover: PieceType | None = None
        self.promotion_rects: dict[PieceType, pygame.Rect] = {}
        self.log_scroll = 0.0
        self.log_follow = True

        self.buttons: dict[str, Button] = {
            "new": Button("Новая партия", self.new_game, accent=True, font_size=19),
            "rules": Button("Правила", self.app.show_rules, font_size=18),
            "menu": Button("В меню", self.app.show_menu, font_size=18),
        }
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
        self.state = GameState.initial(self.game_config)
        self._clear_selection()
        self.pending_promotion = None
        self.log_scroll = 0.0
        self.log_follow = True

    def _clear_selection(self) -> None:
        self.selected = None
        self.legal_by_target = {}
        self.hover_capture = None

    def _select(self, square: Square) -> None:
        moves = [
            move
            for move in generate_legal_moves(self.state)
            if move.from_square == square
        ]
        self.selected = square
        self.legal_by_target = {}
        for move in moves:
            self.legal_by_target.setdefault(move.to_square, []).append(move)

    def _execute(self, move: Move) -> None:
        self.state = self.state.apply_turn(Turn.single(move))
        self.pending_promotion = None
        self._clear_selection()
        self.log_follow = True

    def _handle_board_click(self, square: Square) -> None:
        if self.state.result is not None:
            return
        piece = self.state.board.piece_at(square)

        if self.selected is None:
            if piece is not None and piece.color is self.state.side_to_move:
                self._select(square)
            return

        if square == self.selected:
            self._clear_selection()
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
        # снимает его. Такое поведение описано в README.
        if piece is not None and piece.color is self.state.side_to_move:
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
        self.status_rect = pygame.Rect(px, self.panel_rect.top + 82, inner_w, 64)

        button_h = 40
        gap = 8
        y = self.panel_rect.bottom - (button_h * 3 + gap * 2) - 16
        self.buttons_top = y
        for key in ("new", "rules", "menu"):
            self.buttons[key].set_rect(pygame.Rect(px, y, inner_w, button_h))
            y += button_h + gap

        journal_top = self.status_rect.bottom + 52
        journal_bottom = self.buttons_top - 16
        self.journal_rect = pygame.Rect(
            px,
            journal_top,
            inner_w,
            max(80, journal_bottom - journal_top),
        )
        self._layout_overlays()

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
            self._clear_selection()
            return

        for button in self.buttons.values():
            if button.handle_event(event):
                return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
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

        self.hover_capture = None
        if (
            self.selected is not None
            and self.pending_promotion is None
            and self.state.result is None
        ):
            square = self.board_view.square_at(pygame.mouse.get_pos())
            if square is not None:
                core_square = Square(*square)
                candidates = self.legal_by_target.get(core_square, [])
                if any(move.is_capture for move in candidates):
                    self.hover_capture = square

        mouse = pygame.mouse.get_pos()
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
            f"Доска {self.game_config.size}×{self.game_config.size} · hot-seat · клик-клик",
            16,
            theme.TEXT_MUTED,
            (self.margin, 58),
        )

        self._draw_board(surface)
        self._draw_panel(surface)

        if self.pending_promotion:
            self._draw_promotion(surface)
        elif self.state.result is not None:
            self._draw_result(surface)

    def _draw_board(self, surface: pygame.Surface) -> None:
        state = self.state
        pieces = [
            DisplayPiece(
                piece_type=piece.type,
                color=piece.color,
                square=_ui_square(piece.square),
            )
            for piece in state.board.pieces.values()
        ]

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
        if self.config.show_legal_hints and self.selected is not None:
            for target, moves in self.legal_by_target.items():
                kind = "capture" if any(move.is_capture for move in moves) else "move"
                legal_targets[_ui_square(target)] = kind

        self.board_view.draw(
            surface,
            pieces=pieces,
            selected=selected,
            last_move=last_move,
            check_square=check_square,
            legal_targets=legal_targets,
            hover_capture=self.hover_capture,
            show_coordinates=True,
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
        if self.config.portal_count or self.config.abilities_enabled:
            theme.draw_text(
                surface,
                "Будет добавлено на следующих этапах.",
                11,
                theme.TEXT_DIM,
                (x, self.panel_rect.top + 62),
                max_width=self.panel_rect.w - 36,
            )

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
        elif not is_result:
            detail += " · выберите фигуру"
        theme.draw_text(
            surface,
            detail,
            14,
            theme.DANGER if in_check else theme.TEXT_MUTED,
            (self.status_rect.left + 14, self.status_rect.top + 40),
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
