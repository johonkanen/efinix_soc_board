#!/usr/bin/env python3
"""Small grid router for the remaining nets (run with work/venv/bin/python; needs numpy).

    grid_router.py GEOM.json OPS.json --nets REGEX [REGEX ...] [--width 0.12] [--layers F.Cu,In2.Cu,In5.Cu,B.Cu]
                   [--via-cost 1.5] [--no-vias] [--margin 6] [--exclude REGEX] [--prev OPS.json ...]

GEOM.json comes from tools/dump_geom.py, OPS.json goes to tools/apply_ops.py. The router only adds
tracks and 0.30/0.15 through vias; it never touches existing copper.

Method: 0.05 mm grid, A* over the signal layers with 45-degree moves. Every existing pad, track and via
is painted into a per-layer map, grown by half the new track width + clearance, with the net that owns
it; a cell is usable by a net if nothing foreign covers it. Vias use a second map grown for the via and
merged over all eight copper layers (so a via also clears the plane-layer antipads of other vias and
through-hole pads). LPDDR4 copper is grown by DDR_EXTRA more, so nothing new comes closer than 0.3 mm.
A net's copper is grouped into connected pieces (items in a fill of the net count as one piece); each
piece is routed to the nearest other piece until one is left. For a net with zone fills, a piece may also
end in a new via at the nearest spot where the via lands wholly inside a fill of the net (--plane-vias).
"""
import sys, json, math, re, heapq, collections, argparse, time
import numpy as np

P = 0.05
SIG = ["F.Cu", "In2.Cu", "In5.Cu", "B.Cu"]
CLR, SLACK, DDR_EXTRA = 0.10, 0.03, 0.20
VIA_D, VIA_DRILL = 0.30, 0.15
HOLE_HOLE, EDGE = 0.20, 0.5

ap = argparse.ArgumentParser()
ap.add_argument("geom"); ap.add_argument("out")
ap.add_argument("--nets", nargs="+", required=True)
ap.add_argument("--exclude", default=None)
ap.add_argument("--width", type=float, default=0.12)
ap.add_argument("--layers", default=",".join(SIG))
ap.add_argument("--via-cost", type=float, default=1.5, help="mm of track one via is worth")
ap.add_argument("--no-vias", action="store_true")
ap.add_argument("--margin", type=float, default=6.0)
ap.add_argument("--max-len", type=float, default=0, help="give up on a connection longer than this (mm), 0 = no limit")
ap.add_argument("--prev", nargs="*", default=[], help="ops files already produced on this geometry (treated as existing copper)")
ap.add_argument("--plane-vias", action="store_true", help="nets with fills: end at a new via into the fill")
ap.add_argument("--zone-penalty", type=float, default=4.0, help="cost factor for a track cell inside another net's pour on that layer")
ap.add_argument("--probe", nargs=4, metavar=("NET", "X", "Y", "R"), help="report where a via of NET could go within R of (X, Y), then exit")
ap.add_argument("--layer-cost", default="", help="e.g. B.Cu=1.5,F.Cu=1.2")
A = ap.parse_args()

G = json.load(open(A.geom))
for pf in A.prev:
    o = json.load(open(pf))
    G["tracks"] += [dict(t, fill=False) for t in o["tracks"]]
    G["vias"] += [dict(v, fill=False) for v in o["vias"]]
E0, E1, E2, E3 = G["edge"]
IX0, IY0 = int(math.floor(E0 / P)), int(math.floor(E1 / P))
W, H = int(math.ceil(E2 / P)) - IX0 + 1, int(math.ceil(E3 / P)) - IY0 + 1
nets = sorted({p["net"] for p in G["pads"]} | {t["net"] for t in G["tracks"]} | {v["net"] for v in G["vias"]})
NID = {n: i + 1 for i, n in enumerate(n for n in nets if n)}
ALLOWED = [l for l in A.layers.split(",") if l in SIG]
LCOST = {l: 1.0 for l in SIG}
for kv in filter(None, A.layer_cost.split(",")):
    k, v = kv.split("="); LCOST[k] = float(v)


def nid(net):
    return NID.get(net, -1)


def is_ddr(net):
    return "/08 lpddr4/" in net


def gi(x):
    return int(round(x / P)) - IX0


def gj(y):
    return int(round(y / P)) - IY0


class Raster:
    """owner[layer][j, i]: 0 free, n = only net n covers the cell, -1 = blocked for everyone."""

    def __init__(self, infl, layers):
        self.infl = infl
        self.own = {l: np.zeros((H, W), np.int16) for l in layers}
        m = int(math.ceil((EDGE + infl - CLR) / P))
        for a in self.own.values():
            a[:m, :] = -1; a[-m:, :] = -1; a[:, :m] = -1; a[:, -m:] = -1

    def _put(self, l, i0, j0, mask, n):
        sub = self.own[l][j0:j0 + mask.shape[0], i0:i0 + mask.shape[1]]
        cur = sub[mask]
        sub[mask] = np.where(cur == 0, n, np.where(cur == n, n, -1)) if n > 0 else -1

    def _win(self, x0, y0, x1, y1, r):
        i0, i1 = max(gi(x0 - r) - 1, 0), min(gi(x1 + r) + 1, W - 1)
        j0, j1 = max(gj(y0 - r) - 1, 0), min(gj(y1 + r) + 1, H - 1)
        if i1 < i0 or j1 < j0:
            return None
        xs = (np.arange(i0, i1 + 1) + IX0) * P; ys = (np.arange(j0, j1 + 1) + IY0) * P
        return i0, j0, xs[None, :], ys[:, None]

    def seg(self, l, x1, y1, x2, y2, hw, net, extra=0.0):
        if l not in self.own:
            return
        r = hw + self.infl + extra
        w = self._win(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), r)
        if not w:
            return
        i0, j0, X, Y = w
        dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
        t = np.clip(((X - x1) * dx + (Y - y1) * dy) / L, 0, 1) if L > 0 else 0
        d = np.hypot(X - x1 - t * dx, Y - y1 - t * dy)
        self._put(l, i0, j0, d <= r, nid(net))

    def disc(self, l, x, y, r0, net, extra=0.0, raw=False):
        if l not in self.own:
            return
        r = r0 if raw else r0 + self.infl + extra
        w = self._win(x, y, x, y, r)
        if not w:
            return
        i0, j0, X, Y = w
        self._put(l, i0, j0, np.hypot(X - x, Y - y) <= r, nid(net))

    def rect(self, l, box, net, extra=0.0):
        if l not in self.own:
            return
        r = self.infl + extra
        w = self._win(box[0], box[1], box[2], box[3], r)
        if not w:
            return
        i0, j0, X, Y = w
        d = np.hypot(np.maximum(np.maximum(box[0] - X, 0), X - box[2]), np.maximum(np.maximum(box[1] - Y, 0), Y - box[3]))
        self._put(l, i0, j0, d <= r, nid(net))


def paint_track(R, t):
    R.seg(t["layer"], t["x1"], t["y1"], t["x2"], t["y2"], t["w"] / 2, t["net"], DDR_EXTRA if is_ddr(t["net"]) else 0)


def paint_via(R, v, is_via_raster):
    ex = DDR_EXTRA if is_ddr(v["net"]) else 0
    for l in R.own:
        # B.Cu tracks may pass an LPDDR4 via at the normal clearance: the decoupling under both BGAs sits
        # between those vias already, and the plane-side nets there have no other way out
        R.disc(l, v["x"], v["y"], v["d"] / 2, v["net"], 0 if (l == "B.Cu" and not is_via_raster) else ex)
        if is_via_raster:      # hole to hole
            R.disc(l, v["x"], v["y"], v["drill"] / 2 + HOLE_HOLE + VIA_DRILL / 2 + SLACK, v["net"], raw=True)


def paint_pad(R, p, is_via_raster):
    ex = DDR_EXTRA if is_ddr(p["net"]) else 0
    for l in p["layers"]:
        R.rect(l, p["box"], p["net"], ex)
    if p["drill"] and is_via_raster:
        for l in R.own:
            R.disc(l, p["x"], p["y"], p["drill"] / 2 + HOLE_HOLE + VIA_DRILL / 2 + SLACK, p["net"], raw=True)


t0 = time.time()
HW = A.width / 2
RT = Raster(HW + CLR + SLACK, SIG)
RV = Raster(VIA_D / 2 + CLR + SLACK, G["layers"])
for t in G["tracks"]:
    paint_track(RT, t); paint_track(RV, t)
for v in G["vias"]:
    paint_via(RT, v, False); paint_via(RV, v, True)
for p in G["pads"]:
    paint_pad(RT, p, False); paint_pad(RV, p, True)


def merge_via():
    m = None
    for a in RV.own.values():
        if m is None:
            m = a.copy(); continue
        conflict = ((m != 0) & (a != 0) & (m != a)) | (m == -1) | (a == -1)
        m = np.where(m == 0, a, m); m[conflict] = -1
    return m


VIAOWN = merge_via()


def zone_owner():
    """Per signal layer: which net's pour covers the cell (0 none). A track of another net through a pour
    can cut it into islands, so such cells cost more."""
    from PIL import Image, ImageDraw
    out = {}
    for l in SIG:
        im = Image.new("I", (W, H), 0); d = ImageDraw.Draw(im)
        for f in G.get("fills", []):
            if f["layer"] == l:
                d.polygon([((x / P) - IX0, (y / P) - IY0) for x, y in f["pts"]], fill=NID[f["net"]])
                for h_ in f["holes"]:
                    d.polygon([((x / P) - IX0, (y / P) - IY0) for x, y in h_], fill=0)
        out[l] = np.array(im, dtype=np.int32).astype(np.int16)
    return out


ZOWN = zone_owner()
_fillok = {}


def fillok(net):
    """2D mask: a 0.3 mm via centred here lies inside a fill of `net` (0.1 mm inside its edge)."""
    if net in _fillok:
        return _fillok[net]
    from PIL import Image, ImageDraw
    acc = np.zeros((H, W), bool)
    by_layer = collections.defaultdict(list)
    for f in G.get("fills", []):
        if f["net"] == net:
            by_layer[f["layer"]].append(f)
    k = int(math.ceil((VIA_D / 2 + 0.1) / P))
    for layer, fl in by_layer.items():
        im = Image.new("1", (W, H), 0); d = ImageDraw.Draw(im)
        for f in fl:
            d.polygon([((x / P) - IX0, (y / P) - IY0) for x, y in f["pts"]], fill=1)
            for h_ in f["holes"]:
                d.polygon([((x / P) - IX0, (y / P) - IY0) for x, y in h_], fill=0)
        m = np.array(im, dtype=bool)
        er = m.copy()
        for dj in range(-k, k + 1):
            for di in range(-k, k + 1):
                if di * di + dj * dj <= k * k and (di or dj):
                    er &= np.roll(np.roll(m, dj, 0), di, 1)
        acc |= er
    _fillok[net] = acc
    return acc
print(f"rasters built in {time.time() - t0:.1f} s ({W} x {H})", flush=True)


if A.probe:
    net, x, y, r = A.probe[0], float(A.probe[1]), float(A.probe[2]), float(A.probe[3])
    n = NID[net]; k = int(r / P); ci, cj = gi(x), gj(y)
    sl = (slice(cj - k, cj + k + 1), slice(ci - k, ci + k + 1))
    vok = (VIAOWN[sl] == 0) | (VIAOWN[sl] == n)
    fo = fillok(net)[sl] if any(f["net"] == net for f in G.get("fills", [])) else np.zeros_like(vok)
    print(f"{net} around ({x}, {y}) +-{r}: via clear of all layers {int(vok.sum())} cells, inside a fill {int(fo.sum())}, both {int((vok & fo).sum())}")
    for l in G["layers"]:
        a = RV.own[l][sl]; bad = ~((a == 0) | (a == n))
        owners = collections.Counter(int(v) for v in a[bad].ravel())
        names = {i: nm for nm, i in NID.items()}
        print(f"  {l:7s} blocked {int(bad.sum()):5d}  by", ", ".join(f"{names.get(o, 'several')}" for o, c in owners.most_common(4)))
    both = np.argwhere(vok & fo)
    for j, i in both[:8]:
        print(f"  free spot ({(i + ci - k + IX0) * P:.2f}, {(j + cj - k + IY0) * P:.2f})")
    sys.exit(0)

# ---------------------------------------------------------------------------------------------------
# pieces of a net
# ---------------------------------------------------------------------------------------------------
def pt_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


def pt_rect(px, py, r):
    return math.hypot(max(r[0] - px, 0, px - r[2]), max(r[1] - py, 0, py - r[3]))


def seg_seg(a, c):
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    p1, p2, p3, p4 = (a[0], a[1]), (a[2], a[3]), (c[0], c[1]), (c[2], c[3])
    if p1 != p2 and p3 != p4 and ccw(p1, p2, p3) * ccw(p1, p2, p4) < 0 and ccw(p3, p4, p1) * ccw(p3, p4, p2) < 0:
        return 0.0
    return min(pt_seg(*p1, *c), pt_seg(*p2, *c), pt_seg(*p3, *a), pt_seg(*p4, *a))


def seg_rect(s, r):
    if r[0] <= s[0] <= r[2] and r[1] <= s[1] <= r[3]:
        return 0.0
    es = ((r[0], r[1], r[2], r[1]), (r[2], r[1], r[2], r[3]), (r[2], r[3], r[0], r[3]), (r[0], r[3], r[0], r[1]))
    return min(seg_seg(s, e) for e in es)


def pieces(net):
    """List of pieces; a piece is a list of anchors (x, y, layers or None for all, label)."""
    Pd = [p for p in G["pads"] if p["net"] == net and (p["num"] or p["drill"])]
    T = [t for t in G["tracks"] if t["net"] == net]
    V = [v for v in G["vias"] if v["net"] == net]
    n = len(Pd) + len(T) + len(V) + 1
    par = list(range(n))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i

    def join(i, j):
        par[find(i)] = find(j)
    Z = n - 1
    for i, p in enumerate(Pd):
        if p["fill"]:
            join(i, Z)
    for k, v in enumerate(V):
        j = len(Pd) + len(T) + k
        if v["fill"]:
            join(j, Z)
        for i, p in enumerate(Pd):
            if pt_rect(v["x"], v["y"], p["box"]) < v["d"] * 0.3:
                join(i, j)
    for k, t in enumerate(T):
        j = len(Pd) + k; s = (t["x1"], t["y1"], t["x2"], t["y2"])
        if t["fill"]:
            join(j, Z)
        for i, p in enumerate(Pd):
            if t["layer"] in p["layers"] and seg_rect(s, p["box"]) <= t["w"] * 0.25:
                join(i, j)
        for k2, v in enumerate(V):
            if pt_seg(v["x"], v["y"], *s) <= v["d"] / 2:
                join(j, len(Pd) + len(T) + k2)
        for k2 in range(k + 1, len(T)):
            u = T[k2]
            if u["layer"] == t["layer"] and seg_seg(s, (u["x1"], u["y1"], u["x2"], u["y2"])) <= (t["w"] + u["w"]) * 0.3:
                join(j, len(Pd) + k2)
    groups = collections.defaultdict(list)
    for i in range(n - 1):
        groups[find(i)].append(i)
    out = []
    for root, g in groups.items():
        anchors = []
        for i in g:
            if i < len(Pd):
                p = Pd[i]
                anchors.append((p["x"], p["y"], None if p["drill"] else tuple(p["layers"]), f"{p['ref']}.{p['num']}", p["box"]))
            elif i < len(Pd) + len(T):
                t = T[i - len(Pd)]
                anchors.append((t["x1"], t["y1"], (t["layer"],), "track", None)); anchors.append((t["x2"], t["y2"], (t["layer"],), "track", None))
            else:
                v = V[i - len(Pd) - len(T)]
                anchors.append((v["x"], v["y"], None, "via", None))
        out.append({"anchors": anchors, "tied": root == find(Z), "pads": sum(1 for i in g if i < len(Pd))})
    return out


# ---------------------------------------------------------------------------------------------------
# A*
# ---------------------------------------------------------------------------------------------------
MOVES = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def route(net, src, dst, margin):
    n = NID[net]
    xs = [a[0] for a in src] + [a[0] for a in dst]; ys = [a[1] for a in src] + [a[1] for a in dst]
    if margin is None:
        i0, j0, i1, j1 = 0, 0, W - 1, H - 1
    else:
        i0, i1 = max(gi(min(xs) - margin), 0), min(gi(max(xs) + margin), W - 1)
        j0, j1 = max(gj(min(ys) - margin), 0), min(gj(max(ys) + margin), H - 1)
    w, h = i1 - i0 + 1, j1 - j0 + 1
    passb = []
    for l in ALLOWED:
        a = RT.own[l][j0:j1 + 1, i0:i1 + 1]
        passb.append(((a == 0) | (a == n)).astype(np.uint8).tobytes())
    zoneb = []
    for l in ALLOWED:
        z = ZOWN[l][j0:j1 + 1, i0:i1 + 1]
        zoneb.append(((z != 0) & (z != n)).astype(np.uint8).tobytes())
    ZP = A.zone_penalty
    va = VIAOWN[j0:j1 + 1, i0:i1 + 1]
    vok = (va == 0) | (va == n)
    # no new via on top of, or overlapping, a via the net already has (that one is a target instead)
    kk = int(math.ceil(0.5 / P))
    for v in G["vias"]:
        if v["net"] == net:
            ci, cj = gi(v["x"]) - i0, gj(v["y"]) - j0
            if -kk <= ci < w + kk and -kk <= cj < h + kk:
                a0, a1, b0, b1 = max(ci - kk, 0), min(ci + kk, w - 1), max(cj - kk, 0), min(cj + kk, h - 1)
                if a1 >= a0 and b1 >= b0:
                    yy, xx = np.ogrid[b0 - cj:b1 - cj + 1, a0 - ci:a1 - ci + 1]
                    vok[b0:b1 + 1, a0:a1 + 1] &= (xx * xx + yy * yy) > kk * kk
    viab = bytes(w * h) if A.no_vias or len(ALLOWED) < 2 else vok.astype(np.uint8).tobytes()
    nl = len(ALLOWED); wh = w * h
    plane = None
    if A.plane_vias and any(f["net"] == net for f in G.get("fills", [])):
        fa = fillok(net)[j0:j1 + 1, i0:i1 + 1] & vok
        plane = fa.astype(np.uint8).tobytes()
    lcost = [LCOST[l] for l in ALLOWED]
    VC = A.via_cost / P

    def cells(anchor):
        x, y, layers, label, box = anchor
        ci, cj = gi(x) - i0, gj(y) - j0
        out = []
        for li, l in enumerate(ALLOWED):
            if layers is not None and l not in layers:
                continue
            best = None
            for dj in range(-3, 4):
                for di in range(-3, 4):
                    i, j = ci + di, cj + dj
                    if 0 <= i < w and 0 <= j < h and passb[li][j * w + i]:
                        cx, cy = (i + i0 + IX0) * P, (j + j0 + IY0) * P
                        if box is not None and not (box[0] <= cx <= box[2] and box[1] <= cy <= box[3]):
                            continue
                        d = math.hypot(cx - x, cy - y)
                        if d <= 0.16 and (best is None or d < best[0]):
                            best = (d, li * wh + j * w + i)
            if best:
                out.append(best[1])
        return out

    start = {}
    for a in src:
        for c in cells(a):
            start[c] = a
    goal = {}
    for a in dst:
        for c in cells(a):
            goal[c] = a
    if not start or (not goal and plane is None):
        return None, "no free cell at " + ("the source" if not start else "the target")
    sx = sum(a[0] for a in src) / len(src); sy = sum(a[1] for a in src) / len(src)
    near = sorted(goal, key=lambda c: abs(((c % wh) % w + i0 + IX0) * P - sx) + abs(((c % wh) // w + j0 + IY0) * P - sy))[:16]
    tl = [((c % wh) % w, (c % wh) // w) for c in near]
    goalset = set(near) if len(goal) > 16 else set(goal)
    if len(goal) > 16:
        goalset = set(c for c in goal)

    def hfun(i, j):
        if plane is not None:
            return 0.0
        b = 1e18
        for ti, tj in tl:
            dx = abs(ti - i); dy = abs(tj - j)
            d = (dx + dy) - 0.5858 * (dx if dx < dy else dy)
            if d < b:
                b = d
        return b

    gs = {}; came = {}; pq = []
    for c in start:
        gs[c] = 0.0
        heapq.heappush(pq, (hfun((c % wh) % w, (c % wh) // w), c))
    closed = set(); found = None; exp = 0
    maxcost = A.max_len / P if A.max_len else 1e18
    while pq:
        f, c = heapq.heappop(pq)
        if c in closed:
            continue
        closed.add(c)
        if c in goalset or c >= nl * wh:
            found = c; break
        exp += 1
        if exp > 4000000:
            return None, "search limit"
        g0 = gs[c]
        if g0 > maxcost:
            return None, "longer than --max-len"
        li, r = divmod(c, wh); j, i = divmod(r, w)
        pb = passb[li]; lc = lcost[li]; zb = zoneb[li]
        for di, dj, cost in MOVES:
            i2, j2 = i + di, j + dj
            if i2 < 0 or j2 < 0 or i2 >= w or j2 >= h:
                continue
            r2 = j2 * w + i2
            if not pb[r2]:
                continue
            if di and dj and not (pb[j * w + i2] and pb[r2 - di]):
                continue
            c2 = li * wh + r2
            g2 = g0 + cost * lc * (ZP if zb[r2] else 1.0)
            if g2 < gs.get(c2, 1e18):
                gs[c2] = g2; came[c2] = c
                heapq.heappush(pq, (g2 + hfun(i2, j2), c2))
        if plane is not None and plane[r]:
            c2 = nl * wh + r
            if g0 + VC < gs.get(c2, 1e18):
                gs[c2] = g0 + VC; came[c2] = c
                heapq.heappush(pq, (g0 + VC, c2))
        if viab[r]:
            for l2 in range(nl):
                if l2 != li and passb[l2][r]:
                    c2 = l2 * wh + r
                    g2 = g0 + VC
                    if g2 < gs.get(c2, 1e18):
                        gs[c2] = g2; came[c2] = c
                        heapq.heappush(pq, (g2 + hfun(i, j), c2))
    if found is None:
        return None, "no path"
    plane_end = found >= nl * wh
    if plane_end:
        found = came[found]
    path = [found]
    while path[-1] in came:
        path.append(came[path[-1]])
    path.reverse()
    pts = [(c // wh, (c % wh) % w, (c % wh) // w) for c in path]

    def free(li, i, j):
        return 0 <= i < w and 0 <= j < h and passb[li][j * w + i]

    def connect(li, a, b_):
        """Octilinear two-segment connection a -> b on layer li, or None."""
        dx, dy = b_[0] - a[0], b_[1] - a[1]
        sx_, sy_ = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
        nd = min(abs(dx), abs(dy)); ns = max(abs(dx), abs(dy)) - nd
        st = (sx_, 0) if abs(dx) > abs(dy) else (0, sy_)
        for order in (0, 1):
            i, j = a; ok = True; mid = None
            for phase in ((("d", nd), ("s", ns)) if order == 0 else (("s", ns), ("d", nd))):
                for _ in range(phase[1]):
                    if phase[0] == "d":
                        if not (free(li, i + sx_, j) and free(li, i, j + sy_)):
                            ok = False; break
                        i += sx_; j += sy_
                    else:
                        i += st[0]; j += st[1]
                    if not free(li, i, j):
                        ok = False; break
                if not ok:
                    break
                if mid is None:
                    mid = (i, j)
            if ok:
                return [a, mid, b_] if mid not in (a, b_) else [a, b_]
        return None

    # split into per-layer runs, smooth each
    runs = []; cur = [pts[0]]
    for q in pts[1:]:
        if q[0] != cur[-1][0]:
            runs.append(cur); cur = [q]
        else:
            cur.append(q)
    runs.append(cur)
    tracks, vias_ = [], []
    mm = lambda i, j: (round((i + i0 + IX0) * P, 4), round((j + j0 + IY0) * P, 4))
    sa = start[path[0]]
    ga = (None, None, None, "new via into the plane", None) if plane_end else goal[found]
    for k, run in enumerate(runs):
        li = run[0][0]; cells_ = [(q[1], q[2]) for q in run]
        verts = [cells_[0]]; a = 0
        while a < len(cells_) - 1:
            best = (a + 1, [cells_[a], cells_[a + 1]]); m = a + 2; step = 16
            while m < len(cells_):
                c_ = connect(li, cells_[a], cells_[m])
                if c_:
                    best = (m, c_)
                    if m == len(cells_) - 1:
                        break
                    m = min(m + step, len(cells_) - 1)
                else:
                    if step == 1:
                        break
                    m = best[0] + 1; step = 1
                    if m >= len(cells_):
                        break
                    continue
            verts += best[1][1:]; a = best[0]
        ptsmm = [mm(*v) for v in verts]
        if k == 0 and math.hypot(ptsmm[0][0] - sa[0], ptsmm[0][1] - sa[1]) > 1e-4:
            ptsmm.insert(0, (sa[0], sa[1]))
        if k == len(runs) - 1 and plane_end:
            vias_.append({"x": ptsmm[-1][0], "y": ptsmm[-1][1], "d": VIA_D, "drill": VIA_DRILL, "net": net})
        elif k == len(runs) - 1 and math.hypot(ptsmm[-1][0] - ga[0], ptsmm[-1][1] - ga[1]) > 1e-4:
            ptsmm.append((ga[0], ga[1]))
        for p1, p2 in zip(ptsmm, ptsmm[1:]):
            if p1 != p2:
                tracks.append({"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1], "w": A.width, "layer": ALLOWED[li], "net": net})
        if k < len(runs) - 1:
            x, y = mm(*cells_[-1])
            vias_.append({"x": x, "y": y, "d": VIA_D, "drill": VIA_DRILL, "net": net})
    return (tracks, vias_, sa, ga), None


# ---------------------------------------------------------------------------------------------------
ops = {"tracks": [], "vias": [], "log": [], "failed": []}
want = []
for rx in A.nets:
    for nname in nets:
        if nname and re.search(rx, nname) and nname not in want and not (A.exclude and re.search(A.exclude, nname)):
            want.append(nname)
for net in want:
    ps = pieces(net)
    if len(ps) < 2:
        continue
    guard = 0
    while len(ps) > 1 and guard < 200:
        guard += 1
        cand = [p for p in ps if not p["tied"] and not p.get("failed")]
        if not cand:
            break
        src = min(cand, key=lambda p: (len(p["anchors"])))
        others = [a for p in ps if p is not src for a in p["anchors"]]
        t1 = time.time()
        res, why = route(net, src["anchors"], others, A.margin)
        if res is None and why in ("no path",):
            res, why = route(net, src["anchors"], others, None)
        if res is None:
            src["failed"] = True
            lab = ", ".join(sorted({a[3] for a in src["anchors"] if a[3] not in ("track", "via")})[:4]) or "track/via stub at %.1f,%.1f" % src["anchors"][0][:2]
            ops["failed"].append(f"{net}: {lab}: {why}")
            print(f"FAIL {net}: {lab}: {why}", flush=True)
            continue
        tracks, vias_, sa, ga = res
        for t in tracks:
            paint_track(RT, t); paint_track(RV, t)
        for v in vias_:
            paint_via(RT, v, False); paint_via(RV, v, True)
        if vias_ or tracks:
            # refresh the merged via map around the new copper
            xs = [t["x1"] for t in tracks] + [t["x2"] for t in tracks] + [v["x"] for v in vias_]
            ys = [t["y1"] for t in tracks] + [t["y2"] for t in tracks] + [v["y"] for v in vias_]
            a0, a1 = max(gi(min(xs)) - 20, 0), min(gi(max(xs)) + 20, W - 1); b0, b1 = max(gj(min(ys)) - 20, 0), min(gj(max(ys)) + 20, H - 1)
            m = None
            for arr in RV.own.values():
                a = arr[b0:b1 + 1, a0:a1 + 1]
                if m is None:
                    m = a.copy(); continue
                conflict = ((m != 0) & (a != 0) & (m != a)) | (m == -1) | (a == -1)
                m = np.where(m == 0, a, m); m[conflict] = -1
            VIAOWN[b0:b1 + 1, a0:a1 + 1] = m
        ops["tracks"] += tracks; ops["vias"] += vias_
        G["vias"] += [dict(v, fill=False) for v in vias_]
        length = sum(math.hypot(t["x2"] - t["x1"], t["y2"] - t["y1"]) for t in tracks)
        ops["log"].append(f"{net}: {sa[3]} -> {ga[3]}  {length:.1f} mm, {len(vias_)} via(s), layers {'/'.join(sorted({t['layer'] for t in tracks}))}")
        print(f"ok   {net}: {sa[3]} -> {ga[3]}  {length:.1f} mm, {len(vias_)} via(s)  [{time.time() - t1:.1f} s]", flush=True)
        # merge: the piece that owns the reached anchor absorbs the source piece and the new copper
        dstp = next(p for p in ps if p["tied"]) if ga[0] is None else next(p for p in ps if p is not src and any(a is ga for a in p["anchors"]))
        new_anchors = [(t["x1"], t["y1"], (t["layer"],), "track", None) for t in tracks] + [(t["x2"], t["y2"], (t["layer"],), "track", None) for t in tracks] + \
                      [(v["x"], v["y"], None, "via", None) for v in vias_]
        dstp["anchors"] += src["anchors"] + new_anchors
        dstp["pads"] += src["pads"]
        ps.remove(src)
json.dump(ops, open(A.out, "w"), indent=0)
print(f"routed {len(ops['log'])} connection(s), {len(ops['failed'])} failed; {len(ops['tracks'])} tracks, {len(ops['vias'])} vias")
