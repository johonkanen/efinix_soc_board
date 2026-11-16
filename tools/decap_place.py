#!/usr/bin/env python3
"""Place the parked decoupling capacitors (user, 2026-11-16: under the BGA where they fit, else at the switcher outputs):
    tools/p2k/bin/kipy tools/decap_place.py IN.kicad_pcb OUT.kicad_pcb [DRC.json]
A parked part is one right of the board outline (x > 208.5). For every parked 0201 capacitor between a rail and GND:
 1. under U501 on B.Cu on a free pair of ball vias of that rail and GND: straight across two neighbours (0.8 mm),
    or at 45 degrees from the rail via with a 0.5 mm track to the GND via (1.13 mm). Small values go first.
 2. otherwise on B.Cu at the rail's regulator output (its buck_cell pour), nearest free position first, with a via
    in each pad into the rail's plane and GND.
0402 parts go straight to step 2. C701 and C951 go to the supply pin of their own IC (Y701, U902) instead.
With DRC.json (kicad-cli pcb drc --format json of IN): every supply or GND pad it lists as unconnected gets a
via (in the pad, or the nearest position within 2.5 mm with a track); run that as a second pass. Parts that are not rail-to-GND capacitors are left parked and listed."""
import collections
import math
import re
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); MM, TOMM = pcbnew.FromMM, pcbnew.ToMM
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
RAILS = ("VCORE", "1V8", "3V3", "1V1", "0V85")
BC = pcbnew.B_Cu


def seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


class Geo:
    """copper of the board in 1 mm bins: tracks ('t', net, layer, x1, y1, x2, y2, half width), vias ('v', net, x, y, r),
    pads ('p', net, layers, bbox, ref, x, y)"""
    def __init__(self):
        self.bins = collections.defaultdict(list)
        for t in b.GetTracks():
            self.add_track(t)
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.IsOnCopperLayer():
                    self.add_pad(f, p)

    def _put(self, it, x0, y0, x1, y1):
        for i in range(int(math.floor(min(x0, x1) - 0.6)), int(math.floor(max(x0, x1) + 0.6)) + 1):
            for j in range(int(math.floor(min(y0, y1) - 0.6)), int(math.floor(max(y0, y1) + 0.6)) + 1):
                self.bins[(i, j)].append(it)

    def add_track(self, t):
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y = TOMM(t.GetPosition().x), TOMM(t.GetPosition().y)
            self._put(("v", n, x, y, TOMM(t.GetWidth(pcbnew.F_Cu)) / 2), x, y, x, y); return
        pts = [t.GetStart(), t.GetEnd()]
        if t.Type() == pcbnew.PCB_ARC_T:
            a = pcbnew.Cast_to_PCB_ARC(t) if hasattr(pcbnew, "Cast_to_PCB_ARC") else t
            pts = [t.GetStart(), a.GetMid(), t.GetEnd()]
        for s, e in zip(pts, pts[1:]):
            x1, y1, x2, y2 = TOMM(s.x), TOMM(s.y), TOMM(e.x), TOMM(e.y)
            self._put(("t", n, t.GetLayer(), x1, y1, x2, y2, TOMM(t.GetWidth()) / 2), x1, y1, x2, y2)

    def add_pad(self, f, p):
        bb = p.GetBoundingBox(); box = (TOMM(bb.GetLeft()), TOMM(bb.GetTop()), TOMM(bb.GetRight()), TOMM(bb.GetBottom()))
        lays = tuple(l for l in (pcbnew.F_Cu, BC) if p.IsOnLayer(l))
        self._put(("p", p.GetNetname(), lays, box, f.GetReference(), TOMM(p.GetPosition().x), TOMM(p.GetPosition().y)), *box)

    def near(self, x, y):
        return self.bins.get((int(math.floor(x)), int(math.floor(y))), ())

    def via_ok(self, x, y, netname, r=0.15):
        for it in self.near(x, y):
            if it[0] == "v":
                d = math.hypot(it[2] - x, it[3] - y)
                if d < 0.005 and it[1] == netname:
                    continue
                if d < r + it[4] + (0.11 if it[1] != netname else 0.06):
                    return False
            elif it[0] == "t":
                if it[1] != netname and seg_d(x, y, it[3], it[4], it[5], it[6]) < r + 0.11 + it[7]:
                    return False
            elif it[1] != netname:
                bx = it[3]
                if math.hypot(max(bx[0] - x, 0, x - bx[2]), max(bx[1] - y, 0, y - bx[3])) < r + 0.11:
                    return False
        return True

    def disc_ok(self, x, y, netname, layer, r=0.27, skip_ref=None):
        """a pad-sized disc on `layer`: clear of foreign copper, and not on another part's pad (lands are not shared)"""
        for it in self.near(x, y):
            if it[0] == "v":
                if it[1] != netname and math.hypot(it[2] - x, it[3] - y) < r + 0.1 + it[4]:
                    return False
            elif it[0] == "t":
                if it[2] == layer and it[1] != netname and seg_d(x, y, it[3], it[4], it[5], it[6]) < r + 0.1 + it[7]:
                    return False
            elif layer in it[2] and it[4] != skip_ref:
                bx = it[3]; d = math.hypot(max(bx[0] - x, 0, x - bx[2]), max(bx[1] - y, 0, y - bx[3]))
                if d < (r + 0.1 if it[1] != netname else 0.12):
                    return False
        return True

    def line_ok(self, a, c, netname, layer, hw=0.1):
        n = max(1, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.05))
        return all(self.disc_ok(a[0] + (c[0] - a[0]) * k / n, a[1] + (c[1] - a[1]) * k / n, netname, layer, hw) for k in range(n + 1))


geo = Geo()
u501 = b.FindFootprintByReference("U501")
balls = {(round(TOMM(p.GetPosition().x), 2), round(TOMM(p.GetPosition().y), 2)): p.GetNetname() for p in u501.Pads()}
ballvia = {}
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        k = (round(TOMM(t.GetPosition().x), 2), round(TOMM(t.GetPosition().y), 2))
        if balls.get(k) == t.GetNetname():
            ballvia[k] = t.GetNetname()


def set_part(f, cx, cy, p1, towards):
    """0201 on B.Cu, pad of net p1net at p1... returns pad positions by net"""
    if f.GetLayer() != BC:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    best = None
    for rot in (0, 90, 180, 270, 45, 135, 225, 315):
        f.SetOrientationDegrees(rot); f.SetPosition(P(cx, cy))
        q = next(p for p in f.Pads() if p.GetNumber() and p.GetNetname() != "GND").GetPosition()
        e = math.hypot(TOMM(q.x) - p1[0], TOMM(q.y) - p1[1])
        if best is None or e < best[0]:
            best = (e, rot)
    f.SetOrientationDegrees(best[1]); f.SetPosition(P(cx, cy))
    for p in f.Pads():
        if p.IsOnCopperLayer():
            geo.add_pad(f, p)


def add_via(x, y, netname):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(pcbnew.F_Cu, MM(0.3)); v.SetDrill(MM(0.15))
    v.SetLayerPair(pcbnew.F_Cu, BC); v.SetNet(b.FindNet(netname)); b.Add(v); geo.add_track(v)


def add_track(a, c, netname, w=0.2):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetLayer(BC); t.SetWidth(MM(w))
    t.SetNet(b.FindNet(netname)); b.Add(t); geo.add_track(t)


def under_bga(f, rail):
    """a free via pair (rail ball via, GND ball via) for this cap; True if placed"""
    ref = f.GetReference(); opts = []
    for (x, y), n in ballvia.items():
        if n != rail:
            continue
        for dx, dy in ((0.8, 0), (-0.8, 0), (0, 0.8), (0, -0.8), (0.8, 0.8), (0.8, -0.8), (-0.8, 0.8), (-0.8, -0.8)):
            g = (round(x + dx, 2), round(y + dy, 2))
            if ballvia.get(g) != "GND":
                continue
            L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
            if dx and dy:                                   # 45 degrees: pad 1 on the rail via, a track to the GND via
                p1 = (x, y); p2 = (x + 0.64 * ux, y + 0.64 * uy)
            else:                                           # across the pair
                p1 = (x + 0.08 * ux, y + 0.08 * uy); p2 = (x + 0.72 * ux, y + 0.72 * uy)
            mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            if not (geo.disc_ok(*p1, rail, BC, 0.25) and geo.disc_ok(*p2, "GND", BC, 0.25) and geo.disc_ok(*mid, "", BC, 0.12)):
                continue
            if dx and dy and not geo.line_ok(p2, g, "GND", BC):
                continue
            opts.append((1 if (dx and dy) else 0, y, x, p1, p2, g, mid))
    if not opts:
        return False
    _, _, _, p1, p2, g, mid = sorted(opts)[0]
    set_part(f, mid[0], mid[1], p1, None)
    if math.hypot(p2[0] - g[0], p2[1] - g[1]) > 0.2:
        add_track(p2, g, "GND")
    print(f"   {ref} {f.GetValue()} {rail}: under U501 at ({mid[0]:.2f}, {mid[1]:.2f}) on the via pair ({p1[0]:.1f}, {p1[1]:.1f}) / {g}")
    return True


def rail_plane(rail, x, y):
    return any(z.GetNetname() == rail and any(z.HitTestFilledArea(l, P(x, y)) for l in z.GetLayerSet().Seq()) for z in b.Zones())


courts = collections.defaultdict(list)
for f in b.GetFootprints():
    bb = f.GetCourtyard(f.GetLayer()).BBox()
    courts[f.GetLayer()].append([TOMM(bb.GetLeft()), TOMM(bb.GetTop()), TOMM(bb.GetRight()), TOMM(bb.GetBottom()), f.GetReference()])


def court_ok(rect, ref):
    return not any(c[4] != ref and c[0] < rect[2] and c[2] > rect[0] and c[1] < rect[3] and c[3] > rect[1] for c in courts[BC])


def at_switcher(f, rail, size, centre=None, what=None):
    ref = f.GetReference()
    if centre:
        cx0, cy0 = centre
    else:
        zs = [z for z in b.Zones() if z.GetNetname() == rail and z.GetZoneName() == "buck_cell" and z.IsOnLayer(BC)]
        if not zs:
            return False
        bb = zs[0].GetBoundingBox(); cx0, cy0 = TOMM(bb.GetCenter().x), TOMM(bb.GetCenter().y)
    pitch = 0.64 if size == "0201" else 0.96; pr = 0.27 if size == "0201" else 0.36
    hl, hw = (0.78, 0.42) if size == "0201" else (0.98, 0.52)
    best = None
    for i in range(-45, 46):
        for j in range(-45, 46):
            cx, cy = cx0 + 0.2 * i, cy0 + 0.2 * j; d = math.hypot(cx - cx0, cy - cy0)
            if d > 9 or (best and d >= best[0]):
                continue
            for ux, uy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                p1 = (cx - pitch / 2 * ux, cy - pitch / 2 * uy); p2 = (cx + pitch / 2 * ux, cy + pitch / 2 * uy)
                rect = (cx - (hl if ux else hw), cy - (hw if ux else hl), cx + (hl if ux else hw), cy + (hw if ux else hl))
                if not court_ok(rect, ref):
                    continue
                if not (geo.via_ok(*p1, rail) and geo.via_ok(*p2, "GND") and geo.disc_ok(*p1, rail, BC, pr) and geo.disc_ok(*p2, "GND", BC, pr)):
                    continue
                if not rail_plane(rail, *p1):
                    continue
                best = (d, cx, cy, p1, p2, rect); break
    if not best:
        return False
    d, cx, cy, p1, p2, rect = best
    set_part(f, cx, cy, p1, None); add_via(*p1, rail); add_via(*p2, "GND"); courts[BC].append(list(rect) + [ref])
    print(f"   {ref} {f.GetValue()} {rail}: at {what or 'the ' + rail + ' regulator output'}, ({cx:.2f}, {cy:.2f}), {d:.1f} mm away, a via in each pad")
    return True


def cval(s):
    m = re.match(r"([\d.]+)([pnu])(\d*)", s)
    return float(m.group(1) + ("." + m.group(3) if m.group(3) else "")) * {"p": 1e-12, "n": 1e-9, "u": 1e-6}[m.group(2)] if m else 1


todo, other = [], []
for f in b.GetFootprints():
    if TOMM(f.GetPosition().x) <= 208.5:
        continue
    nets = sorted(p.GetNetname() for p in f.Pads() if p.GetNumber())
    rail = next((n for n in nets if n in RAILS), None)
    if f.GetReference().startswith("C") and len(nets) == 2 and "GND" in nets and rail:
        todo.append((cval(f.GetValue()), f.GetReference(), f, rail, "0201" if "0201" in str(f.GetFPID().GetLibItemName()) else "0402"))
    else:
        other.append(f.GetReference())
# capacitors that belong to another IC than U501: at that IC's supply pin
AT_PIN = {"C701": ("Y701", "4"), "C951": ("U902", "5")}
placed = collections.Counter(); failed = []
for _, ref, f, rail, size in sorted(todo, key=lambda t: (t[0], t[1])):
    if ref in AT_PIN:
        q = b.FindFootprintByReference(AT_PIN[ref][0]).FindPadByNumber(AT_PIN[ref][1]).GetPosition()
        if at_switcher(f, rail, size, (TOMM(q.x), TOMM(q.y)), f"{AT_PIN[ref][0]} pin {AT_PIN[ref][1]}"):
            placed["at its IC"] += 1
        else:
            failed.append(ref)
    elif size == "0201" and under_bga(f, rail):
        placed["under U501"] += 1
    elif at_switcher(f, rail, size):
        placed["at the regulator"] += 1
    else:
        failed.append(ref)
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
# supply and GND pads of placed parts that have no copper at all: a via in the pad, or the nearest via position
PLANES = RAILS + ("GND",)
bare = []
if len(sys.argv) > 3:      # only the pads DRC lists as unconnected: kicad-cli pcb drc --format json of the board
    import json
    want = set()
    for v in json.load(open(sys.argv[3]))["unconnected_items"]:
        for it in v["items"]:
            m = re.match(r"Pad (\S+) \[([^\]]+)\] of (\S+) on", it["description"])
            if m and m.group(2) in PLANES and it["pos"]["x"] < 208.5 and m.group(3) != "U501":
                want.add((m.group(3), m.group(1)))
    for ref, num in sorted(want):
        f = b.FindFootprintByReference(ref); p = f.FindPadByNumber(num)
        bare.append((ref, p, p.GetNetname(), pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else BC))
for ref, p, n, lay in bare:
    x0, y0 = TOMM(p.GetPosition().x), TOMM(p.GetPosition().y); best = None
    for i in range(-50, 51):
        for j in range(-50, 51):
            x, y = x0 + 0.05 * i, y0 + 0.05 * j; d = math.hypot(x - x0, y - y0)
            if d > 2.5 or (best and d >= best[0]) or not geo.via_ok(x, y, n):
                continue
            if n != "GND" and not rail_plane(n, x, y):
                continue
            if d > 0.05 and not geo.line_ok((x0, y0), (x, y), n, lay, 0.08):
                continue
            best = (d, x, y)
    if not best:
        print(f"   {ref} pad {p.GetNumber()} ({n}): no via position within 2.5 mm"); continue
    add_via(best[1], best[2], n)
    if best[0] > 0.05:
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x0, y0)); t.SetEnd(P(best[1], best[2])); t.SetLayer(lay); t.SetWidth(MM(0.15))
        t.SetNet(b.FindNet(n)); b.Add(t); geo.add_track(t)
    print(f"   {ref} pad {p.GetNumber()} ({n}): via at ({best[1]:.2f}, {best[2]:.2f}), {best[0]:.2f} mm from the pad")
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(sys.argv[2])
print("decap_place:", dict(placed), "; no place found:", failed, "; left parked (not rail capacitors):", sorted(other))
