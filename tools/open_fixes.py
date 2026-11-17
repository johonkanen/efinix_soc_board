#!/usr/bin/env python3
"""Close the last open power connections and two shorts left by the re-routing work (2026-11-17):
    tools/p2k/bin/kipy tools/open_fixes.py IN.kicad_pcb OUT.kicad_pcb
- Shorts: the 1V8 via in Y701 pad 1 came out in Y901's GND pad on the other side (the F.Cu track from pad 4
  already feeds pad 1): removed. The via in R1402 pad 2 (to J2 pin 2) came out in C202's GND pad: removed, the
  net is routed again with the router afterwards.
- Supply pads with no via position nearby get a routed track on their own layer (a small grid search, 0.05 mm,
  0.15 mm track): C5028 -> C5043 -> the 1V8 via at (173.84, 87.79); R612 -> R605 -> R606 -> the 1V8 via at
  a new 1V8 via; C551 / C5019 pad 2 -> a new GND via (the nearest position a track can reach).
- The In4 3V3 pour at ball M21 had lost its stitching vias to In3's 3V3: two new ones.
- C538 (47 u, 1V1) sat where there is no 1V1 plane: to the nearest place with one, a via in each pad."""
import heapq
import math
import sys

_src = open(__file__.replace("open_fixes.py", "pll_place.py")).read()
__file__ = __file__.replace("open_fixes.py", "pll_place.py")
exec(_src.split("for ref in (\"C504\", \"C5064\", \"C5072\"):")[0])
F = pcbnew.F_Cu


def pad_xy(ref, num):
    q = b.FindFootprintByReference(ref).FindPadByNumber(str(num)).GetPosition()
    return (TOMM(q.x), TOMM(q.y))


def drop_via(x, y, netname):
    for t in list(b.GetTracks()):
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == netname and abs(TOMM(t.GetPosition().x) - x) < 0.01 and abs(TOMM(t.GetPosition().y) - y) < 0.01:
            b.Delete(t); print(f"   via of {netname} at ({x}, {y}) removed"); return True
    return False


def track_ok(x, y, netname, layer, r):
    """a track point: clear of foreign copper on the layer (its own net's pads and tracks may be touched)"""
    for it in geo.near(x, y):
        if it[1] == netname:
            continue
        if it[0] == "v":
            if math.hypot(it[2] - x, it[3] - y) < r + 0.1 + it[4]:
                return False
        elif it[0] == "t":
            if it[2] == layer and seg_d(x, y, it[3], it[4], it[5], it[6]) < r + 0.1 + it[7]:
                return False
        elif layer in it[2]:
            bx = it[3]
            if math.hypot(max(bx[0] - x, 0, x - bx[2]), max(bx[1] - y, 0, y - bx[3])) < r + 0.1:
                return False
    return True


def link(a, c, netname, layer, w=0.15, margin=2.5):
    """a track from a to c on one layer, found on a 0.05 mm grid (A*, 8 directions)"""
    global geo
    st = 0.05; r = w / 2
    x0, y0 = min(a[0], c[0]) - margin, min(a[1], c[1]) - margin
    nx, ny = int((abs(a[0] - c[0]) + 2 * margin) / st) + 1, int((abs(a[1] - c[1]) + 2 * margin) / st) + 1
    S = (round((a[0] - x0) / st), round((a[1] - y0) / st)); G = (round((c[0] - x0) / st), round((c[1] - y0) / st))
    ok = {}

    def free(n):
        if n not in ok:
            x, y = x0 + n[0] * st, y0 + n[1] * st
            ok[n] = 0 <= n[0] < nx and 0 <= n[1] < ny and track_ok(x, y, netname, layer, r)
        return ok[n]
    h = lambda n: math.hypot(n[0] - G[0], n[1] - G[1])
    best = {S: 0}; came = {}; pq = [(h(S), 0, S)]
    while pq:
        f_, g_, n = heapq.heappop(pq)
        if n == G:
            break
        if g_ > best.get(n, 1e9):
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                m = (n[0] + dx, n[1] + dy)
                if not free(m):
                    continue
                g2 = g_ + (1.4142 if dx and dy else 1)
                if g2 < best.get(m, 1e9):
                    best[m] = g2; came[m] = n; heapq.heappush(pq, (g2 + h(m), g2, m))
    else:
        return False
    path = [G]
    while path[-1] != S:
        path.append(came[path[-1]])
    pts = [(x0 + n[0] * st, y0 + n[1] * st) for n in path[::-1]]
    pts[0], pts[-1] = a, c
    out = [pts[0]]
    for i in range(1, len(pts) - 1):                           # keep only the corners
        d1 = (round(pts[i][0] - pts[i - 1][0], 3), round(pts[i][1] - pts[i - 1][1], 3)); d2 = (round(pts[i + 1][0] - pts[i][0], 3), round(pts[i + 1][1] - pts[i][1], 3))
        if i > 1 and i < len(pts) - 2 and d1 == d2:
            continue
        out.append(pts[i])
    out.append(pts[-1])
    for p_, q_ in zip(out, out[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*p_)); t.SetEnd(P(*q_)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(b.FindNet(netname)); b.Add(t)
        geo.add_track(t)
    print(f"   {netname}: {sum(math.hypot(q_[0] - p_[0], q_[1] - p_[1]) for p_, q_ in zip(out, out[1:])):.2f} mm on {b.GetLayerName(layer)} from ({a[0]:.2f}, {a[1]:.2f}) to ({c[0]:.2f}, {c[1]:.2f})")
    return True


drop_via(184.37, 70.25, "1V8")
drop_via(169.65, 98.8, "Net-(J2-Pin_2)")
geo = Geo()
link(pad_xy("C5028", 1), pad_xy("C5043", 1), "1V8", BC); link(pad_xy("C5043", 1), (173.84, 87.79), "1V8", BC)
link(pad_xy("R612", 1), pad_xy("R605", 1), "1V8", F); link(pad_xy("R605", 1), pad_xy("R606", 1), "1V8", F)


def new_via(starts, netname, layer, rmax=4.0, tries=400):
    """nearest position where a via of the net fits (and meets its plane) and that a track can reach from one of
    `starts` on `layer`"""
    cand = []
    for sx, sy in starts:
        n = int(rmax / 0.1)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                x, y = sx + 0.1 * i, sy + 0.1 * j; d = math.hypot(x - sx, y - sy)
                if 0.4 < d <= rmax and geo.via_ok(x, y, netname) and track_ok(x, y, netname, layer, 0.2):
                    cand.append((d, x, y, (sx, sy)))
    for d, x, y, st_ in sorted(cand)[:tries]:
        if netname != "GND" and not rail_plane(netname, x, y):
            continue
        if link(st_, (x, y), netname, layer, margin=2.0):
            add_via(x, y, netname); print(f"   new {netname} via at ({x:.2f}, {y:.2f})"); return True
    print(f"   no reachable via position for {netname} near {starts}"); return False


new_via([pad_xy("R606", 1), pad_xy("R605", 1), pad_xy("R612", 1)], "1V8", F, rmax=7.0, tries=4000)   # In4 under them is 0V85 / 3V3
new_via([pad_xy("C551", 2), pad_xy("C5019", 2)], "GND", BC)
# stitching of plane:3V3_M (In4) to plane:3V3 (In3)
zm = next(z for z in b.Zones() if z.GetZoneName() == "plane:3V3_M")
z3 = next(z for z in b.Zones() if z.GetNetname() == "3V3" and z.IsOnLayer(pcbnew.In3_Cu))
done = []
for i in range(0, 40):
    for j in range(0, 60):
        x, y = 153.2 + 0.05 * i, 79.0 + 0.05 * j
        if len(done) >= 2 or any(math.hypot(x - q[0], y - q[1]) < 0.8 for q in done):
            continue
        if zm.Outline().Contains(P(x, y)) and all(z3.HitTestFilledArea(pcbnew.In3_Cu, P(x + ax, y + ay)) and zm.Outline().Contains(P(x + ax, y + ay))
                                                   for ax, ay in ((0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3), (0, 0))) and geo.via_ok(x, y, "3V3"):
            add_via(x, y, "3V3"); done.append((x, y))
print("   3V3 stitching vias for the M21 pour:", [(round(x, 2), round(y, 2)) for x, y in done])
# C538: nearest place to the FPGA's 1V1 balls where In3 is 1V1
f = b.FindFootprintByReference("C538")
p1 = next(p for p in f.Pads() if p.GetNetname() == "1V1"); p2 = next(p for p in f.Pads() if p.GetNetname() == "GND")
half = math.hypot(p1.GetPosition().x - p2.GetPosition().x, p1.GetPosition().y - p2.GetPosition().y) / 2e6
strip_part(f); f.SetPosition(P(240, 60)); geo = Geo()
cys = courtyards({"C538"}); best = None
zb = next(z for z in b.Zones() if z.GetNetname() == "1V1" and z.GetZoneName() == "buck_cell").GetBoundingBox()
REG = (TOMM(zb.GetCenter().x), TOMM(zb.GetCenter().y))
for ox, oy, n_ in ((172.4, 78.2, 90), REG + (70,)):          # near the FPGA's 1V1 balls first, else at the 1V1 regulator
  if best:
      break
  for i in range(-n_, n_ + 1):
    for j in range(-n_, n_ + 1):
        cx, cy = ox + 0.1 * i, oy + 0.1 * j; d = math.hypot(cx - ox, cy - oy)
        if best and d >= best[0]:
            continue
        for ux, uy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            a1 = (cx - half * ux, cy - half * uy); a2 = (cx + half * ux, cy + half * uy)
            r = [(cx + sx * 1.7 * ux - sy * 0.98 * uy, cy + sx * 1.7 * uy + sy * 0.98 * ux) for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
            xs = [q[0] for q in r]; ys = [q[1] for q in r]
            if any(c[0] < max(xs) and c[2] > min(xs) and c[1] < max(ys) and c[3] > min(ys) and convex_hit(r, c[4]) for c in cys):
                continue
            pts1 = [(a1[0] - 0.45 * uy * k, a1[1] + 0.45 * ux * k) for k in (-1, 0, 1)]; pts2 = [(a2[0] - 0.45 * uy * k, a2[1] + 0.45 * ux * k) for k in (-1, 0, 1)]
            if not (all(geo.disc_ok(*q, "1V1", BC, 0.5) for q in pts1) and all(geo.disc_ok(*q, "GND", BC, 0.5) for q in pts2)):
                continue
            if not (geo.via_ok(*a1, "1V1") and geo.via_ok(*a2, "GND") and rail_plane("1V1", *a1)):
                continue
            best = (d, cx, cy, a1, a2); break
if best:
    d, cx, cy, a1, a2 = best
    bestrot = None
    for rot in (0, 90, 180, 270):
        f.SetOrientationDegrees(rot); f.SetPosition(P(cx, cy))
        e = math.hypot(TOMM(p1.GetPosition().x) - a1[0], TOMM(p1.GetPosition().y) - a1[1])
        if bestrot is None or e < bestrot[0]:
            bestrot = (e, rot)
    f.SetOrientationDegrees(bestrot[1]); f.SetPosition(P(cx, cy)); add_via(*a1, "1V1"); add_via(*a2, "GND")
    print(f"   C538: ({cx:.1f}, {cy:.1f}), {d:.1f} mm from " + ("the 1V1 ball at (172.4, 78.2)" if math.hypot(cx - 172.4, cy - 78.2) < 9.5 else "the 1V1 regulator output") + ", a via in each pad")
else:
    print("   C538: no place found")
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(sys.argv[2])
