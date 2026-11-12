#!/usr/bin/env python3
"""Remove the unlocked tracks (any end inside the box) and vias (centre inside) of nets matching a regex:

    tools/p2k/bin/kipy tools/rip_box.py BOARD NET_REGEX X0 Y0 X1 Y1 [LAYER,LAYER]

Refuses every net in protected_nets.txt. The nets are re-routed afterwards with tools/grid_router.py."""
import sys, re
import pcbnew

prot = {l.split("\t")[1] for l in open("protected_nets.txt") if l[:1] in "AB"}
b = pcbnew.LoadBoard(sys.argv[1]); rx = sys.argv[2]; x0, y0, x1, y1 = map(float, sys.argv[3:7])
layers = sys.argv[7].split(",") if len(sys.argv) > 7 else None
inside = lambda p: x0 <= pcbnew.ToMM(p.x) <= x1 and y0 <= pcbnew.ToMM(p.y) <= y1
n = 0; nets = set()
for t in list(b.GetTracks()):
    net = t.GetNetname()
    if not re.search(rx, net) or t.IsLocked():
        continue
    if net in prot:
        sys.exit(f"{net} is protected")
    if t.Type() == pcbnew.PCB_VIA_T:
        hit = layers is None and inside(t.GetPosition())
    else:
        hit = (inside(t.GetStart()) or inside(t.GetEnd())) and (layers is None or t.GetLayerName() in layers)
    if hit:
        b.RemoveNative(t); n += 1; nets.add(net)
pcbnew.SaveBoard(sys.argv[1], b)
print(f"ripped {n} items of {sorted(nets)}")
