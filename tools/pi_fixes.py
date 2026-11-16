#!/usr/bin/env python3
"""Decoupling fixes from the power-integrity review of 2026-11-15 (reports/order_check/PI_fresh_review.md, S1-S8):
    tools/p2k/bin/kipy tools/pi_fixes.py IN.kicad_pcb OUT.kicad_pcb [STEP ...]      (default: every step, in order)

Each step moves capacitors to the pin they serve or gives them their own via, and removes the copper that only
served the old arrangement. Run on a copy that has its project files beside it; zones are refilled at the end.
"""
import functools
import math
import sys

import pcbnew

print = functools.partial(print, flush=True)
SRC, DST = sys.argv[1:3]
b = pcbnew.LoadBoard(SRC)
MM, TOMM = pcbnew.FromMM, pcbnew.ToMM
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
LAYER = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu, "In2": pcbnew.In2_Cu, "In5": pcbnew.In5_Cu, "In4": pcbnew.In4_Cu}
net = lambda name: b.FindNet(name)
fp = lambda ref: b.FindFootprintByReference(ref)


def pad(ref, num):
    p = fp(ref).FindPadByNumber(str(num)).GetPosition()
    return TOMM(p.x), TOMM(p.y)


def seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def via_free(x, y, netname, r=0.15, why=False):
    """A through via of radius r at (x, y): 0.11 to foreign copper on every layer, 0.36 between via centres + radii."""
    px, py, nc = MM(x), MM(y), net(netname).GetNetCode()
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            d = math.hypot(t.GetPosition().x - px, t.GetPosition().y - py)
            if d < 1000:
                return (False, "via already there") if why else False
            if d < MM(r + 0.11) + t.GetWidth(pcbnew.F_Cu) / 2:
                return (False, "via " + t.GetNetname()) if why else False
        elif t.GetNetCode() != nc:
            s, e = t.GetStart(), t.GetEnd()
            if seg_d(px, py, s.x, s.y, e.x, e.y) < MM(r + 0.11) + t.GetWidth() / 2:
                return (False, f"track {t.GetNetname()} {b.GetLayerName(t.GetLayer())}") if why else False
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == nc or not p.IsOnCopperLayer():  # unnumbered pads are paste apertures
                continue
            bb = p.GetBoundingBox()
            dx = max(bb.GetLeft() - px, 0, px - bb.GetRight()); dy = max(bb.GetTop() - py, 0, py - bb.GetBottom())
            if math.hypot(dx, dy) < MM(r + 0.11):
                return (False, f"pad {f.GetReference()}.{p.GetNumber()}") if why else False
    return (True, "") if why else True


def via(x, y, netname, need=True):
    ok, why = via_free(x, y, netname, why=True)
    if not ok:
        if need:
            raise SystemExit(f"via {netname} at ({x}, {y}) blocked: {why}")
        return None
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(pcbnew.F_Cu, MM(0.3)); v.SetDrill(MM(0.15))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net(netname)); b.Add(v); return v


def track(pts, layer, netname, w=0.2):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetLayer(LAYER[layer]); t.SetWidth(MM(w))
        t.SetNet(net(netname)); b.Add(t)


def place(ref, x, y, rot, side=None):
    f = fp(ref)
    if side and b.GetLayerName(f.GetLayer())[0] != side:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot); f.SetPosition(P(x, y))
    return {p.GetNumber(): (round(TOMM(p.GetPosition().x), 3), round(TOMM(p.GetPosition().y), 3)) for p in f.Pads() if p.GetNumber()}


def opens():
    b.BuildConnectivity()
    return b.GetConnectivity().GetUnconnectedCount(False)


def prune(nets, box, layers=("F", "B", "In2", "In5")):
    """Remove tracks of `nets` inside box (x0, y0, x1, y1) that no connection needs, then the vias left without a
    track or pad. A segment parked on a user layer is itself one open item; two or more means it was needed."""
    codes = {net(n).GetNetCode() for n in nets}; lay = {LAYER[l] for l in layers}
    x0, y0, x1, y1 = box
    inb = lambda p: x0 <= TOMM(p.x) <= x1 and y0 <= TOMM(p.y) <= y1
    base = opens(); n = 0
    while True:
        cand = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T and t.GetNetCode() in codes
                and t.GetLayer() in lay and inb(t.GetStart()) and inb(t.GetEnd())]
        cand.sort(key=lambda t: -t.GetLength()); k = 0
        for t in cand:
            l0 = t.GetLayer(); t.SetLayer(pcbnew.User_9)
            if opens() > base + 1:
                t.SetLayer(l0)
            else:
                b.Delete(t); k += 1
        n += k
        if not k:
            break
    nv = 0
    for v in [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() in codes and inb(t.GetPosition())]:
        pt = v.GetPosition(); nc = v.GetNetCode()
        used = any(o.Type() != pcbnew.PCB_VIA_T and o.GetNetCode() == nc and
                   seg_d(pt.x, pt.y, o.GetStart().x, o.GetStart().y, o.GetEnd().x, o.GetEnd().y) <= o.GetWidth() // 2 + MM(0.15)
                   for o in b.GetTracks())
        used = used or any(p.GetNetCode() == nc and p.HitTest(pt) for f in b.GetFootprints() for p in f.Pads())
        if not used:
            x, y, name = TOMM(pt.x), TOMM(pt.y), v.GetNetname(); b.Delete(v)
            if opens() > base:
                via(x, y, name)
            else:
                nv += 1
    print(f"   pruned {n} segments, {nv} vias of {', '.join(nets)}")


def move(ref, x, y, rot, side=None, on=None):
    """place() (or on_via() with on=(dx, dy)), then tidy the old spot: tracks that met in an old pad are joined
    through it, and the copper that only led to the old pads is stripped back to the first junction."""
    f = fp(ref)
    old = [(TOMM(p.GetPosition().x), TOMM(p.GetPosition().y), p.GetNetname(), f.GetLayer()) for p in f.Pads() if p.GetNumber()]
    if on and side:
        place(ref, x, y, 0, side)
    pp = on_via(ref, x, y, *on) if on else place(ref, x, y, rot, side)
    for ox, oy, name, lay in old:
        ends = []
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == name:  # a via in the old pad
                e = t.GetPosition()
                if math.hypot(TOMM(e.x) - ox, TOMM(e.y) - oy) < 0.5:
                    ends.append((TOMM(e.x), TOMM(e.y)))
            elif t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == name and t.GetLayer() == lay:
                for e in (t.GetStart(), t.GetEnd()):
                    if math.hypot(TOMM(e.x) - ox, TOMM(e.y) - oy) < 0.5:  # also ends on the former 0402 pads
                        ends.append((TOMM(e.x), TOMM(e.y)))
        ends = sorted(set(ends))
        for e in ends[1:]:
            t = pcbnew.PCB_TRACK(b); t.SetStart(P(*ends[0])); t.SetEnd(P(*e)); t.SetLayer(lay); t.SetWidth(MM(0.2))
            t.SetNet(net(name)); b.Add(t)
    strip([(ox, oy) for ox, oy, _, _ in old], {name for _, _, name, _ in old})
    return pp


def strip(seeds, nets):
    """Walk the dead ends that start at `seeds`: a track or via of `nets` that touches a seed and that no connection
    needs is removed, and its far end becomes a seed. Stops at the first junction that is still needed."""
    base = opens(); seeds = [(x, y, 0.3) for x, y in seeds]; n = 0
    while True:
        hit = None
        for t in b.GetTracks():
            if t.GetNetname() not in nets:
                continue
            pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
            if not any(math.hypot(TOMM(q.x) - x, TOMM(q.y) - y) <= r for q in pts for x, y, r in seeds):
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                pt = t.GetPosition(); nc = t.GetNetCode()
                lay = {o.GetLayer() for o in b.GetTracks() if o.Type() != pcbnew.PCB_VIA_T and o.GetNetCode() == nc and
                       seg_d(pt.x, pt.y, o.GetStart().x, o.GetStart().y, o.GetEnd().x, o.GetEnd().y) <= o.GetWidth() // 2 + MM(0.15)}
                plane = any(z.GetNetCode() == nc for z in b.Zones())  # a track into a plane via is a connection
                used = len(lay) >= 2 or (lay and plane)
                used = used or any(p.GetNetCode() == nc and p.HitTest(pt) for f in b.GetFootprints() for p in f.Pads())
                if used:
                    continue
                x, y, name = TOMM(pt.x), TOMM(pt.y), t.GetNetname(); b.Delete(t)
                if opens() > base:
                    via(x, y, name); seeds = [s for s in seeds if math.hypot(s[0] - x, s[1] - y) > s[2]]
                    continue
                hit = True; n += 1; break
            l0 = t.GetLayer(); t.SetLayer(pcbnew.User_9)
            if opens() > base + 1:
                t.SetLayer(l0)
            else:
                seeds += [(TOMM(q.x), TOMM(q.y), 0.16) for q in pts]; b.Delete(t); hit = True; n += 1; break
        if not hit:
            break
    print(f"   stripped {n} tracks / vias of {', '.join(sorted(nets))}")


def refill():
    zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)


# ---------------------------------------------------------------------------------------------------------------
def s3():
    """C1203, U1202's 1V8 (VCCA) capacitor, sat at the LPDDR4: to U1202 pin 1, like C1201 / C1205 / C1207."""
    pp = move("C1203", 147.4, 62.4, 90, "F")
    (x1, y1), (x2, y2) = pp["1"], pp["2"]
    px, py = pad("U1202", 1)
    track([(x1, y1), (px + 0.1, y1)], "F", "1V8", 0.25)
    via(x2, y2 - 0.1, "GND")
    print("S3 C1203 at U1202:", pp)


def s8():
    """C701, Y701's supply capacitor, was 5 mm from VDD (pin 4): beside pin 4, GND via in its pad."""
    pp = move("C701", 182.85, 75.9, -90)
    (x1, y1), (x2, y2) = pp["1"], pp["2"]
    px, py = pad("Y701", 4)
    track([(x1, y1), (px - 0.5, y1)], "F", "1V8", 0.25)
    via(x2, y2, "GND")
    print("S8 C701 at Y701 pin 4:", pp)


def s7():
    """C941 (100 n) reached U901 pin 29 through 5 mm of track and In3. There is no room for a via in its pad
    (phy_rx_ctl on In5 below), so it goes to B.Cu on the pin's own via at (182.72, 62.99); GND in the B.Cu pour."""
    pp = move("C941", 183.52, 62.92, 0, "B")
    if pp["1"][0] > pp["2"][0]:
        pp = place("C941", 183.52, 62.92, 180)
    track([(182.72, 62.99), (pp["1"][0], pp["1"][1])], "B", "3V3", 0.2)
    print("S7 C941 on B.Cu at U901 pin 29's via:", pp)


def on_via(ref, x, y, dx, dy):
    """Put the 0201 `ref` with pad 1 on (x, y) and pad 2 towards (dx, dy), the 45 degree placement on a ball via."""
    n = math.hypot(dx, dy); cx, cy = x + 0.32 * dx / n, y + 0.32 * dy / n
    best = None
    for rot in (45, 135, 225, 315, 0, 90, 180, 270):
        pp = place(ref, cx, cy, rot)
        err = math.hypot(pp["1"][0] - x, pp["1"][1] - y)
        if best is None or err < best[0]:
            best = (err, rot)
    return place(ref, cx, cy, best[1])


def s5():
    """Capacitors connected the long way round. C5046: 1.3 mm to C558's 1V8 via instead of 11.8 mm of track.
    C1308 / C1309 (anti-alias, 6.4 mm of 0.1 mm track to GND): a GND via in the pad.
    Not done, no free via position within 0.7 mm and B.Cu is full: C5056, C5041, C561 (see STATUS.md)."""
    x, y = pad("C5046", 1); x2, y2 = pad("C558", 1)
    track([(x, y), (x2, y2)], "B", "1V8", 0.2)
    prune(["1V8"], (152.3, 82.0, 158.3, 87.0), layers=("B",))
    for ref in ("C1308", "C1309"):
        x, y = pad(ref, 2); via(x, y, "GND")
    print("S5 C5046 tied to C558's via; GND vias in C1308.2 and C1309.2")


def s4():
    """U1304 had no capacitor of its own: C1310 to F.Cu under U1304, pad 1 on the 3V3_analog track 0.75 mm from
    the via of pin 4, GND via in pad 2."""
    pp = move("C1310", 135.52, 95.9, 0, "F")
    if pp["1"][0] < pp["2"][0]:
        pp = place("C1310", 135.52, 95.9, 180)
    track([pp["1"], (136.0, 96.65)], "F", "3V3_analog", 0.3)
    via(134.89, 95.9, "GND")
    print("S4 C1310 under U1304:", pp)


def cap(ref, p1, towards, netname, link1=None, link2=None):
    """0201 `ref` on B.Cu with pad 1 at p1 and pad 2 in direction `towards`; optional tracks pad 1 -> link1 (its net)
    and pad 2 -> link2 (GND)."""
    pp = move(ref, p1[0], p1[1], 0, "B", on=towards)
    if link1:
        track([pp["1"], link1], "B", netname, 0.2)
    if link2:
        track([pp["2"], link2], "B", "GND", 0.2)
    print(f"   {ref} {fp(ref).GetValue()}: pad 1 {pp['1']}, pad 2 {pp['2']}")


BL, PLL = "/05 fpga_power/vcca_bl", "/05 fpga_power/vddpll_mcb_top_phy_ddr"
TR, BR = "/05 fpga_power/vcca_tr", "/05 fpga_power/vcca_br"


def need_0201(*refs):
    bad = [r for r in refs if "0201" not in str(fp(r).GetFPID().GetLibItemName())]
    if bad:
        raise SystemExit(f"{bad} are still 0402: run tools/pi_fixes_sch.py and tools/swap_footprint.py first")


def s2():
    """VCCA_BL (ball R8), filter capacitors were 22-24 mm from the ball: C501 (1 u) on the R8 via, GND on the ball
    via (166.0, 77.4); C5060 (100 n) and C502 (4u7) on the feed at the BGA's north edge, 5.5-6 mm from the ball."""
    need_0201("C501", "C502")
    cap("C501", (166.8, 78.2), (-1, -1), BL, None, (166.0, 77.4))
    cap("C5060", (165.776, 73.376), (-1, -1), BL, None, (165.2, 72.6))
    cap("C502", (166.424, 72.224), (1, 1), BL, (166.5, 72.3), (166.8, 72.6))
    print("S2 VCCA_BL done")


def s1():
    """VDDPLL_MCB_TOP_PHY_DDR (ball W11): C507 (1 u) on the W11 via, GND on the ball via (163.6, 75.8); C5072 (10 n)
    1 mm north of the ball. The vcca_bl feed beside the via is necked to 0.1 mm and moved 0.05 mm east for room.
    C508 (100 n 0402) stays at the ferrite: there is no second spot near W11."""
    need_0201("C507")
    for t in list(b.GetTracks()):
        if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == BL and t.GetLayer() == pcbnew.B_Cu:
            s, e = (TOMM(t.GetStart().x), TOMM(t.GetStart().y)), (TOMM(t.GetEnd().x), TOMM(t.GetEnd().y))
            if {s, e} == {(164.825, 74.05), (164.825, 75.4)}:
                b.Delete(t)
            elif {s, e} == {(164.825, 75.4), (166.225, 75.4)}:
                (t.SetStart if s[0] < e[0] else t.SetEnd)(P(164.875, 75.4))
    track([(164.825, 74.05), (164.875, 74.1), (164.875, 75.4)], "B", BL, 0.1)
    cap("C507", (164.4, 75.0), (-1, 1), PLL, None, (163.6, 75.8))
    cap("C5072", (164.15, 74.07), (0, -1), PLL, (164.4, 75.0), (163.6, 72.6))
    print("S1 VDDPLL done")


def s9():
    """VCCA_TR (J16) and VCCA_BR (G8): filter capacitors were 17 and 9 mm from the balls. C505 (1 u) on the J16
    via and C506 (4u7) 0.6 mm from it; C503 (1 u) 0.3 mm from the G8 via and C504 (4u7) on the track 0.6 mm away."""
    need_0201("C503", "C504", "C505", "C506")
    cap("C505", (160.376, 83.024), (-1, 1), TR, None, (159.6, 83.8))
    cap("C506", (160.824, 83.374), (1, 1), TR, None, (161.2, 83.8))
    cap("C503", (166.874, 84.874), (1, 1), BR, (166.8, 84.6), (167.2, 85.98))
    cap("C504", (166.326, 84.176), (-1, -1), BR, None, (165.2, 83.0))
    print("S9 VCCA_TR / VCCA_BR done")


def s6():
    """U501 G7 / J7 (3V3 through the In4 finger) had one 100 n: C5074 (4u7) and C5075 (1u), new, on B.Cu on the
    finger just south of the BGA. 3V3 via in pad 1 into the finger, GND via in pad 2 beyond the finger's east edge."""
    if not fp("C5074"):
        print("S6 skipped: C5074 / C5075 are not on the board (tools/pi_fixes_sch.py, then tools/add_parts.py)"); return
    rows = [96.8, 97.6, 98.4, 99.2]  # north of 96.7 inner-layer tracks leave no room for a via
    for ref in ("C5074", "C5075"):
        for y in list(rows):
            if via_free(165.9, y, "3V3") and via_free(166.54, y, "GND"):
                pp = place(ref, 166.22, y, 0, "B")
                if pp["1"][0] > pp["2"][0]:
                    pp = place(ref, 166.22, y, 180)
                via(pp["1"][0], y, "3V3"); via(pp["2"][0], y, "GND"); rows.remove(y)
                print(f"S6 {ref} on the 3V3 finger:", pp); break
        else:
            raise SystemExit(f"S6: no room for {ref}")


STEPS = {"s3": s3, "s8": s8, "s7": s7, "s5": s5, "s4": s4, "s2": s2, "s1": s1, "s9": s9, "s6": s6}
for name in (sys.argv[3:] or list(STEPS)):
    STEPS[name]()
# vias of the track-only nets that are left with copper on one layer only
base = opens()
spots = [(t.GetPosition().x, t.GetPosition().y) for t in b.GetTracks()
         if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() in (BL, PLL, TR, BR, "3V3_analog")]
for sx, sy in spots:  # looked up again each time: strip() below may already have removed the via
    v = next((t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetPosition().x == sx and t.GetPosition().y == sy), None)
    if v is None:
        continue
    pt = v.GetPosition(); nc = v.GetNetCode()
    lay = {o.GetLayer() for o in b.GetTracks() if o.Type() != pcbnew.PCB_VIA_T and o.GetNetCode() == nc and
           seg_d(pt.x, pt.y, o.GetStart().x, o.GetStart().y, o.GetEnd().x, o.GetEnd().y) <= o.GetWidth() // 2 + MM(0.15)}
    lay |= {(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu) for f in b.GetFootprints() for p in f.Pads()
            if p.GetNetCode() == nc and p.HitTest(pt)}
    if len(lay) < 2:
        x, y, name = TOMM(pt.x), TOMM(pt.y), v.GetNetname(); b.Delete(v)
        if opens() > base:
            via(x, y, name)
        else:
            print(f"one-sided via of {name} removed at ({x}, {y})")
            strip([(x, y)], {name})
refill()
print("open connections:", opens())
b.Save(DST)
