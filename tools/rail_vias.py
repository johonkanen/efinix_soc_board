#!/usr/bin/env python3
"""Phase 3: tie open rail pads to their planes (layout_plan_remaining.md section 6).

    tools/p2k/bin/kipy tools/rail_vias.py BOARD [--skip FILE] [--log FILE] [--dry]

For every rail that has a zone, the copper of the net is grouped into connected pieces (pads, tracks,
vias, zone fills). A piece that holds pads but touches no fill of its net is open. Each open piece gets
tied in at one pad (single decap pads are their own piece, so each gets its own connection):
  a. a straight stub (<= STUB_MAX) on the pad's layer to copper of the net that is already tied, or
  b. a new 0.30/0.15 via that lands inside a fill of the net, in the pad or up to RING_MAX away with a stub.
Near LPDDR4 copper (within DDR_NEAR) the order is a, b so that the planes get as few new holes as possible,
and a new via keeps DDR_CLR to every LPDDR4 track and via. Elsewhere a via in the pad comes first.
Every candidate is checked on all copper layers against foreign tracks, vias and pads.
--skip lists "x y" positions (mm) of vias a previous DRC run rejected.
Nothing locked is moved or removed; the script only adds tracks and vias.
"""
import sys
import json
import math
import collections
import pcbnew

MM, TO = pcbnew.FromMM, pcbnew.ToMM
args = sys.argv[1:]
board_path = args[0]
skip_file = args[args.index("--skip") + 1] if "--skip" in args else None
log_file = args[args.index("--log") + 1] if "--log" in args else None
DRY = "--dry" in args

VIA_D, VIA_DRILL = 0.30, 0.15
CLR = 0.105            # copper clearance (board minimum 0.09, classes 0.10)
DDR_CLR = 0.30         # new via to LPDDR4 copper
HOLE_CU = 0.18         # hole to foreign copper (rule 0.175)
HOLE_HOLE = 0.21       # rule 0.2
EDGE = 0.5
STUB_W = 0.2
STUB_MAX = 1.5
RING_MAX = 1.2
DDR_NEAR = 1.5

b = pcbnew.LoadBoard(board_path)
cu_layers = [l for l in pcbnew.LSET.AllCuMask(b.GetCopperLayerCount()).Seq()]
skip = set()
if skip_file:
    for line in open(skip_file):
        if line.strip():
            x, y = map(float, line.split()[:2]); skip.add((round(x, 2), round(y, 2)))

zones_by_net = collections.defaultdict(list)
for z in b.Zones():
    if not z.GetIsRuleArea() and z.GetNetname():
        for l in z.GetLayerSet().Seq():
            zones_by_net[z.GetNetname()].append((z, l))
RAILS = [n for n in ("GND", "1V1", "1V8", "VCORE", "0V85", "3V3", "5V0") if n in zones_by_net]


def in_fill(net, x, y, r=0.0, layers=None):
    """Layer of a fill of `net` that contains the whole disc (x, y, r), or None."""
    for z, l in zones_by_net[net]:
        if layers is not None and l not in layers:
            continue
        pts = [(x, y)] + ([(x + r, y), (x - r, y), (x, y + r), (x, y - r)] if r else [])
        if all(z.HitTestFilledArea(l, pcbnew.VECTOR2I(MM(px), MM(py)), 0) for px, py in pts):
            return l
    return None


# ---------------------------------------------------------------------------------------------------
# geometry tables
# ---------------------------------------------------------------------------------------------------
def is_ddr(net):
    return "/08 lpddr4/" in net


class Grid:
    def __init__(self):
        self.g = collections.defaultdict(list)

    def add(self, x0, y0, x1, y1, item):
        for i in range(int(math.floor(x0)), int(math.floor(x1)) + 1):
            for j in range(int(math.floor(y0)), int(math.floor(y1)) + 1):
                self.g[(i, j)].append(item)

    def near(self, x0, y0, x1, y1):
        seen = set(); out = []
        for i in range(int(math.floor(x0)), int(math.floor(x1)) + 1):
            for j in range(int(math.floor(y0)), int(math.floor(y1)) + 1):
                for it in self.g.get((i, j), ()):
                    if id(it) not in seen:
                        seen.add(id(it)); out.append(it)
        return out


segs = {l: Grid() for l in cu_layers}      # (x1, y1, x2, y2, halfw, net)
pads = {l: Grid() for l in cu_layers}      # (rect, net, drill_r)
vias = Grid()                              # (x, y, r, drill_r, net)
ddr_pts = Grid()
all_tracks, all_vias, all_pads = [], [], []
for t in b.GetTracks():
    net = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = TO(t.GetPosition().x), TO(t.GetPosition().y)
        it = (x, y, TO(t.GetWidth(pcbnew.F_Cu)) / 2, TO(t.GetDrillValue()) / 2, net)
        vias.add(x - 1, y - 1, x + 1, y + 1, it); all_vias.append(it)
        if is_ddr(net):
            ddr_pts.add(x - DDR_NEAR, y - DDR_NEAR, x + DDR_NEAR, y + DDR_NEAR, (x, y, x, y))
    else:
        x1, y1, x2, y2 = TO(t.GetStart().x), TO(t.GetStart().y), TO(t.GetEnd().x), TO(t.GetEnd().y)
        it = (x1, y1, x2, y2, TO(t.GetWidth()) / 2, net, t.GetLayer())
        segs[t.GetLayer()].add(min(x1, x2) - 1, min(y1, y2) - 1, max(x1, x2) + 1, max(y1, y2) + 1, it); all_tracks.append(it)
        if is_ddr(net):
            ddr_pts.add(min(x1, x2) - DDR_NEAR, min(y1, y2) - DDR_NEAR, max(x1, x2) + DDR_NEAR, max(y1, y2) + DDR_NEAR, (x1, y1, x2, y2))
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox()
        r = (TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom()))
        tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        drill = TO(p.GetDrillSize().x) / 2 if tht else 0.0
        layers = cu_layers if tht else [l for l in cu_layers if p.IsOnLayer(l)]
        it = (r, p.GetNetname(), drill, f.GetReference(), p.GetNumber(), tuple(layers), (TO(p.GetPosition().x), TO(p.GetPosition().y)))
        for l in layers:
            pads[l].add(r[0] - 1, r[1] - 1, r[2] + 1, r[3] + 1, it)
        if p.GetNumber() or tht:
            all_pads.append(it)
        if is_ddr(p.GetNetname()):
            ddr_pts.add(r[0] - DDR_NEAR, r[1] - DDR_NEAR, r[2] + DDR_NEAR, r[3] + DDR_NEAR, (r[0], r[1], r[2], r[3]))
edge = b.GetBoardEdgesBoundingBox()
E = [TO(v) for v in (edge.GetLeft(), edge.GetTop(), edge.GetRight(), edge.GetBottom())]


def pt_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
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
    return min(pt_seg(*p1, *c[:4]), pt_seg(*p2, *c[:4]), pt_seg(*p3, *a[:4]), pt_seg(*p4, *a[:4]))


def seg_rect(s, r):
    if r[0] <= s[0] <= r[2] and r[1] <= s[1] <= r[3]:
        return 0.0
    edges = ((r[0], r[1], r[2], r[1]), (r[2], r[1], r[2], r[3]), (r[2], r[3], r[0], r[3]), (r[0], r[3], r[0], r[1]))
    return min(seg_seg(s, e) for e in edges)


def near_ddr(x, y):
    return any(pt_rect(x, y, (min(q[0], q[2]), min(q[1], q[3]), max(q[0], q[2]), max(q[1], q[3]))) < DDR_NEAR for q in ddr_pts.near(x, y, x, y))


def via_ok(x, y, net):
    r, dr = VIA_D / 2, VIA_DRILL / 2
    if (round(x, 2), round(y, 2)) in skip:
        return False
    if x - r < E[0] + EDGE or y - r < E[1] + EDGE or x + r > E[2] - EDGE or y + r > E[3] - EDGE:
        return False
    for vx, vy, vr, vdr, vnet in vias.near(x, y, x, y):
        d = math.hypot(vx - x, vy - y)
        if vnet == net:
            if d < 0.5:
                return False                      # use the existing one instead (step a)
        elif d < max(r + vr + (DDR_CLR if is_ddr(vnet) else CLR), dr + vdr + HOLE_HOLE):
            return False
    for l in cu_layers:
        for s in segs[l].near(x, y, x, y):
            if s[5] != net and pt_seg(x, y, *s[:4]) < s[4] + max(r + (DDR_CLR if is_ddr(s[5]) else CLR), dr + HOLE_CU):
                return False
        for p in pads[l].near(x, y, x, y):
            if p[1] != net:
                d = pt_rect(x, y, p[0])
                if d < max(r + (DDR_CLR if is_ddr(p[1]) else CLR), dr + HOLE_CU) or (p[2] and d < dr + HOLE_HOLE):
                    return False
    return True


def stub_ok(layer, x1, y1, x2, y2, net, hw=STUB_W / 2):
    s = (x1, y1, x2, y2)
    bx = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    for o in segs[layer].near(*bx):
        if o[5] != net and seg_seg(s, o) < hw + o[4] + (0.21 if is_ddr(o[5]) else CLR):
            return False
    for vx, vy, vr, vdr, vnet in vias.near(*bx):
        if vnet != net and pt_seg(vx, vy, *s) < hw + max(vr + CLR, vdr + HOLE_CU):
            return False
    for p in pads[layer].near(*bx):
        if p[1] != net and seg_rect(s, p[0]) < hw + CLR:
            return False
    return True


# ---------------------------------------------------------------------------------------------------
# connected pieces of one net
# ---------------------------------------------------------------------------------------------------
def pieces(net):
    P = [p for p in all_pads if p[1] == net]
    T = [t for t in all_tracks if t[5] == net]
    V = [v for v in all_vias if v[4] == net]
    n = len(P) + len(T) + len(V) + 1                  # last node: the fills
    par = list(range(n))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i

    def join(i, j):
        par[find(i)] = find(j)
    Z = n - 1
    fill_layers = {l for _, l in zones_by_net[net]}
    for i, p in enumerate(P):
        if in_fill(net, p[6][0], p[6][1], layers=set(p[5]) & fill_layers):
            join(i, Z)
    for k, v in enumerate(V):
        j = len(P) + len(T) + k
        if in_fill(net, v[0], v[1]):
            join(j, Z)
        for i, p in enumerate(P):
            if pt_rect(v[0], v[1], p[0]) < v[2] * 0.6:
                join(i, j)
    for k, t in enumerate(T):
        j = len(P) + k
        for e in ((t[0], t[1]), (t[2], t[3])):
            if t[6] in fill_layers and in_fill(net, e[0], e[1], layers={t[6]}):
                join(j, Z)
        for i, p in enumerate(P):
            if t[6] in p[5] and seg_rect(t[:4], p[0]) <= t[4] * 0.5:
                join(i, j)
        for k2, v in enumerate(V):
            if pt_seg(v[0], v[1], *t[:4]) <= v[2]:
                join(j, len(P) + len(T) + k2)
        for k2 in range(k + 1, len(T)):
            u = T[k2]
            if u[6] == t[6] and seg_seg(t[:4], u[:4]) <= (t[4] + u[4]) * 0.6:
                join(j, len(P) + k2)
    groups = collections.defaultdict(list)
    for i in range(n - 1):
        groups[find(i)].append(i)
    tied = groups.pop(find(Z), [])
    tied_cu = [("pad", P[i]) for i in tied if i < len(P)] + [("trk", T[i - len(P)]) for i in tied if len(P) <= i < len(P) + len(T)] + \
              [("via", V[i - len(P) - len(T)]) for i in tied if i >= len(P) + len(T)]
    open_pieces = [[P[i] for i in g if i < len(P)] for g in groups.values()]
    return [g for g in open_pieces if g], tied_cu


# ---------------------------------------------------------------------------------------------------
new_tracks, new_vias, log, failed = [], [], [], []


def add_via(x, y, net):
    it = (x, y, VIA_D / 2, VIA_DRILL / 2, net)
    vias.add(x - 1, y - 1, x + 1, y + 1, it); new_vias.append(it)


def add_stub(layer, x1, y1, x2, y2, net):
    it = (x1, y1, x2, y2, STUB_W / 2, net, layer)
    segs[layer].add(min(x1, x2) - 1, min(y1, y2) - 1, max(x1, x2) + 1, max(y1, y2) + 1, it); new_tracks.append(it)


def ring(maxr):
    out = []
    k = int(maxr / 0.05)
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            d = math.hypot(i, j) * 0.05
            if 0 < d <= maxr:
                out.append((d, i * 0.05, j * 0.05))
    return sorted(out)


RING = ring(RING_MAX)


def tie(pad, net, tied_cu):
    """Returns a description of how the pad was tied, or None."""
    r, _, _, ref, num, layers, (px, py) = pad
    smd_layer = layers[0] if len(layers) == 1 else None
    ddr = near_ddr(px, py)
    stub_hw = min(STUB_W, r[2] - r[0], r[3] - r[1]) / 2

    def via_in_pad():
        if in_fill(net, px, py, 0.2) is not None and via_ok(px, py, net):
            add_via(px, py, net); return f"via in pad"

    def to_existing():
        if smd_layer is None:
            return None
        best = None
        for kind, o in tied_cu:
            if kind == "via":
                tx, ty = o[0], o[1]
            elif kind == "pad":
                if smd_layer not in o[5]:
                    continue
                tx, ty = o[6]
            else:
                continue
            d = math.hypot(tx - px, ty - py)
            if 0.05 < d <= STUB_MAX and (best is None or d < best[0]) and stub_ok(smd_layer, px, py, tx, ty, net, stub_hw):
                best = (d, tx, ty, kind)
        if best:
            add_stub(smd_layer, px, py, best[1], best[2], net)
            return f"stub {best[0]:.2f} mm to tied {best[3]}"

    def via_near():
        if smd_layer is None:
            return None
        for d, dx, dy in RING:
            x, y = round(px + dx, 3), round(py + dy, 3)
            if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
                if via_ok(x, y, net) and in_fill(net, x, y, 0.2) is not None:
                    add_via(x, y, net); return f"via in pad, {d:.2f} mm off centre"
                continue
            if via_ok(x, y, net) and in_fill(net, x, y, 0.2) is not None and stub_ok(smd_layer, px, py, x, y, net, stub_hw):
                add_via(x, y, net); add_stub(smd_layer, px, py, x, y, net)
                return f"via {d:.2f} mm away + stub"

    for step in ((to_existing, via_in_pad, via_near) if ddr else (via_in_pad, to_existing, via_near)):
        how = step()
        if how:
            return how + (" (near LPDDR4)" if ddr else "")
    return None


summary = collections.OrderedDict()
for net in RAILS:
    open_pieces, tied_cu = pieces(net)
    done = 0
    for g in open_pieces:
        smd = [p for p in g if len(p[5]) == 1]
        how = None
        for p in sorted(smd or g, key=lambda p: (p[3], p[4])):
            how = tie(p, net, tied_cu)
            if how:
                log.append(f"{net:6s} {p[3]}.{p[4]:4s} {how}" + (f"   (piece of {len(g)} pads)" if len(g) > 1 else ""))
                tied_cu.append(("pad", p)); done += 1
                break
        if not how:
            failed.append(f"{net:6s} " + ", ".join(f"{p[3]}.{p[4]}" for p in g[:6]) + (" ..." if len(g) > 6 else ""))
    summary[net] = (len(open_pieces), done)

for net, (n, d) in summary.items():
    print(f"{net:6s} open pieces {n:4d}, tied {d:4d}, left {n - d}")
print(f"new vias {len(new_vias)}, new stubs {len(new_tracks)}")
for f_ in failed:
    print("LEFT:", f_)
if log_file:
    json.dump({"vias": [[v[0], v[1], v[4]] for v in new_vias], "stubs": [list(t[:4]) + [t[5], b.GetLayerName(t[6])] for t in new_tracks], "log": log, "left": failed},
              open(log_file, "w"), indent=0)
if not DRY:
    for x, y, r, dr, net in new_vias:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetWidth(pcbnew.F_Cu, MM(2 * r)); v.SetDrill(MM(2 * dr))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(b.FindNet(net)); b.Add(v)
    for x1, y1, x2, y2, hw, net, layer in new_tracks:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1))); t.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
        t.SetWidth(MM(2 * hw)); t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t)
    pcbnew.SaveBoard(board_path, b)
