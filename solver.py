#!/usr/bin/env python3
"""
Match-3 Tile Puzzle Solver (3 Tiles / similar games)

Rules:
- Blocks sit on a layered board. A block is clickable only when no
  higher-layer block overlaps it.
- Clicking a block moves it into a 7-slot waiting area.
- New blocks are inserted NEXT TO their matching color group in the slot
  (not necessarily at the end).
- When 3 identical colors are consecutive in the slot they auto-clear.
- If the slot reaches 7 without clearing, it's game over.
- Goal: clear every block from the board.

How to use:
  1. Edit the PUZZLE section at the bottom with your actual board layout.
  2. Run:  python3 solver.py
"""

from collections import deque
from typing import FrozenSet, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Core data
# ---------------------------------------------------------------------------

class Block:
    __slots__ = ("id", "color", "layer", "x", "y", "w", "h")

    def __init__(self, id: int, color: str, layer: int,
                 x: float, y: float, w: float = 1.0, h: float = 1.0):
        self.id    = id
        self.color = color
        self.layer = layer
        self.x, self.y = x, y
        self.w, self.h = w, h

    def __repr__(self):
        return f"Block({self.id}, {self.color!r}, layer={self.layer}, pos=({self.x},{self.y}))"

    # Blocks need to be hashable to live in frozensets
    def __hash__(self):  return self.id
    def __eq__(self, other): return isinstance(other, Block) and self.id == other.id


def overlaps(a: Block, b: Block) -> bool:
    """True when two blocks share any area on the grid."""
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or
        a.y + a.h <= b.y or b.y + b.h <= a.y
    )


def is_accessible(block: Block, remaining: FrozenSet[Block]) -> bool:
    """A block is accessible when nothing with a higher layer overlaps it."""
    for other in remaining:
        if other.layer > block.layer and overlaps(block, other):
            return False
    return True


# ---------------------------------------------------------------------------
# Slot mechanics
# ---------------------------------------------------------------------------

Slot = Tuple[str, ...]   # ordered sequence of colors in the waiting area
MAX_SLOT = 7


def slot_add(slot: Slot, color: str) -> Optional[Slot]:
    """
    Insert *color* into the slot next to its existing group (after the last
    matching tile), then remove any run of 3+ identical consecutive colors.
    Returns None when the slot would exceed MAX_SLOT (game over for that path).
    """
    lst = list(slot)

    # Find insert position: right after the last tile of the same color.
    insert_pos = len(lst)
    for i in range(len(lst) - 1, -1, -1):
        if lst[i] == color:
            insert_pos = i + 1
            break
    lst.insert(insert_pos, color)

    # Collapse runs of 3+ (may chain after each collapse)
    changed = True
    while changed:
        changed = False
        for i in range(len(lst) - 2):
            if lst[i] == lst[i + 1] == lst[i + 2]:
                lst = lst[:i] + lst[i + 3:]
                changed = True
                break

    if len(lst) > MAX_SLOT:
        return None       # slot overflow → dead end
    return tuple(lst)


# ---------------------------------------------------------------------------
# Solver  (BFS over game states)
# ---------------------------------------------------------------------------

# A state is fully described by what's still on the board + the slot contents.
State = Tuple[FrozenSet[Block], Slot]


def solve(blocks: List[Block]) -> Optional[List[int]]:
    """
    BFS search for a click sequence that clears all blocks.
    Returns a list of block IDs in click order, or None if unsolvable.

    For large puzzles BFS can be slow.  See the DFS option below if needed.
    """
    start: State = (frozenset(blocks), ())
    queue: deque = deque([(start, [])])
    visited = {start}

    while queue:
        (remaining, slot), path = queue.popleft()

        if not remaining:
            return path                         # ✓ all blocks cleared

        accessible = [b for b in remaining if is_accessible(b, remaining)]

        for block in accessible:
            new_slot = slot_add(slot, block.color)
            if new_slot is None:
                continue                        # this move overflows the slot

            new_remaining = remaining - {block}
            new_state: State = (new_remaining, new_slot)

            if new_state not in visited:
                visited.add(new_state)
                queue.append((new_state, path + [block.id]))

    return None                                 # exhausted search, no solution


# ---------------------------------------------------------------------------
# DFS alternative — faster for deep solutions, less memory usage
# ---------------------------------------------------------------------------

def solve_dfs(blocks: List[Block]) -> Optional[List[int]]:
    """DFS with a visited-state cache.  Often faster than BFS on large boards."""
    visited: set = set()

    def dfs(remaining: FrozenSet[Block], slot: Slot, path: List[int]):
        if not remaining:
            return path

        state = (remaining, slot)
        if state in visited:
            return None
        visited.add(state)

        accessible = [b for b in remaining if is_accessible(b, remaining)]
        for block in accessible:
            new_slot = slot_add(slot, block.color)
            if new_slot is None:
                continue
            result = dfs(remaining - {block}, new_slot, path + [block.id])
            if result is not None:
                return result
        return None

    return dfs(frozenset(blocks), (), [])


# ---------------------------------------------------------------------------
# Pretty-print helper
# ---------------------------------------------------------------------------

def print_solution(solution: List[int], block_map: dict):
    if solution is None:
        print("No solution found (the puzzle may be unsolvable from this state).")
        return

    print(f"\nSolution found — {len(solution)} moves:\n")
    slot: Slot = ()
    for step, bid in enumerate(solution, 1):
        b = block_map[bid]
        slot = slot_add(slot, b.color)
        slot_str = " | ".join(slot) if slot else "(empty)"
        print(f"  Step {step:>3}: click block #{bid:>3}  color={b.color:<10}"
              f"  layer={b.layer}  pos=({b.x},{b.y})   slot → [{slot_str}]")
    print("\nAll blocks cleared! ✓")


# ---------------------------------------------------------------------------
# ══════════════════════════════════════════════════════════════════════════
#  PUZZLE DEFINITION — edit this section to match your actual stage
# ══════════════════════════════════════════════════════════════════════════
#
# Block(id, color, layer, x, y, width=1.0, height=1.0)
#
#  • id     : unique integer for each block
#  • color  : any string label ("red", "blue", "star", "acorn", …)
#  • layer  : 0 = bottom; higher numbers sit on top
#  • x, y   : top-left grid coordinate of the block
#  • w, h   : size of the block in grid units (default 1×1)
#
# A block at (x=1, y=0, layer=1) covers any layer-0 block whose area
# overlaps (1,0)→(2,1).
#
# Example: a simple 9-block puzzle
# ---------------------------------------------------------------------------

BLOCKS = [
    # layer 0 — bottom row
    Block( 1, "red",    0,  0, 0),
    Block( 2, "red",    0,  1, 0),
    Block( 3, "blue",   0,  2, 0),
    Block( 4, "blue",   0,  0, 1),
    Block( 5, "yellow", 0,  1, 1),
    Block( 6, "yellow", 0,  2, 1),

    # layer 1 — on top, covering some layer-0 blocks
    Block( 7, "red",    1,  0, 0),   # covers block 1
    Block( 8, "blue",   1,  1, 0),   # covers blocks 2 & 5
    Block( 9, "yellow", 1,  2, 0),   # covers blocks 3 & 6
]

# Slot may already have tiles if you're mid-game:
INITIAL_SLOT: Slot = ()   # e.g. ("red", "blue") if two tiles are already there

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    block_map = {b.id: b for b in BLOCKS}

    print("Searching for solution …")

    # Inject initial slot tiles as phantom "already-clicked" blocks
    # so the solver starts from the correct slot state.
    if INITIAL_SLOT:
        # We simulate the initial slot by running it through slot_add
        sim_slot: Slot = ()
        for color in INITIAL_SLOT:
            sim_slot = slot_add(sim_slot, color)
            if sim_slot is None:
                print("ERROR: INITIAL_SLOT already overflows (> 7 tiles).")
                exit(1)
    else:
        sim_slot = ()

    # Patch the solver to accept an initial slot
    def solve_from(blocks, init_slot):
        start: State = (frozenset(blocks), init_slot)
        queue: deque = deque([(start, [])])
        visited = {start}
        while queue:
            (remaining, slot), path = queue.popleft()
            if not remaining:
                return path
            accessible = [b for b in remaining if is_accessible(b, remaining)]
            for block in accessible:
                new_slot = slot_add(slot, block.color)
                if new_slot is None:
                    continue
                new_remaining = remaining - {block}
                new_state: State = (new_remaining, new_slot)
                if new_state not in visited:
                    visited.add(new_state)
                    queue.append((new_state, path + [block.id]))
        return None

    solution = solve_from(BLOCKS, sim_slot)
    print_solution(solution, block_map)
