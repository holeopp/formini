#!/usr/bin/env python3
"""
Graphical Match-3 puzzle player.

Run:  python3 play.py

A window opens. Click blocks with your mouse to play.
Buttons: Hint, Undo, Restart, Quit.

The puzzle layout is read from solver.py (BLOCKS + INITIAL_SLOT).
"""

import tkinter as tk
from tkinter import messagebox

from solver import (
    BLOCKS, INITIAL_SLOT, MAX_SLOT, FROZEN, BOMB,
    accessible_ids, slot_add, step, make_initial_counters, solve_from,
)


# ---------------------------------------------------------------------------
# Visual settings
# ---------------------------------------------------------------------------

BLOCK_SIZE   = 80
PADDING      = 30
LAYER_OFFSET = 7        # px shift per layer to give a 3-D stacked look
SLOT_SIZE    = 50

COLOR_MAP = {
    "red":    "#e74c3c",
    "blue":   "#3498db",
    "yellow": "#f1c40f",
    "green":  "#2ecc71",
    "purple": "#9b59b6",
    "orange": "#e67e22",
    "pink":   "#fd79a8",
    "cyan":   "#1abc9c",
    "white":  "#ecf0f1",
    "black":  "#2c3e50",
    "brown":  "#8b6f47",
    "gray":   "#95a5a6",
}

BG       = "#34495e"
PANEL_BG = "#2c3e50"
BOARD_BG = "#7f8c8d"


def to_hex(name: str) -> str:
    return COLOR_MAP.get(name.lower(), "#bdc3c7")


# ---------------------------------------------------------------------------
# Game window
# ---------------------------------------------------------------------------

class Game:
    def __init__(self, root: tk.Tk, blocks, init_slot=()):
        self.root        = root
        self.blocks_list = blocks
        self.all_blocks  = {b.id: b for b in blocks}
        self.init_slot   = init_slot
        self.history     = []

        max_x     = max(b.x + b.w for b in blocks)
        max_y     = max(b.y + b.h for b in blocks)
        max_layer = max(b.layer   for b in blocks)
        canvas_w  = int(max_x * BLOCK_SIZE + 2 * PADDING + max_layer * LAYER_OFFSET)
        canvas_h  = int(max_y * BLOCK_SIZE + 2 * PADDING + max_layer * LAYER_OFFSET)

        # ---- window chrome -------------------------------------------------
        root.title("Match-3 Tile Solver")
        root.configure(bg=BG)
        root.resizable(False, False)

        # ---- slot strip ----------------------------------------------------
        slot_frame = tk.Frame(root, bg=PANEL_BG)
        slot_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.slot_label = tk.Label(slot_frame, text="SLOT 0/7",
                                   bg=PANEL_BG, fg="white",
                                   font=("Helvetica", 12, "bold"))
        self.slot_label.pack(side="left", padx=10, pady=10)

        slot_w = SLOT_SIZE * MAX_SLOT + 20
        self.slot_canvas = tk.Canvas(slot_frame, height=SLOT_SIZE + 10,
                                     width=slot_w, bg=PANEL_BG,
                                     highlightthickness=0)
        self.slot_canvas.pack(side="left", padx=10, pady=10)

        # ---- main board ----------------------------------------------------
        self.canvas = tk.Canvas(root, width=canvas_w, height=canvas_h,
                                bg=BOARD_BG, highlightthickness=0)
        self.canvas.pack(padx=10, pady=5)
        self.canvas.bind("<Button-1>", self.on_click)

        # ---- buttons -------------------------------------------------------
        btn_frame = tk.Frame(root, bg=BG)
        btn_frame.pack(pady=8)

        for label, cmd, color in [
            ("Hint",    self.hint,         "#f39c12"),
            ("Undo",    self.undo,         "#3498db"),
            ("Restart", self.restart,      "#9b59b6"),
            ("Quit",    self.root.destroy, "#e74c3c"),
        ]:
            tk.Button(btn_frame, text=label, command=cmd,
                      bg=color, fg="white", font=("Helvetica", 11, "bold"),
                      padx=18, pady=6, relief="flat",
                      activebackground=color
                      ).pack(side="left", padx=4)

        # ---- status bar ----------------------------------------------------
        self.status = tk.Label(root, text="Click a block to play!",
                               bg=BG, fg="white",
                               font=("Helvetica", 11), pady=6)
        self.status.pack(fill="x")

        self.reset_state()

    # -----------------------------------------------------------------------
    # State
    # -----------------------------------------------------------------------

    def reset_state(self):
        self.state   = (make_initial_counters(self.blocks_list), self.init_slot)
        self.history = []
        self.draw()

    # -----------------------------------------------------------------------
    # Hit-testing
    # -----------------------------------------------------------------------

    def block_bbox(self, b):
        offset = b.layer * LAYER_OFFSET
        x1 = PADDING + b.x * BLOCK_SIZE + offset
        y1 = PADDING + b.y * BLOCK_SIZE + offset
        x2 = x1 + b.w * BLOCK_SIZE
        y2 = y1 + b.h * BLOCK_SIZE
        return x1, y1, x2, y2

    def find_block_at(self, px, py):
        """Top-most remaining block whose rectangle contains (px,py)."""
        counters = dict(self.state[0])
        # Higher layer first (drawn on top)
        order = sorted(counters.keys(),
                       key=lambda i: -self.all_blocks[i].layer)
        for bid in order:
            x1, y1, x2, y2 = self.block_bbox(self.all_blocks[bid])
            if x1 <= px <= x2 and y1 <= py <= y2:
                return bid
        return None

    # -----------------------------------------------------------------------
    # Drawing
    # -----------------------------------------------------------------------

    def draw(self):
        self.canvas.delete("all")
        self.slot_canvas.delete("all")

        counters      = dict(self.state[0])
        slot          = self.state[1]
        remaining_ids = set(counters.keys())
        access        = accessible_ids(remaining_ids, self.all_blocks)

        # Slot bar
        self.slot_label.config(text=f"SLOT {len(slot)}/{MAX_SLOT}")
        for i in range(MAX_SLOT):
            x = 10 + i * SLOT_SIZE
            self.slot_canvas.create_rectangle(
                x, 5, x + SLOT_SIZE - 5, 5 + SLOT_SIZE,
                outline="#7f8c8d", width=1, fill="#34495e",
            )
        for i, color in enumerate(slot):
            x = 10 + i * SLOT_SIZE
            self.slot_canvas.create_rectangle(
                x + 2, 7, x + SLOT_SIZE - 7, 3 + SLOT_SIZE,
                fill=to_hex(color), outline="white", width=2,
            )

        # Board: draw bottom layers first so top layers visually cover them
        order = sorted(remaining_ids, key=lambda i: self.all_blocks[i].layer)
        for bid in order:
            b   = self.all_blocks[bid]
            cnt = counters[bid]
            x1, y1, x2, y2 = self.block_bbox(b)

            is_top    = bid in access
            is_frozen = b.kind == FROZEN and cnt < b.threshold

            # drop shadow
            self.canvas.create_rectangle(x1 + 4, y1 + 4, x2 + 4, y2 + 4,
                                         fill="#2c3e50", outline="")

            # body
            outline = "#ecf0f1" if is_top else "#5d6d7e"
            width   = 3 if is_top else 1
            self.canvas.create_rectangle(x1, y1, x2, y2,
                                         fill=to_hex(b.color),
                                         outline=outline, width=width)

            # ID badge
            self.canvas.create_text((x1 + x2) / 2, y1 + 14,
                                    text=f"#{bid}", fill="white",
                                    font=("Helvetica", 10, "bold"))

            # color label
            self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2,
                                    text=b.color, fill="white",
                                    font=("Helvetica", 10))

            # Frozen overlay
            if is_frozen:
                self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill="#aed6f1",
                    stipple="gray50", outline="")
                self.canvas.create_text(
                    (x1 + x2) / 2, y2 - 14,
                    text=f"FROZEN  {cnt}/{b.threshold}",
                    fill="#1b4f72", font=("Helvetica", 10, "bold"))

            elif b.kind == FROZEN:
                self.canvas.create_text(
                    (x1 + x2) / 2, y2 - 14,
                    text="THAWED",
                    fill="#ffffff", font=("Helvetica", 10, "bold"))

            elif b.kind == BOMB and is_top:
                remaining = b.threshold - cnt
                fill = "#ffeb3b" if remaining > 2 else "#ff5252"
                self.canvas.create_text(
                    (x1 + x2) / 2, y2 - 14,
                    text=f"BOMB  {remaining}",
                    fill=fill, font=("Helvetica", 10, "bold"))

        if not counters:
            self.canvas.create_text(
                self.canvas.winfo_reqwidth() / 2,
                self.canvas.winfo_reqheight() / 2,
                text="YOU WIN!", fill="#2ecc71",
                font=("Helvetica", 32, "bold"))

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def on_click(self, event):
        if not dict(self.state[0]):
            return

        bid = self.find_block_at(event.x, event.y)
        if bid is None:
            return

        counters = dict(self.state[0])
        access   = accessible_ids(set(counters.keys()), self.all_blocks)

        if bid not in access:
            self.status.config(
                text=f"Block #{bid} is buried — clear what's on top first.",
                fg="#f1c40f")
            return

        b = self.all_blocks[bid]
        if b.kind == FROZEN and counters[bid] < b.threshold:
            need = b.threshold - counters[bid]
            self.status.config(
                text=f"#{bid} is still frozen — click {need} other block(s) first.",
                fg="#85c1e9")
            return

        nxt = step(self.state, bid, self.all_blocks)
        if nxt is None:
            slot_test = slot_add(self.state[1], b.color)
            if slot_test is None:
                messagebox.showinfo("Game Over",
                                    "💀  Slot overflowed (more than 7 tiles)!\n\n"
                                    "Press Undo or Restart to try again.")
                self.status.config(text="Slot overflow.", fg="#e74c3c")
            else:
                messagebox.showinfo("Game Over",
                                    "💥  BOOM!  A bomb just exploded.\n\n"
                                    "Press Undo or Restart to try again.")
                self.status.config(text="Bomb exploded.", fg="#e74c3c")
            return

        self.history.append(self.state)
        self.state = nxt
        self.status.config(
            text=f"Clicked #{bid} ({b.color}).", fg="white")
        self.draw()

        if not dict(self.state[0]):
            self.status.config(text="🎉  You cleared the board!", fg="#2ecc71")

    def hint(self):
        counters = dict(self.state[0])
        if not counters:
            return
        self.status.config(text="Thinking...", fg="white")
        self.root.update_idletasks()

        sol = solve_from([self.all_blocks[i] for i in counters],
                         self.state[1])
        if sol is None:
            self.status.config(
                text="No solution from this position. Try Undo.",
                fg="#e74c3c")
        else:
            nb = self.all_blocks[sol[0]]
            self.status.config(
                text=f"💡 Click #{sol[0]} ({nb.color}) — {len(sol)} moves to win.",
                fg="#f1c40f")

    def undo(self):
        if self.history:
            self.state = self.history.pop()
            self.draw()
            self.status.config(text="Undone.", fg="white")
        else:
            self.status.config(text="Nothing to undo.", fg="#f1c40f")

    def restart(self):
        self.reset_state()
        self.status.config(text="Restarted.", fg="white")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Replay INITIAL_SLOT through slot_add (handles pre-existing matches).
    sim_slot = ()
    for color in INITIAL_SLOT:
        sim_slot = slot_add(sim_slot, color)
        if sim_slot is None:
            print("ERROR: INITIAL_SLOT already overflows.")
            raise SystemExit(1)

    root = tk.Tk()
    Game(root, BLOCKS, sim_slot)
    root.mainloop()
