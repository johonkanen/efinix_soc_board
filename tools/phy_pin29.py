#!/usr/bin/env python3
"""Connect U901 pin 29 (3V3) to the 3V3 plane with a via in the pad (kipy):

    phy_pin29.py rm IN OUT     remove the redundant B.Cu loop of phy_vdd10 below the pin (its own run)
    phy_pin29.py via IN OUT    add the via and refill

The pin cannot leave on F.Cu (phy_rx_ctl runs 0.3 mm in front of pins 28-30) and phy_rxc lies on In2 under the
pad at x 183.05. The one legal via site is the west tip of the pad at (182.72, 62.99): 0.11 mm to the vias of
pins 28 and 30, 0.12 mm to phy_rxc on In2. On B.Cu it only fits once the little loop of phy_vdd10 at y 63.3 is
gone; the via of pin 30 keeps its direct track to C933.
"""
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
SITE = (182.72, 62.99)
mode, src, out = sys.argv[1:4]
b = pcbnew.LoadBoard(src)
if mode == "rm":
    gone = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.B_Cu
            and t.GetNetname().endswith("phy_vdd10")
            and all(182.65 < MM(q.x) < 183.05 and 63.25 < MM(q.y) < 63.45 for q in (t.GetStart(), t.GetEnd()))
            and not (abs(MM(t.GetStart().x) - 182.7) < 0.01 and abs(MM(t.GetEnd().y) - 63.72) < 0.02)]
    for t in gone:
        print("remove", MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y))
    for t in gone:
        b.Remove(t)
else:
    pad = next(p for p in b.FindFootprintByReference("U901").Pads() if p.GetNumber() == "29")
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(FM(SITE[0]), FM(SITE[1]))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(FM(0.3)); v.SetDrill(FM(0.15)); v.SetNet(pad.GetNet()); b.Add(v)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(out, b)
