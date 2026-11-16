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


def trk_d(px, py, t):
    """distance from a point to a track's centre line; an arc is taken as its two chords (start-mid, mid-end)"""
    s_, e_ = t.GetStart(), t.GetEnd()
    if t.Type() == pcbnew.PCB_ARC_T:
        m = pcbnew.Cast_to_PCB_ARC(t).GetMid() if hasattr(pcbnew, "Cast_to_PCB_ARC") else t.GetMid()
        return min(seg_d(px, py, s_.x, s_.y, m.x, m.y), seg_d(px, py, m.x, m.y, e_.x, e_.y)) - MM(0.03)
    return seg_d(px, py, s_.x, s_.y, e_.x, e_.y)


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
            if trk_d(px, py, t) < MM(r + 0.11) + t.GetWidth() / 2:
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


def via(x, y, netname, need=True, force=False):
    """force: a via that was there in the last commit, at the rule limits; via_free() has 0.01 mm of margin and
    judges rotated pads by their bounding box, so DRC decides instead"""
    ok, why = via_free(x, y, netname, why=True)
    if force and why != "via already there":
        ok = True
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


def r603():
    """After R602-R604 became 0201 (user, 2026-11-16; tools/swap_footprint.py): fpga_test_n looped around the end of
    R603's REF_RES_4A track by passing between the pads of the 0402, to reach its pull-up R612 on the far side. It
    does not fit between 0201 pads, and there is no room for a GND via to move R603. So R612 moves to the near
    side instead: pad 2 on the fpga_test_n track at y 92.55, a 1V8 via in pad 1; the loop and R612's old 1V8
    stub go. R603 stays where it was."""
    tn = fp("R612").FindPadByNumber("2").GetNetname()

    def drop(netname, pts):
        for a, c in zip(pts, pts[1:]):
            hit = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == netname and
                   t.GetLayer() == pcbnew.F_Cu and
                   {(round(TOMM(t.GetStart().x), 2), round(TOMM(t.GetStart().y), 2)), (round(TOMM(t.GetEnd().x), 2), round(TOMM(t.GetEnd().y), 2))}
                   == {(round(a[0], 2), round(a[1], 2)), (round(c[0], 2), round(c[1], 2))}]
            assert len(hit) == 1, (netname, a, c, len(hit))
            b.Delete(hit[0])

    drop(tn, [(169.35, 92.55), (169.55, 92.35), (169.55, 91.7), (169.35, 91.5), (167.65, 91.5)])  # the loop
    drop("1V8", [(166.2, 91.2), (166.4, 91.2), (166.75, 91.55), (166.77, 91.571)])                # R612's old stub
    pp = place("R612", 168.35, 92.87, 90)
    if pp["2"][1] > pp["1"][1]:
        pp = place("R612", 168.35, 92.87, 270)
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == tn and t.GetLayer() == pcbnew.F_Cu:
            for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                if abs(TOMM(get().x) - 169.35) < 0.01 and abs(TOMM(get().y) - 92.55) < 0.01:
                    put(P(pp["2"][0], 92.55))
    via(pp["1"][0], pp["1"][1], "1V8")
    for v in [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "1V8"
              and abs(TOMM(t.GetPosition().x) - 166.2) < 0.01 and abs(TOMM(t.GetPosition().y) - 91.2) < 0.01]:
        pt = v.GetPosition()
        if not any(o.Type() != pcbnew.PCB_VIA_T and o.GetNetCode() == v.GetNetCode() and
                   seg_d(pt.x, pt.y, o.GetStart().x, o.GetStart().y, o.GetEnd().x, o.GetEnd().y) <= o.GetWidth() // 2 + MM(0.15)
                   for o in b.GetTracks()) and \
           not any(p.GetNetCode() == v.GetNetCode() and p.HitTest(pt) for f in b.GetFootprints() for p in f.Pads()):
            b.Delete(v); print("   unused 1V8 via at (166.2, 91.2) removed")
    print("R612 moved so that R603 can be 0201:", pp)


def tidy():
    """Second pass, 2026-11-16 (via and decoupling audit):
    - the 3V3_analog via at (142.65, 87.85) and its stub, left over when C1310 moved, go;
    - C564 (100 n 3V3, an U501 bank capacitor that sat 20 mm from any 3V3 ball) onto the via of ball J7;
    - C1302 (680 p, the ADC's sampling capacitor, was 6.7 mm from the pin) to F.Cu beside U1303, between pin 7 (AINP)
      and pin 8 (AINM, GND);
    - C1312 (100 n 3V3_analog, 10.8 mm from any pin) to B.Cu under U1303, across the vias of pin 6 (AVDD) and pin 5.
    C5061 / C5062 / C5063 / C5073 are DNP in the schematic (tools/pi_fixes_sch.py, tools/add_parts.py)."""
    strip([(142.65, 87.85)], {"3V3_analog"})
    cap("C564", (167.6, 83.0), (-1, -1), "3V3", None, (166.8, 82.2))
    ain = fp("C1302").FindPadByNumber("1").GetNetname()
    pp = move("C1302", 138.62, 100.2, 0, "F")
    if pp["1"][0] < pp["2"][0]:
        pp = place("C1302", 138.62, 100.2, 180)
    track([pp["1"], (139.1, 100.8)], "F", ain, 0.2)
    # pad 2 to U1303 pin 8 (AINM = GND, with its via): the capacitor sits across the ADC's input pins. A via in
    # pad 2 is blocked by a 3V3_analog track on In5.
    p8 = pad("U1303", 8)
    track([pp["2"], (pp["2"][0], p8[1] - 0.45), (p8[0] - 0.15, p8[1])], "F", "GND", 0.2)
    print("   C1302:", pp)
    pp = move("C1312", 139.54, 101.3, 0, "B")
    if pp["1"][0] > pp["2"][0]:
        pp = place("C1312", 139.54, 101.3, 180)
    print("   C1312:", pp)
    for ref in ("C5061", "C5062", "C5063", "C5073"):
        fp(ref).SetDNP(True)


def clear_at(x, y, own, r=0.15, layers=None, gap=0.1):
    """A disc of radius r at (x, y) clears copper of nets not in `own` by `gap`; on all layers, or only `layers`."""
    px, py = MM(x), MM(y)
    for t in b.GetTracks():
        if t.GetNetname() in own:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            if math.hypot(t.GetPosition().x - px, t.GetPosition().y - py) < MM(r + gap) + t.GetWidth(pcbnew.F_Cu) / 2:
                return False
        elif layers is None or t.GetLayer() in layers:
            if trk_d(px, py, t) < MM(r + gap) + t.GetWidth() / 2:
                return False
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() in own or not p.IsOnCopperLayer():
                continue
            if layers is not None and not any(p.IsOnLayer(l) for l in layers):
                continue
            bb = p.GetBoundingBox()
            dx = max(bb.GetLeft() - px, 0, px - bb.GetRight()); dy = max(bb.GetTop() - py, 0, py - bb.GetBottom())
            if math.hypot(dx, dy) < MM(r + gap):
                return False
    return True


def flash():
    """Flash series resistors and pull-ups out of the crowd at U501's east edge into the free area between the
    FPGA and the flash (user, 2026-11-16). Each 33R goes onto its own In2 run there, on B.Cu with a via in each pad
    (R626 uses the via that was already there); the copper between the old and the new position changes from the
    flash-side net (_r) to the FPGA-side net, and the old pads are bridged. Pull-ups R616 / R617 / R618 go beside
    their resistor's pad 1 where a 1V8 via fits. R619 (rst_n, at the flash) stays."""
    IN2, BC = pcbnew.In2_Cu, pcbnew.B_Cu
    r2 = lambda v: (round(TOMM(v.x), 3), round(TOMM(v.y), 3))
    R = {"sck": "R623", "cs_n": "R624", "io0": "R625", "io1": "R626", "io2": "R627", "io3": "R628"}
    PULL = {"cs_n": "R616", "io2": "R617", "io3": "R618"}

    def seg(netname, layer, a, c, w=None):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetLayer(layer)
        t.SetWidth(MM(w or 0.12)); t.SetNet(net(netname)); b.Add(t)

    def find(netname, layer, pt):
        """the track of the net on the layer that passes through pt"""
        for t in b.GetTracks():
            if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == netname and t.GetLayer() == layer and \
               seg_d(MM(pt[0]), MM(pt[1]), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) < MM(0.02):
                return t
        raise SystemExit(f"no {netname} track at {pt}")

    def cut(netname, layer, pa, pc):
        """remove the part pa..pc of the straight track through both points; returns its width in mm"""
        t = find(netname, layer, pa); s_, e_ = r2(t.GetStart()), r2(t.GetEnd()); w = TOMM(t.GetWidth())
        assert seg_d(MM(pc[0]), MM(pc[1]), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) < MM(0.02), (netname, pc)
        if math.hypot(pa[0] - s_[0], pa[1] - s_[1]) > math.hypot(pc[0] - s_[0], pc[1] - s_[1]):
            pa, pc = pc, pa
        b.Delete(t)
        if math.hypot(pa[0] - s_[0], pa[1] - s_[1]) > 0.01:
            seg(netname, layer, s_, pa, w)
        if math.hypot(pc[0] - e_[0], pc[1] - e_[1]) > 0.01:
            seg(netname, layer, pc, e_, w)
        return w

    def flood(netname, start):
        """every track and via of the net connected to the point `start` (through shared ends and vias)"""
        items = [t for t in b.GetTracks() if t.GetNetname() == netname]
        pts = [start]; got = []
        while True:
            more = False
            for t in items:
                if any(t is g for g in got):
                    continue
                if t.Type() == pcbnew.PCB_VIA_T:
                    ends = [r2(t.GetPosition())]; hit = any(math.hypot(ends[0][0] - q[0], ends[0][1] - q[1]) < 0.16 for q in pts)
                else:
                    ends = [r2(t.GetStart()), r2(t.GetEnd())]
                    hit = any(seg_d(MM(q[0]), MM(q[1]), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) < MM(0.03) for q in pts)
                    hit = hit or any(math.hypot(e[0] - q[0], e[1] - q[1]) < 0.16 and q in viapts for e in ends for q in pts)
                if hit:
                    got.append(t); pts += ends; more = True
                    if t.Type() == pcbnew.PCB_VIA_T:
                        viapts.add(ends[0])
            if not more:
                return got

    def put(sig, v1, v2, new_via=(True, True)):
        """resistor on B.Cu with pad 1 at v1 (FPGA side) and pad 2 at v2; vias; old pads bridged; nets renamed"""
        ref, fnet, rnet = R[sig], "/flash_" + sig, f"/06 fpga_config/flash_{sig}_r"
        o1, o2 = pad(ref, 1), pad(ref, 2)
        for it in flood(rnet, o2):
            it.SetNet(net(fnet))
        seg(fnet, BC, o1, o2, 0.15)
        if new_via[0]:       # before the resistor moves in: via_free() judges rotated pads by their bounding box
            via(v1[0], v1[1], fnet)
        if new_via[1]:
            via(v2[0], v2[1], rnet)
        on_via(ref, v1[0], v1[1], v2[0] - v1[0], v2[1] - v1[1])
        print(f"   {ref} {sig}: pad 1 {pad(ref, 1)}, pad 2 {pad(ref, 2)}")

    def pullup(sig):
        """10k beside the series resistor's pad 1: the nearest spot where the 1V8 pad can have a via"""
        ref, fnet = PULL[sig], "/flash_" + sig
        f = fp(ref); pn = next(p.GetNumber() for p in f.Pads() if p.GetNetname() == fnet)   # the pad on the signal
        oldn = pad(ref, pn); old18 = pad(ref, "1" if pn == "2" else "2")
        x0, y0 = pad(R[sig], 1); best = None
        others = [(TOMM(g.GetPosition().x), TOMM(g.GetPosition().y), 1.9 if g.GetReference() == R[sig] else 1.6)
                  for g in b.GetFootprints() if g.GetLayer() == BC and g.GetReference() != ref]
        own = {fnet, "1V8"}
        for i in range(-56, 57):
            for j in range(-56, 57):
                qx, qy = x0 + 0.05 * i, y0 + 0.05 * j           # the 1V8 pad / via
                for ang in range(0, 360, 45):
                    ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                    nx, ny = qx + 0.64 * ux, qy + 0.64 * uy     # the signal pad
                    d = math.hypot(nx - x0, ny - y0)
                    if d < 0.7 or d > 3.0 or (best and d >= best[0]):
                        continue
                    mx, my = (qx + nx) / 2, (qy + ny) / 2       # keep the courtyards apart
                    if any(abs(mx - ox) < 2.0 and abs(my - oy) < 2.0 and math.hypot(mx - ox, my - oy) < lim for ox, oy, lim in others):
                        continue
                    if not (via_free(qx, qy, "1V8") and clear_at(qx, qy, {"1V8"}, 0.27, {BC}) and clear_at(nx, ny, {fnet}, 0.27, {BC})
                            and clear_at((qx + nx) / 2, (qy + ny) / 2, own, 0.2, {BC})):
                        continue
                    n = max(2, int(d / 0.05))
                    if all(clear_at(x0 + (nx - x0) * k / n, y0 + (ny - y0) * k / n, {fnet}, 0.1, {BC}) for k in range(n + 1)):
                        best = (d, qx, qy, nx, ny)
        if not best:
            print(f"   {ref}: no spot with a 1V8 via near {R[sig]}, left where it is"); return
        _, qx, qy, nx, ny = best
        place(ref, (qx + nx) / 2, (qy + ny) / 2, 0)
        on_via(ref, *((qx, qy, nx - qx, ny - qy) if pn == "2" else (nx, ny, qx - nx, qy - ny)))
        via(qx, qy, "1V8"); seg(fnet, BC, (x0, y0), (nx, ny), 0.15)
        strip([oldn], {fnet}); strip([old18], {"1V8"})
        print(f"   {ref} pull-up of {sig}: signal pad ({nx:.2f}, {ny:.2f}), 1V8 via ({qx:.2f}, {qy:.2f})")

    viapts = set()
    D = 0.32 / math.sqrt(2)
    # sck: off its run at y 84.6, up to two vias at y 84.0
    n = "/06 fpga_config/flash_sck_r"
    w = cut(n, IN2, (181.78, 84.6), (183.62, 84.6))
    seg(n, IN2, (181.78, 84.6), (182.38, 84.0), w); seg(n, IN2, (183.02, 84.0), (183.62, 84.6), w)
    put("sck", (182.38, 84.0), (183.02, 84.0))
    # cs_n: in line at y 88.0
    cut("/06 fpga_config/flash_cs_n_r", IN2, (181.38, 88.0), (182.02, 88.0))
    put("cs_n", (181.38, 88.0), (182.02, 88.0))
    # io2: in line on its diagonal
    c = (183.5, 80.0); v1, v2 = (c[0] - D, c[1] + D), (c[0] + D, c[1] - D)
    cut("/06 fpga_config/flash_io2_r", IN2, v1, v2)
    put("io2", v1, v2)
    # io0: on its diagonal (x + y = 264.6), the vias 0.1 mm towards io2 to keep clear of io1 beside it
    n = "/06 fpga_config/flash_io0_r"
    c = (185.5, 79.1); k = 0.1 / math.sqrt(2); e = 0.62 / math.sqrt(2)
    v1, v2 = (c[0] - D - k, c[1] + D - k), (c[0] + D - k, c[1] - D - k)
    a1, a2 = (c[0] - e, c[1] + e), (c[0] + e, c[1] - e)
    w = cut(n, IN2, a1, a2); seg(n, IN2, a1, v1, w); seg(n, IN2, v2, a2, w)
    put("io0", v1, v2)
    # io3: beside its vertical run at x 188.4, at 45 degrees in the one pocket where two vias fit (eMMC on In5 around)
    n = "/06 fpga_config/flash_io3_r"
    w = cut(n, IN2, (188.4, 84.9), (188.4, 83.9257))
    cut(n, IN2, (188.9, 83.4257), (188.4, 83.9257))
    seg(n, IN2, (188.4, 84.9), (188.5, 84.65), w); seg(n, IN2, (188.9, 84.2), (188.9, 83.4257), w)
    put("io3", (188.5, 84.65), (188.9, 84.2))
    # io1: on B.Cu at the via (179.4, 84.1) where its flash-side run dives to In2
    n = "/06 fpga_config/flash_io1_r"
    t = next(t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T and t.GetNetname() == n and t.GetLayer() == BC
             and (179.4, 84.1) in (r2(t.GetStart()), r2(t.GetEnd())))
    far = t.GetStart() if r2(t.GetEnd()) == (179.4, 84.1) else t.GetEnd()
    L = TOMM(t.GetLength()); ux, uy = (179.4 - TOMM(far.x)) / L, (84.1 - TOMM(far.y)) / L
    assert L > 0.66, L
    p1 = (round(179.4 - 0.64 * ux, 3), round(84.1 - 0.64 * uy, 3))
    (t.SetEnd if r2(t.GetEnd()) == (179.4, 84.1) else t.SetStart)(P(*p1))
    put("io1", p1, (179.4, 84.1), new_via=(False, False))
    for sig in PULL:
        pullup(sig)


def phy():
    """R901 / R902 / R904 / R905 / R906 (RGMII TX 22R) are 0201 (user, 2026-11-16; tools/swap_footprint.py first).
    R905 moves 0.25 mm west: the phy_txd2 via sat between the 0402's pads. R906's FPGA-side track ended under the
    larger pad and gets 0.37 mm more. R903 stays 0402: rgmii_txd2 passes between its pads to reach R905."""
    pp = place("R905", 176.931, 71.794, 0)
    if pp["1"][0] > pp["2"][0]:
        pp = place("R905", 176.931, 71.794, 180)
    track([(177.25, 71.55), pp["2"]], "B", "/09 ethernet/phy_txd2", 0.12)
    track([(175.75, 74.289), pad("R906", 1)], "B", "/rgmii_txd3", 0.12)
    print("PHY TX resistors: R905 at", pp)


def pll():
    """PLL supply filters rebuilt at the balls (user, 2026-11-16: the ferrites and filter capacitors had long traces
    and were parked off the board to be placed close to the pins; 0201 ferrites as on the Agilex card).
    Per rail: via in the ball, 1 u at 45 degrees on that via with GND on a GND ball via, then the ferrite from a
    supply ball via and the 4u7, each within about a millimetre of copper (positions from a spot search)."""
    for (x, y, n) in ((166.8, 78.2, BL), (164.4, 75.0, PLL), (160.4, 83.0, TR)):
        if via_free(x, y, n):
            via(x, y, n)
    # VCCA_BL: ferrite straight across the via pair VCORE (166.8, 77.4) -> R8; the 1 u leaves R8 down-left
    part2("FB501", (166.8, 77.4), (0, 1), "VCORE", BL)
    cap("C501", (166.74, 78.26), (-1, 1), BL, None, (166.0, 79.0))
    # DDR PLL: ferrite across the via pair 0V85 (164.4, 75.8) -> W11; the 1 u 1 mm north of the ball (no GND
    # ball via is free beside W11 once the ferrite is there)
    part2("FB504", (164.4, 75.8), (0, -1), "0V85", PLL)
    if abs(pad("C5072", 1)[0] - 164.15) < 0.05:
        place("C5072", 222.0, 76.0, 0)       # makes room; placed again below if a spot is found
    cap("C507", (164.15, 74.07), (0, -1), PLL, (164.4, 75.0), (163.6, 72.6))
    cap("C505", (160.376, 83.024), (-1, 1), TR, None, (159.6, 83.8))
    cap("C503", (166.874, 84.874), (1, 1), BR, (166.8, 84.6), (167.2, 85.98))
    # copper of the last commit that the rip-up took along and that is still needed
    for x, y, n in ((172.4, 72.6, "GND"), (167.6, 75.8, "0V85"), (166.0, 78.2, "VCORE")):   # vias in U501 balls
        via(x, y, n, need=False, force=True)
    for a_, c_ in (((160.7, 85.1), (160.8, 85.0)), ((161.55, 85.1), (161.85, 85.4)), ((160.35, 85.45), (160.1, 85.2)),
                   ((160.8, 85.0), (160.8, 83.4)), ((161.3, 85.1), (160.7, 85.1)), ((160.1, 85.2), (159.5, 85.2)),
                   ((161.35, 85.15), (161.3, 85.1)), ((160.7, 85.1), (160.35, 85.45)), ((161.5, 85.15), (161.35, 85.15)),
                   ((160.8, 83.4), (160.4, 83.0))):                                           # VCCA_TR's local bus
        track([a_, c_], "B", TR, 0.2)
    # VCORE to the supervisor U401 pin 5 (SENSE): it was one track with the old feed of FB501
    track([(172.866, 96.1315), (174.0185, 96.1315), (179.35, 90.8), (180.7, 90.8), (186.85, 96.95)], "F", "VCORE", 0.2)
    via(186.85, 96.95, "VCORE", need=False, force=True)
    track([(186.85, 96.95), (187.0, 97.1), (187.0, 97.4875)], "B", "VCORE", 0.2)
    for args in PLL_PARTS:
        part2(*args)
    strip([(165.8, 87.2), (164.5, 87.2)], {BR}); strip([(163.947, 75.453)], {"GND"})
    strip([(164.5, 86.2), (163.034, 93.565), (163.519, 93.565)], {"VCORE"})


PLL_PARTS = [   # ref, pad on the first net, direction of the other pad, first net, second net, link tracks
    ("FB503", (160.174, 82.376), (1, -1), "/05 fpga_power/vcca_tr", "VCORE", (160.4, 83.0), (161.2, 81.48)),
    ("C506", (161.25, 84.47), (0, -1), "/05 fpga_power/vcca_tr", "GND", (161.3, 85.1), None),
    ("FB502", (166.35, 84.17), (0, -1), "/05 fpga_power/vcca_br", "VCORE", (166.35, 84.22), (166.0, 83.0)),
    ("C504", (165.65, 84.17), (0, -1), "/05 fpga_power/vcca_br", "GND", (165.78, 84.30), (165.67, 83.51)),
    ("C5072", (164.75, 74.52), (0, -1), "/05 fpga_power/vddpll_mcb_top_phy_ddr", "GND", (164.30, 74.64), (164.15, 73.43)),
    ("C561", (170.93, 76.1), (1, 0), "1V8", "GND", (170.86, 76.62), None),
]


def part2(ref, p1, towards, net1, net2, link1=None, link2=None):
    """two-pad 0201 on B.Cu: pad 1 (net1) at p1, pad 2 (net2) towards `towards`, optional link tracks"""
    place(ref, p1[0], p1[1], 0, "B")
    pp = on_via(ref, p1[0], p1[1], *towards)
    if fp(ref).FindPadByNumber("1").GetNetname() != net1:   # the part's pad 1 is the other net: turn it round
        q = (p1[0] + 0.64 * towards[0] / math.hypot(*towards), p1[1] + 0.64 * towards[1] / math.hypot(*towards))
        pp = on_via(ref, q[0], q[1], -towards[0], -towards[1]); pp = {"1": pp["2"], "2": pp["1"]}
    if link1:
        track([pp["1"], link1], "B", net1, 0.2)
    if link2:
        track([pp["2"], link2], "B", net2, 0.2)
    print(f"   {ref} {fp(ref).GetValue()}: {net1.split('/')[-1]} pad {pp['1']}, {net2.split('/')[-1]} pad {pp['2']}")


def drop():
    """C502, C508, C5073 and C5060 found no room at the PLL balls and were deleted (user, 2026-11-16;
    tools/pi_delete_parts.py for the schematic): the footprints go, with the copper that only led to them."""
    for ref in ("C502", "C508", "C5073", "C5060"):
        f = fp(ref)
        if not f:
            continue
        old = [(TOMM(p.GetPosition().x), TOMM(p.GetPosition().y), p.GetNetname()) for p in f.Pads() if p.GetNumber()]
        b.Delete(f)
        strip([(x, y) for x, y, _ in old], {n for _, _, n in old})
        print("  ", ref, "deleted")


STEPS = {"s3": s3, "s8": s8, "s7": s7, "s5": s5, "s4": s4, "s2": s2, "s1": s1, "s9": s9, "s6": s6}
STEPS["r603"] = r603; STEPS["tidy"] = tidy; STEPS["flash"] = flash; STEPS["phy"] = phy; STEPS["pll"] = pll; STEPS["drop"] = drop  # later changes, not in the default run
for name in (sys.argv[3:] or [k for k in STEPS if k not in ("r603", "tidy", "flash", "phy", "pll", "drop")]):
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
