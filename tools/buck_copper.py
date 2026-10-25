#!/usr/bin/env python3
"""Copper for the five TLV62585 cells on B.Cu (tools/p2k/bin/kipy tools/buck_copper.py IN.kicad_pcb OUT.kicad_pcb).

One layout, TI SLVSDE5F Figure 24 turned to the footprint frame (the placement template, placement/sketches),
written in the regulator's own pin frame and copied to every cell through its pad positions. The frame is taken
from the pads themselves, so the bottom-side mirror comes out right:
  +x = pin 3 (VIN) -> pin 4 (EN), +y = pin 1 (GND) -> pin 3 (VIN); origin = package centre.
- SW: pin 2 -> L pad 1, 0.35 mm through the pin column, 0.8 mm beyond it.
- VIN: pin 3 -> CIN pad 1 (0.4 mm); the B.Cu 5V0 region (placement/planes.json) also reaches both by fill.
- GND: a strip between the two pin rows (x = 0) from CIN's ground pad up to y = -1.0, then over to COUT's
  ground pad, with vias to In6 GND in the strip and at the far caps. Pin 1 joins the strip.
- VOUT: L pad 2 -> COUT1 pad 1 -> COUT2 pad 1 (0.7 mm), vias to the rail's plane (In3/In4) beside COUT; R1's
  sense end gets its own via to the plane. The 3V3 cell has no plane: its output is left to the router.
- FB: pin 5 -> R2 pad 1 -> R1 pad 2 (0.2 mm), on the side away from SW.
EN and PG are left to the router (EN is 5V0 or pg_group1, PG a power-good net).
Every via is placed at the nearest site that clears all foreign pads, tracks and vias on every layer (0.1 mm copper,
0.175 mm hole clearance): strip vias slide along the strip, the others search rings up to 1 mm. Run it on the board
before buck copper (it removes nothing).
"""
import math
import sys

import pcbnew

CELLS = [  # U, L, CIN, COUT list, R1 (VOUT-FB), R2 (FB-GND), output net, has plane
    ("U201", "L201", "C201", ["C202", "C203"], "R201", "R202", "VCORE", True),
    ("U301", "L301", "C301", ["C302", "C303"], "R301", "R302", "1V8", True),
    ("U311", "L311", "C311", ["C312", "C313"], "R311", "R312", "3V3", False),
    ("U331", "L331", "C331", ["C332"], "R331", "R332", "0V85", True),
    ("U341", "L341", "C341", ["C342", "C343"], "R341", "R342", "1V1", True),
]
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
LAYER = b.GetLayerID("B.Cu")


def pad(ref, num):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            q = p.GetPosition()
            return pcbnew.ToMM(q.x), pcbnew.ToMM(q.y), p.GetNet()
    raise KeyError((ref, num))


def track(a, c, w, net):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
    t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
    t.SetWidth(mm(w)); t.SetLayer(LAYER); t.SetNet(net)
    b.Add(t)


CLR, HOLE = 0.1, 0.175          # board copper clearance, hole clearance (drill edge to copper)
OBST = []                        # (kind, geometry, net code): foreign copper a through via must clear


def _load_obstacles():
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            OBST.append(("rect", (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()),
                                  pcbnew.ToMM(bb.GetBottom())), p.GetNetCode()))
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            q = t.GetPosition()
            OBST.append(("circle", (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y), pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2), t.GetNetCode()))
        else:
            a, c = t.GetStart(), t.GetEnd()
            OBST.append(("seg", (pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(c.x), pcbnew.ToMM(c.y),
                                 pcbnew.ToMM(t.GetWidth()) / 2), t.GetNetCode()))


def _gap(kind, g, x, y):
    if kind == "rect":
        dx = max(g[0] - x, 0, x - g[2]); dy = max(g[1] - y, 0, y - g[3]); return math.hypot(dx, dy)
    if kind == "circle":
        return math.hypot(x - g[0], y - g[1]) - g[2]
    ax, ay, cx, cy, hw = g
    L2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if L2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / L2))
    return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay))) - hw


def legal(p, dia, drill, net):
    need_cu, need_hole = dia / 2 + CLR, drill / 2 + HOLE
    return all(_gap(k, g, p[0], p[1]) >= max(need_cu, need_hole) - 1e-6 for k, g, n in OBST if n != net.GetNetCode())


def place_via(p, dia, drill, net, slide=None):
    """The legal via site nearest `p`: along `slide` (a unit vector, e.g. the GND strip) only, else on rings."""
    cands = [p]
    for r in [0.05 * k for k in range(1, 21)]:
        if slide:
            cands += [(p[0] + s * r * slide[0], p[1] + s * r * slide[1]) for s in (1, -1)]
        else:
            cands += [(p[0] + r * math.cos(a * math.pi / 8), p[1] + r * math.sin(a * math.pi / 8)) for a in range(16)]
    for c in cands:
        if legal(c, dia, drill, net):
            via(c, dia, drill, net)
            OBST.append(("circle", (c[0], c[1], dia / 2), net.GetNetCode()))
            return c
    print(f"  no legal site for a {net.GetNetname()} via near ({p[0]:.2f}, {p[1]:.2f}); skipped")
    return None


def via(p, dia, drill, net):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(p[0]), mm(p[1])))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(mm(dia)); v.SetDrill(mm(drill)); v.SetNet(net)
    b.Add(v)


_load_obstacles()
for u, l, cin, couts, r1, r2, rail, plane in CELLS:
    p1, p3, p4 = pad(u, "1"), pad(u, "3"), pad(u, "4")
    o = ((p1[0] + pad(u, "6")[0]) / 2 + (p3[0] - p1[0]) / 2, (p1[1] + pad(u, "6")[1]) / 2 + (p3[1] - p1[1]) / 2)
    ex = ((p4[0] - p3[0]) / math.hypot(p4[0] - p3[0], p4[1] - p3[1]), (p4[1] - p3[1]) / math.hypot(p4[0] - p3[0], p4[1] - p3[1]))
    ey = ((p3[0] - p1[0]) / math.hypot(p3[0] - p1[0], p3[1] - p1[1]), (p3[1] - p1[1]) / math.hypot(p3[0] - p1[0], p3[1] - p1[1]))

    def L(x, y):
        return (o[0] + x * ex[0] + y * ey[0], o[1] + x * ex[1] + y * ey[1])

    def P(ref, num):
        return pad(ref, num)[:2]

    gnd, sw, vout = p1[2], pad(u, "2")[2], pad(l, "2")[2]
    fb, vin = pad(u, "5")[2], p3[2]
    assert vout.GetNetname() == rail, (u, vout.GetNetname())
    # SW
    track(P(u, "2"), L(-1.6, 0), 0.35, sw)
    track(L(-1.6, 0), P(l, "1"), 0.8, sw)
    # VIN
    track(P(u, "3"), P(cin, "1"), 0.4, vin)
    # GND strip between the pin rows, pin 1, CIN / COUT grounds, vias to In6
    track(L(0, 2.04), L(0, -1.0), 0.34, gnd)
    track(P(u, "1"), L(0, -0.5), 0.25, gnd)
    track(L(0, 2.04), P(cin, "2"), 0.5, gnd)
    track(L(0, -1.0), L(1.2, -1.0), 0.34, gnd)
    track(L(1.2, -1.0), P(couts[0], "2"), 0.5, gnd)
    for vy in (0, 1.25):
        place_via(L(0, vy), 0.4, 0.2, gnd, slide=ey)
    v = place_via(L(0.947, 3.2), 0.45, 0.25, gnd)
    if v:
        track(P(cin, "2"), v, 0.5, gnd)
    v = place_via(L(3.35, 0), 0.45, 0.25, gnd)
    if v:
        track(P(r2, "2"), v, 0.3, gnd)
    prev = couts[0]
    for c in couts[1:]:
        track(P(prev, "2"), P(c, "2"), 0.6, gnd)
        track(P(prev, "1"), P(c, "1"), 0.6, vout)
        prev = c
    last = couts[-1]
    ly = {1: -2.035, 2: -4.105}[len(couts)]
    v = place_via(L(2.65, ly), 0.45, 0.25, gnd)
    if v:
        track(P(last, "2"), v, 0.5, gnd)
    # VOUT
    track(P(l, "2"), P(couts[0], "1"), 0.7, vout)
    if plane:
        for c, vy in zip(couts, (-3.3, -4.1) if len(couts) == 2 else (-2.9,)):
            v = place_via(L(-1.45, vy), 0.45, 0.25, vout)
            if v:
                track(v, P(c, "1"), 0.6, vout)
        v = place_via(L(2.272, 2.65), 0.3, 0.15, vout)
        if v:
            track(P(r1, "1"), v, 0.25, vout)
    # FB
    track(P(u, "5"), P(r2, "1"), 0.2, fb)
    track(P(r2, "1"), P(r1, "2"), 0.2, fb)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[2], b)
print("buck_copper:", ", ".join(c[0] for c in CELLS))
