from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from typing import Dict, List, Optional
from PIL import ImageTk, Image

from puzzle_engine import PuzzleState
from algorithms import bfs, dfs, ids, a_star

ALGO_MAP = {
    "BFS  (Breadth-First Search)":           bfs,
    "DFS  (Depth-First Search)":             dfs,
    "IDS  (Iterative Deepening Search)":     ids,
    "A*   (A-Star / Manhattan Distance)":    a_star,
}

class BattleUI:
    def __init__(
        self, 
        parent: tk.Tk, 
        initial_state: PuzzleState, 
        raw_tiles: Dict[int, Image.Image],
        theme: dict,
        theme_mode: str
    ):
        self.window = tk.Toplevel(parent)
        self.window.title("Algorithm Battle Mode — Side by Side")
        self.window.configure(bg=theme["bg_main"])
        self.window.resizable(False, False)
        
        self.initial_state = initial_state
        self.raw_tiles = raw_tiles
        self.theme = theme
        self.theme_mode = theme_mode
        self.font_family = "Segoe UI"
        
        # Scaling tile images for battle mode (100px vs 150px)
        self.tile_size = 100
        self.tile_images = self._prepare_tiles(raw_tiles, self.tile_size)
        
        self.results = {"left": None, "right": None}
        self.animations_done = {"left": False, "right": False}
        self.is_running = False
        self.jobs = [] 
        
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._build_ui()
        self._draw_initial()

    def _build_ui(self):
        header = tk.Frame(self.window, bg=self.theme["bg_panel"], pady=15)
        header.pack(fill="x")
        tk.Label(
            header, text="⚔ ALGORITHM BATTLE", 
            font=(self.font_family, 18, "bold"),
            fg=self.theme["accent"], bg=self.theme["bg_panel"]
        ).pack()

        arena = tk.Frame(self.window, bg=self.theme["bg_main"], padx=20, pady=20)
        arena.pack()

        self.left_panel = self._create_competitor_panel(arena, "LEFT", side="left")
        
        vs_frame = tk.Frame(arena, bg=self.theme["bg_main"], padx=20)
        vs_frame.pack(side="left", fill="y")
        tk.Label(
            vs_frame, text="VS", font=(self.font_family, 24, "italic bold"),
            fg=self.theme["text_muted"], bg=self.theme["bg_main"]
        ).pack(expand=True)

        self.right_panel = self._create_competitor_panel(arena, "RIGHT", side="left")

        controls = tk.Frame(self.window, bg=self.theme["bg_panel"], pady=20)
        controls.pack(fill="x")
        
        self.start_btn = tk.Button(
            controls, text="START BATTLE", command=self._start_battle,
            bg=self.theme["accent"], fg="white", font=(self.font_family, 12, "bold"),
            relief="flat", padx=30, pady=10, cursor="hand2"
        )
        self.start_btn.pack(side="left", expand=True, padx=(50, 5))

        self.stop_btn = tk.Button(
            controls, text="STOP", command=self._stop_battle,
            bg="#EF4444", fg="white", font=(self.font_family, 12, "bold"),
            relief="flat", padx=20, pady=10, cursor="hand2", state="disabled"
        )
        self.stop_btn.pack(side="left", expand=True, padx=(5, 5))

        self.winner_label = tk.Label(
            controls, text="Waiting for battle...", 
            font=(self.font_family, 12, "bold"),
            fg=self.theme["text_muted"], bg=self.theme["bg_panel"]
        )
        self.winner_label.pack(side="left", expand=True, padx=(0, 50))

    def _create_competitor_panel(self, parent: tk.Frame, label: str, side: str):
        frame = tk.Frame(parent, bg=self.theme["bg_main"])
        frame.pack(side=side)

        algo_keys = list(ALGO_MAP.keys())
        algo_var = tk.StringVar(value=algo_keys[0] if label == "LEFT" else algo_keys[-1])
        
        selector = ttk.Combobox(
            frame, textvariable=algo_var, values=algo_keys, 
            state="readonly", width=30
        )
        selector.pack(pady=(0, 10))

        board_size = 300
        self.tile_size = 100
        
        canvas_container = tk.Frame(frame, bg=self.theme["border"], padx=1, pady=1)
        canvas_container.pack()
        
        canvas = tk.Canvas(
            canvas_container, width=board_size, height=board_size,
            bg=self.theme["bg_panel"], highlightthickness=0
        )
        canvas.pack()

        stats_frame = tk.Frame(frame, bg=self.theme["bg_main"], pady=10)
        stats_frame.pack(fill="x")
        
        depth_label = tk.Label(
            stats_frame, text="Step: 0", font=(self.font_family, 10),
            fg=self.theme["text_primary"], bg=self.theme["bg_main"]
        )
        depth_label.pack()
        
        nodes_label = tk.Label(
            stats_frame, text="Nodes: 0", font=(self.font_family, 10),
            fg=self.theme["text_muted"], bg=self.theme["bg_main"]
        )
        nodes_label.pack()

        return {
            "algo_var": algo_var,
            "canvas": canvas,
            "depth_label": depth_label,
            "nodes_label": nodes_label,
            "board_size": board_size
        }

    def _draw_initial(self):
        for side in ["left", "right"]:
            panel = self.left_panel if side == "left" else self.right_panel
            self._draw_state(panel, self.initial_state)

    def _draw_state(self, panel: dict, state: PuzzleState):
        canvas = panel["canvas"]
        canvas.delete("all")
        
        for r in range(3):
            for c in range(3):
                tile_num = state.board[r][c]
                x0, y0 = c * self.tile_size, r * self.tile_size
                
                img = self.tile_images.get(tile_num)
                if img:
                    canvas.create_image(x0, y0, anchor="nw", image=img)
                
                # Draw subtle border
                canvas.create_rectangle(
                    x0, y0, x0 + self.tile_size, y0 + self.tile_size,
                    outline=self.theme["border"], width=1
                )

    def _prepare_tiles(self, raw_tiles: Dict[int, Image.Image], size: int) -> Dict[int, ImageTk.PhotoImage]:
        converted = {}
        for num, img in raw_tiles.items():
            resized = img.resize((size, size), Image.LANCZOS)
            converted[num] = ImageTk.PhotoImage(resized)
        return converted

    def _start_battle(self):
        if self.is_running: return
        self._stop_battle() # Clear any existing jobs
        self.is_running = True
        self.start_btn.config(state="disabled", text="BATTLING...")
        self.stop_btn.config(state="normal")
        self.winner_label.config(text="Calculating...", fg=self.theme["accent"])
        self.results = {"left": None, "right": None}
        self.animations_done = {"left": False, "right": False}

        threads = [
            threading.Thread(target=self._run_engine, args=("left",), daemon=True),
            threading.Thread(target=self._run_engine, args=("right",), daemon=True)
        ]
        for t in threads: t.start()

    def _run_engine(self, side: str):
        panel = self.left_panel if side == "left" else self.right_panel
        algo_name = panel["algo_var"].get()
        algo_func = ALGO_MAP[algo_name]
        
        start_time = time.time()
        path, nodes, cost, elapsed = algo_func(self.initial_state)
        
        self.results[side] = {
            "path": path,
            "nodes": nodes,
            "cost": cost,
            "time": elapsed
        }
        
        if path:
            self._animate_path(side, path)
        else:
            self.window.after(0, lambda: messagebox.showwarning("Battle Error", f"{algo_name} failed!"))
        
        if self.results["left"] and self.results["right"]:
            self.window.after(500, self._announce_winner)

    def _animate_path(self, side: str, path: List[PuzzleState]):
        panel = self.left_panel if side == "left" else self.right_panel
        delay = 400
        total_steps = len(path)
        for i, state in enumerate(path):
            is_last = (i == total_steps - 1)
            job = self.window.after(i * delay, lambda s=state, idx=i, last=is_last: self._update_view(side, s, idx, last))
            self.jobs.append(job)

    def _stop_battle(self):
        self.is_running = False
        for job in self.jobs:
            try:
                self.window.after_cancel(job)
            except:
                pass
        self.jobs = []
        self.start_btn.config(state="normal", text="START BATTLE")
        self.stop_btn.config(state="disabled")
        self.winner_label.config(text="Battle Stopped.", fg="#EF4444")

    def _update_view(self, side: str, state: PuzzleState, step: int, is_last: bool):
        if not self.window.winfo_exists(): return
        panel = self.left_panel if side == "left" else self.right_panel
        self._draw_state(panel, state)
        panel["depth_label"].config(text=f"Step: {step}")
        if self.results[side]:
            panel["nodes_label"].config(text=f"Nodes: {self.results[side]['nodes']}")
        
        if is_last:
            self.animations_done[side] = True
            if all(self.animations_done.values()):
                self._announce_winner()

    def _on_close(self):
        self._stop_battle()
        self.window.destroy()

    def _announce_winner(self):
        self.is_running = False
        self.start_btn.config(state="normal", text="RESTART BATTLE")
        self.stop_btn.config(state="disabled")
        
        l = self.results["left"]
        r = self.results["right"]
        
        l_score = l["cost"]
        r_score = r["cost"]
        
        if l_score < r_score:
            winner_text = f"🏆 LEFT ({panel_name(self.left_panel)}) WINS!"
            winner_color = self.theme["accent"]
        elif r_score < l_score:
            winner_text = f"🏆 RIGHT ({panel_name(self.right_panel)}) WINS!"
            winner_color = self.theme["accent"]
        else:
            if l["time"] < r["time"]:
                winner_text = f"🤝 DRAW! LEFT is FASTER"
            else:
                winner_text = f"🤝 DRAW! RIGHT is FASTER"
            winner_color = self.theme["text_primary"]

        self.winner_label.config(text=winner_text, fg=winner_color)

def panel_name(panel):
    return panel["algo_var"].get().split("(")[0].strip()
