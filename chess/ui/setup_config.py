"""Настройки партии, выбранные на экране подготовки."""

from __future__ import annotations

from dataclasses import dataclass

from chess.core.board_config import GameConfig
from chess.core.pieces import BlessingType

BOARD_SIZES = (6, 8, 10)
PORTAL_COUNTS = (0, 1, 2, 3)


@dataclass
class SetupConfig:
    """Параметры партии, которые затем попадают в :class:`GameConfig`."""

    board_size: int = 8
    portal_count: int = 0
    abilities_enabled: bool = False
    white_ability: BlessingType | None = None
    black_ability: BlessingType | None = None
    show_legal_hints: bool = True

    def normalized(self) -> "SetupConfig":
        """Приводит значения к допустимым, не отключая механики этапа 3."""

        config = self.copy()
        if config.board_size not in BOARD_SIZES:
            config.board_size = 8
        if config.portal_count not in PORTAL_COUNTS:
            config.portal_count = 0
        return config

    def to_game_config(self) -> GameConfig:
        """Создаёт чистое описание партии для игрового ядра."""

        config = self.normalized()
        return GameConfig.for_size(
            config.board_size,
            portal_count=config.portal_count,
            abilities_enabled=config.abilities_enabled,
        )

    def abilities_ready(self) -> bool:
        if not self.abilities_enabled:
            return True
        return self.white_ability is not None and self.black_ability is not None

    def validation_error(self) -> str | None:
        if self.board_size not in BOARD_SIZES:
            return "Недопустимый размер доски."
        if self.portal_count not in PORTAL_COUNTS:
            return "Недопустимое количество порталов."
        if self.abilities_enabled and self.white_ability is None:
            return "Белые должны выбрать способность короля."
        if self.abilities_enabled and self.black_ability is None:
            return "Чёрные должны выбрать способность короля."
        return None

    def copy(self) -> "SetupConfig":
        return SetupConfig(
            board_size=self.board_size,
            portal_count=self.portal_count,
            abilities_enabled=self.abilities_enabled,
            white_ability=self.white_ability,
            black_ability=self.black_ability,
            show_legal_hints=self.show_legal_hints,
        )

    @property
    def summary(self) -> str:
        """Короткое описание настроек для интерфейса."""

        size = f"{self.board_size}×{self.board_size}"
        abilities = "вкл" if self.abilities_enabled else "выкл"
        return f"доска {size} · порталы: {self.portal_count} · способности: {abilities}"
