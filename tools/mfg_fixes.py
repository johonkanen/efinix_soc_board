#!/usr/bin/env python3
"""Board side of the fixes from the manufacturability check of 2026-11-17 (reports/mfg_check/). Run after
tools/mfg_fixes_sch.py, tools/io_swap.py (no arguments) and tools/add_parts.py on the same board:
    tools/p2k/bin/kipy tools/mfg_fixes.py IN.kicad_pcb OUT.kicad_pcb
- lcd_mosi / lcd_miso: the two nets exchange names (pads were re-netted by add_parts.py); copper unchanged.
- U501 escape vias that sat 0.2-0.35 mm beside their ball (H5, G6, F5, L8, H6; from the J5 re-route) are
  centred in the ball like the other via-in-pad balls; the F.Cu stub goes, the inner track is extended.
- U1204 pin 5 (A3) gets a GND via. R804 (10k, ddr_rst_n to GND) is placed on B.Cu at U801 T11's via.
- Three junctions that overlapped by 0.05-0.08 mm get a segment into the pad / via.
- Reference designators are hidden (no reference silkscreen on this card; pin-1 marks stay).
- Zones are refilled with the hole-to-zone rules added to kicad/ti135_card.kicad_dru."""
import math
import sys

_src = open(__file__.replace("mfg_fixes.py", "pll_place.py")).read()
__file__ = __file__.replace("mfg_fixes.py", "pll_place.py")
exec(_src.split("for ref in (\"C504\", \"C5064\", \"C5072\"):")[0])      # board b, Geo, geo, do, P, MM, TOMM, BC
F = pcbnew.F_Cu


def xy(v):
    return TOMM(v.x), TOMM(v.y)


def seg(a, c, netname, layer, w):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetLayer(layer); t.SetWidth(MM(w))
    t.SetNet(b.FindNet(netname)); b.Add(t); return t


def pad(ref, num):
    return next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)


# ---- lcd_mosi <-> lcd_miso ----
if pad("U501", "H6").GetNetname() == "/lcd_miso" and pad("J5", "6").GetNetname() == "/lcd_miso":
    c = pad("U501", "H6").GetPosition()
    seed = next((t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and (t.GetPosition() - c).EuclideanNorm() < MM(0.5)
                 and t.GetNetname() in ("/lcd_mosi", "/lcd_miso")), None)
    if seed is not None and seed.GetNetname() == "/lcd_mosi":
        a, m = b.FindNet("/lcd_mosi"), b.FindNet("/lcd_miso"); n = 0
        for t in b.GetTracks():
            if t.GetNetCode() == a.GetNetCode():
                t.SetNet(m); n += 1
            elif t.GetNetCode() == m.GetNetCode():
                t.SetNet(a); n += 1
        print(f"   lcd_mosi / lcd_miso: {n} tracks and vias renamed")
else:
    sys.exit("run tools/add_parts.py first: U501 H6 / J5 pin 6 are not on lcd_miso")

# ---- ball vias ----
u = b.FindFootprintByReference("U501")
# K6 stays 0.10 mm off centre (hole inside the ball pad): centred, it would touch C564's GND pad on B.Cu.
# H5 centred needs t_irq's In5 track moved into the middle of the channels between the ball vias.
for t in list(b.GetTracks()):
    if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == "/t_irq" and t.GetLayer() == pcbnew.In5_Cu and \
       {xy(t.GetStart()), xy(t.GetEnd())} == {(168.5, 82.8), (169.95, 84.25)}:
        b.Delete(t)
        pts = [(168.5, 82.8), (168.5, 82.95), (168.95, 83.4), (169.45, 83.4), (169.6, 83.55), (169.6, 83.9), (169.95, 84.25)]
        for q0, q1 in zip(pts, pts[1:]):
            seg(q0, q1, "/t_irq", pcbnew.In5_Cu, 0.12)
        print("   t_irq: In5 track moved to the middle of the via channels at H5")
for ball in ("H5", "G6", "F5", "L8", "H6"):
    p = pad("U501", ball); c = p.GetPosition(); n = p.GetNetname(); cx, cy = xy(c)
    vs = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == n and MM(0.03) < (t.GetPosition() - c).EuclideanNorm() < MM(0.45)]
    if len(vs) != 1:
        print(f"   {ball}: {len(vs)} off-centre vias, left"); continue
    v = vs[0]; old = v.GetPosition(); ox, oy = xy(old)
    hit = [(f.GetReference(), q.GetNumber(), q.GetNetname()) for f in b.GetFootprints() if f.GetReference() != "U501"
           for q in f.Pads() if q.IsOnCopperLayer() and q.GetBoundingBox().Contains(c) and q.GetNetname() != n]
    if hit:
        print(f"   {ball}: far-side pad {hit} at the ball centre, via left at ({ox}, {oy})"); continue
    lay = None
    for t in list(b.GetTracks()):
        if t.Type() == pcbnew.PCB_VIA_T or t.GetNetname() != n:
            continue
        s, e = t.GetStart(), t.GetEnd()
        if t.GetLayer() == F and (s - c).EuclideanNorm() < MM(0.45) and (e - c).EuclideanNorm() < MM(0.45):
            b.Delete(t)
        elif t.GetLayer() != F and ((s - old).EuclideanNorm() < MM(0.01) or (e - old).EuclideanNorm() < MM(0.01)):
            lay = (t.GetLayer(), TOMM(t.GetWidth()))
    v.SetPosition(c)
    if lay:
        seg((ox, oy), (cx, cy), n, lay[0], lay[1])
    print(f"   {ball} {n.split('/')[-1]}: via ({ox:.2f}, {oy:.2f}) -> ball centre ({cx:.2f}, {cy:.2f}), {b.GetLayerName(lay[0]) if lay else 'no inner track'}")

# ---- U1204 pin 5 to GND ----
p5 = pad("U1204", "5"); px, py = xy(p5.GetPosition())
assert p5.GetNetname() == "GND", "run tools/add_parts.py first"
for t in list(b.GetTracks()):
    if t.GetNetname().startswith("unconnected-(U1204-A3"):
        b.Delete(t)
# the only free spot is outside the pad row (the escapes of pins 3-10 fill the space under the body)
v = pcbnew.PCB_VIA(b); v.SetPosition(P(px, py - 1.2)); v.SetWidth(F, MM(0.3)); v.SetDrill(MM(0.15)); v.SetLayerPair(F, BC)
v.SetNet(b.FindNet("GND")); b.Add(v); seg((px, py), (px, py - 1.2), "GND", F, 0.15)
print(f"   U1204 pin 5: GND via at ({px:.2f}, {py - 1.2:.2f})")

# ---- thin junctions ----
c = pad("J5", "7").GetPosition()
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == "/lcd_led" and t.GetLayer() == F:
        for e in (t.GetStart(), t.GetEnd()):
            if MM(0.3) < (e - c).EuclideanNorm() < MM(1.0):
                seg(xy(e), xy(c), "/lcd_led", F, 0.12); print("   lcd_led: track run to the centre of J5 pin 7"); break
p4 = pad("U1302", "4"); c = p4.GetPosition(); lay = b.FindFootprintByReference("U1302").GetLayer()
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_VIA_T and t.GetNetCode() == p4.GetNetCode() and t.GetLayer() == lay:
        for e in (t.GetStart(), t.GetEnd()):
            if MM(0.2) < (e - c).EuclideanNorm() < MM(0.7) and abs(e.x - c.x) > MM(0.2):
                seg(xy(e), (TOMM(c.x) - 0.05, TOMM(e.y)), p4.GetNetname(), lay, 0.12); print("   U1302 pin 4: track run into the pad")
vc = P(172.626, 96.181)
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == "VCORE" and t.GetLayer() == F and TOMM(t.GetWidth()) == 0.2:
        for e in (t.GetStart(), t.GetEnd()):
            if MM(0.15) < (e - vc).EuclideanNorm() < MM(0.3):
                seg(xy(e), xy(vc), "VCORE", F, 0.2); print("   VCORE sense: track run to the via centre"); break

# ---- reference designators off the silkscreen ----
n = 0
for f in b.GetFootprints():
    if f.Reference().IsVisible():
        f.Reference().SetVisible(False); n += 1
print(f"   {n} reference designators hidden")

# ---- R804 ----
if b.FindFootprintByReference("R804") is None:
    print("   R804 is not on the board (tools/add_parts.py)")
else:
    geo = Geo(); N = "/08 lpddr4/ddr_rst_n"
    if not (do("R804", N, "GND", (161.6, 62.37), 3.0, 1.2) or do("R804", N, "GND", (163.6, 73.4), 3.0, 1.2)):
        print("   R804: NOT PLACED")
    for t in b.GetTracks():                                 # the net is in the LPDDR4 class: 0.11 mm at most near the balls
        if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == N and t.GetLayer() == BC:
            t.SetWidth(MM(0.1))
    b.FindFootprintByReference("R804").Reference().SetVisible(False)
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.BuildConnectivity(); print("   open connections:", b.GetConnectivity().GetUnconnectedCount(False))
b.Save(sys.argv[2])
