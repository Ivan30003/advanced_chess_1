"""Хранение фигур на доске.

Доска отвечает только за расстановку и доступ к клеткам. Правила ходов
находятся в :mod:`chess.core.rules`, поэтому этот модуль не импортирует
pygame.
"""

from __future__ import annotations

from collections.abc import Iterator

from chess.core.board_config import BoardConfig
from chess.core.coords import Square
from chess.core.pieces import Color, Piece, PieceType


class Board:
    """Словарь клетка → фигура с удобными операциями."""

    def __init__(
        self,
        pieces: dict[Square, Piece] | None = None,
        config: BoardConfig | None = None,
    ) -> None:
        self.config = config or BoardConfig.for_size(8)
        self.pieces: dict[Square, Piece] = dict(pieces or {})

    # ------------------------------------------------------------------
    # Создание и клонирование
    # ------------------------------------------------------------------

    @classmethod
    def empty(cls, config: BoardConfig | int | None = None) -> "Board":
        return cls(config=_resolve_board_config(config))

    @classmethod
    def initial(cls, config: BoardConfig | int | None = None) -> "Board":
        """Начальная расстановка выбранного размера."""

        board_config = _resolve_board_config(config)
        board = cls(config=board_config)
        size = board_config.size
        for file, piece_type in enumerate(board_config.back_rank):
            if piece_type is None:
                continue
            board._place(piece_type, Color.WHITE, Square(file, 0))
            board._place(piece_type, Color.BLACK, Square(file, size - 1))
        for file in range(size):
            board._place(
                PieceType.PAWN,
                Color.WHITE,
                Square(file, board_config.white_pawn_rank),
            )
            board._place(
                PieceType.PAWN,
                Color.BLACK,
                Square(file, board_config.black_pawn_rank),
            )
        return board

    def _place(
        self,
        piece_type: PieceType,
        color: Color,
        square: Square,
    ) -> None:
        prefix = "w" if color is Color.WHITE else "b"
        piece = Piece(
            id=f"{prefix}{piece_type.letter}-{square.name}",
            type=piece_type,
            color=color,
            square=square,
            original_square=square,
        )
        self.pieces[square] = piece

    def copy(self) -> "Board":
        """Быстрая копия: фигуры неизменяемые, достаточно скопировать словарь."""

        copy = Board.__new__(Board)
        copy.config = self.config
        copy.pieces = dict(self.pieces)
        return copy

    # ------------------------------------------------------------------
    # Доступ к клеткам
    # ------------------------------------------------------------------

    def piece_at(self, square: Square) -> Piece | None:
        return self.pieces.get(square)

    def is_empty(self, square: Square) -> bool:
        return square not in self.pieces

    def is_on_board(self, square: Square) -> bool:
        return self.config.is_on_board(square)

    def add_piece(self, piece: Piece) -> None:
        self.pieces[piece.square] = piece

    def remove_piece(self, square: Square) -> Piece | None:
        return self.pieces.pop(square, None)

    def move_piece(self, from_square: Square, to_square: Square) -> Piece:
        """Переносит фигуру и помечает её как двигавшуюся."""

        piece = self.pieces.pop(from_square)
        moved = piece.moved_to(to_square)
        self.pieces[to_square] = moved
        return moved

    def replace_piece(self, piece: Piece) -> None:
        """Кладёт (заменяет) фигуру на её клетке."""

        self.pieces[piece.square] = piece

    # ------------------------------------------------------------------
    # Обход и поиск
    # ------------------------------------------------------------------

    def iter_pieces(self, color: Color | None = None) -> Iterator[Piece]:
        if color is None:
            return iter(tuple(self.pieces.values()))
        return (piece for piece in tuple(self.pieces.values()) if piece.color is color)

    def pieces_of(self, color: Color) -> list[Piece]:
        return [piece for piece in self.pieces.values() if piece.color is color]

    def king_square(self, color: Color) -> Square | None:
        for piece in self.pieces.values():
            if piece.color is color and piece.type is PieceType.KING:
                return piece.square
        return None

    def find_piece(self, piece_id: str) -> Piece | None:
        for piece in self.pieces.values():
            if piece.id == piece_id:
                return piece
        return None

    def __contains__(self, square: Square) -> bool:
        return square in self.pieces

    def __len__(self) -> int:
        return len(self.pieces)

    def squares(self) -> tuple[Square, ...]:
        return self.config.squares()


def _resolve_board_config(config: BoardConfig | int | None) -> BoardConfig:
    if config is None:
        return BoardConfig.for_size(8)
    if isinstance(config, int):
        return BoardConfig.for_size(config)
    return config
