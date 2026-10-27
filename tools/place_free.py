#!/usr/bin/env python3
"""Put parts on B.Cu at the nearest free spot to a target (kipy):
    place_free.py IN OUT SPEC [SPEC ...]

SPEC is REF@X,Y (target point, mm) or REF@X,Y,ROT (only that orientation), or a bare REF: the target is then every
U501 ball of the part's rail (its non-GND net), so a decap lands as close to its rail as there is room. Parts are
placed in the order given, each one flipped to B.Cu and tried at 0.05 mm steps outward from its target(s), at 0 and
90 deg (180/270 give the same footprint here), until it clears everything already on B.Cu with the clearances of
tools/place_bga_decaps.py: other nets' via copper 0.1 mm and via holes 0.175 mm, tracks and pads (SMD and
through-hole) 0.1 mm, B-side courtyards, and 0.5 mm from the board edge. No copper is moved.
"""
import math
import sys

import pcbnew

mm, FM = pcbnew.ToMM, pcbnew.FromMM
CLR, HOLE_CLR, EDGE, MARGIN, STEP, RMAX = 0.1, 0.175, 0.5, 0.0005, 0.05, 8.0

b = pcbnew.LoadBoard(sys.argv[1])
specs = sys.argv[3:]
eb = b.GetBoardEdgesBoundingBox()
EX0, EY0, EX1, EY1 = mm(eb.GetLeft()), mm(eb.GetTop()), mm(eb.GetRight()), mm(eb.GetBottom())
u501 = b.FindFootprintByReference("U501")
copper = lambda f: [p for p in f.Pads() if p.GetNumber() and p.IsOnCopperLayer()]


def rect(bb):
    return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())


def court(f):
    return rect(f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox())


def rect_dist(r, s):
    dx = max(r[0] - s[2], s[0] - r[2], 0); dy = max(r[1] - s[3], s[1] - r[3], 0)
    return math.hypot(dx, dy)


def seg_rect(r, ax, ay, bx, by):
    n = max(2, int(math.hypot(bx - ax, by - ay) / 0.05))
    return min(rect_dist(r, (ax + (bx - ax) * i / n, ay + (by - ay) * i / n) * 2) for i in range(n + 1))


# obstacles on B.Cu, by net code: (kind, geometry, required distance)
vias, tracks, pads, courts = [], [], [], []
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        x, y = mm(t.GetPosition().x), mm(t.GetPosition().y)
        vias.append((x, y, t.GetNetCode(), mm(t.GetWidth(pcbnew.B_Cu)) / 2 + CLR, mm(t.GetDrillValue()) / 2 + HOLE_CLR))
    elif t.GetLayer() == pcbnew.B_Cu:
        tracks.append((mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y), t.GetNetCode(),
                       mm(t.GetWidth()) / 2 + CLR))
moving = {s.split("@")[0] for s in specs}


def add_footprint(f):
    for p in copper(f):
        if p.IsOnLayer(pcbnew.B_Cu):
            pads.append((rect(p.GetBoundingBox()), p.GetNetCode()))
    if f.IsFlipped():
        courts.append(court(f))


for f in b.GetFootprints():
    if f.GetReference() not in moving:
        add_footprint(f)


GRID = 1.0
index = {}


def cells(r, pad=1.0):
    for i in range(int(math.floor((r[0] - pad) / GRID)), int(math.floor((r[2] + pad) / GRID)) + 1):
        for j in range(int(math.floor((r[1] - pad) / GRID)), int(math.floor((r[3] + pad) / GRID)) + 1):
            yield i, j


def build_index():
    index.clear()
    for k, v in enumerate(vias):
        for c in cells((v[0], v[1], v[0], v[1]), 0):
            index.setdefault(c, set()).add(("v", k))
    for k, t in enumerate(tracks):
        r = (min(t[0], t[2]), min(t[1], t[3]), max(t[0], t[2]), max(t[1], t[3]))
        for c in cells(r, 0):
            index.setdefault(c, set()).add(("t", k))
    for k, q in enumerate(pads):
        for c in cells(q[0], 0):
            index.setdefault(c, set()).add(("p", k))
    for k, q in enumerate(courts):
        for c in cells(q, 0):
            index.setdefault(c, set()).add(("c", k))


def near(r):
    out = set()
    for c in cells(r, 0.8):
        out |= index.get(c, set())
    return out


def fits(f):
    cf = court(f)
    if cf[0] < EX0 + EDGE or cf[1] < EY0 + EDGE or cf[2] > EX1 - EDGE or cf[3] > EY1 - EDGE:
        return False
    for kind, k in near(cf):
        if kind == "c":
            oc = courts[k]
            if cf[0] < oc[2] and oc[0] < cf[2] and cf[1] < oc[3] and oc[1] < cf[3]:
                return False
    for p in copper(f):
        pr = rect(p.GetBoundingBox()); net = p.GetNetCode()
        for kind, k in near(pr):
            if kind == "v":
                x, y, n, dc, dh = vias[k]
                d = rect_dist(pr, (x, y, x, y))
                if n != net and (d < dc + MARGIN or d < dh + MARGIN):
                    return False
            elif kind == "t":
                ax, ay, bx, by, n, dc = tracks[k]
                if n != net and seg_rect(pr, ax, ay, bx, by) < dc + MARGIN:
                    return False
            elif kind == "p":
                q, n = pads[k]
                if n != net and rect_dist(pr, q) < CLR + MARGIN:
                    return False
    return True


def targets(f, spec):
    if "@" in spec:
        v = [float(a) for a in spec.split("@")[1].split(",")]
        return [(v[0], v[1])], ([v[2]] if len(v) > 2 else [0, 90])
    rail = next(p.GetNetname() for p in copper(f) if p.GetNetname() != "GND")
    pts = [(mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in u501.Pads() if p.GetNetname() == rail]
    if not pts:
        sys.exit(f"place_free: {f.GetReference()}: no U501 ball on {rail}; give a target")
    return pts, [0, 90]


build_index()
done = []
for spec in specs:
    ref = spec.split("@")[0]
    f = b.FindFootprintByReference(ref)
    if not f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    pts, rots = targets(f, spec)
    # candidate centres on a STEP grid around every target, nearest first
    cand = {}
    for px, py in pts:
        for i in range(-int(RMAX / STEP), int(RMAX / STEP) + 1):
            for j in range(-int(RMAX / STEP), int(RMAX / STEP) + 1):
                x, y = round(round(px / STEP) * STEP + i * STEP, 3), round(round(py / STEP) * STEP + j * STEP, 3)
                d = math.hypot(x - px, y - py)
                if d <= RMAX and d < cand.get((x, y), 1e9):
                    cand[(x, y)] = d
    ok = False
    for (x, y), d in sorted(cand.items(), key=lambda kv: kv[1]):
        for rot in rots:
            f.SetOrientationDegrees(rot)
            f.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))
            if fits(f):
                ok = True; break
        if ok:
            break
    if not ok:
        sys.exit(f"place_free: no free spot within {RMAX} mm for {ref}")
    add_footprint(f)
    build_index()
    done.append(f"{ref} ({x:.2f}, {y:.2f}) {rot} deg, {d:.2f} mm from target")
    print("  " + done[-1], flush=True)
pcbnew.SaveBoard(sys.argv[2], b)
print(f"place_free: {len(done)} parts placed")
