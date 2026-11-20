"""Экран правил (краткая версия этапа 2)."""

from __future__ import annotations

import pygame

from chess.ui import theme
from chess.ui.app import Scene
from chess.ui.widgets import Button, ScrollableText


_RULES_BLOCKS = [
    (
        "Текущий этап",
        "Реализован этап 2: полноценные стандартные шахматы на доске 8×8 "
        "в режиме hot-seat. Доступны все ходы фигур, рокировка, взятие на "
        "проходе, превращение, шах, мат, пат, журнал ходов и экран результата. "
        "Порталы, благословения и доски 6×6 / 10×10 появятся на следующих этапах.",
    ),
    (
        "Доска 8×8",
        "Файлы a–h, ранги 1–8. Белые всегда снизу, доска не переворачивается, "
        "клетка a1 тёмная. В начале партии у каждой стороны 8 пешек и по две "
        "ладьи, коня, слона, а также ферзь и король. Ферзь стоит на d1, король — на e1.",
    ),
    (
        "Ходы фигур",
        "Пешка идёт на одну клетку вперёд, с начальной позиции — на две, бьёт "
        "по диагонали. Конь ходит буквой «Г» и перепрыгивает фигуры. Слон и "
        "ладья скользят по диагонали и прямым соответственно. Ферзь сочетает "
        "ходы слона и ладьи. Король ходит на одну клетку в любом направлении.",
    ),
    (
        "Рокировка, en passant и превращение",
        "Рокировка возможна, если король и ладья ещё не ходили, клетки между "
        "ними пусты, а король не находится под шахом и не проходит через "
        "атакованную клетку. Взятие на проходе доступно только сразу после "
        "двойного хода вражеской пешки. Пешка на последнем ранге превращается "
        "в ферзя, ладью, слона или коня по выбору игрока.",
    ),
    (
        "Шах, мат и пат",
        "Шах — король атакован. Сторона не может оставить своего короля под "
        "шахом, поэтому такие ходы не предлагаются. Мат — шах и отсутствие "
        "легальных ходов; партия завершается победой противоположной стороны. "
        "Пат — легальных ходов нет, но шаха нет; это ничья.",
    ),
    (
        "Управление",
        "Партия ведётся только мышью, без drag-and-drop. Клик по своей фигуре "
        "выбирает её и показывает легальные ходы точками и кольцами. Второй "
        "клик по легальной клетке выполняет ход. Клик по другой своей фигуре "
        "переключает выбор, клик по пустой или нелегальной клетке снимает его. "
        "Правый клик или Esc также снимают выбор. При наведении на вражескую "
        "фигуру, которую можно взять, появляется пульсирующее красное свечение.",
    ),
    (
        "Превращение и результат",
        "При достижении последнего ранга открывается модальное окно с четырьмя "
        "фигурами: Q (ферзь), R (ладья), B (слон) и N (конь). Отмена превращения "
        "невозможна. После мата или пата ввод блокируется; доступны кнопки "
        "«Новая партия» и «В меню».",
    ),
    (
        "Будущие этапы",
        "Этап 3 добавит доски 6×6 и 10×10 и полные правила ничьих. Этап 4 — "
        "порталы, этап 5 — благословения короля, этап 6 — полный журнал, "
        "экран правил и полировку.",
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
            "Краткая версия правил · этап 2",
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
