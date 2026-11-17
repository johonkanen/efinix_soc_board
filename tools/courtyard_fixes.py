#!/usr/bin/env python3
"""Clear the remaining courtyard overlaps (user, 2026-11-17: none are accepted; the eMMC match is redone afterwards):
    tools/p2k/bin/kipy tools/courtyard_fixes.py IN.kicad_pcb OUT.kicad_pcb
- R1009 (emmc_dat6) and R1022 (emmc_ds) sat inside U501's courtyard and on each other's. R1009 moves onto its own
  eMMC-side inner-layer run, to the nearest place where two vias fit on every layer and the courtyard is clear,
  with a via in each pad; the old via in pad 2 stays as the FPGA-side layer change and the copper from there to
  the new pad 1 changes from the _r net to the FPGA-side net. R1022 has no such place: it is flipped to B.Cu
  where it is (U501's courtyard is on F.Cu), pad 2 on its via, a new via in pad 1.
- C5055 (4u7 1V1, between C5056 and C5058) goes to the 1V1 regulator output.
- C1005 and C105 are shifted clear of C1004 and U101, with the vias in their pads.
"""
import math
import sys

_src = open(__file__.replace("courtyard_fixes.py", "pll_place.py")).read()
__file__ = __file__.replace("courtyard_fixes.py", "pll_place.py")
exec(_src.split("for ref in (\"C504\", \"C5064\", \"C5072\"):")[0])     # Geo, geo, courtyard helpers, to_regulator ...

F = pcbnew.F_Cu


def cy_list(layer, skip):
    out = []
    for f in b.GetFootprints():
        if f.GetLayer() != layer or f.GetReference() in skip or TOMM(f.GetPosition().x) > 208.5:
            continue
        cs = f.GetCourtyard(layer)
        if cs.OutlineCount():
            o = cs.Outline(0); pts = [(TOMM(o.CPoint(i).x), TOMM(o.CPoint(i).y)) for i in range(o.PointCount())]
            out.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts), pts))
    return out


def via_ok(x, y, own, r=0.15):
    for it in geo.near(x, y):
        if it[0] == "v":
            d = math.hypot(it[2] - x, it[3] - y)
            if d < r + it[4] + (0.11 if it[1] not in own else 0.06) and d > 0.005:
                return False
        elif it[0] == "t":
            if it[1] not in own and seg_d(x, y, it[3], it[4], it[5], it[6]) < r + 0.11 + it[7]:
                return False
        elif it[1] not in own:
            bx = it[3]
            if math.hypot(max(bx[0] - x, 0, x - bx[2]), max(bx[1] - y, 0, y - bx[3])) < r + 0.11:
                return False
    return True


def pad_ok(x, y, own, layer, skip):
    for it in geo.near(x, y):
        if it[0] == "v":
            if it[1] not in own and math.hypot(it[2] - x, it[3] - y) < 0.25 + 0.1 + it[4]:
                return False
        elif it[0] == "t":
            if it[2] == layer and it[1] not in own and seg_d(x, y, it[3], it[4], it[5], it[6]) < 0.25 + 0.1 + it[7]:
                return False
        elif layer in it[2] and it[4] != skip:
            bx = it[3]
            if math.hypot(max(bx[0] - x, 0, x - bx[2]), max(bx[1] - y, 0, y - bx[3])) < 0.35:
                return False
    return True


def inline(ref, fnet, rnet):
    f = b.FindFootprintByReference(ref)
    old2 = next(p for p in f.Pads() if p.GetNetname() == rnet).GetPosition(); o2 = (TOMM(old2.x), TOMM(old2.y))
    old1 = next(p for p in f.Pads() if p.GetNetname() == fnet).GetPosition(); o1 = (TOMM(old1.x), TOMM(old1.y))
    own = {fnet, rnet}; best = None
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_TRACE_T or t.GetNetname() != rnet or t.GetLayer() not in (pcbnew.In2_Cu, pcbnew.In5_Cu):
            continue
        a = (TOMM(t.GetStart().x), TOMM(t.GetStart().y)); c = (TOMM(t.GetEnd().x), TOMM(t.GetEnd().y))
        L = math.hypot(c[0] - a[0], c[1] - a[1])
        if L < 1.4:
            continue
        ux, uy = (c[0] - a[0]) / L, (c[1] - a[1]) / L
        for k in range(int((L - 1.0) / 0.05) + 1):
            s = 0.5 + 0.05 * k; cx, cy = a[0] + ux * s, a[1] + uy * s
            d = math.hypot(cx - o2[0], cy - o2[1])
            if d < 0.9 or d > 8 or (best and d >= best[0]):
                continue
            p1 = (cx - 0.32 * ux, cy - 0.32 * uy); p2 = (cx + 0.32 * ux, cy + 0.32 * uy)
            if not (via_ok(*p1, own) and via_ok(*p2, own)):
                continue
            for layer in (F, BC):
                if not (pad_ok(*p1, own, layer, ref) and pad_ok(*p2, own, layer, ref)):
                    continue
                r = rect(cx, cy, ux, uy); xs = [p[0] for p in r]; ys = [p[1] for p in r]
                if any(q[0] < max(xs) and q[2] > min(xs) and q[1] < max(ys) and q[3] > min(ys) and convex_hit(r, q[4]) for q in cy_list(layer, {ref})):
                    continue
                best = (d, t, p1, p2, layer, (cx, cy)); break
    if not best:
        print(f"   {ref}: no place on its {rnet.split('/')[-1]} run within 8 mm"); return False
    d, t, p1, p2, layer, c = best
    lay, w = t.GetLayer(), t.GetWidth()
    a = (TOMM(t.GetStart().x), TOMM(t.GetStart().y)); e = (TOMM(t.GetEnd().x), TOMM(t.GetEnd().y))   # copies: t goes
    near1 = math.hypot(a[0] - p1[0], a[1] - p1[1]) < math.hypot(a[0] - p2[0], a[1] - p2[1])
    pa, pe = (p1, p2) if near1 else (p2, p1)                 # pa is on the start side of the track
    b.Delete(t)
    for s_, e_ in ((a, pa), (pe, e)):
        n = pcbnew.PCB_TRACK(b); n.SetStart(P(*s_)); n.SetEnd(P(*e_)); n.SetLayer(lay); n.SetWidth(w); n.SetNet(b.FindNet(rnet)); b.Add(n)
    # the part of the _r copper that is still joined to the old pad-2 via becomes the FPGA-side net
    items = [x for x in b.GetTracks() if x.GetNetname() == rnet]
    pts = [o2]; got = []
    while True:
        more = False
        for x in items:
            if any(x is g for g in got):
                continue
            ends = [(TOMM(x.GetPosition().x), TOMM(x.GetPosition().y))] if x.Type() == pcbnew.PCB_VIA_T else \
                   [(TOMM(x.GetStart().x), TOMM(x.GetStart().y)), (TOMM(x.GetEnd().x), TOMM(x.GetEnd().y))]
            if any(math.hypot(q[0] - z[0], q[1] - z[1]) < 0.16 for q in ends for z in pts):
                got.append(x); pts += ends; more = True
        if not more:
            break
    for x in got:
        x.SetNet(b.FindNet(fnet))
    fside = pa if any(math.hypot(pa[0] - z[0], pa[1] - z[1]) < 0.02 for z in pts) else pe
    rside = pe if fside is pa else pa
    # old pads: pad 1's track end joins the old via directly
    n = pcbnew.PCB_TRACK(b); n.SetStart(P(*o1)); n.SetEnd(P(*o2)); n.SetLayer(f.GetLayer()); n.SetWidth(MM(0.12)); n.SetNet(b.FindNet(fnet)); b.Add(n)
    if f.GetLayer() != layer:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    bestrot = None
    for rot in (0, 90, 180, 270, 45, 135, 225, 315):
        f.SetOrientationDegrees(rot); f.SetPosition(P(*c))
        q = next(p for p in f.Pads() if p.GetNetname() == fnet).GetPosition()
        err = math.hypot(TOMM(q.x) - fside[0], TOMM(q.y) - fside[1])
        if bestrot is None or err < bestrot[0]:
            bestrot = (err, rot)
    f.SetOrientationDegrees(bestrot[1]); f.SetPosition(P(*c))
    add_via(*fside, fnet); add_via(*rside, rnet)
    print(f"   {ref}: on its {b.GetLayerName(lay)} run at ({c[0]:.2f}, {c[1]:.2f}), {b.GetLayerName(layer)}, {d:.1f} mm from the old position")
    return True


def flip_in_place(ref, fnet, rnet):
    """to B.Cu at the same spot: pad 2 stays on its via, pad 1 gets a via to its F.Cu track"""
    f = b.FindFootprintByReference(ref)
    q1 = next(p for p in f.Pads() if p.GetNetname() == fnet).GetPosition(); o1 = (TOMM(q1.x), TOMM(q1.y))
    q2 = next(p for p in f.Pads() if p.GetNetname() == rnet).GetPosition(); o2 = (TOMM(q2.x), TOMM(q2.y))
    c = ((o1[0] + o2[0]) / 2, (o1[1] + o2[1]) / 2); ux, uy = (o2[0] - o1[0]) / 0.64, (o2[1] - o1[1]) / 0.64
    r = rect(c[0], c[1], ux, uy); xs = [p[0] for p in r]; ys = [p[1] for p in r]
    if any(q[0] < max(xs) and q[2] > min(xs) and q[1] < max(ys) and q[3] > min(ys) and convex_hit(r, q[4]) for q in cy_list(BC, {ref})):
        print(f"   {ref}: its courtyard would touch another on B.Cu"); return False
    if not (via_ok(*o1, {fnet}) and pad_ok(*o1, {fnet}, BC, ref) and pad_ok(*o2, {rnet}, BC, ref)):
        print(f"   {ref}: no room on B.Cu or for a via in pad 1"); return False
    f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    bestrot = None
    for rot in (0, 90, 180, 270):
        f.SetOrientationDegrees(rot); f.SetPosition(P(*c))
        q = next(p for p in f.Pads() if p.GetNetname() == fnet).GetPosition()
        err = math.hypot(TOMM(q.x) - o1[0], TOMM(q.y) - o1[1])
        if bestrot is None or err < bestrot[0]:
            bestrot = (err, rot)
    f.SetOrientationDegrees(bestrot[1]); f.SetPosition(P(*c)); add_via(*o1, fnet)
    print(f"   {ref}: flipped to B.Cu in place, a via in pad 1 at ({o1[0]:.2f}, {o1[1]:.2f})")
    return True


def shift(ref, dx, dy):
    """move a part with the vias in its pads; tracks ending in the pads are stretched"""
    f = b.FindFootprintByReference(ref)
    moved = []
    for p in f.Pads():
        if not p.GetNumber():
            continue
        for t in b.GetTracks():
            if t.GetNetCode() != p.GetNetCode():
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                if p.HitTest(t.GetPosition()):
                    moved.append((t, None))
            else:
                for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                    if p.IsOnLayer(t.GetLayer()) and p.HitTest(get()):
                        moved.append((t, (get, put)))
    d = pcbnew.VECTOR2I(MM(dx), MM(dy))
    for t, gp in moved:
        if gp is None:
            x, y = TOMM(t.GetPosition().x) + dx, TOMM(t.GetPosition().y) + dy
            globals()["geo"] = geo
            t.SetPosition(t.GetPosition() + d)
        else:
            gp[1](gp[0]() + d)
    f.SetPosition(f.GetPosition() + d)
    print(f"   {ref}: shifted by ({dx}, {dy}) with {sum(1 for t, g in moved if g is None)} via(s)")


inline("R1009", "/emmc_dat6", "/10 emmc/emmc_dat6_r"); geo = Geo()
flip_in_place("R1022", "/emmc_ds", "/10 emmc/emmc_ds_r"); geo = Geo()
to_regulator("C5055")
shift("C1005", 0.0, 0.48)
shift("C105", 0.0, 0.47)
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(sys.argv[2])
