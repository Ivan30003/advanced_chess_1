"""Благословения короля: типы, метаданные и действия.

Модуль чистый: он не импортирует pygame и не зависит от состояния партии.
Типы фигур и цвета импортируются только для аннотаций, чтобы избежать
циклического импорта с :mod:`chess.core.pieces`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from chess.core.coords import Square

if TYPE_CHECKING:  # pragma: no cover - только для аннотаций
    from chess.core.pieces import Color, PieceType


class BlessingType(Enum):
    """Пять способностей, доступных королю."""

    INVULNERABILITY = "invulnerability"
    DOUBLE_MOVE = "double_move"
    RESURRECTION = "resurrection"
    FREEZE = "freeze"
    PASS_THROUGH = "pass_through"


@dataclass(frozen=True)
class BlessingInfo:
    """Отображаемые и механические свойства способности."""

    name: str
    short: str
    description: str
    icon: str
    active: bool
    one_time: bool = True


BLESSING_INFO: dict[BlessingType, BlessingInfo] = {
    BlessingType.INVULNERABILITY: BlessingInfo(
        name="Неуязвимость",
        short="Одно взятие будет отменено",
        description=(
            "Первое взятие фигуры отменяется: весь составной ход атакующего "
            "сбрасывается, а благословение снимается."
        ),
        icon="shield",
        active=False,
    ),
    BlessingType.DOUBLE_MOVE: BlessingInfo(
        name="Двойной ход",
        short="Два хода одной фигурой",
        description=(
            "Фигура делает два обычных хода за один ход. Можно взять две "
            "фигуры, но нельзя поставить мат."
        ),
        icon="double",
        active=True,
    ),
    BlessingType.RESURRECTION: BlessingInfo(
        name="Возрождение",
        short="Один раз после гибели",
        description=(
            "После гибели фигура возвращается на клетку, где стояла в начале "
            "партии, в начале следующего хода владельца, если клетка свободна."
        ),
        icon="resurrection",
        active=False,
    ),
    BlessingType.FREEZE: BlessingInfo(
        name="Заморозка",
        short="Стоп соседям на ход",
        description=(
            "Ортогонально соседние вражеские фигуры пропускают свой "
            "следующий ход. Они продолжают атаковать."
        ),
        icon="freeze",
        active=True,
    ),
    BlessingType.PASS_THROUGH: BlessingInfo(
        name="Проход сквозь фигуры",
        short="Один ход сквозь любые фигуры",
        description=(
            "Фигура один раз может пройти сквозь любые фигуры и взять "
            "только на конечной клетке."
        ),
        icon="ghost",
        active=True,
    ),
}


def blessing_info(blessing: BlessingType | None) -> BlessingInfo | None:
    return BLESSING_INFO.get(blessing) if blessing is not None else None


def is_active(blessing: BlessingType | None) -> bool:
    info = blessing_info(blessing)
    return bool(info and info.active)


@dataclass(frozen=True)
class BlessAction:
    """Благословение соседней фигуры вместо хода короля."""

    king_square: Square
    target_square: Square
    target_piece_id: str


@dataclass(frozen=True)
class FreezeAction:
    """Активация заморозки благословлённой фигурой."""

    source_square: Square
    source_piece_id: str
    targets: tuple[Square, ...]


@dataclass(frozen=True)
class PendingResurrection:
    """Отложенное возрождение погибшей благословлённой фигуры."""

    piece_id: str
    piece_type: "PieceType"
    color: "Color"
    original_square: Square
    turn_created: int
