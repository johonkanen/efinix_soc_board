#!/usr/bin/env python3
"""PLL filter parts and other two-pad 0201s at a ball of U501, with no courtyard overlap (user, 2026-11-16):
    tools/p2k/bin/kipy tools/pll_place.py IN.kicad_pcb OUT.kicad_pcb
For each part in JOBS: the position on B.Cu nearest to its ball where
- both pads clear foreign copper and sit on no other part's pad,
- each pad touches copper of its net (a ball via, a pad, a track) or reaches it by a straight clear track (<= 1.2 mm),
- the part's courtyard (1.48 x 0.78 mm) does not touch any other courtyard on B.Cu.
Parts are tried at 0 / 90 degrees first and at 45 degrees only if nothing else fits.
C501 and C507 (the 1 u of VCCA_BL and of the DDR PLL) must be at their ball: if nothing is free, one ordinary rail
capacitor within 1.7 mm of the ball is moved to its regulator output to make room (tools/decap_place.py's rule).
Their ferrites go to the nearest clean site with a source via (SITE). FB504's filtered pad is linked by the
track in LINK (the router found no path); FB501's is routed to the ball afterwards:
    KICAD_RIP_PREEXISTING=0 ~/dev/KiCadRoutingTools/.venv/bin/python -X utf8 ~/dev/KiCadRoutingTools/py_router/route.py \
        OUT ROUTED --nets "/05 fpga_power/vcca_bl" --layers F.Cu In1.Cu In2.Cu \
        In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --track-width 0.15 --clearance 0.11 --via-size 0.3 --via-drill 0.15 --grid-step 0.05 \
        --no-bga-zones U501 --no-fix-drc-settings --board-edge-clearance 0.5 --escalation off --layer-costs 5 -1 3 -1 -1 3 -1 1"""
import math
import sys

_src = open(__file__.replace("pll_place.py", "decap_place.py")).read()
exec(_src.split("def cval(")[0])            # board, Geo, geo, add_via, add_track, at_switcher (argv[1] is the board)

BL, BR = "/05 fpga_power/vcca_bl", "/05 fpga_power/vcca_br"
PLL = "/05 fpga_power/vddpll_mcb_top_phy_ddr"
#        ref      net of pad A  net of pad B  ball (x, y)
JOBS = [("FB502", BR, "VCORE", (166.8, 84.6)), ("C503", BR, "GND", (166.8, 84.6))]     # placed only if still parked
# balls that take one part only once no courtyards may touch: the 1 u goes on the ball, the ferrite beside it
#        capacitor ferrite  filtered net  source   ball
AT_BALL = [("C501", "FB501", BL, "VCORE", (166.8, 78.2)), ("C507", "FB504", PLL, "0V85", (164.4, 75.0))]
#        ferrite: centre x, y, angle (filtered pad -> source pad), ordinary capacitors moved to their regulator for it
LINK = {"FB504": [(163.2, 76.18), (163.2, 74.6), (164.0, 74.6), (164.4, 75.0)]}     # B.Cu, between the ball vias
SITE = {"FB501": (168.15, 78.35, 225, []), "FB504": (163.2, 76.5, 90, ["C5018"])}
MOVE_FIRST = []              # (C519, whose courtyard touched C5053's, went to its regulator in the first run)
HL, HW = 0.74, 0.39


def rect(cx, cy, ux, uy):
    return [(cx + sx * HL * ux - sy * HW * uy, cy + sx * HL * uy + sy * HW * ux) for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1))]


def convex_hit(a, c):
    for poly in (a, c):
        for i in range(len(poly)):
            x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
            nx, ny = y2 - y1, x1 - x2
            pa = [nx * x + ny * y for x, y in a]; pc = [nx * x + ny * y for x, y in c]
            if max(pa) <= min(pc) + 1e-6 or max(pc) <= min(pa) + 1e-6:
                return False
    return True


def courtyards(skip):
    out = []
    for f in b.GetFootprints():
        if f.GetLayer() != BC or f.GetReference() in skip or TOMM(f.GetPosition().x) > 208.5:
            continue
        cs = f.GetCourtyard(BC)
        if cs.OutlineCount() == 0:
            continue
        o = cs.Outline(0); pts = [(TOMM(o.CPoint(i).x), TOMM(o.CPoint(i).y)) for i in range(o.PointCount())]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        out.append((min(xs), min(ys), max(xs), max(ys), pts))
    return out


def attach(x, y, netname, maxlink):
    """nearest copper of the net to (x, y) on B.Cu or a via: (distance, point), or None"""
    best = None
    for it in geo.near(x, y):
        if it[1] != netname:
            continue
        if it[0] == "v":
            q = (it[2], it[3])
        elif it[0] == "t":
            if it[2] != BC:
                continue
            dx, dy = it[5] - it[3], it[6] - it[4]
            t = 0 if dx == dy == 0 else max(0, min(1, ((x - it[3]) * dx + (y - it[4]) * dy) / (dx * dx + dy * dy)))
            q = (it[3] + t * dx, it[4] + t * dy)
        elif BC in it[2]:
            q = (it[5], it[6])
        else:
            continue
        d = math.hypot(q[0] - x, q[1] - y)
        if d <= maxlink and (best is None or d < best[0]) and (d < 0.12 or geo.line_ok((x, y), q, netname, BC, 0.1)):
            best = (d, q)
    return best


def find(ref, na, nb, ball, R=3.5, maxlink=1.2):
    cys = courtyards({ref}); best = None
    n = int(R / 0.05)
    for diag in (False, True):
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                cx, cy = ball[0] + 0.05 * i, ball[1] + 0.05 * j
                if math.hypot(i, j) * 0.05 > R:
                    continue
                for ang in ((45, 135, 225, 315) if diag else (0, 90, 180, 270)):
                    ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                    pa = (cx - 0.32 * ux, cy - 0.32 * uy); pb = (cx + 0.32 * ux, cy + 0.32 * uy)
                    da = math.hypot(pa[0] - ball[0], pa[1] - ball[1])
                    if best and da >= best[0]:
                        continue
                    if not (geo.disc_ok(*pa, na, BC, 0.25) and geo.disc_ok(*pb, nb, BC, 0.25) and geo.disc_ok(cx, cy, "", BC, 0.12)):
                        continue
                    r = rect(cx, cy, ux, uy); xs = [p[0] for p in r]; ys = [p[1] for p in r]
                    if any(c[0] < max(xs) and c[2] > min(xs) and c[1] < max(ys) and c[3] > min(ys) and convex_hit(r, c[4]) for c in cys):
                        continue
                    a1 = attach(*pa, na, maxlink); a2 = attach(*pb, nb, maxlink)
                    if not a1 or not a2:
                        continue
                    score = da + a1[0] + a2[0]
                    if best is None or score < best[0]:
                        best = (score, cx, cy, pa, pb, a1, a2, ang)
        if best:
            break
    return best


def do(ref, na, nb, ball, R=3.5, maxlink=1.2):
    f = b.FindFootprintByReference(ref)
    got = find(ref, na, nb, ball, R, maxlink)
    if not got:
        print(f"   {ref}: no position without a courtyard overlap within 3.5 mm of {ball}"); return False
    _, cx, cy, pa, pb, a1, a2, ang = got
    if f.GetLayer() != BC:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    bestrot = None
    for rot in (0, 90, 180, 270, 45, 135, 225, 315):
        f.SetOrientationDegrees(rot); f.SetPosition(P(cx, cy))
        q = next(p for p in f.Pads() if p.GetNumber() and p.GetNetname() == na).GetPosition()
        e = math.hypot(TOMM(q.x) - pa[0], TOMM(q.y) - pa[1])
        if bestrot is None or e < bestrot[0]:
            bestrot = (e, rot)
    f.SetOrientationDegrees(bestrot[1]); f.SetPosition(P(cx, cy))
    for p in f.Pads():
        if p.IsOnCopperLayer():
            geo.add_pad(f, p)
    if a1[0] >= 0.12:
        add_track(pa, a1[1], na)
    if a2[0] >= 0.12:
        add_track(pb, a2[1], nb)
    print(f"   {ref} {f.GetValue()}: ({cx:.2f}, {cy:.2f}) at {ang} deg, {na.split('/')[-1]} pad {math.hypot(pa[0] - ball[0], pa[1] - ball[1]):.2f} mm "
          f"from the ball, links {a1[0]:.2f} / {a2[0]:.2f} mm")
    return True


def strip_part(f):
    """tracks that end on this part's pads go with it (short links to a via)"""
    for p in f.Pads():
        if not p.GetNumber():
            continue
        for t in list(b.GetTracks()):
            if t.Type() != pcbnew.PCB_VIA_T and t.GetNetCode() == p.GetNetCode() and t.GetLayer() == BC and \
               (p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd())) and t.GetLength() < MM(1.3):
                b.Delete(t)


def to_regulator(ref):
    f = b.FindFootprintByReference(ref)
    rail = next(p.GetNetname() for p in f.Pads() if p.GetNumber() and p.GetNetname() != "GND")
    strip_part(f); f.SetPosition(P(230, 40))
    globals()["geo"] = Geo()
    ok = at_switcher(f, rail, "0201")
    globals()["geo"] = Geo()
    return ok


def do_evict(ref, na, nb, ball, R=2.0, maxlink=0.8):
    """no free spot: try with one, then two, ordinary rail capacitors within 1.7 mm of the ball moved to their regulator"""
    global geo
    import itertools
    cands = []
    for f in b.GetFootprints():
        r = f.GetReference()
        if f.GetLayer() != BC or not r.startswith("C") or r in KEEP or math.hypot(TOMM(f.GetPosition().x) - ball[0], TOMM(f.GetPosition().y) - ball[1]) > 1.7:
            continue
        nets = {p.GetNetname() for p in f.Pads() if p.GetNumber()}
        if "GND" in nets and (nets - {"GND"}) and next(iter(nets - {"GND"})) in RAILS:
            cands.append(f)
    best = None
    for k in (1, 2):
        for group in itertools.combinations(cands, k):
            here = [f.GetPosition() for f in group]
            for f in group:
                f.SetPosition(P(230, 40))
            geo = Geo()
            got = find(ref, na, nb, ball, R, maxlink)
            for f, h in zip(group, here):
                f.SetPosition(h)
            if got and (best is None or got[0] < best[0]):
                best = (got[0], [f.GetReference() for f in group])
        if best:
            break
    geo = Geo()
    if not best:
        print(f"   {ref}: no position near {ball} even with two neighbours moved away"); return False
    print(f"   {ref}: needs the place of {', '.join(best[1])}, moved to the regulator")
    for r in best[1]:
        if not to_regulator(r):
            print(f"   {r}: no room at its regulator"); return False
    return do(ref, na, nb, ball, R, maxlink)


for ref in ("C504", "C5064", "C5072"):       # deleted from the schematic (user): no courtyard-clean place for them
    f = b.FindFootprintByReference(ref)
    if f:
        b.Delete(f); print("  ", ref, "deleted")
geo = Geo()
KEEP = {j[0] for j in JOBS} | {c for c, *_ in AT_BALL} | {"C505", "C506", "C5068"}
for ref in MOVE_FIRST:
    to_regulator(ref)
for job in JOBS:
    if TOMM(b.FindFootprintByReference(job[0]).GetPosition().x) > 208.5:
        do(*job)
for cap, fb, fnet, src, ball in AT_BALL:
    f = b.FindFootprintByReference(fb); strip_part(f); f.SetPosition(P(232, 42)); geo = Geo()
    c = b.FindFootprintByReference(cap); strip_part(c); c.SetPosition(P(234, 42)); geo = Geo()
    if not (do(cap, fnet, "GND", ball, 0.6, 0.8) or do_evict(cap, fnet, "GND", ball, 0.6, 0.8)):
        continue
    # the ferrite: nearest courtyard-clean site with a source via beside it (found by a wider search, all angles,
    # for FB504 with one VCORE capacitor moved out); its filtered pad is linked to the ball by the router afterwards
    cx, cy, ang, out = SITE[fb]
    for r in out:
        to_regulator(r)
    ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    pa = (cx - 0.32 * ux, cy - 0.32 * uy); pb = (cx + 0.32 * ux, cy + 0.32 * uy)
    bestrot = None
    for rot in (0, 90, 180, 270, 45, 135, 225, 315):
        f.SetOrientationDegrees(rot); f.SetPosition(P(cx, cy))
        q = next(p for p in f.Pads() if p.GetNumber() and p.GetNetname() == fnet).GetPosition()
        e = math.hypot(TOMM(q.x) - pa[0], TOMM(q.y) - pa[1])
        if bestrot is None or e < bestrot[0]:
            bestrot = (e, rot)
    a2 = attach(*pb, src, 0.8)              # before the ferrite's own pads are in the geometry
    f.SetOrientationDegrees(bestrot[1]); f.SetPosition(P(cx, cy)); geo = Geo()
    if a2 and a2[0] >= 0.12:
        add_track(pb, a2[1], src)
    for a_, c_ in zip(LINK.get(fb, []), LINK.get(fb, [])[1:]):       # a hand-drawn link where the router found none
        add_track(a_, c_, fnet, 0.1)
    print(f"   {fb}: ({cx}, {cy}) at {ang} deg, {src} link {a2[0] if a2 else -1:.2f} mm; filtered pad {math.hypot(pa[0] - ball[0], pa[1] - ball[1]):.2f} mm from the ball (to be routed)")
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(sys.argv[2])
