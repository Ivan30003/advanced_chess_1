"""Экран настройки партии."""

from __future__ import annotations

import pygame

from chess.core.pieces import BLESSING_INFO, BlessingType, Color
from chess.ui import theme
from chess.ui.app import Scene
from chess.ui.board_view import BoardView
from chess.ui.setup_config import BOARD_SIZES, PORTAL_COUNTS, SetupConfig
from chess.ui.widgets import AbilityCard, Button, ConfirmDialog, RadioGroup, Toggle, Tooltip

_ABILITY_ORDER = [
    BlessingType.INVULNERABILITY,
    BlessingType.DOUBLE_MOVE,
    BlessingType.RESURRECTION,
    BlessingType.FREEZE,
    BlessingType.PASS_THROUGH,
]


class SetupScene(Scene):
    def __init__(self, app, config: SetupConfig | None = None) -> None:
        super().__init__(app)
        self.config = (config or SetupConfig()).normalized()
        self.tooltip = Tooltip()
        self._background: pygame.Surface | None = None
        self._background_size = (0, 0)
        self._last_size = (0, 0)

        board_index = BOARD_SIZES.index(self.config.board_size) if self.config.board_size in BOARD_SIZES else 1
        self.board_radio = RadioGroup(
            ["6×6", "8×8", "10×10"],
            selected=board_index,
            callback=self._on_board_size,
            horizontal=True,
            font_size=19,
        )
        self.portal_radio = RadioGroup(
            ["0", "1", "2", "3"],
            selected=self.config.portal_count,
            callback=self._on_portal_count,
            horizontal=True,
            font_size=19,
        )
        self.abilities_toggle = Toggle(
            "Способности короля (этап 5)",
            self.config.abilities_enabled,
            callback=self._on_abilities_toggle,
            font_size=20,
        )
        self.hints_toggle = Toggle(
            "Подсказки легальных ходов",
            self.config.show_legal_hints,
            callback=self._on_hints_toggle,
            font_size=20,
        )
        self.start_button = Button(
            "Начать партию",
            self._start_game,
            accent=True,
            font_size=22,
        )
        self.back_button = Button("Назад", self.app.show_menu, font_size=20)
        self.rules_button = Button("Правила", self.app.show_rules, font_size=20)
        self.quit_button = Button("Выход", self._ask_quit, font_size=18)
        self.quit_dialog = ConfirmDialog(
            "Выход",
            "Закрыть игру?",
            on_confirm=self.app.quit,
            confirm_text="Выйти",
            cancel_text="Остаться",
        )
        self.cards: dict[Color, list[AbilityCard]] = {
            Color.WHITE: [],
            Color.BLACK: [],
        }
        self._build_cards()
        self._preview = BoardView(self.config.board_size)
        self._sync_cards()
        self._update_start_state()
        self._layout()

    # ------------------------------------------------------------------
    # Построение и синхронизация
    # ------------------------------------------------------------------

    def _build_cards(self) -> None:
        for color in (Color.WHITE, Color.BLACK):
            self.cards[color] = [
                AbilityCard(
                    blessing,
                    selected=self._ability_for(color) is blessing,
                    enabled=self.config.abilities_enabled,
                    callback=lambda value, c=color: self._select_ability(c, value),
                )
                for blessing in _ABILITY_ORDER
            ]

    def _ability_for(self, color: Color) -> BlessingType | None:
        return self.config.white_ability if color is Color.WHITE else self.config.black_ability

    def _set_ability_for(self, color: Color, blessing: BlessingType | None) -> None:
        if color is Color.WHITE:
            self.config.white_ability = blessing
        else:
            self.config.black_ability = blessing

    def _select_ability(self, color: Color, blessing: BlessingType) -> None:
        if not self.config.abilities_enabled:
            return
        self._set_ability_for(color, blessing)
        self._sync_cards()
        self._update_start_state()

    def _sync_cards(self) -> None:
        for color, cards in self.cards.items():
            selected = self._ability_for(color)
            for card in cards:
                card.enabled = self.config.abilities_enabled
                card.set_selected(card.blessing is selected)
                if self.config.abilities_enabled:
                    card.tooltip = BLESSING_INFO[card.blessing].description
                else:
                    card.tooltip = "Способности короля выключены."

    def _update_start_state(self) -> None:
        self.start_button.enabled = self.config.abilities_ready()

    # ------------------------------------------------------------------
    # Обработчики настроек
    # ------------------------------------------------------------------

    def _on_board_size(self, index: int) -> None:
        if not 0 <= index < len(BOARD_SIZES):
            return
        self.config.board_size = BOARD_SIZES[index]
        self._preview.board_size = self.config.board_size
        self._layout()

    def _on_portal_count(self, index: int) -> None:
        if not 0 <= index < len(PORTAL_COUNTS):
            return
        self.config.portal_count = index

    def _on_abilities_toggle(self, value: bool) -> None:
        self.config.abilities_enabled = value
        self._sync_cards()
        self._update_start_state()

    def _on_hints_toggle(self, value: bool) -> None:
        self.config.show_legal_hints = value

    def _start_game(self) -> None:
        if self.config.abilities_ready() and self.config.validation_error() is None:
            self.app.show_game(self.config.normalized())

    def _ask_quit(self) -> None:
        self.quit_dialog.open()

    # ------------------------------------------------------------------
    # Компоновка
    # ------------------------------------------------------------------

    def _layout(self) -> None:
        width, height = self.app.screen.get_size()
        self._last_size = (width, height)
        margin = 28
        header_h = 66
        footer_h = 72
        abilities_h = 248
        main_top = header_h + 16
        main_h = max(220, height - main_top - abilities_h - footer_h - 16)
        left_w = min(430, max(330, int(width * 0.36)))
        self.margin = margin
        self.header_h = header_h
        self.main_top = main_top
        self.main_h = main_h
        self.left_w = left_w
        self.abilities_top = main_top + main_h + 10
        self.abilities_h = abilities_h

        control_y = main_top + 10
        self.board_label_pos = (margin, control_y)
        self.board_radio.set_rect(pygame.Rect(margin, control_y + 28, left_w, 44))
        self.portal_label_pos = (margin, control_y + 88)
        self.portal_radio.set_rect(pygame.Rect(margin, control_y + 116, left_w, 44))
        self.abilities_toggle.set_rect(pygame.Rect(margin, control_y + 180, left_w, 36))
        self.hints_toggle.set_rect(pygame.Rect(margin, control_y + 220, left_w, 36))
        self.info_pos = (margin, control_y + 262)

        preview_rect = pygame.Rect(
            margin + left_w + 24,
            main_top,
            width - (margin + left_w + 24) - margin,
            main_h,
        )
        self.preview_panel_rect = preview_rect
        board_rect = preview_rect.inflate(-20, -20)
        board_rect.top += 26
        board_rect.height -= 26
        self._preview.set_rect(board_rect)

        self.abilities_label_pos = (margin, self.abilities_top)
        self.cards_left = margin + 64
        self.cards_right = width - margin
        self.card_gap = 8
        card_w = max(
            100,
            (self.cards_right - self.cards_left - 4 * self.card_gap) // 5,
        )
        row_area = (abilities_h - 46 - 6) // 2
        card_h = min(86, row_area - 6)
        self.card_w = card_w
        self.card_h = card_h
        self.row1_top = self.abilities_top + 46
        self.row2_top = self.row1_top + row_area

        for row_color, row_top in (
            (Color.WHITE, self.row1_top),
            (Color.BLACK, self.row2_top),
        ):
            for index, card in enumerate(self.cards[row_color]):
                x = self.cards_left + index * (card_w + self.card_gap)
                y = row_top + (row_area - card_h) // 2
                card.set_rect(pygame.Rect(x, y, card_w, card_h))

        footer_y = height - footer_h + 8
        self.back_button.set_rect(pygame.Rect(margin, footer_y, 150, 48))
        self.rules_button.set_rect(pygame.Rect(margin + 160, footer_y, 140, 48))
        self.start_button.set_rect(pygame.Rect(width - margin - 270, footer_y, 270, 48))
        self.footer_message_pos = (margin + 316, footer_y + 24)
        self.quit_button.set_rect(pygame.Rect(width - margin - 118, 22, 118, 38))

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
    # События и отрисовка
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.app.screen.get_size() != self._last_size:
            self._layout()
        if self.quit_dialog.visible:
            self.quit_dialog.handle_event(event)
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.show_menu()
            return

        for widget in (
            self.back_button,
            self.rules_button,
            self.start_button,
            self.quit_button,
            self.abilities_toggle,
            self.hints_toggle,
            self.board_radio,
            self.portal_radio,
            *self.cards[Color.WHITE],
            *self.cards[Color.BLACK],
        ):
            if widget.handle_event(event):
                return

    def update(self, dt: float) -> None:
        del dt
        if self.app.screen.get_size() != self._last_size:
            self._layout()
        mouse = pygame.mouse.get_pos()
        self.tooltip.hide()
        if self.quit_dialog.visible:
            return
        if self.config.abilities_enabled:
            for cards in self.cards.values():
                for card in cards:
                    if card.enabled and card.rect.collidepoint(mouse):
                        self.tooltip.set(card.tooltip, mouse)
                        return
        if self.abilities_toggle.rect.collidepoint(mouse):
            self.tooltip.set(
                "Способности короля появятся на этапе 5. "
                "Выбранный параметр сохраняется в состоянии партии.",
                mouse,
            )
        elif self.hints_toggle.rect.collidepoint(mouse):
            self.tooltip.set(
                "Показывать точки и кольца на клетках, куда может пойти выбранная фигура.",
                mouse,
            )
        elif self.board_radio.rect.collidepoint(mouse):
            self.tooltip.set(
                "Доступны доски 6×6, 8×8 и 10×10.",
                mouse,
            )
        elif self.portal_radio.rect.collidepoint(mouse):
            self.tooltip.set(
                "Порталы появятся на этапе 4. Количество сохраняется в состоянии партии.",
                mouse,
            )

    def draw(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        if (width, height) != self._last_size:
            self._layout()
        surface.blit(self._ensure_background((width, height)), (0, 0))

        theme.draw_text(
            surface,
            "Настройка партии",
            32,
            theme.TEXT,
            (self.margin, 22),
            bold=True,
        )
        theme.draw_text(
            surface,
            "Доски 6×6, 8×8 и 10×10 · порталы и способности — на следующих этапах",
            16,
            theme.TEXT_MUTED,
            (self.margin, 58),
        )
        self.quit_button.draw(surface)

        self._draw_settings(surface)
        self._draw_preview(surface)
        self._draw_abilities(surface)
        self._draw_footer(surface)
        self.tooltip.draw(surface)
        self.quit_dialog.draw(surface)

    def _draw_settings(self, surface: pygame.Surface) -> None:
        theme.draw_text(
            surface,
            "Размер доски",
            18,
            theme.TEXT,
            self.board_label_pos,
            bold=True,
        )
        self.board_radio.draw(surface)

        theme.draw_text(
            surface,
            "Количество порталов",
            18,
            theme.TEXT,
            self.portal_label_pos,
            bold=True,
        )
        self.portal_radio.draw(surface)

        self.abilities_toggle.draw(surface)
        self.hints_toggle.draw(surface)
        theme.draw_text(
            surface,
            "Этап 3: доступны доски 6×6, 8×8 и 10×10 со всеми стандартными "
            "правилами и ничьими. Порталы (этап 4) и способности (этап 5) "
            "пока только сохраняются в настройках.",
            14,
            theme.TEXT_DIM,
            self.info_pos,
            max_width=self.left_w,
            line_spacing=4,
        )

    def _draw_preview(self, surface: pygame.Surface) -> None:
        theme.draw_panel(
            surface,
            self.preview_panel_rect,
            theme.PANEL_DARK,
            radius=theme.RADIUS,
            border=theme.BORDER_SOFT,
        )
        theme.draw_text(
            surface,
            f"Предпросмотр доски {self.config.board_size}×{self.config.board_size}",
            16,
            theme.TEXT_MUTED,
            (self.preview_panel_rect.left + 14, self.preview_panel_rect.top + 9),
            bold=True,
        )
        self._preview.draw(surface, show_coordinates=True)

    def _draw_abilities(self, surface: pygame.Surface) -> None:
        theme.draw_text(
            surface,
            "Способности короля",
            18,
            theme.TEXT,
            self.abilities_label_pos,
            bold=True,
        )
        if not self.config.abilities_enabled:
            theme.draw_text(
                surface,
                "Выключены. Механика способностей короля появится на этапе 5; "
                "выбранные параметры уже передаются в состояние партии.",
                14,
                theme.TEXT_DIM,
                (self.margin, self.abilities_top + 26),
                max_width=surface.get_width() - self.margin * 2,
            )
        else:
            theme.draw_text(
                surface,
                "Выберите по одной способности для белых и чёрных. Обе стороны могут выбрать одинаковую.",
                13,
                theme.TEXT_DIM,
                (self.margin, self.abilities_top + 24),
                max_width=surface.get_width() - self.margin * 2,
            )

        for color, label in ((Color.WHITE, "Белые"), (Color.BLACK, "Чёрные")):
            cards = self.cards[color]
            if not cards:
                continue
            label_rect = pygame.Rect(
                self.margin,
                cards[0].rect.top,
                56,
                cards[0].rect.h,
            )
            theme.draw_text(
                surface,
                label,
                15,
                theme.TEXT_MUTED,
                (label_rect.centerx, label_rect.centery),
                align="center",
                valign="middle",
                bold=True,
            )
            for card in cards:
                card.draw(surface)

    def _draw_footer(self, surface: pygame.Surface) -> None:
        self.back_button.draw(surface)
        self.rules_button.draw(surface)
        self.start_button.draw(surface)
        if not self.config.abilities_ready():
            theme.draw_text(
                surface,
                "Выберите способность для обеих сторон",
                13,
                theme.DANGER,
                self.footer_message_pos,
                valign="middle",
            )
        else:
            theme.draw_text(
                surface,
                f"Готово: {self.config.summary}",
                13,
                theme.TEXT_DIM,
                self.footer_message_pos,
                valign="middle",
            )
