#!/usr/bin/env python3
"""LPDDR4 die-to-die delay per net and the Efinix checks (tools/p2k/bin/kipy tools/ddr/ddr_timing.py [BOARD]).

Board delay = track length per layer x propagation delay (field solve, TI135_PCB_NOTES.md §6.5: In2/In5 stripline
eps_eff 4.42 -> 7.01 ps/mm; F.Cu/B.Cu microstrip with mask eps_eff 3.36 -> 6.11 ps/mm) + 5.5 ps per via (about half
the 1.6 mm board at 6.9 ps/mm; a coarse figure) + the U501 pad-to-die delay on the board (tools/pad_to_die.py).
U801 has no package data. Pairs use the mean of P and N.
Checks (TI135_PCB_NOTES.md §6.3; timing budget at 3700 Mbps, the board is routed to it although the I3 part runs
<= 2.8 Gbps): DQ/DM - DQS of its byte in 0..66 ps (0..375 mil), and |DQ - DQS| <= 75 ps; DQS P/N <= 1.8 ps (10 mil),
CK P/N <= 0.9 ps (5 mil); CA/CKE/CS vs CK within +-5.3 ps (30 mil) of the length rule, and within the 100 ps timing
budget.
"""
import os
import re
import sys

import pcbnew

PS_PER_MM = {"F.Cu": 6.11, "B.Cu": 6.11, "In2.Cu": 7.01, "In5.Cu": 7.01}
VIA_PS = 5.5
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
args = [a for a in sys.argv[1:]]
KICAD_CSV = PLAN = None
NETS = "--nets" in args
if NETS:
    args.remove("--nets")
if "--plan" in args:
    i = args.index("--plan"); PLAN = args[i + 1]; del args[i:i + 2]
if "--kicad" in args:
    i = args.index("--kicad"); KICAD_CSV = args[i + 1]; del args[i:i + 2]
b = pcbnew.LoadBoard(args[0] if args else os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb"))
import heapq
from collections import defaultdict
# copper graph per net: nodes = rounded points on a layer; a via (and a THT/via-in-pad position) joins its layers.
R = lambda v: round(pcbnew.ToMM(v) * 50) / 50   # 0.02 mm snap: routed endpoints differ by a few um
items = defaultdict(lambda: {"seg": [], "via": [], "pads": []})
for t in b.GetTracks():
    n = t.GetNetname()
    if "ddr_" not in n or "CAL" in n:
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        items[n]["via"].append((R(t.GetPosition().x), R(t.GetPosition().y)))
    else:
        L = b.GetLayerName(t.GetLayer())
        items[n]["seg"].append(((R(t.GetStart().x), R(t.GetStart().y)), (R(t.GetEnd().x), R(t.GetEnd().y)), L,
                                pcbnew.ToMM(t.GetLength()) * PS_PER_MM.get(L, 7.01)))
for ref in ("U501", "U801"):
    for p in b.FindFootprintByReference(ref).Pads():
        n = p.GetNetname()
        if n in items:
            bb = p.GetBoundingBox()
            items[n]["pads"].append((ref, (R(p.GetPosition().x), R(p.GetPosition().y)),
                                     (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())),
                                     p.GetPadToDieDelay() / pcbnew.pcbIUScale.IU_PER_PS if ref == "U501" else 0.0))


def path_delays(n):
    """{U801 pad position: die-to-die delay from the U501 pad} along the copper."""
    it = items[n]; adj = defaultdict(list)
    def link(a, c, w):
        adj[a].append((c, w)); adj[c].append((a, w))
    pts = defaultdict(set)
    for a, c, L, w in it["seg"]:
        link((a, L), (c, L), w); pts[a].add(L); pts[c].add(L)
    # join endpoints closer than 0.06 mm, and endpoints that land on another segment's middle (T-junctions)
    ends_by_layer = defaultdict(list)
    for (q, L) in [k for k in adj if k[0] not in ("V", "P")]:
        ends_by_layer[L].append(q)
    for L, qs in ends_by_layer.items():
        for i, q in enumerate(qs):
            for r in qs[i + 1:]:
                if abs(q[0] - r[0]) < 0.06 and abs(q[1] - r[1]) < 0.06:
                    link((q, L), (r, L), 0.0)
        for a, c, L2, w in it["seg"]:
            if L2 != L:
                continue
            dx, dy = c[0] - a[0], c[1] - a[1]; l2 = dx * dx + dy * dy
            if l2 == 0:
                continue
            for q in qs:
                t = ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / l2
                if 0.02 < t < 0.98 and abs((q[0] - a[0]) * dy - (q[1] - a[1]) * dx) / l2 ** 0.5 < 0.03:
                    link((q, L), (a, L), w * t); link((q, L), (c, L), w * (1 - t))
    for v in it["via"]:   # every track end within the via's copper (r <= 0.2 mm) joins it, on any layer
        near = [(q, L) for q in pts for L in pts[q] if abs(q[0] - v[0]) <= 0.2 and abs(q[1] - v[1]) <= 0.2]
        for node in near:
            link(("V", v), node, VIA_PS / 2)
        link(("V", v), (v, "F.Cu"), VIA_PS / 2)
    # pads: join every node inside the pad box on F.Cu (and a via in the pad, through its F.Cu node)
    pad_nodes = []
    for ref, pos, (x0, y0, x1, y1), dd in it["pads"]:
        pn = ("P", ref, pos); pad_nodes.append((ref, pn, dd))
        for v in it["via"]:   # a via overlapping the pad (in it, or offset) connects by copper overlap
            if x0 - 0.15 <= v[0] <= x1 + 0.15 and y0 - 0.15 <= v[1] <= y1 + 0.15:
                link(pn, ("V", v), 0.0)
        for node in list(adj):
            if node[0] in ("V", "P"):
                continue
            q, L = node
            if L == "F.Cu" and x0 - 0.01 <= q[0] <= x1 + 0.01 and y0 - 0.01 <= q[1] <= y1 + 0.01:
                link(pn, (q, L), 0.0)
    src = [(pn, dd) for ref, pn, dd in pad_nodes if ref == "U501"]
    if not src:
        return {}
    start, dd0 = src[0]
    import itertools
    cnt = itertools.count()
    dist = {start: dd0}; pq = [(dd0, next(cnt), start)]
    while pq:
        dv, _, u = heapq.heappop(pq)
        if dv > dist.get(u, 1e18):
            continue
        for v, w in adj[u]:
            if dv + w < dist.get(v, 1e18):
                dist[v] = dv + w; heapq.heappush(pq, (dv + w, next(cnt), v))
    return {pn[2]: dist.get(pn) for ref, pn, dd in pad_nodes if ref == "U801"}


short = lambda n: n.split("/")[-1]
full = {short(n): n for n in items}
ends = {s: path_delays(full[s]) for s in full}


def get(name, which=None):
    e = ends.get(name) or {}
    vals = [v for v in e.values() if v is not None]
    if not vals:
        return None
    return vals if which == "all" else max(vals)


def pair(base):
    p, n = get(base + "_P"), get(base + "_N")
    if p is None or n is None:
        return None, None
    return (p + n) / 2, abs(p - n)


bad = 0
print("byte  DQS(ps)  P/N skew  DQ/DM - DQS min..max (ps)  [rule 0..66, |.| <= 75]")
for k in range(4):
    dqs, sk = pair(f"ddr_dqs{k}")
    members = [f"ddr_dq{8 * k + i}" for i in range(8)] + [f"ddr_dm{k}"]
    missing = [m for m in members if get(m) is None]
    if missing or dqs is None:
        print(f"  {k}   NO PATH for {', '.join(missing) or 'DQS'}"); bad += 1; continue
    diffs = [get(m) - dqs for m in members]
    ok = min(diffs) >= 0 and max(diffs) <= 66 and sk <= 1.8
    bad += not ok
    print(f"  {k}   {dqs:6.1f}   {sk:5.2f}     {min(diffs):7.1f} .. {max(diffs):6.1f}   {'OK' if ok else 'FAIL'}")
    if NETS:
        print("        " + "  ".join(f"{m[4:]} {get(m) - dqs:+.0f}" for m in members) +
              f"  (DQS P {get(f'ddr_dqs{k}_P'):.0f}, N {get(f'ddr_dqs{k}_N'):.0f} ps)")
ck, cks = pair("ddr_ck")
ca = ["ddr_ca0", "ddr_ca1", "ddr_ca2", "ddr_ca3", "ddr_ca4", "ddr_ca5", "ddr_cke0", "ddr_cs0_n", "ddr_cs2_n"]
ckA = get("ddr_ck_P", "all")
allv = []
print(f"CK to each DRAM channel (P leg): {', '.join(f'{v:.1f}' for v in sorted(ckA))} ps; P/N skew {cks:.2f} (rule 0.9)")
for n in ca:
    vs = get(n, "all")
    if vs is None:  # connected per DRC, but no die-to-die path found (e.g. a stub that loops back)
        print(f"   {n:10} NO PATH from U501 to the DRAM"); bad += 1; continue
    allv += [v - ck for v in vs]
    print(f"   {n:10} to each channel: {', '.join(f'{v:6.1f}' for v in sorted(vs))} ps   vs CK {', '.join(f'{v - ck:+6.1f}' for v in sorted(vs))}")
lo, hi = min(allv), max(allv)
print(f"CA/CKE/CS - CK: {lo:+.1f} .. {hi:+.1f} ps   length rule +-5.3: {'OK' if lo >= -5.3 and hi <= 5.3 else 'FAIL'}"
      f"   timing budget +-100: {'OK' if max(abs(lo), abs(hi)) <= 100 else 'FAIL'}")


# ---- meander plan (--plan FILE, for tools/ddr/tune.sh): the path delay each net must gain, in ps -------------------
# Meanders only add delay. CA/CKE/CS and both CK legs: every path to the group's longest (CA-CK and CK P/N -> 0).
# Byte k: DQS P and N to max(P, N, longest DQ/DM - DQ_HI); every DQ/DM to at least DQS + DQ_LO. That keeps DQ - DQS in
# [DQ_LO, DQ_HI] inside Efinix's 0..66 ps with margin either side for the meander error.
DQ_LO, DQ_HI = 8.0, 58.0
if PLAN:
    import json as _json
    plan = {}
    grp = ca + ["ddr_ck_P", "ddr_ck_N"]
    T = max(get(n) for n in grp if get(n) is not None)
    for n in grp:
        if get(n) is not None:
            plan[n] = T - get(n)
    for k in range(4):
        p_, n_ = f"ddr_dqs{k}_P", f"ddr_dqs{k}_N"
        members = [f"ddr_dq{8 * k + i}" for i in range(8)] + [f"ddr_dm{k}"]
        if any(get(m) is None for m in members + [p_, n_]):
            continue
        dqs = max(get(p_), get(n_), max(get(m) for m in members) - DQ_HI)
        plan[p_], plan[n_] = dqs - get(p_), dqs - get(n_)
        for m in members:
            plan[m] = max(0.0, dqs + DQ_LO - get(m))
    plan = {full[n]: round(v, 2) for n, v in plan.items() if v > 0.3}
    _json.dump(plan, open(PLAN, "w"), indent=1)
    print(f"\nplan: {len(plan)} nets to lengthen, {sum(plan.values()):.0f} ps in all, largest "
          f"{max(plan.values()):.1f} ps -> {PLAN}")

# ---- KiCad tuner targets (--kicad CSV from tools/ddr/kicad_delays.sh) -------------------------------------------
# KiCad sums a net's whole copper, so its readout = path + (for a shared CA/CK net) the second branch. A net that must
# gain d ps of path delay must read kicad + d in KiCad. Meanders only add delay, so every target is the group's longest.
if KICAD_CSV:
    import csv as _csv
    kd = {r["net"]: float(r["kicad_ps"]) for r in _csv.DictReader(open(KICAD_CSV))}
    print("\nKiCad readout vs path (model check; shared CA/CK nets add one branch, ~10-20 ps):")
    for n in sorted(kd):
        if get(n) is not None:
            print(f"   {n:12} KiCad {kd[n]:6.1f}   path {get(n):6.1f}   diff {kd[n] - get(n):+6.1f}")
    # KiCad is the reference for tuning (its tuner and DRC use it): path_k = KiCad readout, minus the second branch on a
    # shared CA/CK net (its exact geometry from tools/ddr/ca_trunk_branch.py). The model check above differs by the
    # via model (KiCad: 7.2 ps/mm of traversed height; here a flat 5.5 ps) and stub copper KiCad also counts.
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("ctb", os.path.join(ROOT, "tools", "ddr", "ca_trunk_branch.py"))
    ctb = _ilu.module_from_spec(_spec); _spec.loader.exec_module(ctb)
    ctb.U801 = b.FindFootprintByReference("U801")
    branch = {n: ctb.branch_delay(b, n) for n in ctb.SHARED}
    get_model = get
    def get(n):
        return kd[n] - branch.get(n, 0.0) if n in kd else get_model(n)
    print("\nPaths in KiCad terms (readout - second branch for shared nets): " +
          ", ".join(f"{n} {get(n):.1f}" for n in ca + ["ddr_ck_P", "ddr_ck_N"]))
    print("\nTUNER TARGETS (tune each net in pcbnew until KiCad shows this delay):")
    grp = ca + ["ddr_ck_P", "ddr_ck_N"]
    T = max(get(n) for n in grp)
    print(f" CA/CKE/CS/CK group: every path to {T:.1f} ps")
    for n in grp:
        d = T - get(n)
        print(f"   {n:12} now {kd[n]:6.1f} ps -> {kd[n] + d:6.1f} ps   (+{d:5.1f})" if d > 0.4 else f"   {n:12} {kd[n]:6.1f} ps  (longest, leave)")
    for k in range(4):
        p_, n_ = f"ddr_dqs{k}_P", f"ddr_dqs{k}_N"
        members = [f"ddr_dq{8 * k + i}" for i in range(8)] + [f"ddr_dm{k}"]
        dqs = max(get(p_), get(n_))
        top = max(get(m) for m in members)
        if top - dqs > 60:                    # a DQ already > 60 ps over: raise DQS so it sits <= 60 under it
            dqs = top - 60
        print(f" byte {k}: DQS P/N to {dqs:.1f} ps, DQ/DM to >= {dqs + 5:.1f} ps (<= {dqs + 66:.1f})")
        for n in [p_, n_]:
            d = dqs - get(n)
            print(f"   {n:12} now {kd[n]:6.1f} ps -> {kd[n] + d:6.1f} ps   (+{d:5.1f})" if d > 0.4 else f"   {n:12} {kd[n]:6.1f} ps  (leave)")
        for n in members:
            d = dqs + 5 - get(n)
            if d > 0.4:
                print(f"   {n:12} now {kd[n]:6.1f} ps -> {kd[n] + d:6.1f} ps   (+{d:5.1f})")
