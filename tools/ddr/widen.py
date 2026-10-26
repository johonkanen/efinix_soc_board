#!/usr/bin/env python3
"""Fit the LPDDR4 tracks to the 40 ohm / 80 ohm widths outside the BGA courtyards (kipy; IN OUT).

TI135_PCB_NOTES.md §6.3/§6.5: single-ended 0.18 mm on In2/In5, 0.25 mm on F/B; pairs (lpddr_diff) 0.14 mm inner,
0.20 mm outer. Inside U501/U801's courtyards the 0.1 mm neck-down stays (rule lpddr_bga_neckdown). Each segment gets
the widest width from its target down to the DRC minimum (0.17 / 0.23 SE, 0.13 / 0.19 pair) that clears:
- every other net's track by CLR, pad by CLR, via copper by VIA_CLR (keeps the 0.175 mm drill clearance);
- a pair's other half by the rule's minimum pair gap (0.14 inner, 0.18 outer);
- the board edge by EDGE_CLR;
- with --xtalk, other LPDDR tracks by the crosstalk spacing (rules lpddr_xtalk_spacing / lpddr_xtalk_group: 0.2 mm,
  0.3 mm between CA and DQ/DQS) instead of CLR;
otherwise it is left as it is. A segment wider than the rule maximum (KRT's --impedance has no solder mask in its
microstrip model and routes F/B about 0.27 mm for 40 ohm) is narrowed to the target. Zones are refilled afterwards (they give way). KiCad caps each DRC error type at 199
reports, so the summary line counts the segments still below the rule minimum itself.
"""
import math
import sys
import collections
from collections import defaultdict

import pcbnew

CLR, VIA_CLR, EDGE_CLR = 0.11, 0.13, 0.5
XT, XT_GROUP = 0.2, 0.3
SE = {"inner": [0.18, 0.17], "outer": [0.25, 0.24, 0.23]}
DIFF = {"inner": [0.14, 0.13], "outer": [0.20, 0.19]}
MAX = {(False, "inner"): 0.19, (False, "outer"): 0.27, (True, "inner"): 0.15, (True, "outer"): 0.21}  # rule maxima
PAIR_GAP_MIN = {"inner": 0.14, "outer": 0.18}
OUTER = ("F.Cu", "B.Cu")
mm = pcbnew.ToMM
CELL = 1.0

args = [a for a in sys.argv[1:] if not a.startswith("--")]
XTALK = "--xtalk" in sys.argv
b = pcbnew.LoadBoard(args[0])
court = [b.FindFootprintByReference(r).GetCourtyard(pcbnew.F_CrtYd).BBox() for r in ("U501", "U801")]
court = [(mm(c.GetLeft()), mm(c.GetTop()), mm(c.GetRight()), mm(c.GetBottom())) for c in court]


def in_court(x, y):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in court)


def strictly_in(x, y, e=1e-4):
    """Inside a courtyard and not on its edge (a split piece starts on the edge)."""
    return any(x0 + e < x < x1 - e and y0 + e < y < y1 - e for x0, y0, x1, y1 in court)


def exit_point(p, q):
    """Where the segment p (inside a courtyard) -> q (outside) leaves that courtyard rectangle."""
    for x0, y0, x1, y1 in court:
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            dx, dy = q[0] - p[0], q[1] - p[1]
            t = min([(x1 - p[0]) / dx if dx > 0 else (x0 - p[0]) / dx if dx < 0 else 1e9,
                     (y1 - p[1]) / dy if dy > 0 else (y0 - p[1]) / dy if dy < 0 else 1e9])
            return p[0] + t * dx, p[1] + t * dy


# A segment that leaves a courtyard is under the neck-down rule (intersectsCourtyard) along its whole length, however
# far it runs outside: split it at the courtyard edge so the outside part gets the full width.
split = 0
for t in list(b.GetTracks()):
    if isinstance(t, pcbnew.PCB_VIA) or "ddr_" not in t.GetNetname():
        continue
    a = (mm(t.GetStart().x), mm(t.GetStart().y)); c = (mm(t.GetEnd().x), mm(t.GetEnd().y))
    if in_court(*a) == in_court(*c):
        continue
    ins, out = (a, c) if in_court(*a) else (c, a)
    e = exit_point(ins, out)
    if math.hypot(out[0] - e[0], out[1] - e[1]) < 0.2:
        continue
    pe = pcbnew.VECTOR2I(pcbnew.FromMM(e[0]), pcbnew.FromMM(e[1]))
    n = pcbnew.PCB_TRACK(b); n.SetLayer(t.GetLayer()); n.SetWidth(t.GetWidth()); n.SetNet(t.GetNet())
    n.SetStart(pe); n.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(out[0]), pcbnew.FromMM(out[1])))
    if ins == a:
        t.SetEnd(pe)
    else:
        t.SetStart(pe)
    b.Add(n); split += 1


# obstacles per layer in a grid: ("seg", ax, ay, cx, cy, half width, net) / ("circ", x, y, r, net) / ("rect", ...)
grid = defaultdict(list)


def put(layer, item, x0, y0, x1, y1):
    for i in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
        for j in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
            grid[(layer, i, j)].append(item)


copper = [b.GetLayerName(l) for l in b.GetEnabledLayers().CuStack()]
ddr_class = {}  # net code -> "ca" / "dq" (DQ, DM, DQS) for the LPDDR tracks
for t in b.GetTracks():
    n = t.GetNetCode()
    if "ddr_" in t.GetNetname():
        ddr_class[n] = "ca" if "lpddr_ca" in t.GetNetClassName() else "dq"
    if isinstance(t, pcbnew.PCB_VIA):
        x, y, r = mm(t.GetPosition().x), mm(t.GetPosition().y), mm(t.GetWidth(pcbnew.F_Cu)) / 2
        for L in copper:
            put(L, ("circ", x, y, r, n, id(t)), x - r, y - r, x + r, y + r)
    else:
        ax, ay, cx, cy, hw = mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y), mm(t.GetWidth()) / 2
        put(b.GetLayerName(t.GetLayer()), ("seg", ax, ay, cx, cy, hw, n, id(t)),
            min(ax, cx) - hw, min(ay, cy) - hw, max(ax, cx) + hw, max(ay, cy) + hw)
for d in b.GetDrawings():
    if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        ax, ay, cx, cy = mm(d.GetStart().x), mm(d.GetStart().y), mm(d.GetEnd().x), mm(d.GetEnd().y)
        for L in copper:
            put(L, ("edge", ax, ay, cx, cy, -1, id(d)), min(ax, cx), min(ay, cy), max(ax, cx), max(ay, cy))
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox(); x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
        for lid in p.GetLayerSet().CuStack():
            put(b.GetLayerName(lid), ("rect", x0, y0, x1, y1, p.GetNetCode(), id(p)), x0, y0, x1, y1)


def seg_seg(a, c, p, q):
    """Distance between segments a-c and p-q."""
    def pt_seg(o, u, v):
        dx, dy = v[0] - u[0], v[1] - u[1]; l2 = dx * dx + dy * dy
        t = 0 if l2 == 0 else max(0, min(1, ((o[0] - u[0]) * dx + (o[1] - u[1]) * dy) / l2))
        return math.hypot(o[0] - u[0] - t * dx, o[1] - u[1] - t * dy)
    def cross(u, v, w, z):
        def o(p1, p2, p3): return (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
        return o(u, v, w) * o(u, v, z) < 0 and o(w, z, u) * o(w, z, v) < 0
    if cross(a, c, p, q):
        return 0.0
    return min(pt_seg(a, p, q), pt_seg(c, p, q), pt_seg(p, a, c), pt_seg(q, a, c))


def rect_seg(x0, y0, x1, y1, a, c):
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
        return 0.0
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return min(seg_seg(a, c, u, v) for u, v in edges)


def gap(t, layer, a, c, hw, partner):
    """Smallest (distance - required clearance) to foreign copper around the segment of half width hw."""
    worst = 1e9; me = t.GetNetCode(); seen = set()
    x0, x1 = min(a[0], c[0]) - hw - 0.5, max(a[0], c[0]) + hw + 0.5
    y0, y1 = min(a[1], c[1]) - hw - 0.5, max(a[1], c[1]) + hw + 0.5
    for i in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
        for j in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
            for it in grid[(layer, i, j)]:
                if id(it) in seen or it[-2] == me:
                    continue
                seen.add(id(it))
                if it[0] == "seg":
                    need = CLR
                    if it[-2] == partner:
                        need = PAIR_GAP_MIN["outer" if layer in OUTER else "inner"]
                    elif XTALK and it[-2] in ddr_class and not in_court((it[1] + it[3]) / 2, (it[2] + it[4]) / 2):
                        need = XT_GROUP if {ddr_class[me], ddr_class[it[-2]]} == {"ca", "dq"} else XT
                    d = seg_seg(a, c, (it[1], it[2]), (it[3], it[4])) - hw - it[5] - need
                elif it[0] == "edge":
                    d = seg_seg(a, c, (it[1], it[2]), (it[3], it[4])) - hw - EDGE_CLR
                elif it[0] == "circ":
                    d = seg_seg(a, c, (it[1], it[2]), (it[1], it[2])) - hw - it[3] - VIA_CLR
                else:
                    d = rect_seg(it[1], it[2], it[3], it[4], a, c) - hw - CLR
                worst = min(worst, d)
    return worst


codes = {}
for i in range(b.GetNetCount()):
    n = b.FindNet(i)
    if n is not None:
        codes[n.GetNetname()] = n.GetNetCode()
done = kept = narrowed = 0
for t in list(b.GetTracks()):
    if isinstance(t, pcbnew.PCB_VIA):
        continue
    name = t.GetNetname()
    if "ddr_" not in name or "CAL" in name:
        continue
    layer = b.GetLayerName(t.GetLayer())
    a = (mm(t.GetStart().x), mm(t.GetStart().y)); c = (mm(t.GetEnd().x), mm(t.GetEnd().y))
    side = "outer" if layer in OUTER else "inner"
    pair = "lpddr_diff" in t.GetNetClassName()
    partner = codes.get(name[:-1] + ("N" if name.endswith("P") else "P")) if pair else None
    cur = mm(t.GetWidth())
    if cur > MAX[(pair, side)] + 1e-6:  # also inside the courtyards: the neck-down rule inherits these maxima
        t.SetWidth(pcbnew.FromMM((DIFF if pair else SE)[side][0]))
        narrowed += 1
        continue
    if strictly_in(*a) or strictly_in(*c) or strictly_in((a[0] + c[0]) / 2, (a[1] + c[1]) / 2):
        continue
    for w in (DIFF if pair else SE)[side]:
        if w <= cur + 1e-6:
            break
        if gap(t, layer, a, c, w / 2, partner) >= -1e-6:
            t.SetWidth(pcbnew.FromMM(w))
            # keep the obstacle index current: later segments see the wider copper
            put(layer, ("seg", a[0], a[1], c[0], c[1], w / 2, t.GetNetCode(), id(t) + 1),
                min(a[0], c[0]) - w / 2, min(a[1], c[1]) - w / 2, max(a[0], c[0]) + w / 2, max(a[1], c[1]) + w / 2)
            done += 1
            break
    else:
        kept += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(args[1], b)
narrow = collections.Counter()
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA) or "ddr_" not in t.GetNetname() or "CAL" in t.GetNetname():
        continue
    a, c = t.GetStart(), t.GetEnd()
    if strictly_in(mm(a.x), mm(a.y)) or strictly_in(mm(c.x), mm(c.y)) or strictly_in(mm(a.x + c.x) / 2, mm(a.y + c.y) / 2):
        continue
    side = "outer" if b.GetLayerName(t.GetLayer()) in OUTER else "inner"
    pair = "lpddr_diff" in t.GetNetClassName()
    if mm(t.GetWidth()) < (DIFF if pair else SE)[side][-1] - 1e-6:
        narrow[t.GetNetname().split("/")[-1]] += mm(t.GetLength())
print(f"widen{' --xtalk' if XTALK else ''}: {split} split at a courtyard edge, {done} DDR segments widened outside the BGA courtyards, "
      f"{narrowed} narrowed to the target; {sum(narrow.values()):.0f} mm still below the rule minimum")
print("  narrow mm per net:", ", ".join(f"{k} {v:.1f}" for k, v in narrow.most_common()))
