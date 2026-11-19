"""Настройки партии, выбранные на экране подготовки."""

from __future__ import annotations

from dataclasses import dataclass

from chess.core.pieces import BlessingType

BOARD_SIZES = (6, 8, 10)
PORTAL_COUNTS = (0, 1, 2, 3)


@dataclass
class SetupConfig:
    board_size: int = 8
    portal_count: int = 0
    abilities_enabled: bool = False
    white_ability: BlessingType | None = None
    black_ability: BlessingType | None = None

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
        )
