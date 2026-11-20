"""Конфигурация доски и партии.

Модуль чистый: никаких импортов pygame. Все особенности размеров доски
(расстановка, рокировка, превращение, двойной ход пешки) собраны здесь,
чтобы ядро правил было общим для 6×6, 8×8 и 10×10.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from chess.core.coords import FILES, Square, squares_for_size
from chess.core.pieces import PieceType

_KNIGHT = PieceType.KNIGHT
_BISHOP = PieceType.BISHOP
_ROOK = PieceType.ROOK
_QUEEN = PieceType.QUEEN
_KING = PieceType.KING

_STANDARD_BACK_RANK = (_ROOK, _KNIGHT, _BISHOP, _QUEEN, _KING, _BISHOP, _KNIGHT, _ROOK)
_BOARD_6_BACK_RANK = (_ROOK, _KNIGHT, _BISHOP, _QUEEN, _KING, _ROOK)
_BOARD_10_BACK_RANK = (
    None,
    _ROOK,
    _KNIGHT,
    _BISHOP,
    _QUEEN,
    _KING,
    _BISHOP,
    _KNIGHT,
    _ROOK,
    None,
)


def _square(name: str) -> Square:
    return Square.from_name(name)


@dataclass(frozen=True)
class CastlingConfig:
    """Параметры рокировки для конкретного размера доски."""

    king_from: Square
    king_side_rook_from: Square
    queen_side_rook_from: Square
    king_side_king_to: Square
    queen_side_king_to: Square
    king_side_rook_to: Square
    queen_side_rook_to: Square
    king_side_empty: tuple[Square, ...]
    queen_side_empty: tuple[Square, ...]
    king_side_safe: tuple[Square, ...]
    queen_side_safe: tuple[Square, ...]


_STANDARD_CASTLING = CastlingConfig(
    king_from=_square("e1"),
    king_side_rook_from=_square("h1"),
    queen_side_rook_from=_square("a1"),
    king_side_king_to=_square("g1"),
    queen_side_king_to=_square("c1"),
    king_side_rook_to=_square("f1"),
    queen_side_rook_to=_square("d1"),
    king_side_empty=(_square("f1"), _square("g1")),
    queen_side_empty=(_square("b1"), _square("c1"), _square("d1")),
    king_side_safe=(_square("e1"), _square("f1"), _square("g1")),
    queen_side_safe=(_square("e1"), _square("d1"), _square("c1")),
)

_GENERALIZED_CASTLING = CastlingConfig(
    king_from=_square("f1"),
    king_side_rook_from=_square("i1"),
    queen_side_rook_from=_square("b1"),
    king_side_king_to=_square("h1"),
    queen_side_king_to=_square("d1"),
    king_side_rook_to=_square("g1"),
    queen_side_rook_to=_square("e1"),
    king_side_empty=(_square("g1"), _square("h1")),
    queen_side_empty=(_square("c1"), _square("d1"), _square("e1")),
    king_side_safe=(_square("f1"), _square("g1"), _square("h1")),
    queen_side_safe=(_square("f1"), _square("e1"), _square("d1")),
)


def _mirror(square: Square, size: int) -> Square:
    return Square(square.file, size - 1 - square.rank)


def _mirror_castling(config: CastlingConfig, size: int) -> CastlingConfig:
    return CastlingConfig(
        king_from=_mirror(config.king_from, size),
        king_side_rook_from=_mirror(config.king_side_rook_from, size),
        queen_side_rook_from=_mirror(config.queen_side_rook_from, size),
        king_side_king_to=_mirror(config.king_side_king_to, size),
        queen_side_king_to=_mirror(config.queen_side_king_to, size),
        king_side_rook_to=_mirror(config.king_side_rook_to, size),
        queen_side_rook_to=_mirror(config.queen_side_rook_to, size),
        king_side_empty=tuple(_mirror(square, size) for square in config.king_side_empty),
        queen_side_empty=tuple(_mirror(square, size) for square in config.queen_side_empty),
        king_side_safe=tuple(_mirror(square, size) for square in config.king_side_safe),
        queen_side_safe=tuple(_mirror(square, size) for square in config.queen_side_safe),
    )


@dataclass(frozen=True)
class BoardConfig:
    """Полное описание доски выбранного размера."""

    size: int
    back_rank: tuple[PieceType | None, ...]
    white_pawn_rank: int
    black_pawn_rank: int
    white_promotion_rank: int
    black_promotion_rank: int
    castling_white: CastlingConfig | None = None
    castling_black: CastlingConfig | None = None

    @property
    def files(self) -> str:
        return FILES[: self.size]

    @property
    def ranks(self) -> tuple[str, ...]:
        return tuple(str(index + 1) for index in range(self.size))

    def square(self, file: int, rank: int) -> Square:
        if not self.is_on_board(Square(file, rank)):
            raise ValueError(f"Клетка {file},{rank} вне доски {self.size}×{self.size}")
        return Square(file, rank)

    def is_on_board(self, square: Square) -> bool:
        return 0 <= square.file < self.size and 0 <= square.rank < self.size

    def squares(self) -> tuple[Square, ...]:
        return squares_for_size(self.size)

    def castling_for(self, color_is_white: bool) -> CastlingConfig | None:
        return self.castling_white if color_is_white else self.castling_black

    @property
    def has_castling(self) -> bool:
        return self.castling_white is not None

    @property
    def initial_castling_rights(self) -> frozenset[str]:
        if not self.has_castling:
            return frozenset()
        return frozenset({"K", "Q", "k", "q"})

    @classmethod
    @lru_cache(maxsize=3)
    def for_size(cls, size: int) -> "BoardConfig":
        if size == 6:
            return cls(
                size=6,
                back_rank=_BOARD_6_BACK_RANK,
                white_pawn_rank=1,
                black_pawn_rank=4,
                white_promotion_rank=5,
                black_promotion_rank=0,
            )
        if size == 8:
            return cls(
                size=8,
                back_rank=_STANDARD_BACK_RANK,
                white_pawn_rank=1,
                black_pawn_rank=6,
                white_promotion_rank=7,
                black_promotion_rank=0,
                castling_white=_STANDARD_CASTLING,
                castling_black=_mirror_castling(_STANDARD_CASTLING, 8),
            )
        if size == 10:
            return cls(
                size=10,
                back_rank=_BOARD_10_BACK_RANK,
                white_pawn_rank=1,
                black_pawn_rank=8,
                white_promotion_rank=9,
                black_promotion_rank=0,
                castling_white=_GENERALIZED_CASTLING,
                castling_black=_mirror_castling(_GENERALIZED_CASTLING, 10),
            )
        raise ValueError("Поддерживаются только доски 6×6, 8×8 и 10×10")


@dataclass(frozen=True)
class GameConfig:
    """Параметры партии: доска и настройки будущих механик."""

    board: BoardConfig
    portal_count: int = 0
    abilities_enabled: bool = False

    @property
    def size(self) -> int:
        return self.board.size

    @property
    def files(self) -> str:
        return self.board.files

    @property
    def ranks(self) -> tuple[str, ...]:
        return self.board.ranks

    @classmethod
    def for_size(
        cls,
        size: int,
        portal_count: int = 0,
        abilities_enabled: bool = False,
    ) -> "GameConfig":
        return cls(
            board=BoardConfig.for_size(size),
            portal_count=portal_count,
            abilities_enabled=abilities_enabled,
        )
