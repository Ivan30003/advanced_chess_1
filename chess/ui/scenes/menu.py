"""Главное меню."""

from __future__ import annotations

import pygame

from chess.ui import piece_art, theme
from chess.ui.app import Scene
from chess.ui.widgets import Button, ConfirmDialog


class MenuScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._background: pygame.Surface | None = None
        self._background_size = (0, 0)
        self._last_size = (0, 0)
        self._gallery: pygame.Surface | None = None
        self._gallery_size = 0
        self.buttons: dict[str, Button] = {}
        self.quit_dialog = ConfirmDialog(
            "Выход",
            "Закрыть игру?",
            on_confirm=self.app.quit,
            confirm_text="Выйти",
            cancel_text="Остаться",
        )
        self._build_buttons()

    def _build_buttons(self) -> None:
        self.buttons = {
            "play": Button("Играть", self.app.show_setup, accent=True, font_size=24),
            "rules": Button("Правила", self.app.show_rules, font_size=22),
            "quit": Button("Выход", self.app.quit, font_size=22),
        }

    def _layout(self) -> None:
        width, height = self.app.screen.get_size()
        self._last_size = (width, height)
        button_w = min(340, width - 120)
        button_h = 56
        gap = 14
        total = button_h * 3 + gap * 2
        start_y = int(height * 0.33)
        x = width // 2 - button_w // 2
        for index, key in enumerate(("play", "rules", "quit")):
            self.buttons[key].set_rect(
                pygame.Rect(x, start_y + index * (button_h + gap), button_w, button_h)
            )

    def _ensure_background(self, size: tuple[int, int]) -> pygame.Surface:
        if self._background is not None and self._background_size == size:
            return self._background
        width, height = size
        background = theme.vertical_gradient(size, theme.BACKGROUND_TOP, theme.BACKGROUND_BOTTOM)
        theme.draw_checker_pattern(
            background,
            pygame.Rect(int(width * 0.52), 0, int(width * 0.48), height),
            cell=max(48, width // 22),
            color=theme.ACCENT,
            alpha=7,
        )
        theme.draw_checker_pattern(
            background,
            pygame.Rect(0, int(height * 0.55), int(width * 0.35), int(height * 0.45)),
            cell=max(48, width // 24),
            color=theme.TEXT,
            alpha=4,
        )
        glow = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.circle(glow, (224, 179, 84, 18), (int(width * 0.18), int(height * 0.22)), 220)
        pygame.draw.circle(glow, (63, 208, 224, 12), (int(width * 0.84), int(height * 0.72)), 260)
        background.blit(glow, (0, 0))
        self._background = background
        self._background_size = size
        return background

    def _ensure_gallery(self, piece_size: int) -> pygame.Surface:
        if self._gallery is not None and self._gallery_size == piece_size:
            return self._gallery
        self._gallery = piece_art.render_gallery(
            piece_size,
            spacing=max(10, piece_size // 5),
            show_labels=True,
            label_width=max(64, piece_size + 12),
        )
        self._gallery_size = piece_size
        return self._gallery

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.app.screen.get_size() != self._last_size:
            self._layout()
        if self.quit_dialog.visible:
            self.quit_dialog.handle_event(event)
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.quit_dialog.open()
            return
        for button in self.buttons.values():
            if button.handle_event(event):
                return

    def draw(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        surface.blit(self._ensure_background((width, height)), (0, 0))
        self._layout()

        theme.draw_text(
            surface,
            "Advanced Chess",
            max(48, min(76, width // 17)),
            theme.TEXT,
            (width // 2, int(height * 0.12)),
            align="center",
            valign="middle",
            bold=True,
        )
        theme.draw_text(
            surface,
            "Продвинутые шахматы",
            max(18, min(28, width // 45)),
            theme.ACCENT,
            (width // 2, int(height * 0.19)),
            align="center",
            valign="middle",
        )

        for button in self.buttons.values():
            button.draw(surface)

        piece_size = max(40, min(70, int(height * 0.075)))
        gallery = self._ensure_gallery(piece_size)
        padding = 22
        panel_rect = pygame.Rect(
            0,
            0,
            gallery.get_width() + padding * 2,
            gallery.get_height() + padding * 2,
        )
        panel_rect.center = (width // 2, int(height * 0.75))
        theme.draw_panel(
            surface,
            panel_rect,
            theme.PANEL_DARK,
            radius=theme.RADIUS,
            border=theme.BORDER_SOFT,
            shadow=True,
        )
        surface.blit(gallery, gallery.get_rect(center=panel_rect.center))

        theme.draw_text(
            surface,
            "hot-seat · доски 6×6, 8×8 и 10×10 · этап 3",
            max(12, min(16, width // 80)),
            theme.TEXT_DIM,
            (width // 2, height - 28),
            align="center",
            valign="middle",
        )

        self.quit_dialog.draw(surface)
