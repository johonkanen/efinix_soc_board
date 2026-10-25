#!/usr/bin/env python3
"""Copy footprint poses (position, orientation, side, lock) from a placed board onto kicad/ti135_card.kicad_pcb
(run under KiCad's python: tools/p2k/bin/kipy tools/apply_placement.py PLACED.kicad_pcb [--keep-locks]).
--keep-locks keeps this board's lock flags (for a partial re-placement made on a copy with extra parts locked).

The placed board is a KiCadRoutingTools place_simple seed made from this board (work/place/, see STATUS.md), so the
footprints match by reference. A part only on this board (added to the schematic since) keeps make_board's staging
position off the board and is listed; a part only on the placed board is ignored.
"""
import os
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb")


def main():
    src = {fp.GetReference(): fp for fp in pcbnew.LoadBoard(sys.argv[1]).GetFootprints()}
    board = pcbnew.LoadBoard(PCB)
    dst = {fp.GetReference(): fp for fp in board.GetFootprints()}
    new = sorted(set(dst) - set(src))
    for ref, s in src.items():
        d = dst.get(ref)
        if d is None:
            continue
        if d.IsFlipped() != s.IsFlipped():
            d.Flip(d.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        d.SetOrientation(s.GetOrientation())
        d.SetPosition(s.GetPosition())
        if "--keep-locks" not in sys.argv:
            d.SetLocked(s.IsLocked())
    pcbnew.SaveBoard(PCB, board)
    print(f"apply_placement: {len(dst) - len(new)} footprints placed from {os.path.relpath(sys.argv[1], ROOT)}"
          + (f"; not on it, left in staging: {', '.join(new)}" if new else ""))


if __name__ == "__main__":
    main()
