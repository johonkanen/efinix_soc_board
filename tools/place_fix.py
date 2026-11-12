#!/usr/bin/env python3
"""Phase 2 placement corrections (layout_plan_remaining.md section 5).

    tools/p2k/bin/kipy tools/place_fix.py BOARD [SET]   (edits BOARD in place: run it on a copy in work/)

SET is "phase2" (default) or "pll" (phase 3: the VCCA_BL and DDR-PLL ferrites and their 1 u caps, which sat
25 mm from their balls beside the PHY, flipped to B.Cu and moved next to the balls).

1. NUDGES: fixed small moves that clear the courtyard overlaps. Copper on a moved pad follows it: a via
   in the pad moves with the pad, and every track that ended there gets a stub from the old spot.
2. RELOCATE: two-pad parts that sit far from the net they serve are moved to the nearest legal spot
   on their own side near a target point (courtyard free, pads clear of foreign vias, tracks and pads).
   A part is left alone if no spot beats the limit given for it.
Locked footprints and footprints in protected_footprints.txt are never moved.
"""
import sys
import math
import pcbnew

MM = pcbnew.FromMM
board_path = sys.argv[1]
b = pcbnew.LoadBoard(board_path)
fps = {f.GetReference(): f for f in b.GetFootprints()}
protected = {l.split("\t")[0] for l in open("protected_footprints.txt") if l.strip() and not l.startswith("#")}

# ref: (dx, dy) mm
NUDGES = {
    "C105": (0.55, 0.0),      # off U101's courtyard
    "C1004": (0.20, 0.0),     # off C1005 (C1005 itself sits between via rows)
    "R1016": (0.15, 0.0),     # its pad 2 off the emmc_rst_n_r via that moves with R1023
    "R1009": (0.40, 0.0),     # off U501's courtyard (not north: flash_io3 runs on In2 at y 88.125)
    "R1022": (0.60, 0.12),    # off U501's courtyard and off R1009
    "R1023": (0.60, 0.12),
}
# ref: (target ref, target pad, search radius mm, accept only if closer than this to the target, mm)
RELOCATE = {
    # eMMC pull-ups/pull-down that sit at the eMMC but are on the FPGA-side net (west of the 33R)
    "R1011": ("R1003", "1", 6.0, 6.0),   # emmc_dat0
    "R1012": ("R1004", "1", 6.0, 6.0),   # emmc_dat1
    "R1013": ("R1005", "1", 6.0, 6.0),   # emmc_dat2
    "R1015": ("R1007", "1", 6.0, 6.0),   # emmc_dat4
    "R1017": ("R1009", "1", 6.0, 6.0),   # emmc_dat6
    "R1018": ("R1021", "1", 6.0, 6.0),   # emmc_dat7
    "R1020": ("R1022", "1", 6.0, 6.0),   # emmc_ds pull-down
    # VCCA_BL caps: closer to ball R8 only if a spot within 3.5 mm exists
    "C5061": ("U501", "R8", 3.5, 3.5),
    "C5062": ("U501", "R8", 3.5, 3.5),
    "C5060": ("U501", "R8", 3.5, 3.5),
}
SET = sys.argv[2] if len(sys.argv) > 2 else "phase2"
FLIP = set()
if SET == "pll":
    NUDGES = {}
    RELOCATE = {
        "C501": ("U501", "R8", 6.0, 6.0),     # vcca_bl 1u
        "FB501": ("U501", "R8", 7.0, 7.0),    # VCORE -> vcca_bl
        "C507": ("U501", "W11", 6.0, 6.0),    # vddpll 1u
        "C508": ("U501", "W11", 6.0, 6.0),    # vddpll 100n
        "FB504": ("U501", "W11", 7.0, 7.0),   # 0V85 -> vddpll
    }
    FLIP = set(RELOCATE)
if SET == "c542":
    # 1V1 decap boxed in by routed RGMII on every layer: onto the 1V1 ball via R1 if a spot exists
    NUDGES = {}
    RELOCATE = {"C542": ("U501", "R1", 1.2, 1.2)}
if SET == "c502":
    # the third vcca_bl cap left beside the PHY when FB501/C501 moved in phase 3
    NUDGES = {}
    RELOCATE = {"C502": ("U501", "R8", 7.0, 7.0)}
    FLIP = {"C502"}
TOP = set()
if SET == "pll_top":
    # 2026-11-12, user: the B.Cu strip north-east of U501 is too crowded and F.Cu beside it has room.
    # The two PLL ferrites and their larger caps go to F.Cu east of the DDR corridor; only the small
    # caps stay on B.Cu at the balls. Targets "@" are board coordinates for the named pad.
    NUDGES = {}
    RELOCATE = {
        "FB501": ("@", (176.9, 75.0, "2"), 3.0, 99), "C501": ("@", (176.9, 74.0, "1"), 3.0, 99),
        "C5060": ("@", (178.0, 75.0, "1"), 3.0, 99), "C502": ("@", (178.0, 74.0, "1"), 3.0, 99),
        "FB504": ("@", (176.9, 71.5, "2"), 3.0, 99), "C507": ("@", (176.9, 70.5, "1"), 3.0, 99),
        "C508": ("@", (178.0, 70.5, "1"), 3.0, 99),
        "C5062": ("U501", "R8", 3.0, 3.0), "C5063": ("U501", "R8", 3.0, 3.0),
        "C5072": ("U501", "W11", 3.0, 3.0), "C5073": ("U501", "W11", 3.0, 3.0),
    }
    TOP = {"FB501", "C501", "C5060", "C502", "FB504", "C507", "C508"}
if SET == "bulk_top":
    # 2026-11-12, user: bulk caps on the east side of the crowded B.Cu strip go to F.Cu, where the 1V1
    # (In3) and 1V8 (In4) planes are under the free area. C542 (1V1, boxed in on B.Cu) goes with them.
    NUDGES = {}
    RELOCATE = {
        "C538": ("@", (178.5, 73.5, "1"), 5.0, 99), "C5023": ("@", (181.0, 73.5, "1"), 5.0, 99),
        "C5020": ("@", (180.0, 70.0, "1"), 5.0, 99),
    }   # C542 stays: its GND pad carries copper from before this work, and a flip in place would short
    TOP = set(RELOCATE)
ALLOW_PROTECTED = set()
if SET == "ddr_caps":
    # the four 22u LPDDR4 1V1 bulk caps that were parked above the board edge; the user allowed moving
    # them on 2026-11-12. They are locked again after the move (and the baseline is re-taken).
    NUDGES = {}
    RELOCATE = {"C806": ("U801", "U3", 7.0, 99), "C807": ("U801", "F3", 7.0, 99), "C823": ("U801", "U10", 7.0, 99), "C824": ("U801", "F10", 7.0, 99)}
    ALLOW_PROTECTED = set(RELOCATE)
CLR = 0.10          # copper clearance used for the search (board minimum 0.09)
HOLE = 0.175        # hole to copper
STEP = 0.05


def movable(ref):
    f = fps[ref]
    if ref in ALLOW_PROTECTED:
        f.SetLocked(False)
    elif f.IsLocked() or ref in protected:
        sys.exit(f"{ref} is locked/protected: not moved")
    return f


def pad(ref, num):
    return next(p for p in fps[ref].Pads() if p.GetNumber() == num)


def cy_box(f):
    f.BuildCourtyardCaches()
    bb = f.GetCourtyard(pcbnew.F_CrtYd if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd).BBox()
    return [pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())]


def pad_box(p):
    bb = p.GetBoundingBox()
    return [pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())]


# ---------------------------------------------------------------------------------------------------
# 1. nudges
# ---------------------------------------------------------------------------------------------------
for ref, (dx, dy) in NUDGES.items():
    f = movable(ref)
    d = pcbnew.VECTOR2I(MM(dx), MM(dy))
    old = {p.GetNumber(): (p.GetPosition(), p.GetNetname(), p.GetNetCode()) for p in f.Pads() if p.GetNumber()}
    f.SetPosition(f.GetPosition() + d)
    stubs = 0
    for num, (pos, net, code) in old.items():
        new = pos + d
        for t in list(b.GetTracks()):
            if t.GetNetname() != net:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                if t.GetPosition() == pos:
                    t.SetPosition(new)
            else:
                for end in (t.GetStart(), t.GetEnd()):
                    if (end - pos).EuclideanNorm() < MM(0.03):
                        s = pcbnew.PCB_TRACK(b)
                        s.SetStart(pcbnew.VECTOR2I(end.x, end.y)); s.SetEnd(new)
                        s.SetLayer(t.GetLayer()); s.SetWidth(t.GetWidth()); s.SetNetCode(code)
                        b.Add(s); stubs += 1
    print(f"nudge {ref}: ({dx:+.2f}, {dy:+.2f}) mm, {stubs} stub(s)")

# ---------------------------------------------------------------------------------------------------
# 2. relocation to the nearest legal spot
# ---------------------------------------------------------------------------------------------------
edge = b.GetBoardEdgesBoundingBox()
EX0, EY0, EX1, EY1 = [pcbnew.ToMM(v) for v in (edge.GetLeft(), edge.GetTop(), edge.GetRight(), edge.GetBottom())]


def seg_rect_dist(x1, y1, x2, y2, r):
    """Distance from segment to rectangle r = (l, t, rgt, btm); 0 if they touch."""
    n = max(2, int(math.hypot(x2 - x1, y2 - y1) / 0.04) + 1)
    best = 1e9
    for i in range(n + 1):
        x = x1 + (x2 - x1) * i / n; y = y1 + (y2 - y1) * i / n
        ddx = max(r[0] - x, 0, x - r[2]); ddy = max(r[1] - y, 0, y - r[3])
        best = min(best, math.hypot(ddx, ddy))
    return best


def relocate(ref, tref, tpad, radius, limit):
    f = movable(ref)
    flipped = (ref in FLIP and f.GetLayer() == pcbnew.F_Cu) or (ref in TOP and f.GetLayer() == pcbnew.B_Cu)
    if flipped:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    side = f.GetLayer()
    fx, fy = pcbnew.ToMM(f.GetPosition().x), pcbnew.ToMM(f.GetPosition().y)
    if tref == "@":
        tx, ty = tpad[0], tpad[1]
        signal_pad = pad(ref, tpad[2]); tpad = "(%.1f, %.1f)" % (tx, ty)
    else:
        tp = pad(tref, tpad).GetPosition()
        tx, ty = pcbnew.ToMM(tp.x), pcbnew.ToMM(tp.y)
        signal_pad = next(p for p in f.Pads() if p.GetNumber() and p.GetNetname() == pad(tref, tpad).GetNetname())
    cur = math.hypot(pcbnew.ToMM(signal_pad.GetPosition().x) - tx, pcbnew.ToMM(signal_pad.GetPosition().y) - ty)
    # shape relative to the footprint position, at the current orientation
    c = cy_box(f)
    rel_cy = (c[0] - fx, c[1] - fy, c[2] - fx, c[3] - fy)
    rel_pads = []
    for p in f.Pads():
        if not p.GetNumber():
            continue
        q = pad_box(p)
        rel_pads.append((q[0] - fx, q[1] - fy, q[2] - fx, q[3] - fy, p.GetNetname(), p.GetNumber() == signal_pad.GetNumber()))

    def rot(box, k):          # k quarter turns, counter-clockwise on screen (KiCad's positive angle)
        l, t, r, btm = box[:4]
        for _ in range(k):
            l, t, r, btm = t, -r, btm, -l
        return (min(l, r), min(t, btm), max(l, r), max(t, btm))

    # obstacles in the window
    W = radius + 2.0
    near = lambda x, y: abs(x - tx) < W and abs(y - ty) < W
    courts = []
    for o in fps.values():
        if o is f or o.GetLayer() != side:
            continue
        oc = cy_box(o)
        if oc[2] > tx - W and oc[0] < tx + W and oc[3] > ty - W and oc[1] < ty + W:
            courts.append(oc)
    vias, segs, opads = [], [], []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y = pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)
            if near(x, y):
                vias.append((x, y, max(pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2 + CLR, pcbnew.ToMM(t.GetDrillValue()) / 2 + HOLE), t.GetNetname()))
        elif t.GetLayer() == side:
            x1, y1, x2, y2 = [pcbnew.ToMM(v) for v in (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)]
            if near(x1, y1) or near(x2, y2):
                segs.append((x1, y1, x2, y2, pcbnew.ToMM(t.GetWidth()) / 2 + CLR, t.GetNetname()))
    for o in fps.values():
        if o is f:
            continue
        for p in o.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or o.GetLayer() == side:
                q = pad_box(p)
                if near((q[0] + q[2]) / 2, (q[1] + q[3]) / 2):
                    opads.append((q, p.GetNetname()))

    best = None
    n = int(radius / STEP)
    for k in range(4):
        rcy = rot(rel_cy, k)
        rpads = [rot(p, k) + (p[4], p[5]) for p in rel_pads]
        for ix in range(-n, n + 1):
            for iy in range(-n, n + 1):
                # the signal pad's centre lands on (tx + ix*STEP, ty + iy*STEP)
                sp = next(p for p in rpads if p[5])
                x = tx + ix * STEP - (sp[0] + sp[2]) / 2; y = ty + iy * STEP - (sp[1] + sp[3]) / 2
                dist = math.hypot(ix * STEP, iy * STEP)
                if dist > radius or (best and dist >= best[0]):
                    continue
                cy = (rcy[0] + x, rcy[1] + y, rcy[2] + x, rcy[3] + y)
                if cy[0] < EX0 + 0.5 or cy[1] < EY0 + 0.5 or cy[2] > EX1 - 0.5 or cy[3] > EY1 - 0.5:
                    continue
                if any(cy[0] < o[2] - 0.01 and cy[2] > o[0] + 0.01 and cy[1] < o[3] - 0.01 and cy[3] > o[1] + 0.01 for o in courts):
                    continue
                ok = True
                for p in rpads:
                    r = (p[0] + x, p[1] + y, p[2] + x, p[3] + y)
                    for vx, vy, need, net in vias:
                        dd = math.hypot(max(r[0] - vx, 0, vx - r[2]), max(r[1] - vy, 0, vy - r[3]))
                        if net != p[4] and dd < need:
                            ok = False; break
                    if ok:
                        for x1, y1, x2, y2, need, net in segs:
                            if net != p[4] and min(x1, x2) - need < r[2] and max(x1, x2) + need > r[0] and min(y1, y2) - need < r[3] and max(y1, y2) + need > r[1] \
                                    and seg_rect_dist(x1, y1, x2, y2, r) < need:
                                ok = False; break
                    if ok:
                        for q, net in opads:
                            if net != p[4] and r[0] < q[2] + CLR and r[2] > q[0] - CLR and r[1] < q[3] + CLR and r[3] > q[1] - CLR:
                                ok = False; break
                    if not ok:
                        break
                if ok:
                    best = (dist, x, y, k)
    if not best or best[0] >= min(limit, cur - 0.5):
        print(f"relocate {ref}: no better spot (now {cur:.1f} mm from {tref}.{tpad}); left in place")
        if flipped:
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        return
    dist, x, y, k = best
    for p in f.Pads():
        if p.GetNumber():
            pos = p.GetPosition()
            if any(t.GetNetname() == p.GetNetname() and t.Type() != pcbnew.PCB_VIA_T and
                   ((t.GetStart() - pos).EuclideanNorm() < MM(0.2) or (t.GetEnd() - pos).EuclideanNorm() < MM(0.2)) for t in b.GetTracks()):
                print(f"relocate {ref}: pad {p.GetNumber()} has a track on it; left in place")
                if flipped:
                    f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                return
    f.SetOrientationDegrees(f.GetOrientationDegrees() + 90 * k)
    f.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    got = signal_pad.GetPosition()
    err = math.hypot(pcbnew.ToMM(got.x) - tx, pcbnew.ToMM(got.y) - ty) - dist
    if abs(err) > 0.02:
        sys.exit(f"relocate {ref}: predicted and actual pad position differ by {err:.3f} mm")
    if ref in ALLOW_PROTECTED:
        f.SetLocked(True)
    print(f"relocate {ref}: ({fx:.2f}, {fy:.2f}) -> ({x:.2f}, {y:.2f}) rot +{90 * k}; {cur:.1f} -> {dist:.2f} mm from {tref}.{tpad}")


for ref, args in RELOCATE.items():
    relocate(ref, *args)

pcbnew.SaveBoard(board_path, b)
