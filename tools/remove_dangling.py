#!/usr/bin/env python3
"""Delete unlocked rail tracks and vias that DRC reports as dangling, near given points only:

    tools/p2k/bin/kipy tools/remove_dangling.py BOARD DRC.json R "X Y" ...

Only the reported item itself is removed (a track with an end at the DRC position, or the via centred there),
on GND/VCORE/1V1/1V8/3V3/0V85, and never a locked item. Run DRC again afterwards and repeat until nothing is left."""
import sys, json, math
import pcbnew

RAILS = ("GND", "VCORE", "1V1", "1V8", "3V3", "0V85")
b = pcbnew.LoadBoard(sys.argv[1]); drc = json.load(open(sys.argv[2])); R = float(sys.argv[3])
pts = [tuple(map(float, s.split())) for s in sys.argv[4:]]
mm = pcbnew.ToMM; n = 0
for v in drc["violations"]:
    if v["type"] not in ("track_dangling", "via_dangling"):
        continue
    it = v["items"][0]; x, y = it["pos"]["x"], it["pos"]["y"]; via = v["type"] == "via_dangling"
    if not any(math.hypot(x - px, y - py) <= R for px, py in pts):
        continue
    for t in list(b.GetTracks()):
        if t.IsLocked() or t.GetNetname() not in RAILS or f"[{t.GetNetname()}]" not in it["description"]:
            continue
        if via != (t.Type() == pcbnew.PCB_VIA_T):
            continue
        if via:
            hit = math.hypot(x - mm(t.GetPosition().x), y - mm(t.GetPosition().y)) < 0.01
        else:
            hit = t.GetLayerName() in it["description"] and any(math.hypot(x - mm(p.x), y - mm(p.y)) < 0.01 for p in (t.GetStart(), t.GetEnd()))
        if hit:
            print("removed %s %s at %.3f %.3f" % ("via" if via else "track", t.GetNetname(), x, y))
            b.RemoveNative(t); n += 1; break
pcbnew.SaveBoard(sys.argv[1], b)
print(f"removed {n}")
