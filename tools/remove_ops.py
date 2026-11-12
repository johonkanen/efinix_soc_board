#!/usr/bin/env python3
"""Take copper that an earlier grid_router ops file added off the board again.

    tools/p2k/bin/kipy tools/remove_ops.py BOARD OPS.json NET_REGEX [X0 Y0 X1 Y1]

Removes the unlocked tracks and vias that match an entry of OPS.json exactly (ends, layer, net), for nets
matching NET_REGEX, optionally only inside the box. Only copper the router itself added can match."""
import sys, json, re
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); ops = json.load(open(sys.argv[2])); rx = sys.argv[3]
box = [float(v) for v in sys.argv[4:8]] if len(sys.argv) >= 8 else None
inside = lambda x, y: box is None or (box[0] <= x <= box[2] and box[1] <= y <= box[3])
MM = pcbnew.FromMM
want_t = {(MM(t["x1"]), MM(t["y1"]), MM(t["x2"]), MM(t["y2"]), t["layer"], t["net"]) for t in ops["tracks"]
          if re.search(rx, t["net"]) and inside(t["x1"], t["y1"]) and inside(t["x2"], t["y2"])}
want_v = {(MM(v["x"]), MM(v["y"]), v["net"]) for v in ops["vias"] if re.search(rx, v["net"]) and inside(v["x"], v["y"])}
n = 0
for t in list(b.GetTracks()):
    if t.IsLocked():
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        hit = (t.GetPosition().x, t.GetPosition().y, t.GetNetname()) in want_v
    else:
        hit = (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetLayerName(), t.GetNetname()) in want_t
    if hit:
        b.RemoveNative(t); n += 1
pcbnew.SaveBoard(sys.argv[1], b)
print(f"removed {n} of {len(want_t) + len(want_v)} listed items")
