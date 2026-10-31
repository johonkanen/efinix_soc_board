"""Coupled lengths between LPDDR4 nets on the routed board (LPDDR4_IBIS_PLAN.md step 6): every pair of parallel
track pieces of two different ddr_ nets on the same layer, edge gap <= 0.4 mm, outside the U501/U801 courtyards.
  ../../tools/p2k/bin/kipy coupled_lengths.py [BOARD] > results/coupled_lengths.md
Per victim net: coupled length per (layer, gap bucket) to each aggressor, and the totals the crosstalk runs use."""
import collections, math, sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1] if len(sys.argv) > 1 else '../../kicad/ti135_card.kicad_pcb')
cy = [fp.GetCourtyard(pcbnew.F_CrtYd).BBox() for fp in b.GetFootprints() if fp.GetReference() in ('U501', 'U801')]
inside = lambda x, y: any(c.GetX() <= x <= c.GetRight() and c.GetY() <= y <= c.GetBottom() for c in cy)
segs = collections.defaultdict(list)
for t in b.GetTracks():
    n = t.GetNetname()
    if t.Type() != pcbnew.PCB_TRACE_T or 'ddr_' not in n or 'CAL' in n: continue
    s, e = t.GetStart(), t.GetEnd()
    if t.GetLength() < 0.05e6 or (inside(s.x, s.y) and inside(e.x, e.y)): continue
    segs[t.GetLayer()].append((n.split('/')[-1], s.x / 1e6, s.y / 1e6, e.x / 1e6, e.y / 1e6, t.GetWidth() / 1e6))
pair = collections.defaultdict(float)          # (victim, aggressor, layer, gap bucket) -> mm
for layer, L in segs.items():
    for i, (na, ax, ay, bx, by, wa) in enumerate(L):
        la = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / la, (by - ay) / la
        for nb, cx, cyy, dx, dy, wb in L[i + 1:]:
            if nb == na: continue
            lb = math.hypot(dx - cx, dy - cyy); vx, vy = (dx - cx) / lb, (dy - cyy) / lb
            if abs(ux * vy - uy * vx) > 0.03: continue                       # not parallel
            d = abs((cx - ax) * uy - (cyy - ay) * ux)                         # centre distance
            gap = d - (wa + wb) / 2
            if gap > 0.4 or gap < 0: continue
            t1, t2 = sorted(((cx - ax) * ux + (cyy - ay) * uy, (dx - ax) * ux + (dy - ay) * uy))
            ov = min(la, t2) - max(0.0, t1)
            if ov <= 0.02: continue
            mx, my = ax + ux * (max(0.0, t1) + ov / 2), ay + uy * (max(0.0, t1) + ov / 2)
            if inside(mx, my): continue
            g = round(math.floor(gap / 0.05 + 1e-6) * 0.05, 2)               # bucket [g, g+0.05)
            ln = b.GetLayerName(layer)
            pair[(na, nb, ln, g)] += ov; pair[(nb, na, ln, g)] += ov
pairs_of = lambda n, a: [n, a] if n < a else [a, n]
print('| victim | aggressor | layer | edge gap (mm) | coupled length (mm) |'); print('|---|---|---|---|---|')
seen = set()
for (v, a, ln, g), mm in sorted(pair.items(), key=lambda x: (x[0][3], -x[1])):
    k = (tuple(pairs_of(v, a)), ln, g)
    if k in seen or mm < 0.5: continue
    seen.add(k); print(f'| {v} | {a} | {ln} | {g:.2f}-{g + 0.05:.2f} | {mm:.1f} |')
tot = collections.defaultdict(lambda: collections.defaultdict(float))
for (v, a, ln, g), mm in pair.items():
    if g < 0.25: tot[v][(ln, g)] += mm
print('\n| victim | coupled length with edge gap < 0.25 mm, per layer and gap (mm) | total (mm) |'); print('|---|---|---|')
for v, d in sorted(tot.items(), key=lambda x: -sum(x[1].values()))[:15]:
    print(f"| {v} | {', '.join(f'{ln} {g:.2f}: {mm:.1f}' for (ln, g), mm in sorted(d.items()))} | {sum(d.values()):.1f} |")
