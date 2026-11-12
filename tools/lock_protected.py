#!/usr/bin/env python3
"""Lock everything in protected_baseline.json on the board: the tier A tracks and vias, the
tier B rail copper inside the frozen regions, and the protected footprints.

    tools/p2k/bin/kipy tools/lock_protected.py [BOARD]

Run verify_protected.py snapshot first. Locking changes no geometry.
"""
import sys, json, os
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verify_protected import item_key, BASELINE

board_path = sys.argv[1] if len(sys.argv) > 1 else "kicad/ti135_card.kicad_pcb"
base = json.load(open(BASELINE))
keys = {n: {json.dumps(k) for k in v} for n, v in base["nets"].items()}
b = pcbnew.LoadBoard(board_path)
nt = nf = 0
for t in b.GetTracks():
    if json.dumps(item_key(b, t)) in keys.get(t.GetNetname(), ()):
        t.SetLocked(True); nt += 1
for f in b.GetFootprints():
    if f.GetReference() in base["footprints"]:
        f.SetLocked(True); nf += 1
pcbnew.SaveBoard(board_path, b)
print(f"locked {nt} tracks/vias and {nf} footprints")
