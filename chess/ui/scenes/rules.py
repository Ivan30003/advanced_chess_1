"""Экран правил (краткая версия первого этапа)."""

from __future__ import annotations

import pygame

from chess.ui import theme
from chess.ui.app import Scene
from chess.ui.widgets import Button, ScrollableText


_RULES_BLOCKS = [
    (
        "Размеры доски",
        "Перед партией можно выбрать доску 6×6, 8×8 или 10×10. "
        "На 6×6 у каждой стороны меньше фигур, на 10×10 — больше свободного пространства. "
        "Белые всегда расположены снизу, доска не переворачивается.",
    ),
    (
        "Порталы",
        "Перед партией можно выбрать от 0 до 3 пар порталов. "
        "Портал — это две клетки одного цвета. Фигура, закончившая ход на портале, "
        "может выйти на парной клетке в начале следующего хода. "
        "Слон, ладья и ферзь могут телепортироваться во время хода и продолжить движение.",
    ),
    (
        "Благословения",
        "Если способности включены, каждая сторона выбирает одну из пяти способностей короля. "
        "Раз в 3 своих хода король может благословить соседнюю фигуру. "
        "Способности: щит, двойной ход, возрождение, заморозка и проход сквозь фигуры.",
    ),
    (
        "Управление",
        "Игра идёт на одном компьютере: два игрока ходят по очереди. "
        "Клик по фигуре выбирает её, второй клик по клетке делает ход. "
        "Правый клик или Esc отменяет выбор. "
        "Кнопка благословения появляется над выбранным королём, когда способность доступна.",
    ),
    (
        "Этап разработки",
        "Сейчас реализован этап 1: каркас, меню, настройка и предпросмотр доски. "
        "Игровая логика, порталы и благословения появятся на следующих этапах.",
    ),
]


class RulesScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.scroll = ScrollableText(blocks=_RULES_BLOCKS)
        self.back_button = Button("Назад", self.app.back_from_rules, font_size=20)
        self._background: pygame.Surface | None = None
        self._background_size = (0, 0)
        self._last_size = (0, 0)
        self._layout()

    def _layout(self) -> None:
        width, height = self.app.screen.get_size()
        self._last_size = (width, height)
        margin = 28
        header_h = 74
        footer_h = 76
        self.margin = margin
        self.header_h = header_h
        self.content_rect = pygame.Rect(
            margin,
            header_h + 10,
            width - margin * 2,
            height - header_h - footer_h - 20,
        )
        self.scroll.set_rect(self.content_rect)
        self.back_button.set_rect(
            pygame.Rect(
                width - margin - 200,
                height - footer_h + 14,
                200,
                46,
            )
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

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.app.screen.get_size() != self._last_size:
            self._layout()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.back_from_rules()
            return
        if self.back_button.handle_event(event):
            return
        self.scroll.handle_event(event)

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
            "Правила",
            32,
            theme.TEXT,
            (self.margin, 22),
            bold=True,
        )
        theme.draw_text(
            surface,
            "Краткая версия · полный текст появится на этапе 6",
            16,
            theme.TEXT_MUTED,
            (self.margin, 58),
        )

        self.scroll.draw(surface)
        self.back_button.draw(surface)

        theme.draw_text(
            surface,
            "Прокрутка: колесо мыши, ↑/↓, PageUp/PageDown",
            13,
            theme.TEXT_DIM,
            (self.margin, height - 34),
        )
