from __future__ import annotations

import copy
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from PIL import Image, ImageTk, ImageDraw, ImageFont

from puzzle_engine import PuzzleState, GOAL_STATE, shuffle
from algorithms import (
    bfs, dfs, ids, a_star,
    run_all_algorithms,
    format_comparison_table,
)

TILE_SIZE   = 150
BOARD_PX    = TILE_SIZE * 3
BLANK_COLOR = "#000000"
FONT_FAMILY = "Helvetica"
ANIM_DELAY  = 350

ALGO_MAP = {
    "BFS  (Breadth-First Search)":           bfs,
    "DFS  (Depth-First Search)":             dfs,
    "IDS  (Iterative Deepening Search)":     ids,
    "A*   (A-Star / Manhattan Distance)":    a_star,
}

ALGO_KEYS = list(ALGO_MAP.keys())


def slice_image(image_path: str, tile_size: int = TILE_SIZE) -> Dict[int, ImageTk.PhotoImage]:
    board_size = tile_size * 3
    img = Image.open(image_path).convert("RGB")

    w, h = img.size
    min_dim = min(w, h)
    left   = (w - min_dim) // 2
    top    = (h - min_dim) // 2
    img    = img.crop((left, top, left + min_dim, top + min_dim))
    img    = img.resize((board_size, board_size), Image.LANCZOS)

    tiles: Dict[int, ImageTk.PhotoImage] = {}

    blank = Image.new("RGB", (tile_size, tile_size), BLANK_COLOR)
    tiles[0] = ImageTk.PhotoImage(blank)

    tile_num = 1
    for row in range(3):
        for col in range(3):
            if tile_num > 8:
                break
            x0, y0 = col * tile_size, row * tile_size
            piece = img.crop((x0, y0, x0 + tile_size, y0 + tile_size))
            tiles[tile_num] = ImageTk.PhotoImage(piece)
            tile_num += 1

    return tiles


def make_placeholder_tiles(tile_size: int = TILE_SIZE) -> Dict[int, ImageTk.PhotoImage]:
    colours = [
        "#1a1a2e", "#16213e", "#0f3460", "#533483",
        "#e94560", "#f5a623", "#7ed321", "#4a90e2", "#9b59b6",
    ]
    tiles: Dict[int, ImageTk.PhotoImage] = {}
    for i in range(9):
        colour = BLANK_COLOR if i == 0 else colours[i]
        img = Image.new("RGB", (tile_size, tile_size), colour)
        if i != 0:
            draw = ImageDraw.Draw(img)
            text  = str(i)
            bbox = draw.textbbox((0, 0), text, font=None)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                ((tile_size - tw) // 2, (tile_size - th) // 2),
                text,
                fill="white",
            )
        tiles[i] = ImageTk.PhotoImage(img)
    return tiles


class PuzzleGUI:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("8-Puzzle Image Solver — CSC-202L AI Lab")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        self.current_state: PuzzleState = PuzzleState(
            board=copy.deepcopy(GOAL_STATE)
        )
        self.tile_images: Dict[int, ImageTk.PhotoImage] = make_placeholder_tiles()
        self.solution_path: List[PuzzleState] = []
        self.anim_index: int = 0
        self.anim_job: Optional[str] = None
        self._solving: bool = False

        self._build_ui()
        self._draw_board(self.current_state)

    def _build_ui(self) -> None:
        title_frame = tk.Frame(self.root, bg="#0f3460", pady=8)
        title_frame.pack(fill="x")
        tk.Label(
            title_frame,
            text="🧩  8-Puzzle Image Solver",
            font=(FONT_FAMILY, 20, "bold"),
            fg="#f5a623",
            bg="#0f3460",
        ).pack()
        tk.Label(
            title_frame,
            text="CSC-202L — Artificial Intelligence Lab  |  UET Lahore",
            font=(FONT_FAMILY, 10),
            fg="#a0a0c0",
            bg="#0f3460",
        ).pack()

        mid_frame = tk.Frame(self.root, bg="#1a1a2e")
        mid_frame.pack(padx=10, pady=10)

        self._build_canvas(mid_frame)
        self._build_controls(mid_frame)

        self._build_table_panel()

    def _build_canvas(self, parent: tk.Frame) -> None:
        canvas_frame = tk.Frame(
            parent, bg="#16213e", relief="ridge", bd=3
        )
        canvas_frame.pack(side="left", padx=(0, 10))

        self.canvas = tk.Canvas(
            canvas_frame,
            width=BOARD_PX,
            height=BOARD_PX,
            bg="#16213e",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.step_label = tk.Label(
            canvas_frame,
            text="Step: — / —",
            font=(FONT_FAMILY, 11),
            fg="#a0a0c0",
            bg="#16213e",
        )
        self.step_label.pack(pady=4)

    def _build_controls(self, parent: tk.Frame) -> None:
        ctrl = tk.Frame(parent, bg="#1a1a2e", width=280)
        ctrl.pack(side="left", fill="y")
        ctrl.pack_propagate(False)

        self._section_label(ctrl, "📷  Image")
        tk.Button(
            ctrl,
            text="Upload Image",
            command=self._upload_image,
            **self._btn_style("#4a90e2"),
        ).pack(fill="x", padx=10, pady=4)

        self._section_label(ctrl, "🤖  Algorithm")
        self.algo_var = tk.StringVar(value=ALGO_KEYS[0])
        algo_menu = ttk.Combobox(
            ctrl,
            textvariable=self.algo_var,
            values=ALGO_KEYS,
            state="readonly",
            width=34,
        )
        algo_menu.pack(padx=10, pady=4)

        self._section_label(ctrl, "🎲  Board")
        tk.Button(
            ctrl,
            text="Shuffle Board",
            command=self._shuffle_board,
            **self._btn_style("#f5a623"),
        ).pack(fill="x", padx=10, pady=4)

        tk.Button(
            ctrl,
            text="Reset to Goal",
            command=self._reset_board,
            **self._btn_style("#7ed321"),
        ).pack(fill="x", padx=10, pady=4)

        self._section_label(ctrl, "🔍  Solve")
        tk.Button(
            ctrl,
            text="▶  Solve (Animate)",
            command=self._solve_and_animate,
            **self._btn_style("#e94560"),
        ).pack(fill="x", padx=10, pady=4)

        tk.Button(
            ctrl,
            text="⏭  Show Final Solution",
            command=self._show_final,
            **self._btn_style("#9b59b6"),
        ).pack(fill="x", padx=10, pady=4)

        tk.Button(
            ctrl,
            text="⏹  Stop Animation",
            command=self._stop_animation,
            **self._btn_style("#533483"),
        ).pack(fill="x", padx=10, pady=4)

        self._section_label(ctrl, "📊  Analysis")
        tk.Button(
            ctrl,
            text="Compare All Algorithms",
            command=self._compare_all,
            **self._btn_style("#16213e", fg="#f5a623"),
        ).pack(fill="x", padx=10, pady=4)

        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(
            ctrl,
            textvariable=self.status_var,
            font=(FONT_FAMILY, 10, "italic"),
            fg="#a0a0c0",
            bg="#1a1a2e",
            wraplength=260,
        ).pack(padx=10, pady=10)

    def _build_table_panel(self) -> None:
        frame = tk.Frame(self.root, bg="#0f3460", relief="ridge", bd=2)
        frame.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(
            frame,
            text="Algorithm Comparison Table",
            font=(FONT_FAMILY, 12, "bold"),
            fg="#f5a623",
            bg="#0f3460",
        ).pack(anchor="w", padx=8, pady=4)

        self.table_text = tk.Text(
            frame,
            height=8,
            font=("Courier", 11),
            bg="#16213e",
            fg="#c0c0e0",
            insertbackground="white",
            relief="flat",
            wrap="none",
        )
        scrollbar = tk.Scrollbar(frame, command=self.table_text.yview)
        self.table_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table_text.pack(fill="x", padx=8, pady=(0, 8))

        self._write_table(
            "Run an algorithm or click 'Compare All Algorithms' to populate this table.\n\n"
            f"{'Algorithm':<12} {'Nodes Explored':>16} {'Path Cost':>12} {'Time (s)':>12}"
        )

    @staticmethod
    def _section_label(parent: tk.Frame, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            font=(FONT_FAMILY, 11, "bold"),
            fg="#f5a623",
            bg="#1a1a2e",
        ).pack(anchor="w", padx=10, pady=(10, 0))

    @staticmethod
    def _btn_style(bg: str, fg: str = "white") -> dict:
        return {
            "bg":              bg,
            "fg":              fg,
            "activebackground": bg,
            "activeforeground":  fg,
            "font":            (FONT_FAMILY, 11, "bold"),
            "relief":          "flat",
            "cursor":          "hand2",
            "pady":            6,
        }

    def _draw_board(self, state: PuzzleState) -> None:
        self.canvas.delete("all")
        for r in range(3):
            for c in range(3):
                tile_num = state.board[r][c]
                x0 = c * TILE_SIZE
                y0 = r * TILE_SIZE
                img = self.tile_images.get(tile_num)
                if img:
                    self.canvas.create_image(x0, y0, anchor="nw", image=img)

        for i in range(1, 3):
            self.canvas.create_line(
                i * TILE_SIZE, 0, i * TILE_SIZE, BOARD_PX,
                fill="#f5a623", width=2
            )
            self.canvas.create_line(
                0, i * TILE_SIZE, BOARD_PX, i * TILE_SIZE,
                fill="#f5a623", width=2
            )

    def _upload_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select an Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            self.tile_images = slice_image(path)
            self._draw_board(self.current_state)
            self.status_var.set(f"Image loaded: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Image Error", str(exc))

    def _shuffle_board(self) -> None:
        self._stop_animation()
        self.solution_path = []
        self.current_state = shuffle(50)
        self._draw_board(self.current_state)
        self.step_label.config(text="Step: — / —")
        self.status_var.set("Board shuffled. Ready to solve.")

    def _reset_board(self) -> None:
        self._stop_animation()
        self.solution_path = []
        self.current_state = PuzzleState(board=copy.deepcopy(GOAL_STATE))
        self._draw_board(self.current_state)
        self.step_label.config(text="Step: — / —")
        self.status_var.set("Board reset to goal state.")

    def _solve_and_animate(self) -> None:
        if self._solving:
            return
        self._stop_animation()

        algo_name = self.algo_var.get()
        algo_func = ALGO_MAP[algo_name]
        initial   = self.current_state
        self.status_var.set(f"Solving with {algo_name.split('(')[0].strip()}…")
        self._solving = True

        def _run() -> None:
            path, nodes, cost, elapsed = algo_func(initial)
            self.root.after(0, lambda: self._on_solve_done(
                path, nodes, cost, elapsed, algo_name
            ))

        threading.Thread(target=_run, daemon=True).start()

    def _on_solve_done(
        self,
        path: List[PuzzleState],
        nodes: int,
        cost: int,
        elapsed: float,
        algo_name: str,
    ) -> None:
        self._solving = False
        short_name = algo_name.split("(")[0].strip()

        if not path:
            self.status_var.set("No solution found!")
            messagebox.showwarning("No Solution", "This algorithm could not find a solution.")
            return

        self.solution_path = path
        row = (
            f"{short_name:<12}"
            f" {nodes:>16}"
            f" {cost:>12}"
            f" {elapsed:>12.6f}"
        )
        self._append_table(row)
        self.status_var.set(
            f"{short_name}: {cost} moves | {nodes} nodes | {elapsed:.4f}s"
        )
        self.anim_index = 0
        self._animate_step()

    def _animate_step(self) -> None:
        if self.anim_index >= len(self.solution_path):
            self.status_var.set("Animation complete ✓")
            return

        state = self.solution_path[self.anim_index]
        self._draw_board(state)
        total = len(self.solution_path) - 1
        self.step_label.config(
            text=f"Step: {self.anim_index} / {total}"
        )
        self.anim_index += 1
        self.anim_job = self.root.after(ANIM_DELAY, self._animate_step)

    def _stop_animation(self) -> None:
        if self.anim_job is not None:
            self.root.after_cancel(self.anim_job)
            self.anim_job = None

    def _show_final(self) -> None:
        self._stop_animation()
        if not self.solution_path:
            messagebox.showinfo("No Solution", "Solve the puzzle first.")
            return
        last = self.solution_path[-1]
        self._draw_board(last)
        total = len(self.solution_path) - 1
        self.step_label.config(text=f"Step: {total} / {total}")
        self.status_var.set("Showing final (goal) state.")

    def _compare_all(self) -> None:
        if self._solving:
            return
        initial = self.current_state
        self.status_var.set("Running all algorithms — please wait…")
        self._solving = True

        def _run() -> None:
            results = run_all_algorithms(initial)
            table   = format_comparison_table(results)
            self.root.after(0, lambda: self._on_compare_done(table))

        threading.Thread(target=_run, daemon=True).start()

    def _on_compare_done(self, table: str) -> None:
        self._solving = False
        self._write_table(table)
        self.status_var.set("All algorithms complete. See table below.")

    def _write_table(self, text: str) -> None:
        self.table_text.config(state="normal")
        self.table_text.delete("1.0", tk.END)
        self.table_text.insert(tk.END, text)
        self.table_text.config(state="disabled")

    def _append_table(self, row: str) -> None:
        self.table_text.config(state="normal")
        self.table_text.insert(tk.END, "\n" + row)
        self.table_text.see(tk.END)
        self.table_text.config(state="disabled")
