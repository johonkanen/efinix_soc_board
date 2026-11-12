#!/usr/bin/env python3
"""Delete locked (frozen, tier B) rail stubs that DRC reports as dangling, near given points only:

    tools/p2k/bin/kipy tools/remove_frozen_stubs.py BOARD DRC.json R "X Y" ...

Allowed by the user on 2026-11-12 for the stubs left at the old pads of C5056, C5055, C5027 and C5054.
Only tracks (never vias) on GND/1V1/1V8 whose DRC position is within R mm of one of the points are removed.
The protected baseline has to be re-taken afterwards."""
import sys, json, math
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); drc = json.load(open(sys.argv[2])); R = float(sys.argv[3])
pts = [tuple(map(float, s.split())) for s in sys.argv[4:]]
mm = pcbnew.ToMM; n = 0
for v in drc["violations"]:
    if v["type"] != "track_dangling":
        continue
    it = v["items"][0]; x, y = it["pos"]["x"], it["pos"]["y"]
    if not any(math.hypot(x - px, y - py) <= R for px, py in pts):
        continue
    for t in list(b.GetTracks()):
        if t.Type() == pcbnew.PCB_VIA_T or t.GetNetname() not in ("GND", "1V1", "1V8") or t.GetLayerName() != "B.Cu":
            continue
        if f"[{t.GetNetname()}]" not in it["description"]:
            continue
        ends = [(mm(p.x), mm(p.y)) for p in (t.GetStart(), t.GetEnd())]
        if any(math.hypot(x - ex, y - ey) < 0.01 for ex, ey in ends):
            print("removed %s %.3f %.3f -> %.3f %.3f%s" % (t.GetNetname(), *ends[0], *ends[1], " (locked)" if t.IsLocked() else ""))
            b.RemoveNative(t); n += 1; break
pcbnew.SaveBoard(sys.argv[1], b)
print(f"removed {n}")
