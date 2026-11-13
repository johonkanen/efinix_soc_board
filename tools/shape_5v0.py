#!/usr/bin/env python3
"""Shape the 5V0 pour on B.Cu (kipy):  shape_5v0.py IN OUT

User decision 2026-11-13: 5 V only has to reach the VIN pin of each regulator, where the cell's own input caps sit
(tools/buck_cell.py: 10 u + 100 n on the cell's VIN and GND pours). So the pour 'plane:5V0' becomes a feeder instead
of an area fill: a trunk along the south edge from J101 / J6 and the input caps C101-C103, one finger up to the VIN
pour of U301, U201 and U331, fingers to the EN stubs of the group 1 cells (EN is tied to 5 V), a strip up the west side to U311 and U341, and a tab under U101 / C104.
"""
import sys

import pcbnew

FM = pcbnew.FromMM
OUTLINE = [
    (143.0, 56.7), (147.5, 56.7), (146.9, 58.2), (145.8, 58.5), (142.6, 60.6),      # head at U341 (VIN pour, C341)
    (142.6, 96.0), (148.3, 96.0), (148.3, 96.9), (145.3, 96.9),                      # finger to EN of U311 ...
    (145.3, 98.4), (146.4, 98.4), (146.4, 99.6), (142.6, 99.6),                      # ... and round a B.Cu track of
                                                                                     # U1302 (x 144.3) to C311
    (142.6, 109.0),                                                                  # west strip meets the trunk
    (158.1, 109.0), (158.1, 105.0), (159.5, 105.0), (159.5, 109.0),                  # finger to U331 (C331)
    (167.7, 109.0), (167.7, 101.2), (168.6, 101.2), (168.6, 109.0),                  # finger to EN of U201
    (170.1, 109.0), (170.1, 103.6), (171.5, 103.6), (171.5, 109.0),                  # finger to U201 (C201)
    (178.8, 109.0), (178.8, 100.9), (179.8, 100.9), (179.8, 103.8),                  # finger to EN of U301, R401
    (181.2, 103.8), (181.2, 103.3), (182.6, 103.3),                                  # finger to U301 (C301)
    (182.6, 108.4), (190.5, 108.4), (190.5, 109.0),                                  # input caps C101-C103
    (202.2, 109.0), (202.2, 112.6), (199.2, 112.6), (199.2, 114.5), (204.2, 114.5),  # J101, J6
    (204.2, 116.1), (191.1, 116.2), (188.3, 112.8),
    (137.6, 112.8), (137.6, 103.6), (139.6, 103.6),                                  # tab under U101 / C104 (F.Cu)
    (139.6, 60.6),
]


def main(src, out):
    b = pcbnew.LoadBoard(src)
    z = next(z for z in b.Zones() if z.GetZoneName() == "plane:5V0")
    o = z.Outline(); o.RemoveAllContours(); o.NewOutline()
    for x, y in OUTLINE:
        o.Append(pcbnew.VECTOR2I(FM(x), FM(y)))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)    # solid on the SMD caps, reliefs on J101 / J6
    z.UnFill()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(out, b)
    print(f"shape_5v0: {len(OUTLINE)} corners, filled area {z.GetFilledArea() / 1e12:.0f} mm2")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
