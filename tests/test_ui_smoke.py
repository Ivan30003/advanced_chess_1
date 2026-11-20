"""Дымовые и интерактивные тесты интерфейса.

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

from chess.core.board import Board
from chess.core.board_config import BoardConfig, GameConfig
from chess.core.coords import Square
from chess.core.game_state import GameState
from chess.core.pieces import BlessingType, Color, Piece, PieceType
from chess.core.rules import generate_legal_moves
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


def _find_move(state: GameState, from_name: str, to_name: str):
    for move in generate_legal_moves(state):
        if move.from_square.name == from_name and move.to_square.name == to_name:
            return move
    raise AssertionError(f"Ход {from_name}-{to_name} не найден")


def _play_scene(scene: GameScene, from_name: str, to_name: str) -> None:
    scene._execute(_find_move(scene.state, from_name, to_name))


def _promotion_state(size: int = 8) -> GameState:
    board = Board.empty(BoardConfig.for_size(size))
    for piece in (
        Piece(
            "wK-e1",
            PieceType.KING,
            Color.WHITE,
            Square.from_name("e1"),
            Square.from_name("e1"),
        ),
        Piece(
            "bK-e8",
            PieceType.KING,
            Color.BLACK,
            Square.from_name(f"e{size}"),
            Square.from_name(f"e{size}"),
        ),
        Piece(
            "wP-a7",
            PieceType.PAWN,
            Color.WHITE,
            Square.from_name(f"a{size - 1}"),
            Square.from_name(f"a{size - 1}"),
        ),
    ):
        board.add_piece(piece)
    return GameState(
        board=board,
        config=GameConfig.for_size(size),
        side_to_move=Color.WHITE,
    )


# ---------------------------------------------------------------------------
# Отрисовка и базовые сцены
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Настройка партии в рамках этапа 2
# ---------------------------------------------------------------------------


def test_setup_validation() -> None:
    config = SetupConfig()
    assert config.abilities_ready()
    assert config.validation_error() is None
    assert config.show_legal_hints is True

    config.abilities_enabled = True
    assert not config.abilities_ready()
    assert config.validation_error() is not None

    config.white_ability = BlessingType.INVULNERABILITY
    assert not config.abilities_ready()
    config.black_ability = BlessingType.FREEZE
    assert config.abilities_ready()
    assert config.validation_error() is None

    normalized = SetupConfig(board_size=7, portal_count=9).normalized()
    assert normalized.board_size == 8
    assert normalized.portal_count == 0

    game_config = SetupConfig(
        board_size=10,
        portal_count=2,
        abilities_enabled=True,
    ).to_game_config()
    assert game_config.size == 10
    assert game_config.portal_count == 2
    assert game_config.abilities_enabled is True


def test_setup_allows_all_stage_three_options(app: App) -> None:
    config = SetupConfig(
        board_size=10,
        portal_count=2,
        abilities_enabled=True,
        white_ability=BlessingType.RESURRECTION,
        black_ability=BlessingType.FREEZE,
    )
    scene = SetupScene(app, config)
    assert scene.config.board_size == 10
    assert scene.config.portal_count == 2
    assert scene.config.abilities_enabled
    assert scene.start_button.enabled
    assert scene.abilities_toggle.enabled
    assert scene.board_radio.disabled == set()
    assert scene.portal_radio.disabled == set()
    assert all(card.enabled for cards in scene.cards.values() for card in cards)
    surface = pygame.Surface(theme.WINDOW_DEFAULT_SIZE)
    scene.draw(surface)


def test_setup_board_size_and_preview(app: App) -> None:
    scene = SetupScene(app, SetupConfig(board_size=8))
    assert scene._preview.board_size == 8

    scene._on_board_size(0)
    assert scene.config.board_size == 6
    assert scene._preview.board_size == 6
    scene._on_board_size(2)
    assert scene.config.board_size == 10
    assert scene._preview.board_size == 10
    scene._on_board_size(1)
    assert scene.config.board_size == 8
    assert scene._preview.board_size == 8

    scene._on_portal_count(2)
    assert scene.config.portal_count == 2

    scene._on_hints_toggle(False)
    assert scene.config.show_legal_hints is False
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
    assert not app.current_scene.config.abilities_enabled
    assert app.current_scene.state.config.size == 10
    assert len(app.current_scene.state.board) == 36
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

    # Способности включаются, но до выбора обеих сторон старт недоступен.
    toggle = setup.abilities_toggle
    _click(setup, (toggle.rect.right - 28, toggle.rect.centery))
    assert setup.config.abilities_enabled
    assert not setup.start_button.enabled
    setup._select_ability(Color.WHITE, BlessingType.FREEZE)
    setup._select_ability(Color.BLACK, BlessingType.PASS_THROUGH)
    assert setup.start_button.enabled

    hints = setup.hints_toggle
    _click(setup, (hints.rect.right - 28, hints.rect.centery))
    assert setup.config.show_legal_hints is False

    _click(setup, setup.start_button.rect.center)
    assert isinstance(app.current_scene, GameScene)
    assert app.current_scene.config.board_size == 10
    assert app.current_scene.config.portal_count == 2
    assert app.current_scene.config.abilities_enabled
    assert app.current_scene.config.show_legal_hints is False
    assert app.current_scene.state.config.size == 10
    assert app.current_scene.state.config.portal_count == 2
    assert app.current_scene.state.config.abilities_enabled


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


def test_board_view_scales_for_all_sizes() -> None:
    for size in (6, 8, 10):
        view = BoardView(size)
        view.set_rect(pygame.Rect(0, 0, 800, 800))
        assert view.square_size <= BoardView.MAX_SQUARE_SIZE
        assert view.square_at(view.square_rect(0, 0).center) == (0, 0)
        assert view.square_at(view.square_rect(size - 1, size - 1).center) == (
            size - 1,
            size - 1,
        )

    large_board = BoardView(10)
    large_board.set_rect(pygame.Rect(0, 0, 800, 800))
    # На 10×10 клетка должна использовать доступное место, а не быть крошечной.
    assert large_board.square_size >= 60
    assert large_board.square_size == 800 // 11


# ---------------------------------------------------------------------------
# Игровой экран
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("size", "piece_count"), [(6, 24), (8, 32), (10, 36)])
def test_game_scene_renders_each_size(
    app: App,
    size: int,
    piece_count: int,
) -> None:
    scene = GameScene(app, SetupConfig(board_size=size))
    scene._layout()
    assert scene.board_view.board_size == size
    assert scene.game_config.size == size
    assert scene.state.config.size == size
    assert len(scene.state.board) == piece_count
    surface = pygame.Surface(app.screen.get_size())
    scene.update(0.016)
    scene.draw(surface)


def test_game_click_move_on_6x6(app: App) -> None:
    scene = GameScene(app, SetupConfig(board_size=6))
    scene._layout()
    _click(scene, scene.board_view.square_center(4, 1))  # e2
    assert scene.selected == Square.from_name("e2")
    assert Square.from_name("e4") in scene.legal_by_target
    _click(scene, scene.board_view.square_center(4, 3))  # e4
    assert scene.state.history == ["e2-e4"]
    assert scene.state.board.piece_at(Square.from_name("e4")).type is PieceType.PAWN
    assert scene.state.side_to_move is Color.BLACK


def test_game_click_move_on_10x10(app: App) -> None:
    scene = GameScene(app, SetupConfig(board_size=10))
    scene._layout()
    _click(scene, scene.board_view.square_center(5, 1))  # f2
    assert scene.selected == Square.from_name("f2")
    assert Square.from_name("f4") in scene.legal_by_target
    _click(scene, scene.board_view.square_center(5, 3))  # f4
    assert scene.state.history == ["f2-f4"]
    assert scene.state.board.piece_at(Square.from_name("f4")).type is PieceType.PAWN
    assert scene.state.side_to_move is Color.BLACK


def test_game_draw_result_overlay_draws(app: App) -> None:
    scene = GameScene(app, SetupConfig())
    scene.state = scene.state.agree_draw()
    assert scene.state.result is not None
    assert scene.state.result.title == "Ничья по соглашению"
    surface = pygame.Surface(app.screen.get_size())
    scene.draw(surface)
    _click(scene, scene.board_view.square_center(4, 1))
    assert scene.selected is None


def test_game_click_select_and_move(app: App) -> None:
    scene = GameScene(app, SetupConfig())
    scene._layout()
    surface = pygame.Surface(app.screen.get_size())
    scene.draw(surface)

    _click(scene, scene.board_view.square_center(4, 1))  # e2
    assert scene.selected == Square.from_name("e2")
    assert Square.from_name("e4") in scene.legal_by_target
    assert Square.from_name("e3") in scene.legal_by_target

    _click(scene, scene.board_view.square_center(4, 3))  # e4
    assert scene.state.history == ["e2-e4"]
    assert scene.state.board.piece_at(Square.from_name("e4")).type is PieceType.PAWN
    assert scene.state.side_to_move is Color.BLACK
    assert scene.selected is None


def test_game_click_own_piece_switches_selection(app: App) -> None:
    scene = GameScene(app, SetupConfig())
    scene._layout()
    _click(scene, scene.board_view.square_center(4, 1))  # e2
    assert scene.selected == Square.from_name("e2")
    _click(scene, scene.board_view.square_center(3, 1))  # d2
    assert scene.selected == Square.from_name("d2")
    assert scene.state.history == []


def test_game_hover_legal_capture_pulses(app: App, monkeypatch: pytest.MonkeyPatch) -> None:
    scene = GameScene(app, SetupConfig())
    scene._layout()
    _play_scene(scene, "e2", "e4")
    _play_scene(scene, "d7", "d5")

    _click(scene, scene.board_view.square_center(4, 3))  # e4
    assert scene.selected == Square.from_name("e4")
    assert Square.from_name("d5") in scene.legal_by_target

    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: scene.board_view.square_center(3, 4))
    scene.update(0.016)
    assert scene.hover_capture == (3, 4)

    # Ладья на a8 не является легальной целью взятия — свечения нет.
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: scene.board_view.square_center(0, 7))
    scene.update(0.016)
    assert scene.hover_capture is None


def test_game_promotion_modal_requires_choice(app: App) -> None:
    scene = GameScene(app, SetupConfig())
    scene.state = _promotion_state()
    scene._layout()
    surface = pygame.Surface(app.screen.get_size())
    scene.draw(surface)

    _click(scene, scene.board_view.square_center(0, 6))  # a7
    _click(scene, scene.board_view.square_center(0, 7))  # a8
    assert scene.pending_promotion is not None
    assert len(scene.pending_promotion) == 4
    scene.draw(surface)

    # Esc не отменяет превращение.
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert scene.pending_promotion is not None

    _click(scene, scene.promotion_rects[PieceType.QUEEN].center)
    assert scene.pending_promotion is None
    assert scene.state.board.piece_at(Square.from_name("a8")).type is PieceType.QUEEN
    assert scene.state.history == ["a7-a8=Q"]


@pytest.mark.parametrize("size", [6, 10])
def test_game_promotion_modal_on_6_and_10(app: App, size: int) -> None:
    scene = GameScene(app, SetupConfig(board_size=size))
    scene.state = _promotion_state(size)
    scene._layout()
    surface = pygame.Surface(app.screen.get_size())
    scene.draw(surface)

    _click(scene, scene.board_view.square_center(0, size - 2))
    _click(scene, scene.board_view.square_center(0, size - 1))
    assert scene.pending_promotion is not None
    assert len(scene.pending_promotion) == 4
    scene.draw(surface)

    _click(scene, scene.promotion_rects[PieceType.ROOK].center)
    target = Square.from_name(f"a{size}")
    assert scene.pending_promotion is None
    assert scene.state.board.piece_at(target).type is PieceType.ROOK
    assert scene.state.history == [f"a{size - 1}-a{size}=R"]


def test_game_hover_capture_on_6x6(
    app: App,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = GameScene(app, SetupConfig(board_size=6))
    scene._layout()
    _play_scene(scene, "e2", "e4")
    _play_scene(scene, "a5", "a4")

    _click(scene, scene.board_view.square_center(4, 3))  # e4
    assert Square.from_name("d5") in scene.legal_by_target
    monkeypatch.setattr(
        pygame.mouse,
        "get_pos",
        lambda: scene.board_view.square_center(3, 4),
    )
    scene.update(0.016)
    assert scene.hover_capture == (3, 4)


def test_game_result_overlay_blocks_board_and_new_game_works(app: App) -> None:
    scene = GameScene(app, SetupConfig())
    scene._layout()
    for from_name, to_name in (
        ("f2", "f3"),
        ("e7", "e5"),
        ("g2", "g4"),
        ("d8", "h4"),
    ):
        _play_scene(scene, from_name, to_name)

    assert scene.state.result is not None
    assert scene.state.result.kind == "checkmate"
    assert scene.state.result.winner is Color.BLACK

    surface = pygame.Surface(app.screen.get_size())
    scene.draw(surface)

    history_before = list(scene.state.history)
    _click(scene, scene.board_view.square_center(4, 1))  # e2
    assert scene.state.history == history_before
    assert scene.selected is None

    _click(scene, scene.result_buttons["new"].rect.center)
    assert scene.state.result is None
    assert scene.state.history == []
    assert len(scene.state.board) == 32


def test_game_escape_cancels_selection(app: App) -> None:
    scene = GameScene(app, SetupConfig())
    scene._layout()
    _click(scene, scene.board_view.square_center(4, 1))
    assert scene.selected == Square.from_name("e2")
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert scene.selected is None


def test_game_layout_survives_minimum_window(app: App) -> None:
    app._resize(1024, 720)
    try:
        scene = GameScene(app, SetupConfig())
        scene._layout()
        assert scene.board_view.board_size == 8
        assert scene.journal_rect.h > 0
        assert scene.buttons["menu"].rect.bottom <= 720
        surface = pygame.Surface((1024, 720))
        _click(scene, scene.board_view.square_center(4, 1))
        scene.update(0.016)
        scene.draw(surface)
    finally:
        app._resize(*theme.WINDOW_DEFAULT_SIZE)


def test_core_has_no_pygame_imports() -> None:
    core_dir = Path(__file__).resolve().parents[1] / "chess" / "core"
    for path in core_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import pygame" not in text, f"pygame найден в {path}"
        assert "from pygame" not in text, f"pygame найден в {path}"
