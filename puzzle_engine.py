from __future__ import annotations

import copy
import random
from typing import List, Optional, Tuple

GOAL_STATE: List[List[int]] = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 0],
]

MOVES: dict[str, Tuple[int, int]] = {
    "Up":    (-1,  0),
    "Down":  ( 1,  0),
    "Left":  ( 0, -1),
    "Right": ( 0,  1),
}


class PuzzleState:

    def __init__(
        self,
        board: List[List[int]],
        parent: Optional["PuzzleState"] = None,
        move: Optional[str] = None,
        depth: int = 0,
    ) -> None:
        self.board: List[List[int]] = board
        self.parent: Optional[PuzzleState] = parent
        self.move: Optional[str] = move
        self.depth: int = depth

    def find_blank(self) -> Tuple[int, int]:
        for r, row in enumerate(self.board):
            for c, val in enumerate(row):
                if val == 0:
                    return r, c
        raise ValueError("Board has no blank tile — invalid state.")

    def get_neighbors(self) -> List["PuzzleState"]:
        neighbors: List[PuzzleState] = []
        blank_r, blank_c = self.find_blank()

        for direction, (dr, dc) in MOVES.items():
            new_r, new_c = blank_r + dr, blank_c + dc

            if 0 <= new_r < 3 and 0 <= new_c < 3:
                new_board = copy.deepcopy(self.board)
                new_board[blank_r][blank_c], new_board[new_r][new_c] = (
                    new_board[new_r][new_c],
                    new_board[blank_r][blank_c],
                )
                neighbors.append(
                    PuzzleState(
                        board=new_board,
                        parent=self,
                        move=direction,
                        depth=self.depth + 1,
                    )
                )

        return neighbors

    def is_goal(self) -> bool:
        return self.board == GOAL_STATE

    def get_path(self) -> List["PuzzleState"]:
        path: List[PuzzleState] = []
        node: Optional[PuzzleState] = self
        while node is not None:
            path.append(node)
            node = node.parent
        path.reverse()
        return path

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PuzzleState):
            return NotImplemented
        return self.board == other.board

    def __hash__(self) -> int:
        return hash(tuple(cell for row in self.board for cell in row))

    def __lt__(self, other: "PuzzleState") -> bool:
        return self.depth < other.depth

    def __repr__(self) -> str:
        rows = [" ".join(str(v) for v in row) for row in self.board]
        return "\n".join(rows)


def is_solvable(board: List[List[int]]) -> bool:
    flat = [cell for row in board for cell in row if cell != 0]
    inversions = sum(
        1
        for i in range(len(flat))
        for j in range(i + 1, len(flat))
        if flat[i] > flat[j]
    )
    return inversions % 2 == 0


def shuffle(num_moves: int = 50) -> PuzzleState:
    state = PuzzleState(board=copy.deepcopy(GOAL_STATE))
    prev_move: Optional[str] = None

    opposites = {"Up": "Down", "Down": "Up", "Left": "Right", "Right": "Left"}

    for _ in range(num_moves):
        neighbors = state.get_neighbors()

        if prev_move is not None:
            forbidden = opposites[prev_move]
            neighbors = [n for n in neighbors if n.move != forbidden] or neighbors

        chosen = random.choice(neighbors)
        prev_move = chosen.move
        state = PuzzleState(board=chosen.board)

    return state
