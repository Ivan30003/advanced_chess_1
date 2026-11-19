"""Заглушка игрового экрана первого этапа."""

from __future__ import annotations

import pygame

from chess.core.pieces import BLESSING_INFO
from chess.ui import theme
from chess.ui.app import Scene
from chess.ui.board_view import BoardView
from chess.ui.setup_config import SetupConfig
from chess.ui.widgets import Button


class GameScene(Scene):
    def __init__(self, app, config: SetupConfig) -> None:
        super().__init__(app)
        self.config = config.copy()
        self.board_view = BoardView(self.config.board_size)
        self.buttons: dict[str, Button] = {
            "rules": Button("Правила", self.app.show_rules, font_size=18),
            "setup": Button("Назад в настройки", self._back_to_setup, font_size=18),
            "menu": Button("В меню", self.app.show_menu, font_size=18),
        }
        self._background: pygame.Surface | None = None
        self._background_size = (0, 0)
        self._last_size = (0, 0)
        self._layout()

    def _back_to_setup(self) -> None:
        self.app.show_setup(self.config)

    def _layout(self) -> None:
        width, height = self.app.screen.get_size()
        self._last_size = (width, height)
        margin = 28
        header_h = 72
        self.margin = margin
        self.header_h = header_h
        panel_w = min(370, max(300, int(width * 0.29)))
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

        button_h = 42
        gap = 8
        y = self.panel_rect.bottom - (button_h * 3 + gap * 2) - 16
        for key in ("rules", "setup", "menu"):
            self.buttons[key].set_rect(
                pygame.Rect(
                    self.panel_rect.left + 16,
                    y,
                    self.panel_rect.w - 32,
                    button_h,
                )
            )
            y += button_h + gap
        self.buttons_top = self.panel_rect.bottom - (button_h * 3 + gap * 2) - 16

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

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.app.screen.get_size() != self._last_size:
            self._layout()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back_to_setup()
            return
        for button in self.buttons.values():
            if button.handle_event(event):
                return

    def update(self, dt: float) -> None:
        del dt
        if self.app.screen.get_size() != self._last_size:
            self._layout()

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
            "Игровой экран · этап 1",
            16,
            theme.TEXT_MUTED,
            (self.margin, 58),
        )

        self.board_view.draw(surface, show_coordinates=True)
        self._draw_board_placeholder(surface)
        self._draw_panel(surface)

    def _draw_board_placeholder(self, surface: pygame.Surface) -> None:
        center = self.board_view.board_rect.center
        overlay = pygame.Surface((self.board_view.board_rect.w, self.board_view.board_rect.h), pygame.SRCALPHA)
        overlay.fill((16, 16, 20, 38))
        surface.blit(overlay, self.board_view.board_rect.topleft)
        theme.draw_text(
            surface,
            "Здесь будет партия",
            max(20, min(34, self.board_view.square_size // 2)),
            (255, 255, 255, 120),
            center,
            align="center",
            valign="middle",
            bold=True,
        )
        theme.draw_text(
            surface,
            "Расстановка и ходы появятся на этапе 2",
            14,
            (255, 255, 255, 100),
            (center[0], center[1] + 36),
            align="center",
            valign="middle",
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
        y = self.panel_rect.top + 18
        theme.draw_text(
            surface,
            "Параметры партии",
            20,
            theme.TEXT,
            (x, y),
            bold=True,
        )
        y += 38

        abilities_text = "включены" if self.config.abilities_enabled else "выключены"
        lines = [
            ("Доска", f"{self.config.board_size}×{self.config.board_size}"),
            ("Порталы", str(self.config.portal_count)),
            ("Способности", abilities_text),
        ]
        for label, value in lines:
            theme.draw_text(surface, label, 15, theme.TEXT_MUTED, (x, y))
            theme.draw_text(
                surface,
                value,
                15,
                theme.TEXT,
                (self.panel_rect.right - 18, y),
                align="right",
                bold=True,
            )
            y += 26

        if self.config.abilities_enabled:
            y += 6
            theme.draw_text(surface, "Способности сторон", 15, theme.TEXT, (x, y), bold=True)
            y += 26
            for color, ability in (
                ("Белые", self.config.white_ability),
                ("Чёрные", self.config.black_ability),
            ):
                info = BLESSING_INFO.get(ability) if ability is not None else None
                theme.draw_text(surface, f"{color}:", 14, theme.TEXT_MUTED, (x, y))
                theme.draw_text(
                    surface,
                    info.name if info is not None else "не выбрана",
                    14,
                    theme.ACCENT if info is not None else theme.TEXT_DIM,
                    (x + 74, y),
                )
                y += 24

        note_rect = pygame.Rect(
            x,
            self.buttons_top - 118,
            self.panel_rect.w - 36,
            92,
        )
        theme.draw_panel(
            surface,
            note_rect,
            (48, 43, 32),
            radius=theme.RADIUS_SMALL,
            border=theme.ACCENT_DARK,
        )
        theme.draw_text(
            surface,
            "Этап 1",
            13,
            theme.ACCENT,
            (note_rect.left + 12, note_rect.top + 10),
            bold=True,
        )
        theme.draw_text(
            surface,
            "Игровая логика будет добавлена на этапе 2. Сейчас доступны только настройка и предпросмотр.",
            13,
            theme.TEXT_MUTED,
            (note_rect.left + 12, note_rect.top + 34),
            max_width=note_rect.w - 24,
            line_spacing=3,
        )

        for button in self.buttons.values():
            button.draw(surface)
