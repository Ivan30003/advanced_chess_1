"""Приложение и менеджер сцен."""

from __future__ import annotations

import pygame

from chess.ui import theme
from chess.ui.setup_config import SetupConfig


class Scene:
    """Базовый интерфейс сцены."""

    def __init__(self, app: "App") -> None:
        self.app = app

    def handle_event(self, event: pygame.event.Event) -> None:
        del event

    def update(self, dt: float) -> None:
        del dt

    def draw(self, surface: pygame.Surface) -> None:
        del surface


class App:
    def __init__(self, size: tuple[int, int] = theme.WINDOW_DEFAULT_SIZE) -> None:
        pygame.init()
        pygame.display.set_caption("Advanced Chess — продвинутые шахматы")
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.last_setup_config: SetupConfig | None = None
        self._rules_return_scene: Scene | None = None
        self.current_scene: Scene | None = None
        self.show_menu()

    # ------------------------------------------------------------------
    # Переходы между сценами
    # ------------------------------------------------------------------

    def set_scene(self, scene: Scene) -> None:
        self.current_scene = scene

    def show_menu(self) -> None:
        from chess.ui.scenes.menu import MenuScene

        self.set_scene(MenuScene(self))

    def show_setup(self, config: SetupConfig | None = None) -> None:
        from chess.ui.scenes.setup import SetupScene

        if config is not None:
            self.last_setup_config = config.copy()
        elif self.last_setup_config is not None:
            config = self.last_setup_config.copy()
        else:
            config = SetupConfig()
        self.set_scene(SetupScene(self, config))

    def show_game(self, config: SetupConfig) -> None:
        from chess.ui.scenes.game import GameScene

        self.last_setup_config = config.copy()
        self.set_scene(GameScene(self, config.copy()))

    def show_rules(self) -> None:
        from chess.ui.scenes.rules import RulesScene

        if self.current_scene is not None:
            self._rules_return_scene = self.current_scene
        self.set_scene(RulesScene(self))

    def back_from_rules(self) -> None:
        if self._rules_return_scene is not None:
            self.set_scene(self._rules_return_scene)
            self._rules_return_scene = None
        else:
            self.show_menu()

    def quit(self) -> None:
        self.running = False

    # ------------------------------------------------------------------
    # Главный цикл
    # ------------------------------------------------------------------

    def _resize(self, width: int, height: int) -> None:
        width = max(theme.WINDOW_MIN_SIZE[0], int(width))
        height = max(theme.WINDOW_MIN_SIZE[1], int(height))
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(theme.FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                if event.type == pygame.VIDEORESIZE:
                    self._resize(event.w, event.h)
                if self.current_scene is not None:
                    self.current_scene.handle_event(event)
            if not self.running:
                break
            if self.current_scene is not None:
                self.current_scene.update(dt)
                self.current_scene.draw(self.screen)
            pygame.display.flip()
        pygame.quit()
