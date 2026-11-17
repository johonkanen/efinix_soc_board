#!/usr/bin/env python3
"""Plane changes after the decoupling and filter parts moved (user, 2026-11-17):
    tools/p2k/bin/kipy tools/plane_fixes.py IN.kicad_pcb OUT.kicad_pcb
1. Regulator outputs. When C204 / C202 (VCORE) and C5020 (1V8) were moved, two vias of each output row came under
   or beside a GND pad and KiCad made them GND: VCORE 5 -> 3 plane vias, 1V8 6 -> 4, and each B.Cu output pour
   fell into two pieces. The VCORE via that no pad touches, (170.63, 96.18), goes back to VCORE; the others touch
   a capacitor's GND pad and stay GND (they are that capacitor's ground vias now). New 0.45 / 0.25 vias are added
   in the piece of the pour that holds the inductor, where one fits: five in all on each rail.
2. In3: the 1V1 region's arm east of U501 (x 172.85-178.72, y 70.69-81.6) fed C538-C542, which are gone from
   there. It is cut off; the GND zone of In3 (lowest priority) fills the area."""
import math
import sys

_src = open(__file__.replace("plane_fixes.py", "pll_place.py")).read()
__file__ = __file__.replace("plane_fixes.py", "pll_place.py")
exec(_src.split("for ref in (\"C504\", \"C5064\", \"C5072\"):")[0])      # board b, Geo, geo, rail_plane, P, MM, TOMM


def refill():
    zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)


for x, y, rail in ((170.63, 96.18, "VCORE"),):
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T and abs(TOMM(t.GetPosition().x) - x) < 0.01 and abs(TOMM(t.GetPosition().y) - y) < 0.01 and t.GetNetname() == "GND":
            t.SetNet(b.FindNet(rail)); print(f"   via at ({x}, {y}) back on {rail}")
refill(); geo = Geo()
for rail, ind, want, layer in (("VCORE", "L201", 5, pcbnew.In3_Cu), ("1V8", "L301", 6, pcbnew.In4_Cu)):
    z = next(z for z in b.Zones() if z.GetZoneName() == "buck_cell" and z.GetNetname() == rail and z.IsOnLayer(BC))
    fp_ = z.GetFilledPolysList(BC); bb = z.GetBoundingBox()
    lp = next(p for p in b.FindFootprintByReference(ind).Pads() if p.GetNetname() == rail).GetPosition()
    isl = next((i for i in range(fp_.OutlineCount()) if fp_.Outline(i).PointInside(lp)), None)
    have = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == rail and bb.Contains(t.GetPosition())
            and t.GetWidth(pcbnew.F_Cu) >= MM(0.4)]
    print(f"   {rail}: {fp_.OutlineCount()} piece(s) of output pour, {len(have)} large plane vias")
    plane = next(q for q in b.Zones() if q.GetNetname() == rail and q.IsOnLayer(layer) and q.GetZoneName().startswith("plane:"))
    added = []
    x0, y0, x1, y1 = TOMM(bb.GetLeft()), TOMM(bb.GetTop()), TOMM(bb.GetRight()), TOMM(bb.GetBottom())
    cand = []
    for i in range(int((x1 - x0) / 0.05) + 1):
        for j in range(int((y1 - y0) / 0.05) + 1):
            x, y = x0 + 0.05 * i, y0 + 0.05 * j; pt = P(x, y)
            if isl is None or not fp_.Outline(isl).PointInside(pt):
                continue
            if not all(fp_.Outline(isl).PointInside(P(x + ax, y + ay)) for ax, ay in ((0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3))):
                continue
            if geo.via_ok(x, y, rail, 0.225) and geo.disc_ok(x, y, rail, pcbnew.F_Cu, 0.3) and plane.HitTestFilledArea(layer, pt):
                cand.append((y, x))
    for y, x in sorted(cand):                                # nearest to the output edge first
        if len(have) + len(added) >= want:
            break
        if all(math.hypot(x - q[0], y - q[1]) >= 0.8 for q in added) and \
           all(math.hypot(x - TOMM(t.GetPosition().x), y - TOMM(t.GetPosition().y)) >= 0.8 for t in have):
            v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(pcbnew.F_Cu, MM(0.45)); v.SetDrill(MM(0.25))
            v.SetLayerPair(pcbnew.F_Cu, BC); v.SetNet(b.FindNet(rail)); b.Add(v); geo.add_track(v); added.append((x, y))
    print(f"   {rail}: new plane vias beside the inductor's part of the pour:", [(round(x, 2), round(y, 2)) for x, y in added])

z = next(z for z in b.Zones() if z.GetZoneName() == "plane:1V1")
cut = pcbnew.SHAPE_POLY_SET(); cut.NewOutline()
for x, y in ((172.85, 70.69), (179.5, 70.69), (179.5, 82.0), (172.85, 82.0)):
    cut.Append(MM(x), MM(y))
before = z.Outline().Area() / 1e12
z.Outline().BooleanSubtract(cut)
print(f"   1V1 region on In3: {before:.0f} -> {z.Outline().Area() / 1e12:.0f} mm2 (east arm removed), outlines {z.Outline().OutlineCount()}")
refill()
b.BuildConnectivity(); print("   open connections:", b.GetConnectivity().GetUnconnectedCount(False))
b.Save(sys.argv[2])
