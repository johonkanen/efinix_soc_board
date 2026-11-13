#!/usr/bin/env python3
"""Tie pads on the other side of the board to a pour with a via each (kipy):

    pour_vias.py IN OUT ZONE_NAME REF.PAD [REF.PAD ...]      e.g. plane:5V0 U101.1 U101.3 C104.1 R401.1

For each pad: a via (0.3/0.15) in the pad, else within 1.2 mm of it with a 0.2 mm track on the pad's layer. The via
must be legal on every layer (0.1 mm copper, 0.175 mm hole to copper, 0.2 mm hole to hole) and land on the filled
copper of the named zone (same net as the pad). Zones are refilled at the end.
"""
import math
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
CLR, HOLE, H2H = 0.1, 0.175, 0.2
VIA, DRILL, TRK = 0.3, 0.15, 0.2

b = pcbnew.LoadBoard(sys.argv[1])
zone = next(z for z in b.Zones() if z.GetZoneName() == sys.argv[3])
zl = zone.GetLayerSet().Seq()[0]
items = []      # kind, geometry, net code, layer name or None (= all layers), drill radius
for f in b.GetFootprints():
    for p in f.Pads():
        if p.IsOnCopperLayer():
            bb = p.GetBoundingBox()
            through = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            items.append(("rect", (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())), p.GetNetCode(),
                          None if through else f.GetLayerName(), 0))
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        q = t.GetPosition()
        items.append(("circle", (MM(q.x), MM(q.y), MM(t.GetWidth(pcbnew.B_Cu)) / 2), t.GetNetCode(), None, MM(t.GetDrill()) / 2))
    else:
        pts = [t.GetStart(), t.GetMid(), t.GetEnd()] if isinstance(t, pcbnew.PCB_ARC) else [t.GetStart(), t.GetEnd()]
        for a, c in zip(pts, pts[1:]):
            items.append(("seg", (MM(a.x), MM(a.y), MM(c.x), MM(c.y), MM(t.GetWidth()) / 2 + (0.05 if len(pts) == 3 else 0)),
                          t.GetNetCode(), t.GetLayerName(), 0))


def gap(kind, g, x, y):
    if kind == "rect":
        return math.hypot(max(g[0] - x, 0, x - g[2]), max(g[1] - y, 0, y - g[3]))
    if kind == "circle":
        return math.hypot(x - g[0], y - g[1]) - g[2]
    ax, ay, cx, cy, hw = g
    l2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
    return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay))) - hw


def via_ok(p, code):
    need = max(VIA / 2 + CLR, DRILL / 2 + HOLE) - 1e-6
    for k, g, n, lay, dr in items:
        d = gap(k, g, p[0], p[1])
        if n != code and d < need:
            return False
        if k == "circle" and d + g[2] < dr + DRILL / 2 + H2H - 1e-6:
            return False
    return True


def seg_ok(a, c, code, layer):
    n_s = max(2, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.04)); need = TRK / 2 + CLR - 1e-6
    for i in range(n_s + 1):
        x, y = a[0] + (c[0] - a[0]) * i / n_s, a[1] + (c[1] - a[1]) * i / n_s
        if any(n != code and lay in (None, layer) and gap(k, g, x, y) < need for k, g, n, lay, dr in items):
            return False
    return True


def on_pour(p):
    return all(zone.HitTestFilledArea(zl, pcbnew.VECTOR2I(FM(p[0] + dx), FM(p[1] + dy)))
               for dx, dy in ((0, 0), (.2, 0), (-.2, 0), (0, .2), (0, -.2)))


done, left = [], []
for spec in sys.argv[4:]:
    ref, num = spec.split(".")
    f = b.FindFootprintByReference(ref); p = next(q for q in f.Pads() if q.GetNumber() == num)
    assert p.GetNetCode() == zone.GetNetCode(), spec
    c = (MM(p.GetPosition().x), MM(p.GetPosition().y)); code = p.GetNetCode()
    cands = [c] + [(c[0] + r * math.cos(a * math.pi / 12), c[1] + r * math.sin(a * math.pi / 12))
                   for r in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2) for a in range(24)]
    for q in cands:
        if via_ok(q, code) and on_pour(q) and (q == c or seg_ok(c, q, code, f.GetLayerName())):
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(FM(q[0]), FM(q[1]))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(FM(VIA)); v.SetDrill(FM(DRILL)); v.SetNet(p.GetNet()); b.Add(v)
            items.append(("circle", (q[0], q[1], VIA / 2), code, None, DRILL / 2))
            if q != c:
                t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(c[0]), FM(c[1]))); t.SetEnd(pcbnew.VECTOR2I(FM(q[0]), FM(q[1])))
                t.SetWidth(FM(TRK)); t.SetLayer(f.GetLayer()); t.SetNet(p.GetNet()); b.Add(t)
                items.append(("seg", (c[0], c[1], q[0], q[1], TRK / 2), code, f.GetLayerName(), 0))
            done.append(f"{spec} {'in pad' if q == c else f'{math.hypot(q[0] - c[0], q[1] - c[1]):.1f} mm beside'} at ({q[0]:.2f}, {q[1]:.2f})")
            break
    else:
        left.append(spec)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[2], b)
print("pour_vias:", "; ".join(done)); print("  no site:", " ".join(left) or "none")
