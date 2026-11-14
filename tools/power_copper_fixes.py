#!/usr/bin/env python3
"""Power-copper touch-ups from the pre-order review of 2026-11-13 (kipy), one step per run so DRC can follow each:

    power_copper_fixes.py spokes IN OUT          5V0 pour: wider thermal spokes on the J6 / J101 pins (0.5 mm, was 0.25)
    power_copper_fixes.py pin21 IN OUT           U901 pin 21 (phy_vdd10): a via in its pad and a B.Cu link to C931
    power_copper_fixes.py widen IN OUT W UUID..  set these tracks to width W (see `candidates`)
    power_copper_fixes.py candidates IN          the 0.2 mm 3V3 tracks feeding the translators and the three
                                                 VCCIO33 balls of U501 (G7, J7, M21): uuid per line
    power_copper_fixes.py bridge IN OUT          5V0 west column: a second path round the via wall at y 101.3-102.
                                                 NOT APPLIED: the only legal bridge is 5.2 mm of 0.25 mm track on In2
                                                 (about 21 mOhm) beside a pinch of under 1 mOhm, so it carries nothing
    power_copper_fixes.py fiducials IN OUT       three fiducials per side (board-only footprints, not in BOM / CPL)
Legal = 0.1 mm copper, 0.175 mm hole to copper, 0.2 mm hole to hole, checked per layer here and by DRC afterwards.
"""
import math
import os
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
CLR, HOLE = 0.1, 0.175
CU = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "In5.Cu", "In6.Cu", "B.Cu"]


def seg_d(ax, ay, cx, cy, x, y):
    l2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
    return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay)))


class World:
    """Copper per layer: ('c', x, y, r, net, drill_r) circles, ('s', ax, ay, cx, cy, hw, net), ('r', x0, y0, x1, y1, net)."""
    def __init__(self, b):
        self.b = b
        self.L = {n: [] for n in CU}
        self.holes = []
        for t in b.GetTracks():
            n = t.GetNetname()
            if t.GetClass() == "PCB_VIA":
                q = t.GetPosition(); r = MM(t.GetWidth(pcbnew.F_Cu)) / 2
                for l in CU:
                    self.L[l].append(("c", MM(q.x), MM(q.y), r, n))
                self.holes.append((MM(q.x), MM(q.y), MM(t.GetDrill()) / 2, n))
            else:
                pts = [t.GetStart(), t.GetEnd()]
                if t.GetClass() == "PCB_ARC":
                    pts.insert(1, pcbnew.Cast_to_PCB_ARC(t).GetMid())
                for a, c in zip(pts, pts[1:]):
                    self.L[t.GetLayerName()].append(("s", MM(a.x), MM(a.y), MM(c.x), MM(c.y), MM(t.GetWidth()) / 2 + (0.02 if len(pts) == 3 else 0), n))
        for f in b.GetFootprints():
            for p in f.Pads():
                bb = p.GetBoundingBox(); g = (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
                for l in CU:
                    if p.IsOnLayer(b.GetLayerID(l)):
                        self.L[l].append(("r", *g, p.GetNetname()))
                if p.GetDrillSize().x > 0:
                    self.holes.append((MM(p.GetPosition().x), MM(p.GetPosition().y), MM(p.GetDrillSize().x) / 2, p.GetNetname()))

    @staticmethod
    def dist(it, x, y):
        if it[0] == "c":
            return math.hypot(x - it[1], y - it[2]) - it[3]
        if it[0] == "s":
            return seg_d(it[1], it[2], it[3], it[4], x, y) - it[5]
        return math.hypot(max(it[1] - x, 0, x - it[3]), max(it[2] - y, 0, y - it[4]))

    def point_ok(self, layer, x, y, r, net):
        return all(it[-1] == net or self.dist(it, x, y) >= r + CLR - 1e-6 for it in self.L[layer])

    def via_ok(self, x, y, dia, drill, net):
        if not all(self.point_ok(l, x, y, dia / 2, net) for l in CU):
            return False
        if not all(it[-1] == net or self.dist(it, x, y) >= drill / 2 + HOLE - 1e-6 for l in CU for it in self.L[l]):
            return False
        return all(math.hypot(x - hx, y - hy) >= drill / 2 + hr + 0.2 - 1e-6 for hx, hy, hr, _ in self.holes)

    def seg_ok(self, layer, a, c, w, net):
        m = max(2, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.04) + 1)
        return all(self.point_ok(layer, a[0] + (c[0] - a[0]) * i / m, a[1] + (c[1] - a[1]) * i / m, w / 2, net) for i in range(m + 1))


def add_via(b, x, y, dia, drill, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(FM(dia)); v.SetDrill(FM(drill)); v.SetNet(net); b.Add(v)


def add_track(b, a, c, w, layer, net):
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(a[0]), FM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(FM(c[0]), FM(c[1])))
    t.SetWidth(FM(w)); t.SetLayer(b.GetLayerID(layer)); t.SetNet(net); b.Add(t)


def save(b, out):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(out, b)


def spokes(b):
    z = next(z for z in b.Zones() if z.GetZoneName() == "plane:5V0")
    print("5V0 pour: spoke width", MM(z.GetThermalReliefSpokeWidth()), "-> 0.5, gap", MM(z.GetThermalReliefGap()))
    z.SetThermalReliefSpokeWidth(FM(0.5))


def pin21(b):
    w = World(b)
    u = b.FindFootprintByReference("U901")
    p = next(q for q in u.Pads() if q.GetNumber() == "21")
    c = next(q for q in b.FindFootprintByReference("C931").Pads() if q.GetNumber() == "1" and q.IsOnCopperLayer())
    net = p.GetNet(); name = net.GetNetname()
    bb = p.GetBoundingBox(); y = MM(p.GetPosition().y)
    cx, cy = MM(c.GetPosition().x), MM(c.GetPosition().y)
    xs = sorted((MM(bb.GetLeft()) + 0.15 + k * 0.01 for k in range(0, int((MM(bb.GetRight()) - MM(bb.GetLeft()) - 0.3) / 0.01) + 1)), key=lambda x: abs(x - cx))
    for x in xs:
        if w.via_ok(x, y, 0.3, 0.15, name) and w.seg_ok("B.Cu", (x, y), (cx, cy), 0.2, name):
            add_via(b, x, y, 0.3, 0.15, net); add_track(b, (x, y), (cx, cy), 0.2, "B.Cu", net)
            print(f"U901.21: via at ({x:.2f}, {y:.2f}), B.Cu link {math.hypot(x - cx, y - cy):.2f} mm to C931.1")
            return
    sys.exit("U901.21: no legal via site in the pad")


def candidates(b):
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" or t.GetNetname() != "3V3" or abs(MM(t.GetWidth()) - 0.2) > 0.001:
            continue
        xs = [MM(t.GetStart().x), MM(t.GetEnd().x)]; ys = [MM(t.GetStart().y), MM(t.GetEnd().y)]
        if (all(143 < x < 151 for x in xs) and all(52 < y < 90 for y in ys)) or (all(152 < x < 176 for x in xs) and all(70 < y < 92 for y in ys)):
            print(t.m_Uuid.AsString())


def widen(b, wmm, uuids):
    n = 0
    for t in b.GetTracks():
        if t.m_Uuid.AsString() in uuids:
            t.SetWidth(FM(wmm)); n += 1
    print("widened", n, "tracks to", wmm)


def bridge(b):
    """Two 0.45/0.25 vias in the 5V0 pour, north and south of the via wall, joined by a straight track on another layer."""
    w = World(b); net = b.FindNet("5V0")
    def near(it):                                            # only what lies round the pinch
        xs = (it[1], it[3]) if it[0] != "c" else (it[1],); ys = (it[2], it[4]) if it[0] != "c" else (it[2],)
        return min(xs) < 146 and max(xs) > 134 and min(ys) < 109 and max(ys) > 95
    w.L = {l: [it for it in v if near(it)] for l, v in w.L.items()}
    w.holes = [h for h in w.holes if 134 < h[0] < 146 and 95 < h[1] < 109]
    z = next(z for z in b.Zones() if z.GetZoneName() == "plane:5V0")
    def in_fill(x, y):
        return all(z.HitTestFilledArea(pcbnew.B_Cu, pcbnew.VECTOR2I(FM(x + dx), FM(y + dy))) for dx, dy in ((0, 0), (0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3)))
    def sites(y0, y1):
        return [(x / 10, y / 10) for x in range(int(137.8 * 10), int(142.5 * 10)) for y in range(int(y0 * 10), int(y1 * 10))
                if in_fill(x / 10, y / 10) and w.via_ok(x / 10, y / 10, 0.45, 0.25, "5V0")]
    north, south = sites(98.5, 101.0), sites(102.6, 105.5)
    print(len(north), "sites north,", len(south), "south")
    best = None
    for width in (0.4, 0.3, 0.25):
        pairs = sorted((math.hypot(a[0] - c[0], a[1] - c[1]), a, c) for a in north for c in south)
        for d, a, c in pairs:                                # shortest first
            layer = next((l for l in ("F.Cu", "In2.Cu", "In5.Cu") if w.seg_ok(l, a, c, width, "5V0")), None)
            if layer:
                best = (d, a, c, layer, width); break
        if best:
            break
    if not best:
        sys.exit("bridge: no legal pair")
    d, a, c, layer, width = best
    add_via(b, *a, 0.45, 0.25, net); add_via(b, *c, 0.45, 0.25, net); add_track(b, a, c, width, layer, net)
    print(f"5V0 bridge: vias at ({a[0]:.2f}, {a[1]:.2f}) and ({c[0]:.2f}, {c[1]:.2f}), {d:.2f} mm of {width} mm track on {layer}")


def fiducials(b):
    w = World(b)
    lib = os.path.join(os.environ["KICAD_MOUNT"], "share", "kicad", "footprints", "Fiducial.pretty")
    outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, True)
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())
    def inside(x, y):
        return all(outline.Contains(pcbnew.VECTOR2I(FM(x + dx), FM(y + dy))) for dx, dy in ((1.5, 0), (-1.5, 0), (0, 1.5), (0, -1.5)))
    n = 0
    for layer, side in (("F.Cu", pcbnew.F_Cu), ("B.Cu", pcbnew.B_Cu)):
        crt = pcbnew.F_CrtYd if side == pcbnew.F_Cu else pcbnew.B_CrtYd
        boxes = []
        for f in b.GetFootprints():
            if f.GetLayer() == side or any(p.GetDrillSize().x > 0 for p in f.Pads()):
                c = f.GetBoundingBox(False)
                boxes.append((MM(c.GetLeft()) - 1.1, MM(c.GetTop()) - 1.1, MM(c.GetRight()) + 1.1, MM(c.GetBottom()) + 1.1))
        zones = [z for z in b.Zones() if z.IsOnLayer(side)]
        cand = []
        for i in range(int((x1 - x0) / 0.5)):
            for j in range(int((y1 - y0) / 0.5)):
                x, y = x0 + i * 0.5, y0 + j * 0.5
                if not inside(x, y) or any(q[0] < x < q[2] and q[1] < y < q[3] for q in boxes):
                    continue
                if not w.point_ok(layer, x, y, 1.05, "\0"):
                    continue
                if any(z.HitTestFilledArea(side, pcbnew.VECTOR2I(FM(x + dx), FM(y + dy))) for z in zones for dx, dy in ((0, 0), (0.9, 0), (-0.9, 0), (0, 0.9), (0, -0.9))):
                    continue
                cand.append((x, y))
        if len(cand) < 3:
            print(layer, "only", len(cand), "free spots; none placed"); continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        pick = [max(cand, key=lambda q: math.hypot(q[0] - cx, q[1] - cy))]
        while len(pick) < 3:
            pick.append(max(cand, key=lambda q: min(math.hypot(q[0] - k[0], q[1] - k[1]) for k in pick)))
        for x, y in pick:
            n += 1
            f = pcbnew.FootprintLoad(lib, "Fiducial_1mm_Mask2mm")
            f.SetFPID(pcbnew.LIB_ID("Fiducial", "Fiducial_1mm_Mask2mm"))
            f.SetReference(f"FID{n}"); f.SetValue("Fiducial"); b.Add(f)
            f.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))
            if side == pcbnew.B_Cu:
                f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            f.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
            f.Reference().SetVisible(False); f.Value().SetVisible(False)
        print(layer, "fiducials at", [(round(x, 1), round(y, 1)) for x, y in pick], f"({len(cand)} free spots)")


if __name__ == "__main__":
    cmd = sys.argv[1]
    bd = pcbnew.LoadBoard(sys.argv[2])
    if cmd == "candidates":
        candidates(bd); sys.exit()
    out = sys.argv[3]
    if cmd == "spokes":
        spokes(bd)
    elif cmd == "pin21":
        pin21(bd)
    elif cmd == "bridge":
        bridge(bd)
    elif cmd == "fiducials":
        fiducials(bd)
    elif cmd == "widen":
        widen(bd, float(sys.argv[4]), set(sys.argv[5:]))
    else:
        sys.exit(__doc__)
    save(bd, out)
