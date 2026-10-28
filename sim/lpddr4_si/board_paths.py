#!/usr/bin/env python3
"""Per-net LPDDR4 paths from a board copy, for the SI model: layer runs (mm), vias, T point, U501 pad-to-die.

  tools/p2k/bin/kipy sim/lpddr4_si/board_paths.py BOARD.kicad_pcb > sim/lpddr4_si/results/board_paths.json

For every ddr_ net: the shortest copper path from the U501 pad to each U801 pad (same graph as
tools/ddr/ddr_timing.py: 0.02 mm snap, T-junctions, vias join every track end within 0.2 mm, via-in-pad joins the
pad), written as a list of runs [layer, mm, mm narrower than 0.125 mm] with 'via' entries between them. For nets with two U801 pads (CA/CKE/CK)
the common part is the trunk and the rest the two branches. Read only: never run it on kicad/ti135_card.kicad_pcb in
place of a copy if a pcbnew session might save it (this script does not save).
"""
import heapq
import itertools
import json
import sys
from collections import defaultdict

import pcbnew

R = lambda v: round(pcbnew.ToMM(v) * 50) / 50
NECK_W = 0.125
b = pcbnew.LoadBoard(sys.argv[1])
items = defaultdict(lambda: {"seg": [], "via": [], "pads": []})
for t in b.GetTracks():
    n = t.GetNetname()
    if "ddr_" not in n or "CAL" in n:
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        items[n]["via"].append((R(t.GetPosition().x), R(t.GetPosition().y)))
    else:
        items[n]["seg"].append(((R(t.GetStart().x), R(t.GetStart().y)), (R(t.GetEnd().x), R(t.GetEnd().y)),
                                b.GetLayerName(t.GetLayer()), pcbnew.ToMM(t.GetLength()), pcbnew.ToMM(t.GetWidth())))
for ref in ("U501", "U801"):
    for p in b.FindFootprintByReference(ref).Pads():
        n = p.GetNetname()
        if n in items:
            bb = p.GetBoundingBox()
            items[n]["pads"].append((ref, p.GetNumber(), (R(p.GetPosition().x), R(p.GetPosition().y)),
                                     (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()),
                                      pcbnew.ToMM(bb.GetBottom())),
                                     p.GetPadToDieDelay() / pcbnew.pcbIUScale.IU_PER_PS if ref == "U501" else 0.0))


def paths(n):
    it = items[n]; adj = defaultdict(list)

    def link(a, c, w, info):
        adj[a].append((c, w, info)); adj[c].append((a, w, info))
    pts = defaultdict(set)
    for a, c, L, mm, wd in it["seg"]:
        link((a, L), (c, L), mm, (L, mm, wd)); pts[a].add(L); pts[c].add(L)
    ends = defaultdict(list)
    for (q, L) in [k for k in adj if k[0] not in ("V", "P")]:
        ends[L].append(q)
    for L, qs in ends.items():
        for i, q in enumerate(qs):
            for r in qs[i + 1:]:
                if abs(q[0] - r[0]) < 0.06 and abs(q[1] - r[1]) < 0.06:
                    link((q, L), (r, L), 0.0, None)
        for a, c, L2, mm, wd in it["seg"]:
            if L2 != L:
                continue
            dx, dy = c[0] - a[0], c[1] - a[1]; l2 = dx * dx + dy * dy
            if l2 == 0:
                continue
            for q in qs:
                t = ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / l2
                if 0.02 < t < 0.98 and abs((q[0] - a[0]) * dy - (q[1] - a[1]) * dx) / l2 ** 0.5 < 0.03:
                    link((q, L), (a, L), mm * t, (L, mm * t, wd)); link((q, L), (c, L), mm * (1 - t), (L, mm * (1 - t), wd))
    for v in it["via"]:
        for node in [(q, L) for q in pts for L in pts[q] if abs(q[0] - v[0]) <= 0.2 and abs(q[1] - v[1]) <= 0.2]:
            link(("V", v), node, 0.8, "via")      # 0.8 mm-equivalent weight: prefer fewer vias on equal copper
        link(("V", v), (v, "F.Cu"), 0.8, "via")
    pads = []
    for ref, num, pos, (x0, y0, x1, y1), dd in it["pads"]:
        pn = ("P", ref, num); pads.append((ref, num, pn, dd))
        for v in it["via"]:
            if x0 - 0.15 <= v[0] <= x1 + 0.15 and y0 - 0.15 <= v[1] <= y1 + 0.15:
                link(pn, ("V", v), 0.0, "vip")
        for node in list(adj):
            if node[0] in ("V", "P"):
                continue
            q, L = node
            if L == "F.Cu" and x0 - 0.01 <= q[0] <= x1 + 0.01 and y0 - 0.01 <= q[1] <= y1 + 0.01:
                link(pn, (q, L), 0.0, "pad")
    src = [p for p in pads if p[0] == "U501"]
    if not src:
        return None
    _, num0, start, dd0 = src[0]
    cnt = itertools.count(); dist = {start: 0.0}; prev = {}; pq = [(0.0, next(cnt), start)]
    while pq:
        dv, _, u = heapq.heappop(pq)
        if dv > dist.get(u, 1e18):
            continue
        for v, w, info in adj[u]:
            if dv + w < dist.get(v, 1e18):
                dist[v] = dv + w; prev[v] = (u, info); heapq.heappush(pq, (dv + w, next(cnt), v))
    out = {"u501_pad": num0, "u501_pad_to_die_ps": round(dd0, 2), "legs": {}}
    for ref, num, pn, dd in pads:
        if ref != "U801" or pn not in dist:
            continue
        steps, u = [], pn
        while u != start:
            u0, info = prev[u]; steps.append((u0, info)); u = u0
        steps.reverse()
        out["legs"][num] = steps
    return out


def runs(steps):
    """[(node, info)] -> [['In2.Cu', mm, mm_neck], 'via', ...] merged by layer; mm_neck = the part narrower than
    NECK_W (the BGA neck-downs, 0.09-0.10 mm)."""
    r = []
    for node, info in steps:
        if info is None or info in ("pad",):
            continue
        if info in ("via", "vip"):
            if r and r[-1] == "via":
                continue          # pad -> via -> track counts once
            r.append("via"); continue
        L, mm, wd = info
        nk = mm if wd < NECK_W else 0.0
        if r and r[-1] != "via" and r[-1][0] == L:
            r[-1][1] += mm; r[-1][2] += nk
        else:
            r.append([L, mm, nk])
    return [x if x == "via" else [x[0], round(x[1], 3), round(x[2], 3)] for x in r]


res = {}
for n in sorted(items):
    p = paths(n)
    if not p or not p["legs"]:
        continue
    legs = list(p["legs"].items())
    e = {"u501_pad": p["u501_pad"], "u501_pad_to_die_ps": p["u501_pad_to_die_ps"]}
    if len(legs) == 1:
        e["u801_pad"] = legs[0][0]; e["path"] = runs(legs[0][1])
    else:
        a, c = legs[0][1], legs[1][1]
        k = 0
        while k < min(len(a), len(c)) and a[k][0] == c[k][0]:
            k += 1
        e["trunk"] = runs(a[:k]); e["branches"] = {legs[0][0]: runs(a[k:]), legs[1][0]: runs(c[k:])}
        e["paths"] = {num: runs(st) for num, st in legs}
    res[n.split("/")[-1]] = e
json.dump(res, sys.stdout, indent=1)
print()
