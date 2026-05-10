import sys
import tkinter as tk

from ui import PuzzleGUI


def main() -> None:
    root = tk.Tk()

    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root.minsize(820, 850)

    app = PuzzleGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
