#!/usr/bin/env python3
"""Remove unlocked vias/tracks by position:  kipy tools/remove_items.py BOARD "NET X Y [R]" ...
Removes every unlocked via centred, or track with an end, within R (default 0.2 mm) of (X, Y) on NET.
Refuses nets in protected_nets.txt tier A and anything locked."""
import sys, math
import pcbnew

tierA = {l.split("\t")[1] for l in open("protected_nets.txt") if l.startswith("A\t")}
b = pcbnew.LoadBoard(sys.argv[1]); n = 0
for spec in sys.argv[2:]:
    parts = spec.split(); net, x, y = parts[0], float(parts[1]), float(parts[2]); r = float(parts[3]) if len(parts) > 3 else 0.2
    if net in tierA:
        sys.exit(f"{net} is protected")
    victims = []
    for t in b.GetTracks():
        if t.GetNetname() != net or t.IsLocked():
            continue
        pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
        if any(math.hypot(pcbnew.ToMM(p.x) - x, pcbnew.ToMM(p.y) - y) <= r for p in pts):
            victims.append(t)
    for t in victims:
        b.RemoveNative(t); n += 1
pcbnew.SaveBoard(sys.argv[1], b)
print("removed", n)
