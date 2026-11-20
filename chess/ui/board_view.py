"""Отрисовка шахматной доски, фигур, подсветок и порталов."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from chess.core.pieces import Color, PieceType
from chess.ui import piece_art, theme

Square = tuple[int, int]


@dataclass(frozen=True)
class DisplayPiece:
    piece_type: PieceType
    color: Color
    square: Square


@dataclass(frozen=True)
class PortalMarker:
    square: Square
    color_index: int
    label: str = ""


class BoardView:
    """Рисует доску произвольного размера и опциональные элементы."""

    # На маленьких досках не позволяем клеткам разрастаться на всю панель.
    MAX_SQUARE_SIZE = 96

    def __init__(self, board_size: int = 8) -> None:
        self.board_size = board_size
        self.rect = pygame.Rect(0, 0, 1, 1)
        self.square_size = 8
        self.board_rect = pygame.Rect(0, 0, 8, 8)
        self.origin = (0, 0)
        self.pulse_phase = 0.0

    def update(self, dt: float) -> None:
        """Продвигает фазу пульсации красного свечения цели атаки."""

        self.pulse_phase = (self.pulse_phase + dt * 3.2) % (math.tau)

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)
        self._recalculate()

    def _recalculate(self) -> None:
        n = self.board_size
        available = max(1, min(self.rect.w, self.rect.h))
        self.square_size = min(
            self.MAX_SQUARE_SIZE,
            max(8, available // (n + 1)),
        )
        board_px = self.square_size * n
        self.origin = (
            self.rect.centerx - board_px // 2,
            self.rect.centery - board_px // 2,
        )
        self.board_rect = pygame.Rect(self.origin[0], self.origin[1], board_px, board_px)

    def square_rect(self, file: int, rank: int) -> pygame.Rect:
        n = self.board_size
        x = self.board_rect.left + file * self.square_size
        y = self.board_rect.top + (n - 1 - rank) * self.square_size
        return pygame.Rect(x, y, self.square_size, self.square_size)

    def square_center(self, file: int, rank: int) -> tuple[int, int]:
        return self.square_rect(file, rank).center

    def square_at(self, pos: tuple[int, int]) -> Square | None:
        if not self.board_rect.collidepoint(pos):
            return None
        file = (pos[0] - self.board_rect.left) // self.square_size
        rank_from_top = (pos[1] - self.board_rect.top) // self.square_size
        rank = self.board_size - 1 - rank_from_top
        if 0 <= file < self.board_size and 0 <= rank < self.board_size:
            return int(file), int(rank)
        return None

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------

    def draw(
        self,
        surface: pygame.Surface,
        *,
        pieces: list[DisplayPiece] | None = None,
        selected: Square | None = None,
        last_move: tuple[Square, Square] | None = None,
        check_square: Square | None = None,
        legal_targets: dict[Square, str] | None = None,
        hover_capture: Square | None = None,
        portals: list[PortalMarker] | None = None,
        show_coordinates: bool = True,
    ) -> None:
        self._draw_board_base(surface)
        self._draw_squares(surface)

        if last_move is not None:
            for square in last_move:
                self._fill_square(surface, square, theme.ACCENT, 48)

        if check_square is not None:
            self._fill_square(surface, check_square, theme.DANGER, 88)
            self._stroke_square(surface, check_square, theme.DANGER, 3)

        if selected is not None:
            self._fill_square(surface, selected, theme.ACCENT, 40)
            self._stroke_square(surface, selected, theme.ACCENT, 3)

        if legal_targets:
            self._draw_legal_targets(surface, legal_targets)

        if hover_capture is not None:
            pulse = 0.5 + 0.5 * math.sin(self.pulse_phase)
            rect = self.square_rect(*hover_capture).inflate(-8, -8)
            theme.draw_soft_glow(
                surface,
                rect,
                theme.DANGER,
                layers=8,
                max_alpha=int(95 + 85 * pulse),
                spread=int(10 + 5 * pulse),
            )
            frame = self.square_rect(*hover_capture).inflate(-3, -3)
            pygame.draw.rect(
                surface,
                theme.DANGER,
                frame,
                width=3 + int(round(2 * pulse)),
                border_radius=3,
            )

        if portals:
            for marker in portals:
                self._draw_portal(surface, marker)

        if pieces:
            for piece in pieces:
                rect = self.square_rect(*piece.square).inflate(-6, -6)
                piece_art.draw_piece(surface, piece.piece_type, piece.color, rect)

        if show_coordinates:
            self._draw_coordinates(surface)

    def _draw_board_base(self, surface: pygame.Surface) -> None:
        shadow = self.board_rect.move(5, 6)
        pygame.draw.rect(surface, theme.BOARD_SHADOW, shadow, border_radius=4)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.board_rect.inflate(6, 6), border_radius=4)

    def _draw_squares(self, surface: pygame.Surface) -> None:
        for rank in range(self.board_size):
            for file in range(self.board_size):
                rect = self.square_rect(file, rank)
                color = theme.LIGHT_SQUARE if (file + rank) % 2 == 1 else theme.DARK_SQUARE
                pygame.draw.rect(surface, color, rect)

    def _fill_square(
        self,
        surface: pygame.Surface,
        square: Square,
        color: tuple[int, int, int],
        alpha: int,
    ) -> None:
        rect = self.square_rect(*square)
        overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        overlay.fill(theme.with_alpha(color, alpha))
        surface.blit(overlay, rect.topleft)

    def _stroke_square(
        self,
        surface: pygame.Surface,
        square: Square,
        color: tuple[int, int, int],
        width: int,
    ) -> None:
        rect = self.square_rect(*square).inflate(-3, -3)
        pygame.draw.rect(surface, color, rect, width=width, border_radius=3)

    def _draw_legal_targets(
        self,
        surface: pygame.Surface,
        targets: dict[Square, str],
    ) -> None:
        radius = max(4, int(self.square_size * 0.16))
        for square, kind in targets.items():
            rect = self.square_rect(*square)
            center = rect.center
            if kind == "capture":
                pygame.draw.circle(
                    surface,
                    theme.ACCENT,
                    center,
                    max(radius + 4, int(self.square_size * 0.36)),
                    width=max(2, self.square_size // 24),
                )
            elif kind == "portal":
                pygame.draw.circle(
                    surface,
                    theme.PORTAL_COLORS[0],
                    center,
                    max(radius + 4, int(self.square_size * 0.36)),
                    width=max(2, self.square_size // 24),
                )
            else:
                pygame.draw.circle(surface, theme.ACCENT, center, radius)

    def _draw_portal(self, surface: pygame.Surface, marker: PortalMarker) -> None:
        rect = self.square_rect(*marker.square)
        color = theme.portal_color(marker.color_index)
        center = rect.center
        radius = max(8, int(self.square_size * 0.36))

        overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (0, 0, 0, 70), (rect.w // 2, rect.h // 2), radius)
        surface.blit(overlay, rect.topleft)

        pygame.draw.circle(surface, color, center, radius, width=max(2, self.square_size // 20))
        pygame.draw.circle(
            surface,
            color,
            center,
            max(3, radius // 2),
            width=max(1, self.square_size // 30),
        )
        label = marker.label or str(marker.color_index + 1)
        font_size = max(12, int(self.square_size * 0.30))
        theme.draw_text(
            surface,
            label,
            font_size,
            color,
            center,
            align="center",
            valign="middle",
            bold=True,
        )

    def _draw_coordinates(self, surface: pygame.Surface) -> None:
        font_size = max(12, min(22, self.square_size // 3))
        for file in range(self.board_size):
            rect = self.square_rect(file, 0)
            theme.draw_text(
                surface,
                chr(ord("a") + file),
                font_size,
                theme.TEXT_MUTED,
                (rect.centerx, self.board_rect.bottom + 4),
                align="center",
                valign="top",
            )
        for rank in range(self.board_size):
            rect = self.square_rect(0, rank)
            theme.draw_text(
                surface,
                str(rank + 1),
                font_size,
                theme.TEXT_MUTED,
                (self.board_rect.left - 6, rect.centery),
                align="right",
                valign="middle",
            )
