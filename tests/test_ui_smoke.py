"""Дымовые тесты первого этапа.

Важно: переменные окружения выставляются до импорта pygame, чтобы тесты
работали без реального дисплея.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from chess.core.pieces import BlessingType, Color, PieceType
from chess.ui import piece_art, theme
from chess.ui.app import App
from chess.ui.board_view import BoardView
from chess.ui.scenes.game import GameScene
from chess.ui.scenes.menu import MenuScene
from chess.ui.scenes.rules import RulesScene
from chess.ui.scenes.setup import SetupScene
from chess.ui.setup_config import SetupConfig
from chess.ui.widgets import ConfirmDialog


@pytest.fixture(scope="module")
def app() -> App:
    application = App(theme.WINDOW_DEFAULT_SIZE)
    yield application
    pygame.quit()


def _click(scene, position: tuple[int, int]) -> None:
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position))
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=position))


def test_render_piece_all_types(app: App) -> None:
    del app
    for color in Color:
        for piece_type in PieceType:
            image = piece_art.render_piece(piece_type, color, 64)
            assert isinstance(image, pygame.Surface)
            assert image.get_size() == (64, 64)
            assert image.get_bounding_rect().w > 0
            assert image.get_bounding_rect().h > 0


def test_render_gallery_and_icons(app: App) -> None:
    del app
    gallery = piece_art.render_gallery(48, 10)
    assert isinstance(gallery, pygame.Surface)
    assert gallery.get_bounding_rect().w > 0
    for blessing in BlessingType:
        icon = piece_art.render_blessing_icon(blessing, 40)
        assert isinstance(icon, pygame.Surface)
        assert icon.get_bounding_rect().w > 0


def test_scenes_draw_without_errors(app: App) -> None:
    config = SetupConfig()
    scenes = [
        MenuScene(app),
        SetupScene(app, config),
        GameScene(app, config),
        RulesScene(app),
    ]
    surface = pygame.Surface(app.screen.get_size())
    for scene in scenes:
        scene.update(0.016)
        scene.draw(surface)
        assert surface.get_size() == app.screen.get_size()


def test_setup_validation() -> None:
    config = SetupConfig()
    assert config.abilities_ready()
    assert config.validation_error() is None

    config.abilities_enabled = True
    assert not config.abilities_ready()
    assert config.validation_error() is not None

    config.white_ability = BlessingType.INVULNERABILITY
    assert not config.abilities_ready()
    config.black_ability = BlessingType.FREEZE
    assert config.abilities_ready()
    assert config.validation_error() is None


def test_setup_start_button_state(app: App) -> None:
    config = SetupConfig(abilities_enabled=True)
    scene = SetupScene(app, config)
    assert not scene.start_button.enabled

    scene._select_ability(Color.WHITE, BlessingType.DOUBLE_MOVE)
    assert not scene.start_button.enabled
    scene._select_ability(Color.BLACK, BlessingType.RESURRECTION)
    assert scene.start_button.enabled

    scene._on_abilities_toggle(False)
    assert scene.start_button.enabled
    assert all(not card.enabled for cards in scene.cards.values() for card in cards)


def test_setup_board_size_and_preview(app: App) -> None:
    scene = SetupScene(app, SetupConfig(board_size=8))
    assert scene._preview.board_size == 8
    scene._on_board_size(0)
    assert scene.config.board_size == 6
    assert scene._preview.board_size == 6
    scene._on_board_size(2)
    assert scene.config.board_size == 10
    assert scene._preview.board_size == 10
    surface = pygame.Surface(theme.WINDOW_DEFAULT_SIZE)
    scene.draw(surface)


def test_navigation_between_scenes(app: App) -> None:
    app.show_menu()
    assert isinstance(app.current_scene, MenuScene)
    app.show_setup()
    assert isinstance(app.current_scene, SetupScene)
    config = SetupConfig(board_size=10, portal_count=2, abilities_enabled=False)
    app.show_game(config)
    assert isinstance(app.current_scene, GameScene)
    assert app.current_scene.config.board_size == 10
    assert app.current_scene.config.portal_count == 2
    app.show_rules()
    assert isinstance(app.current_scene, RulesScene)
    app.back_from_rules()
    assert isinstance(app.current_scene, GameScene)


def test_confirm_dialog_handles_click_before_first_draw(app: App) -> None:
    del app
    confirmed: list[bool] = []
    dialog = ConfirmDialog(
        "Выход",
        "Закрыть игру?",
        on_confirm=lambda: confirmed.append(True),
        confirm_text="Выйти",
        cancel_text="Остаться",
    )
    dialog.open()
    # Первое событие приходит до draw: раскладка должна быть уже доступна.
    dialog.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)))
    position = dialog.confirm_button.rect.center
    dialog.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position))
    dialog.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=position))
    assert confirmed == [True]
    assert not dialog.visible


def test_setup_layout_fits_minimum_window(app: App) -> None:
    app._resize(1024, 720)
    try:
        config = SetupConfig(
            board_size=10,
            portal_count=3,
            abilities_enabled=True,
            white_ability=BlessingType.INVULNERABILITY,
            black_ability=BlessingType.PASS_THROUGH,
        )
        scene = SetupScene(app, config)
        scene._layout()
        cards = [card for row in scene.cards.values() for card in row]
        assert cards
        assert all(card.rect.bottom <= scene.abilities_top + scene.abilities_h for card in cards)
        assert scene.abilities_top + scene.abilities_h < scene.start_button.rect.top
        assert scene.start_button.rect.bottom <= 720
        surface = pygame.Surface((1024, 720))
        scene.draw(surface)
    finally:
        app._resize(*theme.WINDOW_DEFAULT_SIZE)


def test_menu_click_flow_and_setup_controls(app: App) -> None:
    app._resize(*theme.WINDOW_DEFAULT_SIZE)
    app.show_menu()
    menu = app.current_scene
    assert isinstance(menu, MenuScene)
    menu._layout()
    _click(menu, menu.buttons["play"].rect.center)
    assert isinstance(app.current_scene, SetupScene)

    setup = app.current_scene
    setup._layout()
    _click(setup, setup.board_radio.item_rects[2].center)
    assert setup.config.board_size == 10
    assert setup._preview.board_size == 10

    _click(setup, setup.portal_radio.item_rects[2].center)
    assert setup.config.portal_count == 2

    toggle = setup.abilities_toggle
    _click(setup, (toggle.rect.right - 28, toggle.rect.centery))
    assert setup.config.abilities_enabled
    assert not setup.start_button.enabled

    _click(setup, setup.cards[Color.WHITE][1].rect.center)
    assert setup.config.white_ability is BlessingType.DOUBLE_MOVE
    assert not setup.start_button.enabled
    _click(setup, setup.cards[Color.BLACK][4].rect.center)
    assert setup.config.black_ability is BlessingType.PASS_THROUGH
    assert setup.start_button.enabled

    _click(setup, setup.start_button.rect.center)
    assert isinstance(app.current_scene, GameScene)
    assert app.current_scene.config.board_size == 10
    assert app.current_scene.config.portal_count == 2


def test_menu_escape_opens_quit_dialog(app: App) -> None:
    app.show_menu()
    menu = app.current_scene
    assert isinstance(menu, MenuScene)
    menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert menu.quit_dialog.visible


def test_board_square_mapping() -> None:
    view = BoardView(8)
    view.set_rect(pygame.Rect(0, 0, 400, 400))
    bottom_left = view.square_rect(0, 0)
    top_left = view.square_rect(0, 7)
    assert bottom_left.centery > top_left.centery
    assert view.square_at(bottom_left.center) == (0, 0)
    assert view.square_at(top_left.center) == (0, 7)
    assert view.square_at((0, 0)) is None


def test_core_has_no_pygame_imports() -> None:
    core_dir = Path(__file__).resolve().parents[1] / "chess" / "core"
    for path in core_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import pygame" not in text, f"pygame найден в {path}"
        assert "from pygame" not in text, f"pygame найден в {path}"
