"""Векторные шахматные фигуры и иконки способностей.

Все изображения рисуются примитивами pygame и кэшируются. Внешних файлов нет.
"""

from __future__ import annotations

import math

import pygame

from chess.core.pieces import BlessingType, Color, PieceType
from chess.ui import theme

_SS = 4
_PIECE_CACHE: dict[tuple[PieceType, Color, int], pygame.Surface] = {}
_ICON_CACHE: dict[tuple[BlessingType, int, tuple[int, int, int]], pygame.Surface] = {}
_CACHE_LIMIT = 256


def _poly(
    surface: pygame.Surface,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    points: list[tuple[float, float]],
    scale: float,
    *,
    width: float = 2.0,
) -> None:
    pixels = [(int(x * scale), int(y * scale)) for x, y in points]
    pygame.draw.polygon(surface, fill, pixels)
    pygame.draw.polygon(surface, outline, pixels, max(1, int(width * scale)))


def _rect(
    surface: pygame.Surface,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    rect: tuple[float, float, float, float],
    scale: float,
    *,
    radius: float = 0.0,
    width: float = 2.0,
) -> None:
    pixel_rect = pygame.Rect(
        int(rect[0] * scale),
        int(rect[1] * scale),
        int(rect[2] * scale),
        int(rect[3] * scale),
    )
    pygame.draw.rect(
        surface,
        fill,
        pixel_rect,
        border_radius=max(0, int(radius * scale)),
    )
    pygame.draw.rect(
        surface,
        outline,
        pixel_rect,
        width=max(1, int(width * scale)),
        border_radius=max(0, int(radius * scale)),
    )


def _ellipse(
    surface: pygame.Surface,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    rect: tuple[float, float, float, float],
    scale: float,
    *,
    width: float = 2.0,
) -> None:
    pixel_rect = pygame.Rect(
        int(rect[0] * scale),
        int(rect[1] * scale),
        int(rect[2] * scale),
        int(rect[3] * scale),
    )
    pygame.draw.ellipse(surface, fill, pixel_rect)
    pygame.draw.ellipse(surface, outline, pixel_rect, max(1, int(width * scale)))


def _circle(
    surface: pygame.Surface,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    center: tuple[float, float],
    radius: float,
    scale: float,
    *,
    width: float = 2.0,
) -> None:
    pixel_center = (int(center[0] * scale), int(center[1] * scale))
    pixel_radius = max(1, int(radius * scale))
    pygame.draw.circle(surface, fill, pixel_center, pixel_radius)
    pygame.draw.circle(
        surface,
        outline,
        pixel_center,
        pixel_radius,
        max(1, int(width * scale)),
    )


def _line(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    start: tuple[float, float],
    end: tuple[float, float],
    scale: float,
    *,
    width: float = 2.0,
) -> None:
    pygame.draw.line(
        surface,
        color,
        (int(start[0] * scale), int(start[1] * scale)),
        (int(end[0] * scale), int(end[1] * scale)),
        max(1, int(width * scale)),
    )


def _draw_base(
    surface: pygame.Surface,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    scale: float,
) -> None:
    _ellipse(surface, fill, outline, (20, 74, 60, 18), scale, width=1.8)
    _rect(surface, fill, outline, (28, 87, 44, 7), scale, radius=3.0, width=1.8)


def _draw_pawn(surface, fill, outline, scale: float) -> None:
    _poly(
        surface,
        fill,
        outline,
        [(38, 42), (62, 42), (68, 78), (32, 78)],
        scale,
    )
    _ellipse(surface, fill, outline, (36, 36, 28, 11), scale, width=1.6)
    _circle(surface, fill, outline, (50, 27), 13, scale, width=1.8)
    _draw_base(surface, fill, outline, scale)


def _draw_rook(surface, fill, outline, scale: float) -> None:
    _poly(
        surface,
        fill,
        outline,
        [
            (28, 20),
            (38, 20),
            (38, 28),
            (46, 28),
            (46, 20),
            (54, 20),
            (54, 28),
            (62, 28),
            (62, 20),
            (72, 20),
            (72, 39),
            (28, 39),
        ],
        scale,
    )
    _poly(
        surface,
        fill,
        outline,
        [(33, 39), (67, 39), (70, 78), (30, 78)],
        scale,
    )
    _line(surface, outline, (33, 48), (67, 48), scale, width=1.5)
    _line(surface, outline, (32, 56), (68, 56), scale, width=1.5)
    _draw_base(surface, fill, outline, scale)


def _draw_knight(surface, fill, outline, scale: float) -> None:
    points = [
        (30, 80),
        (34, 62),
        (30, 54),
        (38, 40),
        (46, 28),
        (44, 20),
        (47, 15),
        (50, 24),
        (55, 15),
        (58, 26),
        (64, 32),
        (68, 36),
        (77, 43),
        (81, 49),
        (76, 54),
        (68, 54),
        (62, 49),
        (59, 58),
        (55, 64),
        (60, 80),
    ]
    _poly(surface, fill, outline, points, scale)
    _circle(surface, outline, outline, (59, 35), 3.2, scale, width=0.8)
    _circle(surface, outline, outline, (75, 47), 1.8, scale, width=0.8)
    _line(surface, outline, (46, 28), (40, 46), scale, width=1.6)
    _draw_base(surface, fill, outline, scale)


def _draw_bishop(surface, fill, outline, scale: float) -> None:
    _poly(
        surface,
        fill,
        outline,
        [(38, 52), (62, 52), (68, 78), (32, 78)],
        scale,
    )
    _rect(surface, fill, outline, (34, 44, 32, 9), scale, radius=4.0, width=1.6)
    _poly(
        surface,
        fill,
        outline,
        [(50, 12), (60, 22), (66, 38), (62, 48), (38, 48), (34, 38), (40, 22)],
        scale,
    )
    _circle(surface, fill, outline, (50, 9), 4, scale, width=1.5)
    _line(surface, outline, (50, 24), (50, 40), scale, width=1.6)
    _draw_base(surface, fill, outline, scale)


def _draw_queen(surface, fill, outline, scale: float) -> None:
    _poly(
        surface,
        fill,
        outline,
        [(34, 52), (66, 52), (70, 78), (30, 78)],
        scale,
    )
    _rect(surface, fill, outline, (30, 45, 40, 9), scale, radius=4.0, width=1.6)
    _poly(
        surface,
        fill,
        outline,
        [
            (26, 28),
            (34, 46),
            (42, 26),
            (50, 44),
            (58, 26),
            (66, 46),
            (74, 28),
            (70, 50),
            (30, 50),
        ],
        scale,
    )
    for center in ((26, 24), (42, 22), (58, 22), (74, 24), (50, 18)):
        _circle(surface, fill, outline, center, 4.2, scale, width=1.4)
    _draw_base(surface, fill, outline, scale)


def _draw_king(surface, fill, outline, scale: float) -> None:
    _poly(
        surface,
        fill,
        outline,
        [(34, 52), (66, 52), (70, 78), (30, 78)],
        scale,
    )
    _rect(surface, fill, outline, (30, 45, 40, 9), scale, radius=4.0, width=1.6)
    _poly(
        surface,
        fill,
        outline,
        [
            (28, 30),
            (36, 46),
            (44, 28),
            (50, 44),
            (56, 28),
            (64, 46),
            (72, 30),
            (68, 50),
            (32, 50),
        ],
        scale,
    )
    _poly(
        surface,
        fill,
        outline,
        [
            (47, 10),
            (53, 10),
            (53, 17),
            (61, 17),
            (61, 23),
            (53, 23),
            (53, 36),
            (47, 36),
            (47, 23),
            (39, 23),
            (39, 17),
            (47, 17),
        ],
        scale,
        width=1.5,
    )
    _draw_base(surface, fill, outline, scale)


_DRAWERS = {
    PieceType.PAWN: _draw_pawn,
    PieceType.KNIGHT: _draw_knight,
    PieceType.BISHOP: _draw_bishop,
    PieceType.ROOK: _draw_rook,
    PieceType.QUEEN: _draw_queen,
    PieceType.KING: _draw_king,
}


def render_piece(piece_type: PieceType, color: Color, size: int) -> pygame.Surface:
    """Возвращает кэшированное изображение фигуры указанного размера."""

    size = max(8, int(size))
    key = (piece_type, color, size)
    cached = _PIECE_CACHE.get(key)
    if cached is not None:
        return cached

    if len(_PIECE_CACHE) >= _CACHE_LIMIT:
        _PIECE_CACHE.clear()

    high_size = size * _SS
    surface = pygame.Surface((high_size, high_size), pygame.SRCALPHA)
    scale = high_size / 100.0
    if color is Color.WHITE:
        fill, outline = theme.WHITE_PIECE, theme.WHITE_PIECE_OUTLINE
    else:
        fill, outline = theme.BLACK_PIECE, theme.BLACK_PIECE_OUTLINE

    _DRAWERS[piece_type](surface, fill, outline, scale)
    result = pygame.transform.smoothscale(surface, (size, size))
    _PIECE_CACHE[key] = result
    return result


def draw_piece(
    surface: pygame.Surface,
    piece_type: PieceType,
    color: Color,
    rect: pygame.Rect,
) -> None:
    """Рисует фигуру, вписанную в прямоугольник клетки."""

    size = max(8, min(rect.w, rect.h))
    image = render_piece(piece_type, color, size)
    surface.blit(image, image.get_rect(center=rect.center))


def render_gallery(
    piece_size: int = 64,
    spacing: int = 16,
    *,
    show_labels: bool = True,
    label_width: int = 72,
) -> pygame.Surface:
    """Галерея всех шести фигур обоих цветов."""

    piece_size = max(24, int(piece_size))
    spacing = max(0, int(spacing))
    label_w = label_width if show_labels else 0
    columns = 6
    rows = 2
    width = label_w + columns * piece_size + (columns - 1) * spacing
    height = rows * piece_size + (rows - 1) * spacing
    surface = pygame.Surface((width, height), pygame.SRCALPHA)

    order = [
        PieceType.KING,
        PieceType.QUEEN,
        PieceType.ROOK,
        PieceType.BISHOP,
        PieceType.KNIGHT,
        PieceType.PAWN,
    ]
    font = theme.get_font(16, bold=True)
    for row, color in enumerate((Color.WHITE, Color.BLACK)):
        y = row * (piece_size + spacing)
        if show_labels:
            label = "Белые" if color is Color.WHITE else "Чёрные"
            theme.draw_text(
                surface,
                label,
                font.get_height(),
                theme.TEXT_MUTED,
                (label_w // 2, y + piece_size // 2),
                align="center",
                valign="middle",
                bold=True,
                font=font,
            )
        for col, piece_type in enumerate(order):
            x = label_w + col * (piece_size + spacing)
            rect = pygame.Rect(x, y, piece_size, piece_size)
            draw_piece(surface, piece_type, color, rect)
    return surface


# ---------------------------------------------------------------------------
# Иконки благословений
# ---------------------------------------------------------------------------


def _icon_poly(surface, color, points, scale: float, width: float = 6.0) -> None:
    pixels = [(int(x * scale), int(y * scale)) for x, y in points]
    pygame.draw.polygon(surface, color, pixels, max(1, int(width * scale)))


def _icon_line(surface, color, start, end, scale: float, width: float = 6.0) -> None:
    pygame.draw.line(
        surface,
        color,
        (int(start[0] * scale), int(start[1] * scale)),
        (int(end[0] * scale), int(end[1] * scale)),
        max(1, int(width * scale)),
    )


def _draw_blessing_icon(surface: pygame.Surface, blessing: BlessingType, color, scale: float) -> None:
    if blessing is BlessingType.INVULNERABILITY:
        _icon_poly(
            surface,
            color,
            [(50, 8), (84, 22), (78, 60), (50, 90), (22, 60), (16, 22)],
            scale,
            width=7.0,
        )
        _icon_line(surface, color, (50, 28), (50, 62), scale, width=7.0)
        _icon_line(surface, color, (36, 44), (64, 44), scale, width=7.0)
    elif blessing is BlessingType.DOUBLE_MOVE:
        _icon_poly(surface, color, [(16, 62), (50, 30), (84, 62)], scale, width=8.0)
        _icon_poly(surface, color, [(16, 86), (50, 54), (84, 86)], scale, width=8.0)
    elif blessing is BlessingType.RESURRECTION:
        _icon_line(surface, color, (50, 84), (50, 28), scale, width=8.0)
        _icon_poly(surface, color, [(28, 46), (50, 16), (72, 46)], scale, width=8.0)
        pygame.draw.circle(
            surface,
            color,
            (int(50 * scale), int(84 * scale)),
            max(1, int(8 * scale)),
            max(1, int(6 * scale)),
        )
    elif blessing is BlessingType.FREEZE:
        center = (50, 50)
        for angle in (0, 60, 120):
            dx = 34 * math.cos(math.radians(angle))
            dy = 34 * math.sin(math.radians(angle))
            _icon_line(
                surface,
                color,
                (center[0] - dx, center[1] - dy),
                (center[0] + dx, center[1] + dy),
                scale,
                width=7.0,
            )
        for angle in (0, 60, 120):
            for sign in (-1, 1):
                dx = 34 * math.cos(math.radians(angle))
                dy = 34 * math.sin(math.radians(angle))
                tip = (center[0] + sign * dx, center[1] + sign * dy)
                _icon_line(surface, color, tip, (tip[0] - 10, tip[1] + 6), scale, width=5.0)
                _icon_line(surface, color, tip, (tip[0] - 10, tip[1] - 6), scale, width=5.0)
    elif blessing is BlessingType.PASS_THROUGH:
        _icon_poly(
            surface,
            color,
            [
                (28, 88),
                (28, 38),
                (34, 20),
                (50, 12),
                (66, 20),
                (72, 38),
                (72, 88),
                (62, 78),
                (52, 88),
                (42, 78),
                (32, 88),
            ],
            scale,
            width=7.0,
        )
        pygame.draw.circle(
            surface,
            color,
            (int(42 * scale), int(42 * scale)),
            max(1, int(4 * scale)),
        )
        pygame.draw.circle(
            surface,
            color,
            (int(58 * scale), int(42 * scale)),
            max(1, int(4 * scale)),
        )


def render_blessing_icon(
    blessing: BlessingType,
    size: int,
    color: tuple[int, int, int] = theme.ACCENT,
) -> pygame.Surface:
    size = max(8, int(size))
    key = (blessing, size, color)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_ICON_CACHE) >= _CACHE_LIMIT:
        _ICON_CACHE.clear()

    high_size = size * _SS
    surface = pygame.Surface((high_size, high_size), pygame.SRCALPHA)
    _draw_blessing_icon(surface, blessing, color, high_size / 100.0)
    result = pygame.transform.smoothscale(surface, (size, size))
    _ICON_CACHE[key] = result
    return result


def draw_blessing_icon(
    surface: pygame.Surface,
    blessing: BlessingType,
    rect: pygame.Rect,
    color: tuple[int, int, int] = theme.ACCENT,
) -> None:
    size = max(8, min(rect.w, rect.h))
    image = render_blessing_icon(blessing, size, color)
    surface.blit(image, image.get_rect(center=rect.center))
