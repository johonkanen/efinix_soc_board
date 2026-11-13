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
OUTLINE = [   # since 2026-11-13 for the AP61302 / AP61102 cells (VIN pours 1.06 mm further along, EN out past the inductor)
    (143.0, 56.7), (147.5, 56.7), (147.6, 58.75), (145.8, 58.75), (142.6, 60.6),     # head at U341 (VIN pour, C341)
    (142.6, 94.8), (148.7, 94.8), (148.7, 95.5), (145.3, 95.5),                      # finger to the EN stub of U311 ...
    (145.3, 98.4), (146.4, 98.4), (146.4, 100.5), (142.6, 100.5),                    # ... and round a B.Cu track of
                                                                                     # U1302 (x 144.3) to C311
    (142.6, 109.0),                                                                  # west strip meets the trunk
    (159.2, 109.0), (159.2, 105.0), (160.5, 105.0), (160.5, 109.0),                  # finger to U331 (C331)
    (166.6, 109.0), (166.6, 100.6), (167.3, 100.6), (167.3, 109.0),                  # finger to the EN stub of U201
    (171.2, 109.0), (171.2, 103.6), (172.6, 103.6), (172.6, 109.0),                  # finger to U201 (C201)
    (177.7, 109.0), (177.7, 100.3), (178.45, 100.3), (178.45, 103.8),                # finger to the EN stub of U301, R401
    (181.2, 103.8), (181.2, 103.3), (183.7, 103.3),                                  # finger to U301 (C301)
    (183.7, 108.4), (190.5, 108.4), (190.5, 109.0),                                  # input caps C101-C103
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
