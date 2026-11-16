#!/usr/bin/env python3
"""eMMC pull-ups R1010-R1018 (47k to 1V8 on CMD and DAT0-7, FPGA-side nets), user 2026-11-16:
    tools/p2k/bin/kipy tools/emmc_pullups.py IN.kicad_pcb OUT.kicad_pcb
- The old B.Cu taps to the former pull-up positions are stripped (dead ends of the eMMC nets).
- Pull-ups the user has placed beside the series resistors on F.Cu get 1V8: a via in the 1V8 pad if one fits,
  else the nearest via position with a short track.
- Pull-ups still parked right of the board are placed on F.Cu or B.Cu at the nearest spot to their series
  resistor's pad 1 (or a via of the net) where the part fits, its 1V8 pad can have a via and a straight link
  of at most 2.5 mm is clear.
Rerun tools/emmc_delay_rules.py afterwards: the FPGA-side delays change with the taps."""
import math
import sys

sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2], "none"]
exec(open(__file__.replace("emmc_pullups.py", "pi_fixes.py")).read().split('STEPS = {"s3"')[0])   # helpers, loads the board

SERIES = {"cmd": "R1002", "dat0": "R1003", "dat1": "R1004", "dat2": "R1005", "dat3": "R1006", "dat4": "R1007",
          "dat5": "R1008", "dat6": "R1009", "dat7": "R1021"}
PULL = {"cmd": "R1010", "dat0": "R1011", "dat1": "R1012", "dat2": "R1013", "dat3": "R1014", "dat4": "R1015",
        "dat5": "R1016", "dat6": "R1017", "dat7": "R1018"}
LAY = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}

# 1. old taps: every B.Cu track end of an FPGA-side eMMC net that touches nothing
for sig in SERIES:
    name = "/emmc_" + sig; nc = net(name).GetNetCode()
    its = [t for t in b.GetTracks() if t.GetNetCode() == nc]
    seeds = []
    for t in its:
        if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() != pcbnew.B_Cu:
            continue
        for e in (t.GetStart(), t.GetEnd()):
            touch = any(o is not t and o.m_Uuid != t.m_Uuid and
                        ((o.Type() == pcbnew.PCB_VIA_T and (o.GetPosition() - e).EuclideanNorm() < MM(0.2)) or
                         (o.Type() != pcbnew.PCB_VIA_T and o.GetLayer() == t.GetLayer() and
                          seg_d(e.x, e.y, o.GetStart().x, o.GetStart().y, o.GetEnd().x, o.GetEnd().y) < MM(0.07))) for o in its)
            touch = touch or any(p.GetNetCode() == nc and p.IsOnLayer(pcbnew.B_Cu) and p.HitTest(e) for f in b.GetFootprints() for p in f.Pads())
            if not touch:
                seeds.append((TOMM(e.x), TOMM(e.y)))
    if seeds:
        strip(seeds, {name})


def cy_rect(cx, cy, horizontal):
    hx, hy = (0.75, 0.4) if horizontal else (0.4, 0.75)
    return (cx - hx, cy - hy, cx + hx, cy + hy)


def cy_clear(rect, layer, skip):
    for f in b.GetFootprints():
        if f.GetLayer() != layer or f.GetReference() in skip:
            continue
        bb = f.GetCourtyard(layer).BBox()
        if TOMM(bb.GetLeft()) < rect[2] and TOMM(bb.GetRight()) > rect[0] and TOMM(bb.GetTop()) < rect[3] and TOMM(bb.GetBottom()) > rect[1]:
            return False
    return True


def supply(ref):
    """1V8 for a placed pull-up: via in the 1V8 pad, or the nearest free via position with a straight track"""
    f = fp(ref); p = next(q for q in f.Pads() if q.GetNetname() == "1V8"); lay = f.GetLayer()
    x0, y0 = TOMM(p.GetPosition().x), TOMM(p.GetPosition().y); best = None
    for i in range(-24, 25):
        for j in range(-24, 25):
            x, y = x0 + 0.05 * i, y0 + 0.05 * j; d = math.hypot(x - x0, y - y0)
            if d > 1.2 or (best and d >= best[0]) or not via_free(x, y, "1V8"):
                continue
            n = max(1, int(d / 0.05))
            if all(clear_at(x0 + (x - x0) * k / n, y0 + (y - y0) * k / n, {"1V8"}, 0.1, {lay}) for k in range(n + 1)):
                best = (d, x, y)
    if not best:
        print(f"   {ref}: no 1V8 via position within 1.2 mm"); return
    via(best[1], best[2], "1V8")
    if best[0] > 0.01:
        track([(x0, y0), (best[1], best[2])], "F" if lay == pcbnew.F_Cu else "B", "1V8", 0.15)
    print(f"   {ref}: 1V8 via at ({best[1]:.2f}, {best[2]:.2f}), {best[0]:.2f} mm from the pad")


def park(ref):
    return TOMM(fp(ref).GetPosition().x) > 208.5


def put(sig):
    ref, name = PULL[sig], "/emmc_" + sig; nc = net(name).GetNetCode()
    sp = pad(SERIES[sig], 1)
    anchors = [("F", sp)] + [("B", (TOMM(t.GetPosition().x), TOMM(t.GetPosition().y))) for t in b.GetTracks()
                             if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == nc
                             and math.hypot(TOMM(t.GetPosition().x) - sp[0], TOMM(t.GetPosition().y) - sp[1]) < 3.0]
    anchors += [("F", a) for l, a in anchors if l == "B"]
    best = None
    for side, (ax, ay) in anchors:
        L = LAY[side]
        for i in range(-50, 51):
            for j in range(-50, 51):
                qx, qy = ax + 0.05 * i, ay + 0.05 * j               # 1V8 pad and via
                for ux, uy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = qx + 0.64 * ux, qy + 0.64 * uy          # signal pad
                    d = math.hypot(nx - ax, ny - ay)
                    if d < 0.55 or d > 2.5 or (best and d >= best[0]):
                        continue
                    if not cy_clear(cy_rect((qx + nx) / 2, (qy + ny) / 2, ux != 0), L, {ref}):
                        continue
                    if not (via_free(qx, qy, "1V8") and clear_at(qx, qy, {"1V8"}, 0.27, {L}) and clear_at(nx, ny, {name}, 0.27, {L})
                            and clear_at((qx + nx) / 2, (qy + ny) / 2, {name, "1V8"}, 0.2, {L})):
                        continue
                    n = max(2, int(d / 0.05))
                    if all(clear_at(ax + (nx - ax) * k / n, ay + (ny - ay) * k / n, {name}, 0.1, {L}) for k in range(n + 1)):
                        best = (d, side, ax, ay, qx, qy, nx, ny)
    if not best:
        print(f"   {ref} ({sig}): no spot found, still parked"); return
    d, side, ax, ay, qx, qy, nx, ny = best
    place(ref, (qx + nx) / 2, (qy + ny) / 2, 0, side)
    pn = next(p.GetNumber() for p in fp(ref).Pads() if p.GetNetname() == name)
    on_via(ref, *((nx, ny, qx - nx, qy - ny) if pn == "1" else (qx, qy, nx - qx, ny - qy)))
    via(qx, qy, "1V8"); track([(ax, ay), (nx, ny)], side, name, 0.12)
    print(f"   {ref} ({sig}): {side}.Cu, signal pad ({nx:.2f}, {ny:.2f}) {d:.2f} mm from ({ax:.2f}, {ay:.2f}), 1V8 via ({qx:.2f}, {qy:.2f})")


# found by a wider search (any point of the F.Cu route, B.Cu side): a new via on the route, the pull-up on B.Cu
#        sig     via on the route   signal pad        1V8 pad and via
FIXED = {"dat3": ((173.84, 86.2), (173.84, 87.15), (173.84, 87.79)),
         "dat7": ((173.71, 84.29), (173.71, 83.69), (173.71, 83.05))}


def put_fixed(sig):
    ref, name = PULL[sig], "/emmc_" + sig; v, n, q = FIXED[sig]
    via(v[0], v[1], name); via(q[0], q[1], "1V8")
    place(ref, (n[0] + q[0]) / 2, (n[1] + q[1]) / 2, 0, "B")
    pn = next(p.GetNumber() for p in fp(ref).Pads() if p.GetNetname() == name)
    on_via(ref, *((n[0], n[1], q[0] - n[0], q[1] - n[1]) if pn == "1" else (q[0], q[1], n[0] - q[0], n[1] - q[1])))
    track([v, n], "B", name, 0.12)
    print(f"   {ref} ({sig}): B.Cu, via on the route at {v}, signal pad {n}, 1V8 via {q}")


def has_supply(ref):
    p = next(q for q in fp(ref).Pads() if q.GetNetname() == "1V8")
    return any(t.GetNetname() == "1V8" and (p.HitTest(t.GetPosition()) if t.Type() == pcbnew.PCB_VIA_T else
               (p.IsOnLayer(t.GetLayer()) and (p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd())))) for t in b.GetTracks())


for sig in SERIES:
    if park(PULL[sig]):
        put_fixed(sig) if sig in FIXED else put(sig)
    elif not has_supply(PULL[sig]):
        supply(PULL[sig])
# vias of the FPGA-side nets left with copper on one layer only (in a ball or pad, from the old taps)
base = opens()
for sig in SERIES:
    nc = net("/emmc_" + sig).GetNetCode()
    for v in [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == nc]:
        pt = v.GetPosition()
        lay = {o.GetLayer() for o in b.GetTracks() if o.Type() != pcbnew.PCB_VIA_T and o.GetNetCode() == nc and
               seg_d(pt.x, pt.y, o.GetStart().x, o.GetStart().y, o.GetEnd().x, o.GetEnd().y) <= o.GetWidth() // 2 + MM(0.15)}
        lay |= {(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu) for f in b.GetFootprints() for p in f.Pads()
                if p.GetNetCode() == nc and p.HitTest(pt)}
        if len(lay) < 2:
            x, y = TOMM(pt.x), TOMM(pt.y); b.Delete(v)
            if opens() > base:
                via(x, y, "/emmc_" + sig, force=True)
            else:
                print(f"   one-sided via of emmc_{sig} removed at ({x:.2f}, {y:.2f})")
# eMMC reset: R1023 was moved 0.55 mm east by the user; its F.Cu track and the In5 run stopped at the old pads
p1, p2 = pad("R1023", 1), pad("R1023", 2)
if not any(t.GetNetname() == "/10 emmc/emmc_rst_n_r" and t.Type() == pcbnew.PCB_VIA_T and
           fp("R1023").FindPadByNumber("2").HitTest(t.GetPosition()) for t in b.GetTracks()):
    track([(173.91, 90.05), p1], "F", "/emmc_rst_n", 0.12)
    via(p2[0], p2[1], "/10 emmc/emmc_rst_n_r", force=True)
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(174.54, 90.05)); t.SetEnd(P(*p2)); t.SetLayer(pcbnew.In5_Cu); t.SetWidth(MM(0.12))
    t.SetNet(net("/10 emmc/emmc_rst_n_r")); b.Add(t)
    print("   R1023 (emmc_rst_n) reconnected")
refill()
print("emmc_pullups: open connections", opens())
b.Save(DST)
