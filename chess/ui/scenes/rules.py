"""Экран правил (краткая версия этапа 3)."""

from __future__ import annotations

import pygame

from chess.ui import theme
from chess.ui.app import Scene
from chess.ui.widgets import Button, ScrollableText


_RULES_BLOCKS = [
    (
        "Текущий этап",
        "Реализован этап 3: полноценные стандартные шахматы на досках 6×6, "
        "8×8 и 10×10 в режиме hot-seat. Доступны все ходы фигур, рокировка по "
        "правилам размера, взятие на проходе, превращение, шах, мат, пат, "
        "правило 50 ходов, троекратное повторение, недостаточный материал, "
        "журнал ходов и экран результата. Порталы и благословения появятся "
        "на следующих этапах.",
    ),
    (
        "Размеры доски",
        "На 6×6 у каждой стороны 6 пешек и по одной ладье, коню и слону, "
        "а также ферзь и король; ферзь стоит на d1, король — на e1. "
        "На 8×8 стандартная расстановка: ферзь на d1, король на e1. "
        "На 10×10 крайние клетки a1, j1, a10 и j10 пусты, ферзь стоит на e1, "
        "король — на f1, а у каждой стороны 10 пешек. Белые всегда снизу, "
        "доска не переворачивается.",
    ),
    (
        "Ходы фигур",
        "Пешка идёт на одну клетку вперёд, с начальной позиции — на две, бьёт "
        "по диагонали. Конь ходит буквой «Г» и перепрыгивает фигуры. Слон и "
        "ладья скользят по диагонали и прямым соответственно. Ферзь сочетает "
        "ходы слона и ладьи. Король ходит на одну клетку в любом направлении.",
    ),
    (
        "Рокировка",
        "На 6×6 рокировка запрещена. На 8×8 действует стандартная рокировка. "
        "На 10×10 король стоит на f1: короткая рокировка — f1→h1 с ладьёй "
        "i1→g1, длинная — f1→d1 с ладьёй b1→e1. Нужны свободные клетки между "
        "королём и ладьёй, отсутствие шаха и атаки на клетки, через которые "
        "проходит король. Права теряются при ходе короля, ходе ладьи или её "
        "взятии.",
    ),
    (
        "Пешки, en passant и превращение",
        "Двойной ход возможен только с начального ранга и только если пешка "
        "ещё не двигалась. Взятие на проходе доступно только сразу после "
        "двойного хода вражеской пешки. Пешка на последнем ранге превращается "
        "в ферзя, ладью, слона или коня по выбору игрока; второго ферзя "
        "получать разрешено.",
    ),
    (
        "Шах, мат и пат",
        "Шах — король атакован. Сторона не может оставить своего короля под "
        "шахом, поэтому такие ходы не предлагаются. Мат — шах и отсутствие "
        "легальных ходов; партия завершается победой противоположной стороны. "
        "Пат — легальных ходов нет, но шаха нет; это ничья.",
    ),
    (
        "Ничьи",
        "Автоматическая ничья по правилу 50 ходов наступает на 100-м полуходе "
        "без хода пешкой и без взятия. Троекратное повторение фиксируется по "
        "полному хешу позиции. Недостаточный материал: только короли, K+B vs K, "
        "K+N vs K и K+B vs K+B с одноцветными слонами. Сдача и ничья по "
        "соглашению предусмотрены в состоянии партии и появятся в интерфейсе "
        "на этапе 6.",
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
        "невозможна. После мата, пата или ничьей ввод блокируется; доступны "
        "кнопки «Новая партия» и «В меню». Экран результата показывает причину.",
    ),
    (
        "Будущие этапы",
        "Этап 4 добавит порталы, этап 5 — благословения короля, этап 6 — полный "
        "журнал, экран правил, сдачу, ничью по соглашению и полировку. "
        "Выбранные на экране настройки порталов и способностей уже сохраняются "
        "в состоянии партии, но их механики пока не действуют.",
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
            "Краткая версия правил · этап 3",
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
