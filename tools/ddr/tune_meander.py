#!/usr/bin/env python3
"""LPDDR4 delay tuning by meanders on the routed copper (KiCadRoutingTools venv python; NEXT_SESSION.md phase 3).

    tune_meander.py BOARD.kicad_pcb PLAN.json EDITS.json [--amp 1.0] [--spacing 3] [--clearance 0.11]

PLAN (from `ddr_timing.py --plan`): {net: path delay to add, ps}. For each net, its chains of same-layer segments
outside the BGA courtyards are meandered, longest first, by KiCadRoutingTools' trombone generator
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

# BGA courtyards, approximated by the ball field + 1 mm (the footprints' F.CrtYd is 1 mm outside the outer balls)
court = []
for ref in ("U501", "U801"):
    ps = pcb.footprints[ref].pads
    xs = [p.global_x for p in ps]; ys = [p.global_y for p in ps]
    court.append((min(xs) - 1.0, min(ys) - 1.0, max(xs) + 1.0, max(ys) + 1.0))


def inside(x, y):
    return any(x0 < x < x1 and y0 < y < y1 for x0, y0, x1, y1 in court)


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
        cfg = GridRouteConfig(track_width=w, clearance=opt["--clearance"], meander_amplitude=opt["--amp"],
                              meander_spacing=opt["--spacing"], verbose=bool(os.environ.get("TUNE_VERBOSE")))
        before = sum(seglen(s) for s in c)
        new, bumps = apply_meanders_to_route(c, left / PS_PER_MM[L], cfg, pcb_data=pcb, net_id=nid)
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
