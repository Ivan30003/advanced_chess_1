"""Переиспользуемые виджеты интерфейса."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pygame

from chess.core.pieces import BLESSING_INFO, BlessingType
from chess.ui import piece_art, theme
from chess.ui.theme import draw_panel

Callback = Callable[[], None]

_CARD_TITLES = {
    BlessingType.INVULNERABILITY: "Неуязвимость",
    BlessingType.DOUBLE_MOVE: "Двойной ход",
    BlessingType.RESURRECTION: "Возрождение",
    BlessingType.FREEZE: "Заморозка",
    BlessingType.PASS_THROUGH: "Сквозь фигуры",
}


class Widget:
    def __init__(self, rect: pygame.Rect | None = None) -> None:
        self.rect = pygame.Rect(rect or (0, 0, 0, 0))
        self.visible = True
        self.enabled = True

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def handle_event(self, event: pygame.event.Event) -> bool:
        return False

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surface: pygame.Surface) -> None:
        del surface


class Button(Widget):
    def __init__(
        self,
        text: str,
        callback: Callback | None = None,
        rect: pygame.Rect | None = None,
        *,
        enabled: bool = True,
        font_size: int = 22,
        accent: bool = False,
        tooltip: str | None = None,
    ) -> None:
        super().__init__(rect)
        self.text = text
        self.callback = callback
        self.enabled = enabled
        self.font_size = font_size
        self.accent = accent
        self.tooltip = tooltip
        self.hovered = False
        self.pressed = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.contains(event.pos)
            return False
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.contains(event.pos):
            self.pressed = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self.pressed
            self.pressed = False
            if was_pressed and self.contains(event.pos):
                if self.callback is not None:
                    self.callback()
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        if self.accent:
            if not self.enabled:
                bg = theme.BUTTON_DISABLED
            elif self.pressed:
                bg = theme.ACCENT_DARK
            elif self.hovered:
                bg = theme.ACCENT_HOVER
            else:
                bg = theme.ACCENT
            border = theme.ACCENT_DARK
            text_color = theme.TEXT_DARK if self.enabled else theme.BUTTON_TEXT_DISABLED
        else:
            if not self.enabled:
                bg = theme.BUTTON_DISABLED
            elif self.pressed:
                bg = theme.BUTTON_ACTIVE
            elif self.hovered:
                bg = theme.BUTTON_HOVER
            else:
                bg = theme.BUTTON_BG
            border = theme.BUTTON_BORDER
            text_color = theme.BUTTON_TEXT if self.enabled else theme.BUTTON_TEXT_DISABLED

        draw_panel(
            surface,
            self.rect,
            bg,
            radius=theme.RADIUS_SMALL,
            border=border,
            shadow=False,
        )
        theme.draw_text_in_rect(
            surface,
            self.text,
            self.rect,
            self.font_size,
            text_color,
            bold=True,
        )


class Toggle(Widget):
    def __init__(
        self,
        label: str,
        value: bool,
        callback: Callable[[bool], None] | None = None,
        rect: pygame.Rect | None = None,
        *,
        font_size: int = 20,
        tooltip: str | None = None,
    ) -> None:
        super().__init__(rect)
        self.label = label
        self.value = value
        self.callback = callback
        self.font_size = font_size
        self.tooltip = tooltip
        self.hovered = False

    def set_value(self, value: bool) -> None:
        self.value = value

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.contains(event.pos)
            return False
        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
            and self.enabled
            and self.contains(event.pos)
        ):
            self.value = not self.value
            if self.callback is not None:
                self.callback(self.value)
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        switch_w = 56
        switch_h = 28
        switch_rect = pygame.Rect(
            self.rect.right - switch_w,
            self.rect.centery - switch_h // 2,
            switch_w,
            switch_h,
        )
        text_color = theme.TEXT if self.enabled else theme.TEXT_DIM
        theme.draw_text(
            surface,
            self.label,
            self.font_size,
            text_color,
            (self.rect.left, self.rect.centery),
            align="left",
            valign="middle",
        )
        track_color = theme.ACCENT if self.value else (70, 70, 82)
        if not self.enabled:
            track_color = (58, 58, 66)
        pygame.draw.rect(
            surface,
            track_color,
            switch_rect,
            border_radius=switch_h // 2,
        )
        knob_x = switch_rect.right - switch_h // 2 - 2 if self.value else switch_rect.left + switch_h // 2 + 2
        knob_color = theme.TEXT if self.enabled else theme.TEXT_DIM
        pygame.draw.circle(surface, knob_color, (knob_x, switch_rect.centery), switch_h // 2 - 4)


class RadioGroup(Widget):
    def __init__(
        self,
        options: Sequence[str],
        selected: int = 0,
        callback: Callable[[int], None] | None = None,
        rect: pygame.Rect | None = None,
        *,
        horizontal: bool = True,
        font_size: int = 20,
        gap: int = 8,
        tooltips: Sequence[str] | None = None,
        disabled: Sequence[int] | None = None,
    ) -> None:
        super().__init__(rect)
        self.options = list(options)
        self.selected = max(0, min(selected, len(self.options) - 1)) if self.options else 0
        self.callback = callback
        self.horizontal = horizontal
        self.font_size = font_size
        self.gap = gap
        self.tooltips = list(tooltips) if tooltips else []
        self.disabled: set[int] = set(disabled or ())
        self.item_rects: list[pygame.Rect] = []
        self.hovered_index: int | None = None
        self._recalculate_items()

    def is_disabled(self, index: int) -> bool:
        return index in self.disabled or not self.enabled

    def set_rect(self, rect: pygame.Rect) -> None:
        super().set_rect(rect)
        self._recalculate_items()

    def _recalculate_items(self) -> None:
        self.item_rects = []
        count = len(self.options)
        if count == 0:
            return
        rect = self.rect
        if self.horizontal:
            width = (rect.w - self.gap * (count - 1)) // count
            for index in range(count):
                x = rect.left + index * (width + self.gap)
                self.item_rects.append(pygame.Rect(x, rect.top, width, rect.h))
        else:
            height = (rect.h - self.gap * (count - 1)) // count
            for index in range(count):
                y = rect.top + index * (height + self.gap)
                self.item_rects.append(pygame.Rect(rect.left, y, rect.w, height))

    def set_selected(self, index: int) -> None:
        if not self.options:
            return
        self.selected = max(0, min(index, len(self.options) - 1))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered_index = None
            for index, item in enumerate(self.item_rects):
                if index not in self.disabled and item.collidepoint(event.pos):
                    self.hovered_index = index
                    break
            return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.enabled:
            for index, item in enumerate(self.item_rects):
                if index in self.disabled:
                    continue
                if item.collidepoint(event.pos):
                    self.selected = index
                    if self.callback is not None:
                        self.callback(index)
                    return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        for index, item in enumerate(self.item_rects):
            active = index == self.selected
            hovered = index == self.hovered_index
            option_disabled = index in self.disabled
            if not self.enabled or option_disabled:
                bg = theme.BUTTON_DISABLED
                border = theme.BORDER_SOFT
                text_color = theme.TEXT_DIM
                if active:
                    border = theme.BORDER
            elif active:
                bg = theme.ACCENT
                border = theme.ACCENT_HOVER
                text_color = theme.TEXT_DARK
            elif hovered:
                bg = theme.BUTTON_HOVER
                border = theme.BORDER
                text_color = theme.TEXT
            else:
                bg = theme.BUTTON_BG
                border = theme.BORDER_SOFT
                text_color = theme.TEXT
            draw_panel(
                surface,
                item,
                bg,
                radius=theme.RADIUS_SMALL,
                border=border,
            )
            theme.draw_text_in_rect(
                surface,
                self.options[index],
                item,
                self.font_size,
                text_color,
                bold=active,
            )


class AbilityCard(Widget):
    def __init__(
        self,
        blessing: BlessingType,
        title: str | None = None,
        short_description: str | None = None,
        rect: pygame.Rect | None = None,
        *,
        selected: bool = False,
        enabled: bool = True,
        callback: Callable[[BlessingType], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self.blessing = blessing
        self.info = BLESSING_INFO[blessing]
        self.title = title or _CARD_TITLES[blessing]
        self.short_description = short_description or self.info.short
        self.selected = selected
        self.enabled = enabled
        self.callback = callback
        self.hovered = False
        self.tooltip = self.info.description

    def set_selected(self, selected: bool) -> None:
        self.selected = selected

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.contains(event.pos)
            return False
        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
            and self.enabled
            and self.contains(event.pos)
        ):
            if self.callback is not None:
                self.callback(self.blessing)
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        if not self.enabled:
            bg = (38, 38, 46)
            border = theme.BORDER_SOFT
            title_color = theme.TEXT_DIM
            desc_color = theme.TEXT_DIM
            icon_color = theme.TEXT_DIM
        elif self.selected:
            bg = (62, 55, 38)
            border = theme.ACCENT
            title_color = theme.TEXT
            desc_color = theme.TEXT_MUTED
            icon_color = theme.ACCENT
        elif self.hovered:
            bg = theme.PANEL_LIGHT
            border = theme.BORDER
            title_color = theme.TEXT
            desc_color = theme.TEXT_MUTED
            icon_color = theme.ACCENT
        else:
            bg = theme.PANEL
            border = theme.BORDER_SOFT
            title_color = theme.TEXT
            desc_color = theme.TEXT_MUTED
            icon_color = theme.ACCENT

        draw_panel(surface, self.rect, bg, radius=theme.RADIUS_SMALL, border=border)

        icon_size = max(24, min(36, self.rect.h - 30))
        icon_rect = pygame.Rect(
            self.rect.left + 9,
            self.rect.centery - icon_size // 2,
            icon_size,
            icon_size,
        )
        piece_art.draw_blessing_icon(surface, self.blessing, icon_rect, icon_color)

        text_left = icon_rect.right + 8
        # Оставляем место под индикатор выбора в правом верхнем углу.
        text_width = self.rect.right - text_left - (24 if self.selected else 8)
        title_size = max(11, min(14, self.rect.h // 6))
        title_font = theme.get_font(title_size, bold=True)
        while title_size > 10 and title_font.size(self.title)[0] > text_width:
            title_size -= 1
            title_font = theme.get_font(title_size, bold=True)
        title_lines = theme.wrap_text(self.title, title_font, text_width)
        title_y = self.rect.top + 8
        for line in title_lines[:2]:
            image = title_font.render(line, True, title_color)
            surface.blit(image, (text_left, title_y))
            title_y += title_font.get_linesize()
        desc_size = max(10, min(11, self.rect.h // 8))
        theme.draw_text(
            surface,
            self.short_description,
            desc_size,
            desc_color,
            (text_left, title_y + 1),
            max_width=text_width,
            line_spacing=2,
        )

        if self.selected:
            pygame.draw.circle(
                surface,
                theme.ACCENT,
                (self.rect.right - 14, self.rect.top + 14),
                7,
            )
            pygame.draw.circle(
                surface,
                theme.TEXT_DARK,
                (self.rect.right - 14, self.rect.top + 14),
                3,
            )


class Tooltip:
    """Простая подсказка, следующая за курсором."""

    def __init__(self) -> None:
        self.text: str | None = None
        self.pos = (0, 0)

    def set(self, text: str | None, pos: tuple[int, int]) -> None:
        self.text = text
        self.pos = pos

    def hide(self) -> None:
        self.text = None

    def draw(self, surface: pygame.Surface) -> None:
        if not self.text:
            return
        font = theme.get_font(15)
        max_width = min(340, max(180, surface.get_width() // 3))
        lines = theme.wrap_text(self.text, font, max_width)
        line_height = font.get_linesize()
        width = max((font.size(line)[0] for line in lines), default=0) + 20
        height = len(lines) * line_height + 14
        x, y = self.pos[0] + 18, self.pos[1] + 18
        x = max(8, min(x, surface.get_width() - width - 8))
        y = max(8, min(y, surface.get_height() - height - 8))
        rect = pygame.Rect(x, y, width, height)
        draw_panel(
            surface,
            rect,
            (24, 24, 30),
            radius=8,
            border=theme.BORDER,
            shadow=True,
        )
        text_y = rect.top + 7
        for line in lines:
            image = font.render(line, True, theme.TEXT)
            surface.blit(image, (rect.left + 10, text_y))
            text_y += line_height


class ConfirmDialog:
    def __init__(
        self,
        title: str,
        message: str,
        on_confirm: Callback | None = None,
        on_cancel: Callback | None = None,
        *,
        confirm_text: str = "Да",
        cancel_text: str = "Нет",
    ) -> None:
        self.title = title
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.visible = False
        self.confirm_button = Button(confirm_text, self._confirm, accent=True, font_size=20)
        self.cancel_button = Button(cancel_text, self._cancel, font_size=20)
        self.rect = pygame.Rect(0, 0, 520, 230)

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def _confirm(self) -> None:
        self.close()
        if self.on_confirm is not None:
            self.on_confirm()

    def _cancel(self) -> None:
        self.close()
        if self.on_cancel is not None:
            self.on_cancel()

    def layout(self, size: tuple[int, int]) -> None:
        width, height = size
        dialog_w = min(540, max(420, width - 120))
        dialog_h = 230
        self.rect = pygame.Rect(0, 0, dialog_w, dialog_h)
        self.rect.center = (width // 2, height // 2)
        button_w = 150
        button_h = 44
        gap = 16
        total = button_w * 2 + gap
        left = self.rect.centerx - total // 2
        y = self.rect.bottom - button_h - 20
        self.cancel_button.set_rect(pygame.Rect(left, y, button_w, button_h))
        self.confirm_button.set_rect(pygame.Rect(left + button_w + gap, y, button_w, button_h))

    def _layout(self, surface: pygame.Surface) -> None:
        self.layout(surface.get_size())

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        display = pygame.display.get_surface()
        self.layout(display.get_size() if display is not None else theme.WINDOW_DEFAULT_SIZE)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._cancel()
            return True
        self.cancel_button.handle_event(event)
        self.confirm_button.handle_event(event)
        return True

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        self._layout(surface)
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        surface.blit(overlay, (0, 0))
        draw_panel(
            surface,
            self.rect,
            theme.PANEL,
            radius=theme.RADIUS,
            border=theme.BORDER,
            shadow=True,
        )
        theme.draw_text(
            surface,
            self.title,
            24,
            theme.TEXT,
            (self.rect.centerx, self.rect.top + 24),
            align="center",
            bold=True,
        )
        theme.draw_text(
            surface,
            self.message,
            17,
            theme.TEXT_MUTED,
            (self.rect.left + 28, self.rect.top + 70),
            max_width=self.rect.w - 56,
            line_spacing=5,
        )
        self.cancel_button.draw(surface)
        self.confirm_button.draw(surface)


class ScrollableText(Widget):
    def __init__(
        self,
        rect: pygame.Rect | None = None,
        blocks: Sequence[tuple[str, str]] | None = None,
        *,
        body_size: int = 17,
        heading_size: int = 21,
        padding: int = 18,
    ) -> None:
        super().__init__(rect)
        self.blocks = list(blocks or [])
        self.body_size = body_size
        self.heading_size = heading_size
        self.padding = padding
        self.scroll = 0
        self._lines: list[tuple[str, pygame.font.Font, tuple[int, int, int], int]] = []
        self._content_height = 0
        self._dirty = True

    def set_blocks(self, blocks: Sequence[tuple[str, str]]) -> None:
        self.blocks = list(blocks)
        self._dirty = True
        self.scroll = 0

    def set_rect(self, rect: pygame.Rect) -> None:
        super().set_rect(rect)
        self._dirty = True

    def _rebuild(self) -> None:
        self._lines = []
        body_font = theme.get_font(self.body_size)
        heading_font = theme.get_font(self.heading_size, bold=True)
        text_width = max(60, self.rect.w - self.padding * 2 - 12)
        for heading, body in self.blocks:
            if heading:
                self._lines.append((heading, heading_font, theme.ACCENT, 10))
            for paragraph in body.splitlines():
                if not paragraph.strip():
                    self._lines.append(("", body_font, theme.TEXT, 6))
                    continue
                for line in theme.wrap_text(paragraph, body_font, text_width):
                    self._lines.append((line, body_font, theme.TEXT_MUTED, 2))
            self._lines.append(("", body_font, theme.TEXT, 10))
        self._content_height = sum(font.get_linesize() + gap for _, font, _, gap in self._lines)
        self._dirty = False

    def _max_scroll(self) -> int:
        if self._dirty:
            self._rebuild()
        return max(0, self._content_height - (self.rect.h - self.padding * 2))

    def _set_scroll(self, value: int) -> None:
        self.scroll = max(0, min(int(value), self._max_scroll()))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEWHEEL and self.contains(pygame.mouse.get_pos()):
            self._set_scroll(self.scroll - event.y * 48)
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                self._set_scroll(self.scroll + 40)
                return True
            if event.key == pygame.K_UP:
                self._set_scroll(self.scroll - 40)
                return True
            if event.key == pygame.K_PAGEDOWN:
                self._set_scroll(self.scroll + max(40, self.rect.h - 80))
                return True
            if event.key == pygame.K_PAGEUP:
                self._set_scroll(self.scroll - max(40, self.rect.h - 80))
                return True
            if event.key == pygame.K_HOME:
                self._set_scroll(0)
                return True
            if event.key == pygame.K_END:
                self._set_scroll(10**9)
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        if self._dirty:
            self._rebuild()
        draw_panel(
            surface,
            self.rect,
            theme.PANEL,
            radius=theme.RADIUS,
            border=theme.BORDER_SOFT,
        )
        clip = surface.get_clip()
        inner = self.rect.inflate(-self.padding * 2, -self.padding * 2)
        surface.set_clip(inner)

        cursor_y = inner.top - self.scroll
        for text, font, color, gap in self._lines:
            if cursor_y + font.get_linesize() >= inner.top and cursor_y <= inner.bottom:
                if text:
                    image = font.render(text, True, color)
                    surface.blit(image, (inner.left, cursor_y))
            cursor_y += font.get_linesize() + gap

        surface.set_clip(clip)

        max_scroll = self._max_scroll()
        if max_scroll > 0:
            track = pygame.Rect(self.rect.right - 10, self.rect.top + 8, 4, self.rect.h - 16)
            pygame.draw.rect(surface, theme.BUTTON_BG, track, border_radius=2)
            thumb_h = max(30, int(track.h * (self.rect.h / max(1, self._content_height))))
            thumb_y = track.top + int((track.h - thumb_h) * (self.scroll / max_scroll))
            pygame.draw.rect(
                surface,
                theme.ACCENT,
                pygame.Rect(track.left, thumb_y, track.w, thumb_h),
                border_radius=2,
            )
