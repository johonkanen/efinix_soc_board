#!/usr/bin/env python3
"""Fit the LPDDR4 tracks to the 40 ohm / 80 ohm widths outside the BGA courtyards (kipy; IN OUT).

TI135_PCB_NOTES.md §6.3/§6.5: single-ended 0.18 mm on In2/In5, 0.25 mm on F/B; pairs (lpddr_diff) 0.14 mm inner,
0.20 mm outer. Inside U501/U801's courtyards the 0.1 mm neck-down stays (rule lpddr_bga_neckdown). Each segment gets
the widest width from its target down to the DRC minimum (0.17 / 0.23 SE, 0.13 / 0.19 pair) that clears:
- every other net's track, pad and via copper by CLR (all net classes: 0.1 mm), via holes by HOLE_CLR (board setup)
  and plated through-hole pad holes by PTH_HOLE_CLR (rule jlc_pth_to_track); round pads as circles;
- a pair's other half by the rule's minimum pair gap (0.14 inner, 0.18 outer);
- the board edge by EDGE_CLR;
- with --xtalk, other LPDDR tracks by the crosstalk spacing (rules lpddr_xtalk_spacing / lpddr_xtalk_group: 0.2 mm,
  0.3 mm between CA and DQ/DQS) instead of CLR;
otherwise it is left as it is. Every segment goes to the minimum width first, then still-narrow runs are nudged sideways, then all go to the
target, so the first segments widened do not take the room their neighbours need for the minimum. A segment wider than the rule maximum (KRT's --impedance has no solder mask in its
microstrip model and routes F/B about 0.27 mm for 40 ohm) is narrowed to the target. Zones are refilled afterwards (they give way). KiCad caps each DRC error type at 199
reports, so the summary line counts the segments still below the rule minimum itself. --why lists, for each segment
left narrow, the copper that blocks the minimum width and by how much.
"""
import math
import sys
import collections
from collections import defaultdict

import pcbnew

CLR, HOLE_CLR, PTH_HOLE_CLR, EDGE_CLR = 0.1, 0.175, 0.28, 0.5
NECK_MIN = 0.09  # rule lpddr_bga_neckdown
MARGIN = 0.0005  # mm kept over every clearance (KiCad grades in nm)
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
WHY = "--why" in sys.argv
DEBUG = next((a[8:] for a in sys.argv if a.startswith("--debug=")), None)
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
zero = []
for t in list(b.GetTracks()):
    if isinstance(t, pcbnew.PCB_VIA) or "ddr_" not in t.GetNetname():
        continue
    a = (mm(t.GetStart().x), mm(t.GetStart().y)); c = (mm(t.GetEnd().x), mm(t.GetEnd().y))
    if a == c:  # zero length (KiCad flags these as crossing their neighbours); removed after the loop
        zero.append(t); continue
    if strictly_in(*a) == strictly_in(*c):  # strict: an end on the edge is an earlier split
        continue
    ins, out = (a, c) if strictly_in(*a) else (c, a)
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
for t in zero:  # SWIG: remove last, after all lookups
    b.Remove(t)


# obstacles per layer in a grid: ("seg", ax, ay, cx, cy, half width, net, id) / ("circ", x, y, r, net, id) /
# ("hole", x, y, r, clearance, net, id) / ("rect", x0, y0, x1, y1, net, id) / ("edge", ax, ay, cx, cy, -1, id).
# A track's items carry its UUID as id; a nudged track's old items are retired through `dead`.
grid = defaultdict(list)
dead = set()
track_keys = defaultdict(set)  # track UUID -> every id its items were indexed under


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
        rh = mm(t.GetDrillValue()) / 2
        for L in copper:
            put(L, ("circ", x, y, r, n, id(t)), x - r, y - r, x + r, y + r)
            put(L, ("hole", x, y, rh, HOLE_CLR, n, id(t) + 1), x - r, y - r, x + r, y + r)
    else:
        ax, ay, cx, cy, hw = mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y), mm(t.GetWidth()) / 2
        put(b.GetLayerName(t.GetLayer()), ("seg", ax, ay, cx, cy, hw, n, t.m_Uuid.AsString()),
            min(ax, cx) - hw, min(ay, cy) - hw, max(ax, cx) + hw, max(ay, cy) + hw)
for d in b.GetDrawings():
    if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        ax, ay, cx, cy = mm(d.GetStart().x), mm(d.GetStart().y), mm(d.GetEnd().x), mm(d.GetEnd().y)
        for L in copper:
            put(L, ("edge", ax, ay, cx, cy, -1, id(d)), min(ax, cx), min(ay, cy), max(ax, cx), max(ay, cy))
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox(); x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
        x, y = mm(p.GetPosition().x), mm(p.GetPosition().y)
        if p.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE:
            item = ("circ", x, y, (x1 - x0) / 2, p.GetNetCode(), id(p))
        else:
            item = ("rect", x0, y0, x1, y1, p.GetNetCode(), id(p))
        for lid in p.GetLayerSet().CuStack():
            put(b.GetLayerName(lid), item, x0, y0, x1, y1)
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and p.GetDrillSize().x > 0:
                put(b.GetLayerName(lid), ("hole", x, y, mm(p.GetDrillSize().x) / 2, PTH_HOLE_CLR, p.GetNetCode(), id(p) + 1),
                    x0, y0, x1, y1)


def put_track(t, tag=""):
    """(Re-)index a track's copper: earlier items with the same UUID stay valid only if they are not retired."""
    ax, ay, cx, cy, hw = mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y), mm(t.GetWidth()) / 2
    track_keys[t.m_Uuid.AsString()].add(t.m_Uuid.AsString() + tag)
    put(b.GetLayerName(t.GetLayer()), ("seg", ax, ay, cx, cy, hw, t.GetNetCode(), t.m_Uuid.AsString() + tag),
        min(ax, cx) - hw, min(ay, cy) - hw, max(ax, cx) + hw, max(ay, cy) + hw)


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
    """Smallest (distance - required clearance) to foreign copper around the segment of half width hw, and that copper."""
    worst, blocker = 1e9, None; me = t.GetNetCode(); seen = set()
    x0, x1 = min(a[0], c[0]) - hw - 0.5, max(a[0], c[0]) + hw + 0.5
    y0, y1 = min(a[1], c[1]) - hw - 0.5, max(a[1], c[1]) + hw + 0.5
    for i in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
        for j in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
            for it in grid[(layer, i, j)]:
                if id(it) in seen or it[-2] == me or it[-1] in dead:
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
                    d = seg_seg(a, c, (it[1], it[2]), (it[1], it[2])) - hw - it[3] - CLR
                elif it[0] == "hole":
                    d = seg_seg(a, c, (it[1], it[2]), (it[1], it[2])) - hw - it[3] - it[4]
                else:
                    d = rect_seg(it[1], it[2], it[3], it[4], a, c) - hw - CLR
                d -= MARGIN
                if d < worst:
                    worst, blocker = d, it
    return worst, blocker


codes = {}
for i in range(b.GetNetCount()):
    n = b.FindNet(i)
    if n is not None:
        codes[n.GetNetname()] = n.GetNetCode()
done = narrowed = 0
neck_low = []  # KRT leaves some neck-down at 0.0898 mm (rule minimum 0.09)
fit = []  # (track, layer, a, c, pair, side, partner) of the segments outside the courtyards
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
    if mm(t.GetWidth()) > MAX[(pair, side)] + 1e-6:  # also inside the courtyards: the neck-down rule inherits these maxima
        t.SetWidth(pcbnew.FromMM((DIFF if pair else SE)[side][0]))
        narrowed += 1
        continue
    if not (strictly_in(*a) or strictly_in(*c) or strictly_in((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)):
        fit.append((t, layer, a, c, pair, side, partner))
    elif a != c and mm(t.GetWidth()) < NECK_MIN - 1e-6:
        neck_low.append((t, layer, a, c, None))  # inside the BGA the pair gap minimum is the clearance (neck-down rule)
def widen_pass(pass_):
    global done
    for t, layer, _, _, pair, side, partner in fit:
        a = (mm(t.GetStart().x), mm(t.GetStart().y)); c = (mm(t.GetEnd().x), mm(t.GetEnd().y))  # current (nudged) ends
        widths = (DIFF if pair else SE)[side]
        cur = mm(t.GetWidth())
        for w in (widths[-1:] if pass_ == "min" else widths):
            if w <= cur + 1e-6:
                break
            if gap(t, layer, a, c, w / 2, partner)[0] >= 0:
                if cur < widths[-1] - 1e-6:
                    done += 1
                t.SetWidth(pcbnew.FromMM(w))
                put_track(t, tag="+" + pass_)  # keep the obstacle index current: later segments see the wider copper
                break


widen_pass("min")

# Nudge (between the minimum and the target pass). A segment still below the minimum is usually short by tens of um
# on one side. Offset its run (the same-net segments on its layer between two anchors: a via, pad, junction or BGA
# interior) sideways as a polyline, 5..100 um either way; failing that, only the segment's own two ends. Anchors stay,
# and the move is kept only if every moved segment clears at its width (the narrow ones at the minimum).
def P(v):
    return pcbnew.VECTOR2I(pcbnew.FromMM(v[0]), pcbnew.FromMM(v[1]))


def vk(v):
    return (round(v[0], 4), round(v[1], 4))


minw = {}  # track UUID -> the width it must reach (the minimum for the narrow ones)
info = {}
for t, layer, a, c, pair, side, partner in fit:
    minw[t.m_Uuid.AsString()] = (DIFF if pair else SE)[side][-1]
    info[t.m_Uuid.AsString()] = (pair, side, partner)
ddr_tracks = defaultdict(list)  # (net, layer) -> tracks
for t in b.GetTracks():
    if not isinstance(t, pcbnew.PCB_VIA) and "ddr_" in t.GetNetname():
        ddr_tracks[(t.GetNetCode(), t.GetLayer())].append(t)
anchor_pts = defaultdict(set)  # net -> via positions; pads are tested by containment
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        anchor_pts[t.GetNetCode()].add(vk((mm(t.GetPosition().x), mm(t.GetPosition().y))))
net_pads = defaultdict(list)
for f in b.GetFootprints():
    for p in f.Pads():
        net_pads[p.GetNetCode()].append(p)


def ends(t):
    return (mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y))


def offset_moves(chain, free, k):
    """Vertex moves that offset the polyline `chain` by k (left of its direction; miter joins), free vertices only."""
    normals = []
    for p, q in zip(chain, chain[1:]):
        L = math.hypot(q[0] - p[0], q[1] - p[1]) or 1
        normals.append((-(q[1] - p[1]) / L, (q[0] - p[0]) / L))
    moves = {}
    for i, v in enumerate(chain):
        if vk(v) not in free:
            continue
        n1 = normals[i - 1] if i > 0 else normals[i]
        n2 = normals[i] if i < len(normals) else normals[i - 1]
        f = k / max(1 + n1[0] * n2[0] + n1[1] * n2[1], 0.3)
        moves[vk(v)] = ((n1[0] + n2[0]) * f, (n1[1] + n2[1]) * f)
    return moves


def nudge(t, bga_free=False):
    """Offset t's run sideways until it clears (see above). bga_free: vertices inside the BGA courtyards may move too
    (the clearance repair); otherwise the run stops at the courtyards. True if t moved."""
    global nudged
    net, lid = t.GetNetCode(), t.GetLayer()
    deg = collections.Counter()
    for u in ddr_tracks[(net, lid)]:
        for e in ends(u):
            deg[vk(e)] += 1

    def anchored(v):
        return (deg[vk(v)] != 2 or vk(v) in anchor_pts[net] or (strictly_in(*v) and not bga_free)
                or any(p.HitTest(P(v)) for p in net_pads[net] if p.IsOnLayer(lid)))

    def walk(v, came):
        """Vertices and tracks from v (reached over track `came`) on to the next anchor."""
        vs, ts = [], []
        while not anchored(v):
            nxt = [u for u in ddr_tracks[(net, lid)] if u.m_Uuid.AsString() != came.m_Uuid.AsString()
                   and any(vk(e) == vk(v) for e in ends(u))]
            if not nxt or len(ts) > 400:
                break
            came = nxt[0]; e0, e1 = ends(came)
            v = e1 if vk(e0) == vk(v) else e0
            vs.append(v); ts.append(came)
        return vs, ts
    a, c = ends(t)
    back, tb = walk(a, t); fwd, tf = walk(c, t)
    chain = list(reversed(back)) + [a, c] + fwd
    run = {u.m_Uuid.AsString(): u for u in tb + tf + [t]}
    free_all = {vk(v) for v in chain if not anchored(v)}
    local = {vk(v) for v in (a, c) if not anchored(v)}
    done_here = False
    for free in (free_all, local):
        if not free:
            continue
        for k in [i * 0.005 for i in range(1, 21)]:
            for sgn in (1, -1):
                mv = offset_moves(chain, free, sgn * k)
                ok = True
                for key, u in run.items():
                    ua, uc = ends(u)
                    if vk(ua) not in mv and vk(uc) not in mv:
                        continue
                    da = mv.get(vk(ua), (0, 0)); dc = mv.get(vk(uc), (0, 0))
                    na = (ua[0] + da[0], ua[1] + da[1]); nc = (uc[0] + dc[0], uc[1] + dc[1])
                    w = max(mm(u.GetWidth()), minw.get(key, 0))
                    g, it = gap(u, b.GetLayerName(lid), na, nc, w / 2, info.get(key, (0, 0, None))[2])
                    if g < 0:
                        if DEBUG and DEBUG in t.GetNetname() and k in (0.025, 0.05, 0.1):
                            print(f"  dbg {len(chain)} vtx {len(free)} free k={sgn * k:+.3f}: ({na[0]:.2f},{na[1]:.2f})-"
                                  f"({nc[0]:.2f},{nc[1]:.2f}) w {w} blocked by {it[0]} "
                                  f"{b.FindNet(it[-2]).GetNetname().split('/')[-1] if it[0] != 'edge' else ''} {-g:.3f}")
                        ok = False; break
                if ok:
                    for key, u in run.items():
                        ua, uc = ends(u)
                        if vk(ua) not in mv and vk(uc) not in mv:
                            continue
                        da = mv.get(vk(ua), (0, 0)); dc = mv.get(vk(uc), (0, 0))
                        u.SetStart(P((ua[0] + da[0], ua[1] + da[1]))); u.SetEnd(P((uc[0] + dc[0], uc[1] + dc[1])))
                        if key in minw and mm(u.GetWidth()) < minw[key]:
                            u.SetWidth(pcbnew.FromMM(minw[key]))
                        dead.update(track_keys[key] | {key})
                        put_track(u, tag="+n%d" % nudged)
                    nudged += 1; done_here = True
                    break
            if done_here:
                break
        if done_here:
            break
    return done_here


nudged = 0
for t, layer, a0, c0, pair, side, partner in fit:
    if mm(t.GetWidth()) < minw[t.m_Uuid.AsString()] - 1e-6:
        nudge(t)


floored = 0
for t, layer, a, c, partner in neck_low:  # +0.1 um a side: exact clearance (no MARGIN) is enough
    if gap(t, layer, a, c, NECK_MIN / 2, partner)[0] + MARGIN >= 0:
        t.SetWidth(pcbnew.FromMM(NECK_MIN)); put_track(t, tag="+floor"); floored += 1
    elif WHY:
        d, it = gap(t, layer, a, c, NECK_MIN / 2, partner)
        print(f"  why: {t.GetNetname().split('/')[-1]:10} {layer:6} neck at ({a[0]:.3f},{a[1]:.3f})-({c[0]:.3f},{c[1]:.3f}): "
              f"{it[0]} {b.FindNet(it[-2]).GetNetname().split('/')[-1] if it[0] != 'edge' else ''} short by {-d - MARGIN:.4f} mm")

# Clearance repair: a DDR segment that does not clear at its current width (e.g. a fan-out stub 5 um too close to a via
# hole inside the BGA) is nudged too, inside the courtyards as well.
repaired = 0
for t in list(b.GetTracks()):
    if isinstance(t, pcbnew.PCB_VIA) or "ddr_" not in t.GetNetname() or "CAL" in t.GetNetname():
        continue
    a, c = ends(t)
    if a == c:
        continue
    pt = info.get(t.m_Uuid.AsString(), (0, 0, None))[2]
    if gap(t, b.GetLayerName(t.GetLayer()), a, c, mm(t.GetWidth()) / 2, pt)[0] < 0:
        w0 = t.GetWidth()
        if strictly_in((a[0] + c[0]) / 2, (a[1] + c[1]) / 2) and mm(w0) > NECK_MIN:
            # inside a BGA the neck-down rule allows NECK_MIN: U801's 0.8 mm channel holds a 0.1 mm pair with 0.1 gap
            # and 0.175 mm to both via holes with no margin at all; at 0.09 a nudge has 5 um each way to work with
            t.SetWidth(pcbnew.FromMM(NECK_MIN))
            if gap(t, b.GetLayerName(t.GetLayer()), a, c, NECK_MIN / 2, pt)[0] >= 0:
                dead.update(track_keys[t.m_Uuid.AsString()] | {t.m_Uuid.AsString()}); put_track(t, tag="+neck")
                repaired += 1; continue
        if nudge(t, bga_free=True):
            repaired += 1
        else:
            t.SetWidth(w0)


widen_pass("target")
if WHY:
    for t, layer, a, c, pair, side, partner in fit:
        a, c = ends(t)
        w = (DIFF if pair else SE)[side][-1]
        if mm(t.GetWidth()) < w - 1e-6:
            d, it = gap(t, layer, a, c, w / 2, partner)
            what = "edge" if it[0] == "edge" else f"{it[0]} {b.FindNet(it[-2]).GetNetname().split('/')[-1] or '(no net)'}"
            print(f"  why: {t.GetNetname().split('/')[-1]:10} {layer:6} {mm(t.GetLength()):5.2f} mm at ({a[0]:.2f},{a[1]:.2f})-"
                  f"({c[0]:.2f},{c[1]:.2f}): {what} short by {-d:.3f} mm at {w} mm")
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
print(f"widen{' --xtalk' if XTALK else ''}: {split} split at a courtyard edge, {done} DDR segments brought to the minimum width or wider, "
      f"{narrowed} narrowed to the target, {floored} raised to the neck-down minimum, {nudged} runs nudged ({repaired} to repair a clearance); {sum(narrow.values()):.0f} mm still below the rule minimum")
print("  narrow mm per net:", ", ".join(f"{k} {v:.1f}" for k, v in narrow.most_common()))
