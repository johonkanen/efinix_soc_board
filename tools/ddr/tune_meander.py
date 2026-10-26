#!/usr/bin/env python3
"""LPDDR4 delay tuning by meanders on the routed copper (KiCadRoutingTools venv python; NEXT_SESSION.md phase 3).

    tune_meander.py BOARD.kicad_pcb PLAN.json EDITS.json [--amp 1.0] [--spacing 3] [--clearance 0.11]

PLAN (from `ddr_timing.py --plan`): {net: path delay to add, ps}. For each net, its chains of same-layer segments
outside the BGA courtyards are meandered, longest first (amplitude --amp, else 0.6x, 0.35x), by KiCadRoutingTools' trombone generator
(length_matching.apply_meanders_to_route, which checks each bump against the copper around it) until the deficit is
covered: ps -> mm at the layer's delay (TI135_PCB_NOTES.md §6.5). Meanders on the trunk of a shared CA/CK net add to
both channels alike. Nets are done in plan order (largest first); each one's new copper is an obstacle to the next.
EDITS gets {"remove": [segment uuids], "add": [{net, layer, width, start, end}], "report": {...}}; apply it with
tools/ddr/tune_apply.py (pcbnew), then widen.py (fit and clearance repair) and grade.sh.
"""
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/dev/KiCadRoutingTools/py_router"))
from kicad_parser import parse_kicad_pcb, Segment  # noqa: E402
from routing_config import GridRouteConfig  # noqa: E402
from length_matching import apply_meanders_to_route  # noqa: E402

PS_PER_MM = {"F.Cu": 6.11, "B.Cu": 6.11, "In2.Cu": 7.01, "In5.Cu": 7.01}
args = sys.argv[1:]
opt = {"--amp": 1.0, "--spacing": 3.0, "--clearance": 0.11}
for k in list(opt):
    if k in args:
        i = args.index(k); opt[k] = float(args[i + 1]); del args[i:i + 2]
board, plan_file, out_file = args
pcb = parse_kicad_pcb(board)
plan = json.load(open(plan_file))
ids = {n.name: nid for nid, n in pcb.nets.items()}

# BGA courtyards, approximated by the ball field + 0.95 mm (F.CrtYd is about 1 mm outside the outer balls; the margin
# keeps the points where `widen.py --split-only` cut segments at the real courtyard edge outside). Run that first: a
# segment crossing the edge is otherwise dropped whole, however far it runs outside.
court = []
if os.path.exists(board + ".court.json"):  # the real F.CrtYd boxes, from widen.py --split-only
    court = [tuple(c) for c in json.load(open(board + ".court.json"))]
else:
    for ref in ("U501", "U801"):
        ps = pcb.footprints[ref].pads
        xs = [p.global_x for p in ps]; ys = [p.global_y for p in ps]
        court.append((min(xs) - 0.95, min(ys) - 0.95, max(xs) + 0.95, max(ys) + 0.95))


def inside(x, y, e=1e-4):  # strictly inside: a split point on the edge is outside
    return any(x0 + e < x < x1 - e and y0 + e < y < y1 - e for x0, y0, x1, y1 in court)


def key(x, y):
    return (round(x, 3), round(y, 3))


def chains(segs):
    """Path-ordered chains of segments on one layer, split at junctions and ends (degree != 2)."""
    by_pt = defaultdict(list)
    for s in segs:
        by_pt[key(s.start_x, s.start_y)].append(s); by_pt[key(s.end_x, s.end_y)].append(s)
    used, out = set(), []
    for s in segs:
        if id(s) in used:
            continue
        chain = [s]; used.add(id(s))
        for forward in (True, False):  # grow from both ends while the joint has exactly two segments
            while True:
                end = chain[-1] if forward else chain[0]
                cur = chain[-2] if forward and len(chain) > 1 else (chain[1] if not forward and len(chain) > 1 else None)
                # the free end of `end`: the endpoint not shared with its chain neighbour
                pts = [key(end.start_x, end.start_y), key(end.end_x, end.end_y)]
                if cur is not None:
                    shared = {key(cur.start_x, cur.start_y), key(cur.end_x, cur.end_y)}
                    pts = [p for p in pts if p not in shared] or pts[:1]
                else:
                    pts = pts[1:] if forward else pts[:1]
                p = pts[0]
                nxt = [u for u in by_pt[p] if id(u) not in used]
                if len(by_pt[p]) != 2 or not nxt:
                    break
                used.add(id(nxt[0]))
                if forward:
                    chain.append(nxt[0])
                else:
                    chain.insert(0, nxt[0])
        out.append(chain)
    return out


def oriented(chain):
    """The chain's segments as one start->end path (the generator expects start/end in path order)."""
    if len(chain) == 1:
        return [chain[0]]
    res = []
    a, b2 = chain[0], chain[1]
    nb = {key(b2.start_x, b2.start_y), key(b2.end_x, b2.end_y)}
    cur_end = (a.end_x, a.end_y) if key(a.end_x, a.end_y) in nb else (a.start_x, a.start_y)
    cur_start = (a.start_x, a.start_y) if cur_end == (a.end_x, a.end_y) else (a.end_x, a.end_y)
    res.append(Segment(cur_start[0], cur_start[1], cur_end[0], cur_end[1], a.width, a.layer, a.net_id, a.uuid))
    for s in chain[1:]:
        if key(s.start_x, s.start_y) == key(*cur_end):
            nxt = (s.end_x, s.end_y)
        else:
            nxt = (s.start_x, s.start_y)
        res.append(Segment(cur_end[0], cur_end[1], nxt[0], nxt[1], s.width, s.layer, s.net_id, s.uuid))
        cur_end = nxt
    return res



CLR, HOLE_CLR, PTH_HOLE_CLR, MARGIN = 0.1, 0.175, 0.28, 0.0002  # the board's rules (widen.py)


def _pt_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay; l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _seg_seg(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0:
        return 0.0
    return min(_pt_seg(*a, *c, *d), _pt_seg(*b, *c, *d), _pt_seg(*c, *a, *b), _pt_seg(*d, *a, *b))


def _pad_dist(pad, a, b):
    """Distance from segment a-b to the pad's copper (circle, else its rotated rectangle)."""
    if pad.shape == "circle":
        return _pt_seg(pad.global_x, pad.global_y, *a, *b) - max(pad.size_x, pad.size_y) / 2
    th = math.radians(pad.rotation or 0.0); cs, sn = math.cos(th), math.sin(th)
    def loc(p):  # board -> pad frame
        x, y = p[0] - pad.global_x, p[1] - pad.global_y
        return (x * cs - y * sn, x * sn + y * cs)
    la, lb = loc(a), loc(b); hx, hy = pad.size_x / 2, pad.size_y / 2
    if -hx <= la[0] <= hx and -hy <= la[1] <= hy:
        return 0.0
    corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    return min(_seg_seg(la, lb, corners[i], corners[(i + 1) % 4]) for i in range(4))


def violations(new, nid, layer, box):
    """Count new segments that break a clearance rule against other nets' copper near box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    near = lambda x, y: x0 - 1.5 <= x <= x1 + 1.5 and y0 - 1.5 <= y <= y1 + 1.5
    segs = [o for o in pcb.segments if o.layer == layer and o.net_id != nid
            and (near(o.start_x, o.start_y) or near(o.end_x, o.end_y))]
    vias = [v for v in pcb.vias if v.net_id != nid and near(v.x, v.y)]
    pads = [q for q in pcb_pads if q.net_id != nid and near(q.global_x, q.global_y)
            and (layer in q.layers or "*.Cu" in q.layers)]
    bad = 0
    for s in new:
        a, b, hw = (s.start_x, s.start_y), (s.end_x, s.end_y), s.width / 2
        ok = all(_seg_seg(a, b, (o.start_x, o.start_y), (o.end_x, o.end_y)) - hw - o.width / 2 >= CLR + MARGIN for o in segs)
        ok = ok and all(_pt_seg(v.x, v.y, *a, *b) - hw - v.size / 2 >= CLR + MARGIN and
                        _pt_seg(v.x, v.y, *a, *b) - hw - v.drill / 2 >= HOLE_CLR + MARGIN for v in vias)
        ok = ok and all(_pad_dist(q, a, b) - hw >= CLR + MARGIN and
                        (not q.drill or _pt_seg(q.global_x, q.global_y, *a, *b) - hw - q.drill / 2 >= PTH_HOLE_CLR + MARGIN)
                        for q in pads)
        bad += not ok
    return bad


pcb_pads = [q for plist in pcb.pads_by_net.values() for q in plist]


seglen = lambda s: math.hypot(s.end_x - s.start_x, s.end_y - s.start_y)
remove, add, report = [], [], {}
for net in sorted(plan, key=lambda n: -plan[n]):
    nid = ids.get(net)
    need = plan[net]
    if nid is None or need <= 0.3:
        continue
    mine = [s for s in pcb.segments if s.net_id == nid and s.layer in PS_PER_MM
            and not inside((s.start_x + s.end_x) / 2, (s.start_y + s.end_y) / 2)
            and not inside(s.start_x, s.start_y) and not inside(s.end_x, s.end_y)]
    by_layer = defaultdict(list)
    for s in mine:
        by_layer[s.layer].append(s)
    cands = [oriented(c) for L in by_layer for c in chains(by_layer[L])]
    cands.sort(key=lambda c: -sum(seglen(s) for s in c))
    got = 0.0
    for c in cands:
        left = need - got
        if left <= 0.3:
            break
        L = c[0].layer; w = c[0].width
        before = sum(seglen(s) for s in c)
        box = (min(min(q.start_x, q.end_x) for q in c), min(min(q.start_y, q.end_y) for q in c),
               max(max(q.start_x, q.end_x) for q in c), max(max(q.start_y, q.end_y) for q in c))
        bumps = 0
        # KRT measures a bump from the existing centreline with a corner margin, so a trace already close to a
        # neighbour (legally) gets no bump on either side at the real clearance. Ask it at a small clearance too, and
        # keep a result only if every new segment passes the board's own rules (violations()).
        for amp in (opt["--amp"], opt["--amp"] * 0.6, opt["--amp"] * 0.35):  # smaller bumps fit between vias
            for kc in (opt["--clearance"], 0.03):
                cfg = GridRouteConfig(track_width=w, clearance=kc, meander_amplitude=amp, meander_spacing=opt["--spacing"],
                                      layers=["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "In5.Cu", "In6.Cu", "B.Cu"],
                                      board_edge_clearance=0.5, verbose=bool(os.environ.get("TUNE_VERBOSE")))
                new, bumps = apply_meanders_to_route(c, left / PS_PER_MM[L], cfg, pcb_data=pcb, net_id=nid)
                if bumps and violations([q for q in new if q not in c], nid, L, box) == 0:
                    break
                bumps = 0
            if bumps:
                break
        if bumps == 0:
            continue
        gained = (sum(seglen(s) for s in new) - before) * PS_PER_MM[L]
        got += gained
        olds = {s.uuid for s in c}
        remove += [u for u in olds if u]
        pcb.segments = [s for s in pcb.segments if not (s.net_id == nid and s.uuid in olds)] + \
            [Segment(s.start_x, s.start_y, s.end_x, s.end_y, s.width, s.layer, nid, "new") for s in new]
        add += [{"net": net, "layer": s.layer, "width": s.width, "start": [s.start_x, s.start_y],
                 "end": [s.end_x, s.end_y]} for s in new]
    report[net] = {"need_ps": need, "added_ps": round(got, 1)}
    print(f"  {net.split('/')[-1]:12} need {need:6.1f} ps  added {got:6.1f} ps")
json.dump({"remove": remove, "add": add, "report": report}, open(out_file, "w"))
short = {n: r["need_ps"] - r["added_ps"] for n, r in report.items() if r["need_ps"] - r["added_ps"] > 3}
print(f"tune_meander: {len(report)} nets, {sum(r['added_ps'] for r in report.values()):.0f} of "
      f"{sum(r['need_ps'] for r in report.values()):.0f} ps added; {len(short)} nets > 3 ps short")
