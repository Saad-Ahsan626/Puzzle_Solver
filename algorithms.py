from __future__ import annotations
import heapq
import time
from collections import deque
from typing import List, Optional, Tuple

from puzzle_engine import PuzzleState, GOAL_STATE

SearchResult = Tuple[List[PuzzleState], int, int, float]

_GOAL_POS: dict[int, Tuple[int, int]] = {
    GOAL_STATE[r][c]: (r, c)
    for r in range(3)
    for c in range(3)
}


def manhattan_distance(state: PuzzleState) -> int:
    total = 0
    for r in range(3):
        for c in range(3):
            tile = state.board[r][c]
            if tile != 0:
                goal_r, goal_c = _GOAL_POS[tile]
                total += abs(r - goal_r) + abs(c - goal_c)
    return total


def bfs(initial: PuzzleState) -> SearchResult:
    start_time = time.perf_counter()
    frontier: deque[PuzzleState] = deque([initial])
    explored: set[PuzzleState] = set()
    explored.add(initial)
    nodes_explored = 0

    while frontier:
        node = frontier.popleft()
        nodes_explored += 1

        if node.is_goal():
            path = node.get_path()
            return path, nodes_explored, len(path) - 1, time.perf_counter() - start_time

        for child in node.get_neighbors():
            if child not in explored:
                explored.add(child)
                frontier.append(child)

    return [], nodes_explored, 0, time.perf_counter() - start_time


def dfs(initial: PuzzleState, depth_limit: Optional[int] = None) -> SearchResult:
    start_time = time.perf_counter()
    stack: List[PuzzleState] = [initial]
    explored: set[PuzzleState] = set()
    explored.add(initial)
    nodes_explored = 0

    while stack:
        node = stack.pop()
        nodes_explored += 1

        if node.is_goal():
            path = node.get_path()
            return path, nodes_explored, len(path) - 1, time.perf_counter() - start_time

        if depth_limit is not None and node.depth >= depth_limit:
            continue

        for child in node.get_neighbors():
            if child not in explored:
                explored.add(child)
                stack.append(child)

    return [], nodes_explored, 0, time.perf_counter() - start_time


def _dls_recursive(
    node: PuzzleState,
    limit: int,
    explored: set,
    counter: List[int],
) -> Optional[PuzzleState]:
    counter[0] += 1

    if node.is_goal():
        return node

    if limit == 0:
        return None

    explored.add(node)

    for child in node.get_neighbors():
        if child not in explored:
            result = _dls_recursive(child, limit - 1, explored, counter)
            if result is not None:
                return result

    explored.discard(node)
    return None


def ids(initial: PuzzleState, max_depth: int = 50) -> SearchResult:
    start_time = time.perf_counter()
    total_nodes = 0

    for depth in range(max_depth + 1):
        counter = [0]
        explored: set[PuzzleState] = set()
        result = _dls_recursive(initial, depth, explored, counter)
        total_nodes += counter[0]

        if result is not None:
            path = result.get_path()
            return (
                path,
                total_nodes,
                len(path) - 1,
                time.perf_counter() - start_time,
            )

    return [], total_nodes, 0, time.perf_counter() - start_time


def a_star(initial: PuzzleState) -> SearchResult:
    start_time = time.perf_counter()
    nodes_explored = 0

    h_initial = manhattan_distance(initial)
    counter = 0
    heap: List[Tuple[int, int, PuzzleState]] = []
    heapq.heappush(heap, (h_initial, counter, initial))

    best_g: dict[PuzzleState, int] = {initial: 0}

    while heap:
        f, _, node = heapq.heappop(heap)
        nodes_explored += 1

        if node.is_goal():
            path = node.get_path()
            return path, nodes_explored, len(path) - 1, time.perf_counter() - start_time

        g = node.depth

        if g > best_g.get(node, float("inf")):
            continue

        for child in node.get_neighbors():
            g_child = child.depth
            if g_child < best_g.get(child, float("inf")):
                best_g[child] = g_child
                f_child = g_child + manhattan_distance(child)
                counter += 1
                heapq.heappush(heap, (f_child, counter, child))

    return [], nodes_explored, 0, time.perf_counter() - start_time


def run_all_algorithms(initial: PuzzleState) -> dict:
    algorithms = {
        "BFS":   bfs,
        "DFS":   dfs,
        "IDS":   ids,
        "A*":    a_star,
    }
    results = {}
    for name, func in algorithms.items():
        path, nodes, cost, elapsed = func(initial)
        results[name] = {
            "path":          path,
            "nodes_explored": nodes,
            "path_cost":     cost,
            "time_taken":    elapsed,
        }
    return results


def format_comparison_table(results: dict) -> str:
    header = f"{'Algorithm':<12} {'Nodes Explored':>16} {'Path Cost':>12} {'Time (s)':>12}"
    sep = "-" * len(header)
    rows = [header, sep]
    for algo, data in results.items():
        solved = "✓" if data["path"] else "✗"
        rows.append(
            f"{algo + ' ' + solved:<12}"
            f" {data['nodes_explored']:>16}"
            f" {data['path_cost']:>12}"
            f" {data['time_taken']:>12.6f}"
        )
    rows.append(sep)
    return "\n".join(rows)
