#!/usr/bin/env python3
"""Mirror each TLV62585 cell's support parts about the regulator's VIN-SW-GND axis (kipy; IN OUT).

The B.Cu cells came out of the template fit mirrored relative to the pins (CIN at the GND pin, COUT on the VIN side;
the fitter keeps footprint-frame offsets but the flip mirrors the pads). In the regulator frame (+y = pin 1 -> pin 3)
every member goes from (x, y) to (x, -y). A part whose pads lie along y also swaps its pad ends (rotate 180)."""
import math
import sys

import pcbnew

CELLS = [("U201", ["L201", "C201", "C202", "C203", "R201", "R202"]), ("U301", ["L301", "C301", "C302", "C303", "R301", "R302"]),
         ("U311", ["L311", "C311", "C312", "C313", "R311", "R312"]), ("U331", ["L331", "C331", "C332", "R331", "R332"]),
         ("U341", ["L341", "C341", "C342", "C343", "R341", "R342"])]
b = pcbnew.LoadBoard(sys.argv[1])
mm = pcbnew.ToMM


def padpos(f, n):
    return next((mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in f.Pads() if p.GetNumber() == n)


for u, members in CELLS:
    U = b.FindFootprintByReference(u)
    p1, p3, p4, p6 = (padpos(U, n) for n in "1346")
    o = ((p1[0] + p3[0] + p4[0] + p6[0]) / 4, (p1[1] + p3[1] + p4[1] + p6[1]) / 4)
    ey = ((p3[0] - p1[0]), (p3[1] - p1[1])); n = math.hypot(*ey); ey = (ey[0] / n, ey[1] / n)
    for r in members:
        f = b.FindFootprintByReference(r)
        c = (mm(f.GetPosition().x), mm(f.GetPosition().y))
        d = (c[0] - o[0]) * ey[0] + (c[1] - o[1]) * ey[1]           # local y of the centre
        new = (c[0] - 2 * d * ey[0], c[1] - 2 * d * ey[1])
        a, z = padpos(f, "1"), padpos(f, "2")
        along_y = abs((z[0] - a[0]) * ey[0] + (z[1] - a[1]) * ey[1]) > 0.5 * math.hypot(z[0] - a[0], z[1] - a[1])
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(new[0]), pcbnew.FromMM(new[1])))
        if along_y:
            f.SetOrientationDegrees(f.GetOrientationDegrees() + 180)
pcbnew.SaveBoard(sys.argv[2], b)
print("mirror_buck_cells: done")
