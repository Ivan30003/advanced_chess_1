"""Хранение фигур на доске.

Доска отвечает только за расстановку и доступ к клеткам. Правила ходов
находятся в :mod:`chess.core.rules`, поэтому этот модуль не импортирует
pygame.
"""

from __future__ import annotations

from collections.abc import Iterator

from chess.core.coords import ALL_SQUARES, BOARD_SIZE, Square
from chess.core.pieces import Color, Piece, PieceType

_BACK_RANK = [
    PieceType.ROOK,
    PieceType.KNIGHT,
    PieceType.BISHOP,
    PieceType.QUEEN,
    PieceType.KING,
    PieceType.BISHOP,
    PieceType.KNIGHT,
    PieceType.ROOK,
]


class Board:
    """Словарь клетка → фигура с удобными операциями."""

    def __init__(self, pieces: dict[Square, Piece] | None = None) -> None:
        self.pieces: dict[Square, Piece] = dict(pieces or {})

    # ------------------------------------------------------------------
    # Создание и клонирование
    # ------------------------------------------------------------------

    @classmethod
    def empty(cls) -> "Board":
        return cls()

    @classmethod
    def initial(cls) -> "Board":
        """Стандартная начальная расстановка белых снизу."""

        board = cls()
        for file, piece_type in enumerate(_BACK_RANK):
            board._place(piece_type, Color.WHITE, Square(file, 0))
            board._place(piece_type, Color.BLACK, Square(file, 7))
        for file in range(BOARD_SIZE):
            board._place(PieceType.PAWN, Color.WHITE, Square(file, 1))
            board._place(PieceType.PAWN, Color.BLACK, Square(file, 6))
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
        copy.pieces = dict(self.pieces)
        return copy

    # ------------------------------------------------------------------
    # Доступ к клеткам
    # ------------------------------------------------------------------

    def piece_at(self, square: Square) -> Piece | None:
        return self.pieces.get(square)

    def is_empty(self, square: Square) -> bool:
        return square not in self.pieces

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
        return ALL_SQUARES
