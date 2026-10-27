#!/usr/bin/env python3
"""Replace the LPDDR4 copper of one board with that of another (kipy):
    transplant.py IN_MAIN FROM_BOARD OUT
Removes every track, arc and via of the LPDDR4 nets (`ddr_` in the name, not DDR_CAL) from IN_MAIN and copies those
of FROM_BOARD in (same net names, layers, widths, via sizes); everything else of IN_MAIN stays. Both boards must have
the same U501/U801 poses. Collects first, removes last (removing many items through SWIG garbles later lookups).
"""
import sys

import pcbnew


def is_ddr(name):
    short = name.split("/")[-1]
    return short.startswith("ddr_")


src, frm, dst = sys.argv[1:4]
b = pcbnew.LoadBoard(src)
f = pcbnew.LoadBoard(frm)
nets = {str(n): ni for n, ni in b.GetNetsByName().items()}

for ref in ("U501", "U801"):
    pa, pb = b.FindFootprintByReference(ref), f.FindFootprintByReference(ref)
    if pa.GetPosition() != pb.GetPosition() or pa.GetOrientationDegrees() != pb.GetOrientationDegrees():
        sys.exit(f"transplant: {ref} pose differs between the boards")

doomed = [t for t in b.GetTracks() if is_ddr(t.GetNetname())]
new, missing = [], set()
for t in f.GetTracks():
    name = t.GetNetname()
    if not is_ddr(name):
        continue
    if name not in nets:
        missing.add(name)
        continue
    c = t.Duplicate()
    new.append((c, name))
if missing:
    sys.exit(f"transplant: nets not on {src}: {sorted(missing)}")

for c, name in new:
    c.SetParent(b)
    b.Add(c)
    c.SetNet(nets[name])
for t in doomed:
    b.Remove(t)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
kind = lambda items: sum(isinstance(t, pcbnew.PCB_VIA) for t in items)
print(f"transplant: removed {len(doomed)} ({kind(doomed)} vias), added {len(new)} ({kind([c for c, _ in new])} vias)")
