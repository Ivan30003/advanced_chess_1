"""Визуальная тема: палитра, шрифты и вспомогательные функции отрисовки."""

from __future__ import annotations

from functools import lru_cache

import pygame

# ---------------------------------------------------------------------------
# Размеры окна
# ---------------------------------------------------------------------------

WINDOW_DEFAULT_SIZE = (1280, 860)
WINDOW_MIN_SIZE = (1024, 720)
FPS = 60

# ---------------------------------------------------------------------------
# Палитра
# ---------------------------------------------------------------------------

BACKGROUND = (30, 30, 36)
BACKGROUND_TOP = (24, 24, 30)
BACKGROUND_BOTTOM = (38, 38, 48)
PANEL = (42, 42, 51)
PANEL_LIGHT = (54, 54, 66)
PANEL_DARK = (34, 34, 42)
BORDER = (72, 72, 88)
BORDER_SOFT = (58, 58, 72)

TEXT = (235, 232, 226)
TEXT_MUTED = (166, 164, 156)
TEXT_DIM = (122, 120, 114)
TEXT_DARK = (28, 28, 34)

LIGHT_SQUARE = (232, 211, 176)
DARK_SQUARE = (139, 90, 60)
BOARD_BORDER = (96, 62, 42)
BOARD_SHADOW = (12, 12, 16)

ACCENT = (224, 179, 84)
ACCENT_HOVER = (240, 198, 108)
ACCENT_DARK = (170, 130, 54)
GOLD = (242, 193, 78)
DANGER = (255, 59, 59)
DANGER_DARK = (170, 38, 38)
ICE = (110, 198, 255)
SUCCESS = (116, 210, 150)

WHITE_PIECE = (245, 240, 230)
WHITE_PIECE_OUTLINE = (43, 43, 43)
BLACK_PIECE = (43, 43, 43)
BLACK_PIECE_OUTLINE = (217, 210, 197)

PORTAL_COLORS = [
    (63, 208, 224),
    (224, 79, 208),
    (240, 178, 63),
]

PORTAL_NAMES = ("циан", "маджента", "янтарь")
PORTAL_SYMBOLS = ("◎", "△", "★")

# ---------------------------------------------------------------------------
# Кнопки
# ---------------------------------------------------------------------------

BUTTON_BG = (58, 58, 70)
BUTTON_HOVER = (74, 74, 90)
BUTTON_ACTIVE = (44, 44, 54)
BUTTON_DISABLED = (48, 48, 56)
BUTTON_BORDER = (88, 88, 104)
BUTTON_TEXT = TEXT
BUTTON_TEXT_DISABLED = (108, 106, 102)

# ---------------------------------------------------------------------------
# Отступы и скругления
# ---------------------------------------------------------------------------

MARGIN = 32
GAP_SMALL = 8
GAP = 12
GAP_LARGE = 20
RADIUS = 14
RADIUS_SMALL = 8
BORDER_WIDTH = 1

# ---------------------------------------------------------------------------
# Шрифты
# ---------------------------------------------------------------------------

_FONT_NAMES = "dejavusans,notosans,liberationsans,arial"


@lru_cache(maxsize=128)
def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Возвращает системный шрифт с поддержкой кириллицы."""

    size = max(8, int(size))
    path = pygame.font.match_font(_FONT_NAMES, bold=bold)
    if path:
        return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Переносит текст по словам с сохранением пустых строк."""

    if max_width <= 0:
        return [text]
    result: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            result.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    result.append(current)
                current = word
        if current:
            result.append(current)
    return result or [""]


def draw_text(
    surface: pygame.Surface,
    text: str,
    size: int,
    color: tuple[int, int, int] = TEXT,
    pos: tuple[int, int] = (0, 0),
    *,
    align: str = "left",
    valign: str = "top",
    bold: bool = False,
    max_width: int | None = None,
    line_spacing: int = 4,
    font: pygame.font.Font | None = None,
) -> pygame.Rect:
    """Рисует текст с выравниванием и возвращает занятый прямоугольник."""

    font = font or get_font(size, bold)
    source_lines = text.splitlines() or [""]
    lines: list[str] = []
    for source in source_lines:
        if max_width is not None:
            lines.extend(wrap_text(source, font, max_width))
        else:
            lines.append(source)

    rendered = [font.render(line, True, color) for line in lines]
    width = max((line.get_width() for line in rendered), default=0)
    height = sum(line.get_height() for line in rendered) + line_spacing * max(0, len(rendered) - 1)

    if align == "center":
        x = pos[0] - width // 2
    elif align == "right":
        x = pos[0] - width
    else:
        x = pos[0]

    if valign == "middle":
        y = pos[1] - height // 2
    elif valign == "bottom":
        y = pos[1] - height
    else:
        y = pos[1]

    cursor_y = y
    for line in rendered:
        line_x = x
        if align == "center":
            line_x = pos[0] - line.get_width() // 2
        elif align == "right":
            line_x = pos[0] - line.get_width()
        surface.blit(line, (line_x, cursor_y))
        cursor_y += line.get_height() + line_spacing

    return pygame.Rect(x, y, width, height)


def draw_text_in_rect(
    surface: pygame.Surface,
    text: str,
    rect: pygame.Rect,
    size: int,
    color: tuple[int, int, int] = TEXT,
    *,
    bold: bool = False,
    max_width: int | None = None,
    align: str = "center",
    valign: str = "middle",
    line_spacing: int = 3,
) -> pygame.Rect:
    return draw_text(
        surface,
        text,
        size,
        color,
        (rect.centerx if align == "center" else rect.left, rect.centery),
        align=align,
        valign=valign,
        bold=bold,
        max_width=max_width,
        line_spacing=line_spacing,
    )


def draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int] = PANEL,
    *,
    radius: int = RADIUS,
    border: tuple[int, int, int] | None = None,
    border_width: int = BORDER_WIDTH,
    shadow: bool = False,
) -> None:
    """Рисует панель с опциональной тенью и рамкой."""

    if shadow:
        shadow_surface = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
        pygame.draw.rect(
            shadow_surface,
            (0, 0, 0, 70),
            pygame.Rect(8, 8, rect.w, rect.h),
            border_radius=radius,
        )
        surface.blit(shadow_surface, (rect.x - 8, rect.y - 8))

    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, width=border_width, border_radius=radius)


def lerp_color(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(start, end))


def vertical_gradient(
    size: tuple[int, int],
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> pygame.Surface:
    width, height = size
    surface = pygame.Surface(size)
    for y in range(height):
        color = lerp_color(top, bottom, y / max(1, height - 1))
        pygame.draw.line(surface, color, (0, y), (width, y))
    return surface


def with_alpha(color: tuple[int, int, int], alpha: int) -> tuple[int, int, int, int]:
    return color[0], color[1], color[2], max(0, min(255, alpha))


def draw_soft_glow(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int] = DANGER,
    *,
    layers: int = 7,
    max_alpha: int = 110,
    spread: int = 14,
) -> None:
    """Мягкое свечение вокруг прямоугольника."""

    glow = pygame.Surface((rect.w + spread * 2, rect.h + spread * 2), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        alpha = int(max_alpha * (1 - (i - 1) / layers) ** 2)
        inset = int(spread * (i / layers))
        pygame.draw.rect(
            glow,
            with_alpha(color, alpha),
            pygame.Rect(spread - inset, spread - inset, rect.w + inset * 2, rect.h + inset * 2),
            border_radius=max(4, RADIUS_SMALL + inset // 2),
        )
    surface.blit(glow, (rect.x - spread, rect.y - spread))


def draw_checker_pattern(
    surface: pygame.Surface,
    area: pygame.Rect,
    cell: int = 64,
    color: tuple[int, int, int] = (255, 255, 255),
    alpha: int = 8,
) -> None:
    """Едва заметный шахматный узор для фона."""

    overlay = pygame.Surface((area.w, area.h), pygame.SRCALPHA)
    for row in range((area.h + cell - 1) // cell):
        for col in range((area.w + cell - 1) // cell):
            if (row + col) % 2 == 0:
                pygame.draw.rect(
                    overlay,
                    with_alpha(color, alpha),
                    pygame.Rect(col * cell, row * cell, cell, cell),
                )
    surface.blit(overlay, (area.x, area.y))


def portal_color(index: int) -> tuple[int, int, int]:
    return PORTAL_COLORS[index % len(PORTAL_COLORS)]


def portal_name(index: int) -> str:
    return PORTAL_NAMES[index % len(PORTAL_NAMES)]


def portal_symbol(index: int) -> str:
    return PORTAL_SYMBOLS[index % len(PORTAL_SYMBOLS)]
