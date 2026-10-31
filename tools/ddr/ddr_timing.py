#!/usr/bin/env python3
"""LPDDR4 die-to-die delay per net and the Efinix checks (tools/p2k/bin/kipy tools/ddr/ddr_timing.py [BOARD]).

Board delay = track length per layer x propagation delay (field solve, TI135_PCB_NOTES.md §6.5: In2/In5 stripline
eps_eff 4.42 -> 7.01 ps/mm; F.Cu/B.Cu microstrip with mask eps_eff 3.36 -> 6.11 ps/mm) + the via barrel between the
layers it joins (stack-up height x the tuning profile's via delay, 7.2 ps/mm, as KiCad counts it: F.Cu -> In2 1.8 ps,
F.Cu -> In5 9.4 ps, F.Cu -> B.Cu 11.1 ps) + the U501 pad-to-die delay on the board (tools/pad_to_die.py).
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
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
args = [a for a in sys.argv[1:]]
KICAD_CSV = PLAN = RULES = None
NETS = "--nets" in args
if NETS:
    args.remove("--nets")
if "--plan" in args:
    i = args.index("--plan"); PLAN = args[i + 1]; del args[i:i + 2]
if "--kicad" in args:
    i = args.index("--kicad"); KICAD_CSV = args[i + 1]; del args[i:i + 2]
if "--rules" in args:   # with --kicad: write the targets as DRC length rules (tools/ddr/delay_rules.sh)
    i = args.index("--rules"); RULES = args[i + 1]; del args[i:i + 2]
BOARD = args[0] if args else os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb")
b = pcbnew.LoadBoard(BOARD)


def _via_model():
    """Copper layer depth (mm, top of F.Cu to top of each copper layer) from the board's stack-up, and the via delay
    (ps/mm) of the LPDDR4 tuning profile in the project: KiCad's own via model for time-domain tuning."""
    import json
    src = open(BOARD).read()
    st = src[src.index("(stackup"):src.index("(copper_finish")]
    z, depth = 0.0, {}
    for name, body in re.findall(r'\(layer "([^"]+)"(.*?)(?=\(layer "|\Z)', st, re.S):
        if "Mask" in name or "Paste" in name or "SilkS" in name:
            continue
        if name.endswith(".Cu"):
            depth[name] = z
        t = re.search(r"\(thickness ([0-9.]+)", body)
        z += float(t.group(1)) if t else 0.0
    pro = json.load(open(os.path.splitext(BOARD)[0] + ".kicad_pro"))
    prof = [p for p in pro["tuning_profiles"]["tuning_profiles_impedance_geometric"] if "LPDDR4" in p["profile_name"]]
    return depth, prof[0]["via_prop_delay"] / 1e6


DEPTH, VIA_PS_MM = _via_model()


def via_ps(layers):
    """KiCad: a via counts the barrel between the outermost layers it joins."""
    zs = [DEPTH[L] for L in layers if L in DEPTH]
    return (max(zs) - min(zs)) * VIA_PS_MM if zs else 0.0
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
        layers = sorted({L for _, L in near} | {"F.Cu"}, key=lambda L: DEPTH.get(L, 0.0))
        for L1, L2 in zip(layers, layers[1:]):   # the barrel, layer to layer
            link(("V", v, L1), ("V", v, L2), via_ps([L1, L2]))
        for node in near:
            link(("V", v, node[1]), node, 0.0)
        link(("V", v, "F.Cu"), (v, "F.Cu"), 0.0)
    # pads: join every node inside the pad box on F.Cu (and a via in the pad, through its F.Cu node)
    pad_nodes = []
    for ref, pos, (x0, y0, x1, y1), dd in it["pads"]:
        pn = ("P", ref, pos); pad_nodes.append((ref, pn, dd))
        for v in it["via"]:   # a via overlapping the pad (in it, or offset) connects by copper overlap
            if x0 - 0.15 <= v[0] <= x1 + 0.15 and y0 - 0.15 <= v[1] <= y1 + 0.15:
                link(pn, ("V", v, "F.Cu"), 0.0)
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
DQ_LO, DQ_HI = float(os.environ.get("DQ_LO", 8.0)), float(os.environ.get("DQ_HI", 58.0))
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
        if get(p_) is None or get(n_) is None:
            continue
        members = [m for m in members if get(m) is not None]  # a byte being routed net by net (byte_seq.sh)
        dqs = max(get(p_), get(n_), max([get(m) for m in members] or [0]) - DQ_HI)
        plan[p_], plan[n_] = dqs - get(p_), dqs - get(n_)
        for m in members:
            plan[m] = max(0.0, dqs + DQ_LO - get(m))
    plan = {full[n]: round(v, 2) for n, v in plan.items() if v > 0.3}
    _json.dump(plan, open(PLAN, "w"), indent=1)
    print(f"\nplan: {len(plan)} nets to lengthen, {sum(plan.values()):.0f} ps in all, largest "
          f"{max(plan.values() or [0]):.1f} ps -> {PLAN}")

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
    # KiCad is the reference for tuning (its tuner and DRC use it): path_k = KiCad readout, minus the copper that is not
    # on the die-to-die path of a shared CA/CK net (its second branch, measured on the routed board: all of the net's
    # copper in the path model minus its longest U501 -> U801 path). Both use KiCad's via model, so on a point-to-point
    # net the model check above reads ~0; more is copper off the pad-to-pad path (a stub or a loop) that KiCad counts.
    def total_model(s):
        it = items[full[s]]
        def layers(v):   # the layers a via joins: track ends on it, and F.Cu when it sits in a pad
            ls = {L for a, c, L, _ in it["seg"] for q in (a, c) if abs(q[0] - v[0]) <= 0.2 and abs(q[1] - v[1]) <= 0.2}
            if any(x0 - 0.15 <= v[0] <= x1 + 0.15 and y0 - 0.15 <= v[1] <= y1 + 0.15 for *_, (x0, y0, x1, y1), _ in it["pads"]):
                ls.add("F.Cu")
            return ls
        return (sum(w for *_, w in it["seg"]) + sum(via_ps(layers(v)) for v in it["via"]) +
                max([dd for ref, *_, dd in it["pads"] if ref == "U501"] or [0.0]))
    branch = {n: total_model(n) - get(n) for n in ca + ["ddr_ck_P", "ddr_ck_N"]
              if get(n) is not None and len(ends.get(n) or {}) > 1}
    get_model = get
    def get(n):
        return kd[n] - branch.get(n, 0.0) if n in kd else get_model(n)
    print("\nSecond branch (shared nets, model): " + ", ".join(f"{n} {v:.1f}" for n, v in branch.items()))
    print("Paths in KiCad terms (readout - second branch for shared nets): " +
          ", ".join(f"{n} {get(n):.1f}" for n in ca + ["ddr_ck_P", "ddr_ck_N"]))
    print("\nTUNER TARGETS (pcbnew's tuner delay, pad to pad; DRC adds the second branch of a shared net):")
    def dqs_target(k):
        dqs = max(get(f"ddr_dqs{k}_P"), get(f"ddr_dqs{k}_N"))
        return dqs                           # a DQ more than DQ_MAX over its DQS is flagged: shorten its meander
    # Efinix: every DQS shorter than CK (write leveling only delays DQS), so the CA/CK group sits CK_OVER_DQS above the
    # latest DQS when that is longer than the group's own longest path.
    CK_OVER_DQS = float(os.environ.get("CK_OVER_DQS", 5.0))
    DQ_MAX = float(os.environ.get("DQ_MAX", 15.0))      # DQ/DM window DQS + 5 .. DQ_MAX ps, aimed at + 10
    grp = ca + ["ddr_ck_P", "ddr_ck_N"]
    T_ca = max(get(n) for n in grp)
    T_dqs = max(dqs_target(k) for k in range(4)) + CK_OVER_DQS
    T = max(T_ca, T_dqs)
    print(f" CA/CKE/CS/CK group: every path to {T:.1f} ps (longest path {T_ca:.1f}, latest DQS + {CK_OVER_DQS:.0f} = {T_dqs:.1f})")
    rules = []
    for n in grp:
        d = T - get(n)
        print(f"   {n:12} now {get(n):6.1f} ps -> {T:6.1f} ps   (+{d:5.1f})" if d > 0.4 else f"   {n:12} {get(n):6.1f} ps  (longest, leave)")
        # pcbnew's tuner reads the pad-to-pad path, DRC the whole net (path + the second branch of a shared net).
        # One rule serves both: min/opt in path terms (the tuner, and "Update all tuning patterns", aim at opt; a path
        # below min shows in the tuner), max = path + tol + the measured branch (a net too long shows in DRC). So a
        # shared net is good when its pattern is green after an update AND DRC is green. A pattern override is not
        # honoured when the GUI regenerates patterns (2026-10-31: they were tuned to the rule instead).
        tol = 0.4 if "ck_" in n else 2.5           # CK P/N each +-0.4 -> P/N <= 0.8 ps (Efinix 0.9)
        rules.append((n[4:], [n], T, (-tol, 0.0, tol + branch.get(n, 0.0))))
    for k in range(4):
        p_, n_ = f"ddr_dqs{k}_P", f"ddr_dqs{k}_N"
        members = [f"ddr_dq{8 * k + i}" for i in range(8)] + [f"ddr_dm{k}"]
        dqs = dqs_target(k)
        print(f" byte {k}: DQS P/N to {dqs:.1f} ps, DQ/DM to {dqs + 5:.1f} .. {dqs + DQ_MAX:.1f} ps")
        for n in [p_, n_]:
            d = dqs - get(n)
            print(f"   {n:12} now {kd[n]:6.1f} ps -> {kd[n] + d:6.1f} ps   (+{d:5.1f})" if d > 0.4 else f"   {n:12} {kd[n]:6.1f} ps  (leave)")
        for n in members:
            d = dqs + 5 - get(n)
            if d > 0.4:
                print(f"   {n:12} now {kd[n]:6.1f} ps -> {kd[n] + d:6.1f} ps   (+{d:5.1f})")
            elif get(n) > dqs + DQ_MAX:
                print(f"   {n:12} now {kd[n]:6.1f} ps -> <= {dqs + DQ_MAX:6.1f} ps   (TOO LONG by {get(n) - dqs - DQ_MAX:.1f})")
        rules.append((f"byte{k}_dqs", [p_, n_], dqs, (-0.5, 0.0, 0.5)))
        rules.append((f"byte{k}_dq", members, dqs, (5.0, 10.0, DQ_MAX)))
    if RULES:
        # KiCad's length constraint is per net, in ps with the tuning profiles; its tuner aims at opt. One rule per
        # target: CA/CKE/CS each to the group path (+-2.5 ps: CA - CK <= 5 ps, Efinix 30 mil = 5.3 ps), CK P/N +-0.4 ps,
        # DQS P/N +-0.5 ps, DQ/DM DQS + 5 / 10 / 15 ps (Efinix allows 0..66; the tight max keeps DQ-DQ skew in a byte
        # <= 10 ps). Shared nets: see above (tuner + DRC).
        cond = lambda ns: " || ".join(f"A.NetName == '{full[n]}'" for n in ns)
        with open(RULES, "w") as f:
            for name, ns, t, (lo, opt, hi) in rules:
                f.write(f'(rule "lpddr_delay_{name}"\n\t(condition "{cond(ns)}")\n'
                        f'\t(constraint length (min {t + lo:.1f}ps) (opt {t + opt:.1f}ps) (max {t + hi:.1f}ps)))\n')
        print(f"\n{len(rules)} length rules -> {RULES}")
