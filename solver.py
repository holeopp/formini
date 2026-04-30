#!/usr/bin/env python3
"""
Match-3 Tile Puzzle Solver (3 Tiles / similar games)

Core rules:
- Blocks sit on a layered board. A block is "accessible" only when no
  higher-layer block overlaps it.
- Clicking a block moves its color into a 7-slot waiting area.
- New colors are inserted NEXT TO their matching color group in the slot.
- 3 identical consecutive colors auto-clear (chains allowed).
- If the slot ever exceeds 7 tiles → game over.
- Goal: clear every block from the board.

Special block kinds:
- "frozen": must be on the top layer AND observe `threshold` clicks of OTHER
  blocks while it is on top before it becomes clickable itself.
- "bomb":   when on the top layer it has a countdown.  Each click of any
  OTHER block while the bomb is on top counts down; if it reaches the
  bomb's `threshold` before you defuse it (click it), the bomb explodes
  and the game ends.

How to use:
  1. Edit the PUZZLE section at the bottom with your actual board layout.
  2. Run:  python3 solver.py
"""

from collections import deque
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Block definition
# ---------------------------------------------------------------------------

NORMAL = "normal"
FROZEN = "frozen"
BOMB   = "bomb"

DEFAULT_FROZEN_THRESHOLD = 3   # 3 other clicks while on top → thawed
DEFAULT_BOMB_THRESHOLD   = 5   # 5 other clicks while on top → kaboom


class Block:
    __slots__ = ("id", "color", "layer", "x", "y", "w", "h", "kind", "threshold")

    def __init__(self, id: int, color: str, layer: int,
                 x: float, y: float, w: float = 1.0, h: float = 1.0,
                 kind: str = NORMAL, threshold: Optional[int] = None):
        self.id    = id
        self.color = color
        self.layer = layer
        self.x, self.y = x, y
        self.w, self.h = w, h
        self.kind  = kind
        if threshold is None:
            threshold = (DEFAULT_FROZEN_THRESHOLD if kind == FROZEN
                         else DEFAULT_BOMB_THRESHOLD if kind == BOMB
                         else 0)
        self.threshold = threshold

    def __repr__(self):
        tag = "" if self.kind == NORMAL else f" {self.kind}({self.threshold})"
        return f"Block({self.id}, {self.color!r}, layer={self.layer}, pos=({self.x},{self.y}){tag})"


def overlaps(a: Block, b: Block) -> bool:
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or
        a.y + a.h <= b.y or b.y + b.h <= a.y
    )


def accessible_ids(remaining_ids, all_blocks: Dict[int, Block]) -> set:
    """Return the subset of remaining_ids whose blocks are on top."""
    blocks = [all_blocks[i] for i in remaining_ids]
    out = set()
    for b in blocks:
        covered = False
        for o in blocks:
            if o.layer > b.layer and overlaps(b, o):
                covered = True
                break
        if not covered:
            out.add(b.id)
    return out


# ---------------------------------------------------------------------------
# Slot mechanics
# ---------------------------------------------------------------------------

Slot = Tuple[str, ...]
MAX_SLOT = 7


def slot_add(slot: Slot, color: str) -> Optional[Slot]:
    """Insert next to matching group; collapse 3-runs; None on overflow."""
    lst = list(slot)
    insert_pos = len(lst)
    for i in range(len(lst) - 1, -1, -1):
        if lst[i] == color:
            insert_pos = i + 1
            break
    lst.insert(insert_pos, color)

    changed = True
    while changed:
        changed = False
        for i in range(len(lst) - 2):
            if lst[i] == lst[i + 1] == lst[i + 2]:
                lst = lst[:i] + lst[i + 3:]
                changed = True
                break

    if len(lst) > MAX_SLOT:
        return None
    return tuple(lst)


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------
#
# A state captures everything that influences future legal moves:
#   - which blocks remain on the board
#   - for each remaining block, its "counter" (clicks observed while on top)
#     • normal: counter unused, kept at 0
#     • frozen: counter ∈ [0, threshold];  >= threshold  ⇒ thawed
#     • bomb:   counter ∈ [0, threshold-1];  reaching threshold ⇒ explosion
#   - the current slot contents
#
# We encode the per-block state as a tuple sorted by id, so it's hashable.
#
# Counters: Tuple[Tuple[int, int], ...]   (id, counter)
# State:    (Counters, Slot)

Counters = Tuple[Tuple[int, int], ...]
State    = Tuple[Counters, Slot]


def make_initial_counters(blocks: List[Block]) -> Counters:
    return tuple(sorted((b.id, 0) for b in blocks))


def is_clickable(block: Block, counter: int) -> bool:
    """Given the block is accessible, can the player click it right now?"""
    if block.kind == NORMAL:   return True
    if block.kind == FROZEN:   return counter >= block.threshold
    if block.kind == BOMB:     return True   # always defusable
    return False


def step(state: State, clicked_id: int,
         all_blocks: Dict[int, Block]) -> Optional[State]:
    """
    Apply one click to *state*.  Returns the next state, or None if the
    move is illegal / leads to a dead end (slot overflow, bomb explosion).
    """
    counters_tup, slot = state
    counters = dict(counters_tup)

    if clicked_id not in counters:
        return None

    accessible_now = accessible_ids(counters.keys(), all_blocks)
    if clicked_id not in accessible_now:
        return None

    clicked = all_blocks[clicked_id]
    if not is_clickable(clicked, counters[clicked_id]):
        return None

    # 1. Update slot
    new_slot = slot_add(slot, clicked.color)
    if new_slot is None:
        return None

    # 2. Increment counters of OTHER on-top frozen/bomb blocks.
    #    (They were on top *during* this click; newly-exposed ones don't count.)
    new_counters: Dict[int, int] = {}
    for bid, cnt in counters.items():
        if bid == clicked_id:
            continue
        b = all_blocks[bid]
        if bid in accessible_now and b.kind in (FROZEN, BOMB):
            new_cnt = cnt + 1
            if b.kind == BOMB and new_cnt >= b.threshold:
                return None                    # 💥 explosion → dead end
            if b.kind == FROZEN:
                new_cnt = min(new_cnt, b.threshold)   # cap; no further work
            new_counters[bid] = new_cnt
        else:
            new_counters[bid] = cnt

    return (tuple(sorted(new_counters.items())), new_slot)


def solve_from(blocks: List[Block], init_slot: Slot = ()) -> Optional[List[int]]:
    """BFS for the shortest click sequence that clears the board."""
    all_blocks = {b.id: b for b in blocks}
    start: State = (make_initial_counters(blocks), init_slot)

    queue: deque = deque([(start, [])])
    visited = {start}

    while queue:
        state, path = queue.popleft()
        counters_tup, _ = state

        if not counters_tup:
            return path                                # ✓ board cleared

        remaining_ids = {bid for bid, _ in counters_tup}
        access_now = accessible_ids(remaining_ids, all_blocks)
        counters_dict = dict(counters_tup)

        for bid in access_now:
            block = all_blocks[bid]
            if not is_clickable(block, counters_dict[bid]):
                continue
            nxt = step(state, bid, all_blocks)
            if nxt is None or nxt in visited:
                continue
            visited.add(nxt)
            queue.append((nxt, path + [bid]))

    return None


# ---------------------------------------------------------------------------
# Pretty-print helper
# ---------------------------------------------------------------------------

def print_solution(solution: Optional[List[int]],
                   blocks: List[Block], init_slot: Slot = ()):
    if solution is None:
        print("No solution found (puzzle may be unsolvable from this state).")
        return

    all_blocks = {b.id: b for b in blocks}
    state: State = (make_initial_counters(blocks), init_slot)

    print(f"\nSolution found — {len(solution)} moves:\n")
    for step_idx, bid in enumerate(solution, 1):
        b = all_blocks[bid]
        prev_counter = dict(state[0]).get(bid, 0)
        state = step(state, bid, all_blocks)
        slot_str = " | ".join(state[1]) if state[1] else "(empty)"

        kind_tag = ""
        if b.kind == FROZEN:
            kind_tag = f"  [FROZEN, thawed at {prev_counter}/{b.threshold}]"
        elif b.kind == BOMB:
            kind_tag = f"  [BOMB defused at {prev_counter}/{b.threshold}]"

        print(f"  Step {step_idx:>3}: click #{bid:>3}  {b.color:<10}"
              f"  layer={b.layer}  pos=({b.x},{b.y}){kind_tag}"
              f"\n           slot → [{slot_str}]")

        # Show frozen progress and bomb timers for remaining blocks
        warn = []
        for cbid, cnt in state[0]:
            cb = all_blocks[cbid]
            if cb.kind == BOMB and cnt > 0:
                warn.append(f"#{cbid} bomb {cnt}/{cb.threshold}")
            elif cb.kind == FROZEN and 0 < cnt < cb.threshold:
                warn.append(f"#{cbid} frozen {cnt}/{cb.threshold}")
        if warn:
            print(f"           status: {', '.join(warn)}")

    print("\nAll blocks cleared! ✓")


# ---------------------------------------------------------------------------
# ══════════════════════════════════════════════════════════════════════════
#  PUZZLE DEFINITION — edit this section to match your actual stage
# ══════════════════════════════════════════════════════════════════════════
#
# Block(id, color, layer, x, y, w=1, h=1, kind="normal", threshold=None)
#
#   kind:
#     "normal"  default
#     "frozen"  needs `threshold` clicks of OTHER blocks while exposed
#               before it becomes clickable (default threshold = 3)
#     "bomb"    explodes after `threshold` clicks of OTHER blocks while
#               exposed if you don't click it in time
#               (default threshold = 5)
#
# Example: 9 normal blocks + 1 frozen + 1 bomb
# ---------------------------------------------------------------------------

BLOCKS = [
    # layer 0 — bottom
    Block( 1, "red",    0,  0, 0),
    Block( 2, "red",    0,  1, 0),
    Block( 3, "blue",   0,  2, 0),
    Block( 4, "blue",   0,  0, 1),
    Block( 5, "yellow", 0,  1, 1),
    Block( 6, "yellow", 0,  2, 1),

    # layer 1 — covers some layer-0 blocks
    Block( 7, "red",    1,  0, 0),   # covers #1
    Block( 8, "blue",   1,  1, 0),   # covers #2 and #5
    Block( 9, "yellow", 1,  2, 0),   # covers #3 and #6

    # layer 2 — sits on top of #8 as a frozen blue block
    Block(10, "blue",   2,  1, 0, kind=FROZEN, threshold=3),

    # layer 2 — sits on top of #9 as a bomb (yellow); 5 clicks to defuse
    Block(11, "yellow", 2,  2, 0, kind=BOMB,   threshold=5),
]

# Mid-game initial slot (e.g. ("red", "blue")). Use () if starting fresh.
INITIAL_SLOT: Slot = ()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Validate / replay INITIAL_SLOT through slot_add to handle pre-existing
    # matches and overflow.
    sim_slot: Slot = ()
    for color in INITIAL_SLOT:
        sim_slot = slot_add(sim_slot, color)
        if sim_slot is None:
            print("ERROR: INITIAL_SLOT already overflows (> 7 tiles).")
            raise SystemExit(1)

    print("Searching for solution …")
    solution = solve_from(BLOCKS, sim_slot)
    print_solution(solution, BLOCKS, sim_slot)
