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
ANIM_DELAY  = 350
FONT_FAMILY = "Segoe UI"

# Theme System
THEMES = {
    "light": {
        "bg_main":      "#F9FAFB",
        "bg_panel":     "#FFFFFF",
        "accent":       "#10B981",
        "accent_dark":  "#047857",
        "text_primary": "#111827",
        "text_muted":   "#6B7280",
        "border":       "#E5E7EB",
        "blank_tile":   "#E5E7EB",
        "btn_secondary":"#FFFFFF"
    },
    "dark": {
        "bg_main":      "#0F172A",
        "bg_panel":     "#1E293B",
        "accent":       "#38BDF8",
        "accent_dark":  "#0EA5E9",
        "text_primary": "#F8FAFC",
        "text_muted":   "#94A3B8",
        "border":       "#334155",
        "blank_tile":   "#334155",
        "btn_secondary":"#1E293B"
    }
}

ALGO_MAP = {
    "BFS  (Breadth-First Search)":           bfs,
    "DFS  (Depth-First Search)":             dfs,
    "IDS  (Iterative Deepening Search)":     ids,
    "A*   (A-Star / Manhattan Distance)":    a_star,
}

ALGO_KEYS = list(ALGO_MAP.keys())


def slice_image(image_path: str, blank_color: str, tile_size: int = TILE_SIZE) -> Dict[int, Image.Image]:
    board_size = tile_size * 3
    img = Image.open(image_path).convert("RGB")

    w, h = img.size
    min_dim = min(w, h)
    left   = (w - min_dim) // 2
    top    = (h - min_dim) // 2
    img    = img.crop((left, top, left + min_dim, top + min_dim))
    img    = img.resize((board_size, board_size), Image.LANCZOS)

    tiles: Dict[int, Image.Image] = {}

    blank = Image.new("RGB", (tile_size, tile_size), blank_color)
    tiles[0] = blank

    tile_num = 1
    for row in range(3):
        for col in range(3):
            if tile_num > 8:
                break
            x0, y0 = col * tile_size, row * tile_size
            piece = img.crop((x0, y0, x0 + tile_size, y0 + tile_size))
            tiles[tile_num] = piece
            tile_num += 1

    return tiles


def make_placeholder_tiles(blank_color: str, tile_size: int = TILE_SIZE) -> Dict[int, Image.Image]:
    # Nordic soft palette for numbered tiles
    colours = [
        "#D1FAE5", "#A7F3D0", "#6EE7B7", "#34D399",
        "#10B981", "#059669", "#047857", "#065F46", "#064E3B",
    ]
    tiles: Dict[int, ImageTk.PhotoImage] = {}
    for i in range(9):
        colour = blank_color if i == 0 else colours[i]
        img = Image.new("RGB", (tile_size, tile_size), colour)
        if i != 0:
            draw = ImageDraw.Draw(img)
            text  = str(i)
            try:
                font = ImageFont.truetype("segoeuib.ttf", 40)
            except:
                font = None
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                ((tile_size - tw) // 2, (tile_size - th) // 2),
                text,
                fill="#1F2937",
                font=font
            )
        tiles[i] = img
    return tiles


class PuzzleGUI:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("8-Puzzle Image Solver")
        self.root.resizable(False, False)
        
        self.theme_mode: str = "light"
        self.theme = THEMES[self.theme_mode]
        self.root.configure(bg=self.theme["bg_main"])

        self.current_state: PuzzleState = PuzzleState(
            board=copy.deepcopy(GOAL_STATE)
        )
        self.raw_tiles: Dict[int, Image.Image] = make_placeholder_tiles(self.theme["blank_tile"])
        self.tile_images: Dict[int, ImageTk.PhotoImage] = self._convert_tiles(self.raw_tiles)
        self.solution_path: List[PuzzleState] = []
        self.anim_index: int = 0
        self.anim_job: Optional[str] = None
        self._solving: bool = False
        self.theme_mode: str = "light"
        self.theme = THEMES[self.theme_mode]

        self._build_ui()
        self._draw_board(self.current_state)

    def _build_ui(self) -> None:
        self.root.configure(bg=self.theme["bg_main"])
        
        # Clean existing widgets for theme refresh
        for widget in self.root.winfo_children():
            widget.destroy()

        title_frame = tk.Frame(self.root, bg=self.theme["bg_panel"], pady=12)
        title_frame.pack(fill="x")

        tk.Frame(self.root, bg=self.theme["border"], height=1).pack(fill="x")

        tk.Label(
            title_frame,
            text="8-Puzzle Image Solver",
            font=(FONT_FAMILY, 24, "bold"),
            fg=self.theme["accent_dark"],
            bg=self.theme["bg_panel"],
        ).pack()

        mid_frame = tk.Frame(self.root, bg=self.theme["bg_main"])
        mid_frame.pack(padx=20, pady=20)

        self._build_canvas(mid_frame)
        self._build_controls(mid_frame)

        self._build_table_panel()

    def _build_canvas(self, parent: tk.Frame) -> None:
        canvas_frame = tk.Frame(
            parent, bg=self.theme["bg_panel"], relief="flat", bd=0
        )
        canvas_frame.pack(side="left", padx=(0, 20))

        board_container = tk.Frame(canvas_frame, bg=self.theme["border"], padx=2, pady=2)
        board_container.pack()

        self.canvas = tk.Canvas(
            board_container,
            width=BOARD_PX,
            height=BOARD_PX,
            bg=self.theme["bg_panel"],
            highlightthickness=0,
        )
        self.canvas.pack()

        self.step_label = tk.Label(
            canvas_frame,
            text="Step: — / —",
            font=(FONT_FAMILY, 11),
            fg=self.theme["text_muted"],
            bg=self.theme["bg_panel"],
        )
        self.step_label.pack(pady=10)

    def _build_controls(self, parent: tk.Frame) -> None:
        ctrl = tk.Frame(parent, bg=self.theme["bg_main"], width=300)
        ctrl.pack(side="left", fill="y")

        self._section_label(ctrl, "📷  Image")
        tk.Button(
            ctrl,
            text="Upload Image",
            command=self._upload_image,
            **self._btn_style(self.theme["btn_secondary"], fg=self.theme["text_primary"], border=True),
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

        tk.Button(
            ctrl,
            text="⚔  Algorithm Battle",
            command=self._open_battle_mode,
            **self._btn_style(self.theme["accent"], border=True),
        ).pack(fill="x", padx=10, pady=8)

        tk.Button(
            ctrl,
            text="🌓 Toggle Dark/Light Mode",
            command=self._toggle_theme,
            **self._btn_style(self.theme["btn_secondary"], fg=self.theme["text_primary"], border=True),
        ).pack(fill="x", padx=10, pady=4)

        self._section_label(ctrl, "📊  Analysis")
        tk.Button(
            ctrl,
            text="Compare All Algorithms",
            command=self._compare_all,
            **self._btn_style(self.theme["btn_secondary"], fg=self.theme["accent_dark"], border=True),
        ).pack(fill="x", padx=10, pady=4)

        self._section_label(ctrl, "🎲  Board")
        tk.Button(
            ctrl,
            text="Shuffle Board",
            command=self._shuffle_board,
            **self._btn_style(self.theme["accent"]),
        ).pack(fill="x", padx=10, pady=4)

        tk.Button(
            ctrl,
            text="Reset to Goal",
            command=self._reset_board,
            **self._btn_style(self.theme["btn_secondary"], fg=self.theme["text_primary"], border=True),
        ).pack(fill="x", padx=10, pady=4)

        self._section_label(ctrl, "🔍  Solve")
        tk.Button(
            ctrl,
            text="▶  Solve (Animate)",
            command=self._solve_and_animate,
            **self._btn_style(self.theme["accent_dark"]),
        ).pack(fill="x", padx=10, pady=4)

        tk.Button(
            ctrl,
            text="⏭  Show Final Solution",
            command=self._show_final,
            **self._btn_style(self.theme["btn_secondary"], fg=self.theme["text_primary"], border=True),
        ).pack(fill="x", padx=10, pady=4)

        tk.Button(
            ctrl,
            text="⏹  Stop Animation",
            command=self._stop_animation,
            **self._btn_style("#EF4444"),
        ).pack(fill="x", padx=10, pady=4)

        # Analysis and Settings moved up

        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(
            ctrl,
            textvariable=self.status_var,
            font=(FONT_FAMILY, 10, "italic"),
            fg=self.theme["text_muted"],
            bg=self.theme["bg_main"],
            wraplength=280,
        ).pack(padx=10, pady=15)

    def _build_table_panel(self) -> None:
        frame = tk.Frame(self.root, bg=self.theme["bg_panel"], relief="flat")
        frame.pack(fill="x", padx=20, pady=(0, 20))

        tk.Label(
            frame,
            text="ALGORITHM COMPARISON",
            font=(FONT_FAMILY, 10, "bold"),
            fg=self.theme["text_muted"],
            bg=self.theme["bg_panel"],
        ).pack(anchor="w", padx=8, pady=8)

        text_container = tk.Frame(frame, bg=self.theme["border"], padx=1, pady=1)
        text_container.pack(fill="x")

        self.table_text = tk.Text(
            text_container,
            height=8,
            font=("Consolas", 10),
            bg=self.theme["bg_main"],
            fg=self.theme["text_primary"],
            insertbackground=self.theme["text_primary"],
            relief="flat",
            wrap="none",
            padx=10,
            pady=10,
        )
        scrollbar = tk.Scrollbar(frame, command=self.table_text.yview)
        self.table_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table_text.pack(fill="x")

        self._write_table(
            "Run an algorithm to compare performance stats.\n\n"
            f"{'Algorithm':<12} {'Nodes Explored':>16} {'Path Cost':>12} {'Time (s)':>12}"
        )

    def _section_label(self, parent: tk.Frame, text: str) -> None:
        tk.Label(
            parent,
            text=text.upper(),
            font=(FONT_FAMILY, 9, "bold"),
            fg=self.theme["text_muted"],
            bg=self.theme["bg_main"],
        ).pack(anchor="w", padx=10, pady=(15, 2))

    def _btn_style(self, bg: str, fg: str = "white", border: bool = False) -> dict:
        style = {
            "bg":              bg,
            "fg":              fg,
            "activebackground": bg if not border else self.theme["bg_main"],
            "activeforeground":  fg,
            "font":            (FONT_FAMILY, 10, "bold"),
            "relief":          "flat",
            "cursor":          "hand2",
            "pady":            8,
        }
        if border:
            style["highlightbackground"] = self.theme["border"]
            style["highlightthickness"] = 1
            style["bd"] = 1
            style["relief"] = "solid"
        return style

    def _convert_tiles(self, raw_tiles: Dict[int, Image.Image], size: int = TILE_SIZE) -> Dict[int, ImageTk.PhotoImage]:
        converted = {}
        for num, img in raw_tiles.items():
            resized = img.resize((size, size), Image.LANCZOS)
            converted[num] = ImageTk.PhotoImage(resized)
        return converted

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
                fill=self.theme["border"], width=1
            )
            self.canvas.create_line(
                0, i * TILE_SIZE, BOARD_PX, i * TILE_SIZE,
                fill=self.theme["border"], width=1
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
            self.raw_tiles = slice_image(path, self.theme["blank_tile"])
            self.tile_images = self._convert_tiles(self.raw_tiles)
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

    def _toggle_theme(self) -> None:
        self.theme_mode = "dark" if self.theme_mode == "light" else "light"
        self.theme = THEMES[self.theme_mode]
        self._build_ui()
        self._draw_board(self.current_state)

    def _open_battle_mode(self) -> None:
        from battle_mode import BattleUI
        BattleUI(self.root, self.current_state, self.raw_tiles, self.theme, self.theme_mode)

    def _append_table(self, row: str) -> None:
        self.table_text.config(state="normal")
        self.table_text.insert(tk.END, "\n" + row)
        self.table_text.see(tk.END)
        self.table_text.config(state="disabled")
