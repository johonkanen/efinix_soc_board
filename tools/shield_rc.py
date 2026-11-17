#!/usr/bin/env python3
"""Board side of the Ethernet shield RC (tools/shield_rc_sch.py, then tools/add_parts.py, then this):
    tools/p2k/bin/kipy tools/shield_rc.py IN.kicad_pcb OUT.kicad_pcb
C952 (1 nF 2 kV) sits on B.Cu beside the north shield tab, R951 (1 M) beside the south one, both with the shield
pad east and the GND pad west, on the GND vias that tools/j9_no_pour.py put at x 189.44. The direct GND tracks
of J9's pins go. The two tabs and pin 10 (CHS) are joined by 0.3 mm B.Cu tracks under the jack."""
import sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); MM = pcbnew.FromMM; TOMM = pcbnew.ToMM
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
BC = pcbnew.B_Cu; SH = "/09 ethernet/eth_shield"
j9 = b.FindFootprintByReference("J9")
ends = [p.GetPosition() for p in j9.Pads() if p.GetNetname() == SH]
assert len(ends) == 3, "run tools/add_parts.py first"
# the tracks and vias of tools/j9_no_pour.py follow their pad to eth_shield when the board is loaded: the tracks
# go, the via at pin 10 goes, the other two vias are GND again
for t in list(b.GetTracks()):
    if t.GetNetname() not in ("GND", SH):
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        if (t.GetPosition() - P(189.44, 55.91)).EuclideanNorm() < MM(0.01):
            b.Delete(t)
        elif any((t.GetPosition() - P(189.44, y)).EuclideanNorm() < MM(0.01) for y in (53.88, 69.37)):
            t.SetNet(b.FindNet("GND"))
    elif t.GetLayer() == BC and any((t.GetStart() - e).EuclideanNorm() < MM(0.01) for e in ends):
        b.Delete(t)


def seg(pts, net):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetLayer(BC); t.SetWidth(MM(0.3)); t.SetNet(b.FindNet(net)); b.Add(t)


for ref, y in (("C952", 53.88), ("R951", 69.37)):
    f = b.FindFootprintByReference(ref)
    if f.GetLayer() != BC:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetPosition(P(193.2, y)); f.SetOrientationDegrees(0)
    if next(p for p in f.Pads() if p.GetNetname() == SH).GetPosition().x < f.GetPosition().x:
        f.SetOrientationDegrees(180)
    f.Reference().SetVisible(False)
    for p in f.Pads():
        x = TOMM(p.GetPosition().x)
        seg([(x, y), (197.92, y)] if p.GetNetname() == SH else [(x, y), (189.44, y)], p.GetNetname())
    print(f"   {ref} {f.GetValue()}: B.Cu at (193.2, {y}), shield pad east")
seg([(194.62, 55.91), (195.89, 55.91), (197.92, 53.88)], SH)          # CHS pin to the north tab
seg([(197.92, 53.88), (197.92, 69.37)], SH)                           # tab to tab
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.BuildConnectivity(); print("   open connections:", b.GetConnectivity().GetUnconnectedCount(False))
b.Save(sys.argv[2])
