#!/usr/bin/env python3
"""0201 decaps under U501 placed straight on a supply/GND via pair (kipy): place_bga_decaps.py IN OUT REF [REF ...]

U501's balls are on a 0.8 mm pitch with a 0.3/0.15 via in most pads (tools/via_in_pad.py). Between two via columns
there is 0.5 mm of free copper, too little for a decap and its clearance, but an 0201 (pads 0.46 x 0.40 at 0.64 mm)
sits with its two pads right on two adjacent vias, rail and GND: the shortest decap loop there is. For each listed
cap under U501 (B.Cu) this picks such a pair of its own rail, pad 1 on the rail via, spread over the rail's pairs
(farthest point first). A position is taken only if both pads and the courtyard clear everything else on B.Cu:
other nets' vias (copper 0.1 mm, hole 0.175 mm), tracks and pads (0.1 mm), other courtyards. A cap with no free
pair keeps its place, or moves to the nearest free spot if an earlier cap took it. Give the 0201 refs first: the
refs are placed in order, so the smallest caps get the best spots.
"""
import math
import sys
from collections import defaultdict

import pcbnew

mm, FM = pcbnew.ToMM, pcbnew.FromMM
CLR, HOLE_CLR, MARGIN = 0.1, 0.175, 0.0005
WHY = __import__('collections').Counter()  # why spots were refused (printed with --why)
b = pcbnew.LoadBoard(sys.argv[1]); refs = [a for a in sys.argv[3:] if not a.startswith('--')]
u = b.FindFootprintByReference("U501"); c = u.GetCourtyard(pcbnew.F_CrtYd).BBox()
ux0, uy0, ux1, uy1 = mm(c.GetLeft()), mm(c.GetTop()), mm(c.GetRight()), mm(c.GetBottom())
key = lambda x, y: (round(x, 2), round(y, 2))
vias = {}
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        vias[key(mm(t.GetPosition().x), mm(t.GetPosition().y))] = t
balls = {key(mm(p.GetPosition().x), mm(p.GetPosition().y)): p.GetNetname() for p in u.Pads()}
vb = {k: n for k, n in balls.items() if k in vias and vias[k].GetNetname() == n}  # via-in-pad of the ball's own net

caps = [b.FindFootprintByReference(r) for r in refs]
caps = [f for f in caps if f.IsFlipped() and ux0 < mm(f.GetPosition().x) < ux1 and uy0 < mm(f.GetPosition().y) < uy1]
copper = lambda f: [p for p in f.Pads() if p.GetNumber() and p.IsOnCopperLayer()]  # the 0201 has 2 paste-only pads
rail_of = {f.GetReference(): next(p.GetNetname() for p in copper(f) if p.GetNetname() != "GND") for f in caps}
pairs = defaultdict(list)  # rail -> (rail via, gnd via, horizontal)
for (x, y), n in vb.items():
    for dx, dy in ((0.8, 0), (0, 0.8), (-0.8, 0), (0, -0.8)):
        k = key(x + dx, y + dy)
        if n != "GND" and vb.get(k) == "GND":
            pairs[n].append(((x, y), k, dy == 0))

home = {f.GetReference(): (f.GetPosition(), f.GetOrientation()) for f in caps}
for f in caps:  # off the board while choosing, so the old spots do not block
    f.SetPosition(pcbnew.VECTOR2I(FM(250), FM(150)))


def pt_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay; l2 = dx * dx + dy * dy
    t = 0 if l2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def rect_dist(r, s):  # axis-aligned rectangles (x0, y0, x1, y1)
    dx = max(r[0] - s[2], s[0] - r[2], 0); dy = max(r[1] - s[3], s[1] - r[3], 0)
    return math.hypot(dx, dy)


def bbox(item):
    bb = item.GetBoundingBox(); return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())


def court(f):
    bb = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
    return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())


bcu_tracks = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.B_Cu]
others = lambda f: [o for o in b.GetFootprints() if o.GetReference() != f.GetReference() and o.IsFlipped()]


def fits(f):
    cf = court(f)
    for o in others(f):
        oc = court(o)
        if cf[0] < oc[2] and oc[0] < cf[2] and cf[1] < oc[3] and oc[1] < cf[3]:
            WHY[f'courtyard {o.GetReference()}'] += 1; return False
    for p in copper(f):
        pr = bbox(p); net = p.GetNetCode()
        cx, cy = (pr[0] + pr[2]) / 2, (pr[1] + pr[3]) / 2
        for v in vias.values():
            if v.GetNetCode() == net:
                continue
            vx, vy = mm(v.GetPosition().x), mm(v.GetPosition().y)
            if abs(vx - cx) > 1.2 or abs(vy - cy) > 1.2:
                continue
            d = rect_dist(pr, (vx, vy, vx, vy))
            if d < mm(v.GetWidth(pcbnew.B_Cu)) / 2 + CLR + MARGIN or d < mm(v.GetDrillValue()) / 2 + HOLE_CLR + MARGIN:
                WHY[f'via {v.GetNetname().split("/")[-1]}'] += 1; return False
        for t in bcu_tracks:
            if t.GetNetCode() == net:
                continue
            ax, ay, bx, by = mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y)
            if min(ax, bx) > pr[2] + 1 or max(ax, bx) < pr[0] - 1 or min(ay, by) > pr[3] + 1 or max(ay, by) < pr[1] - 1:
                continue
            # distance from the track centreline to the pad rectangle (sampled along the track)
            n = max(2, int(math.hypot(bx - ax, by - ay) / 0.05))
            d = min(rect_dist(pr, (ax + (bx - ax) * i / n, ay + (by - ay) * i / n) * 2) for i in range(n + 1))
            if d < mm(t.GetWidth()) / 2 + CLR + MARGIN:
                WHY[f'track {t.GetNetname().split("/")[-1]}'] += 1; return False
        for o in others(f):
            for q in copper(o):
                if q.GetNetCode() != net and q.IsOnLayer(pcbnew.B_Cu) and rect_dist(pr, bbox(q)) < CLR + MARGIN:
                    WHY[f'pad {o.GetReference()}'] += 1; return False
    return True


def put(f, rv, gv, horiz):
    """Centre between the two vias, pad 1 on the rail via."""
    f.SetPosition(pcbnew.VECTOR2I(FM((rv[0] + gv[0]) / 2), FM((rv[1] + gv[1]) / 2)))
    for rot in ((0, 180) if horiz else (90, 270)):
        f.SetOrientationDegrees(rot)
        p1 = [p for p in f.Pads() if p.GetNumber() == "1"][0]
        if math.hypot(mm(p1.GetPosition().x) - rv[0], mm(p1.GetPosition().y) - rv[1]) < 0.2:
            return True
    return False


placed, kept, stuck, moved_free = [], [], [], []
by_rail = defaultdict(list)
for f in caps:
    by_rail[rail_of[f.GetReference()]].append(f)
chosen_all = defaultdict(list)
for f in caps:  # in the order given: the 0201 first, then the larger caps take what is left
    rail = rail_of[f.GetReference()]; fs = [f]
    cand = pairs.get(rail, [])
    if cand:  # start next to the rail's centroid, then farthest point from what this rail already has
        cx = sum((a[0] + g[0]) / 2 for a, g, h in cand) / len(cand); cy = sum((a[1] + g[1]) / 2 for a, g, h in cand) / len(cand)
    chosen = chosen_all[rail]
    for f in fs:
        def score(pr):
            m = ((pr[0][0] + pr[1][0]) / 2, (pr[0][1] + pr[1][1]) / 2)
            if not chosen:
                return -math.hypot(m[0] - cx, m[1] - cy)
            return min(math.hypot(m[0] - q[0], m[1] - q[1]) for q in chosen)
        ok = False
        for pr in sorted(cand, key=score, reverse=True):
            if put(f, *pr) and fits(f):
                chosen.append(((pr[0][0] + pr[1][0]) / 2, (pr[0][1] + pr[1][1]) / 2)); cand.remove(pr); ok = True
                break
        if ok:
            placed.append(f.GetReference())
        else:  # back to where it was, or the nearest free spot (an earlier cap may have taken it)
            pos, ori = home[f.GetReference()]; f.SetPosition(pos); f.SetOrientation(ori)
            if not fits(f):
                hx, hy = mm(pos.x), mm(pos.y); free = False
                for rad in [i * 0.1 for i in range(1, 61)]:
                    for k in range(24):
                        a = 2 * math.pi * k / 24
                        for rot in (0, 90):
                            f.SetOrientationDegrees(rot)
                            f.SetPosition(pcbnew.VECTOR2I(FM(hx + rad * math.cos(a)), FM(hy + rad * math.sin(a))))
                            if fits(f):
                                free = True; break
                        if free: break
                    if free: break
                if not free:
                    f.SetPosition(pos); f.SetOrientation(ori); stuck.append(f.GetReference())
                else:
                    moved_free.append(f"{f.GetReference()} {rad:.1f} mm")
            kept.append(f.GetReference())
pcbnew.SaveBoard(sys.argv[2], b)
print(f"place_bga_decaps: {len(placed)} caps on rail/GND via pairs under U501; not on a pair: {kept or 'none'}")
print(f"  moved to the nearest free spot: {moved_free or 'none'}; overlapping, left as they were: {stuck or 'none'}")
for rail, fs in by_rail.items():
    print(f"  {rail}: {sum(1 for f in fs if f.GetReference() in placed)}/{len(fs)} on pairs ({len(pairs.get(rail, []))} pair spots)")
if "--why" in sys.argv:
    print("  refused spots:", ", ".join(f"{k} {v}" for k, v in WHY.most_common(15)))
