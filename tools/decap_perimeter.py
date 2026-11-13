#!/usr/bin/env python3
"""Move rail decaps from under U501 to the ring just outside its body (kipy):

    decap_perimeter.py IN OUT REF [REF ...]

User decision 2026-11-13: the 4.7 u and 1 u 0201 caps gain least from sitting on a ball, so they leave the space
under the BGA to the 100 n / 10 n / 1 n. Strip their old copper first (decap_move.py --strip, its own run).

Each cap goes to the nearest spot, on B.Cu, 0.3 ... 4 mm outside the body outline of U501, axis-parallel, where
- both pads take a via in the pad (0.3/0.15) that is legal on every layer, the rail via on the filled plane of its
  rail (In3: VCORE, 1V1, 3V3; In4: 1V8, 0V85), the GND via to In1/In6;
- the pads keep 0.1 mm to foreign copper on B.Cu, 0.2 mm to other parts' pads, and the courtyard overlaps none.
Legal = 0.1 mm copper, 0.175 mm hole to copper, 0.2 mm hole to hole. Caps without a spot stay and are reported.
"""
import math
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
PLANE = {"VCORE": "In3.Cu", "1V1": "In3.Cu", "3V3": "In3.Cu", "1V8": "In4.Cu", "0V85": "In4.Cu"}
CLR, HOLE, H2H, PADGAP = 0.1, 0.175, 0.2, 0.2
VIA, DRILL = 0.3, 0.15
NEAR, FAR, STEP = 0.3, 4.0, 0.1
BODY = 18.0                                                   # LFBGA-484 body, mm


def rect_of(bb):
    return (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))


def gap_pt_rect(r, x, y):
    return math.hypot(max(r[0] - x, 0, x - r[2]), max(r[1] - y, 0, y - r[3]))


def gap_rect_rect(r, s):
    return math.hypot(max(r[0] - s[2], s[0] - r[2], 0), max(r[1] - s[3], s[1] - r[3], 0))


def gap_pt_seg(g, x, y):
    ax, ay, cx, cy, hw = g
    l2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
    return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay))) - hw


def gap_seg_rect(g, r):
    n = max(2, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.04))
    return min(gap_pt_rect(r, g[0] + (g[2] - g[0]) * i / n, g[1] + (g[3] - g[1]) * i / n) for i in range(n + 1)) - g[4]


def main(src, out, refs):
    b = pcbnew.LoadBoard(src)
    u = b.FindFootprintByReference("U501"); uc = (MM(u.GetPosition().x), MM(u.GetPosition().y))
    body = (uc[0] - BODY / 2, uc[1] - BODY / 2, uc[0] + BODY / 2, uc[1] + BODY / 2)
    win = (body[0] - FAR - 1, body[1] - FAR - 1, body[2] + FAR + 1, body[3] + FAR + 1)
    inwin = lambda x, y: win[0] < x < win[2] and win[1] < y < win[3]
    edge = rect_of(b.GetBoardEdgesBoundingBox())
    pads, crts, segs, vias = [], [], [], []   # (rect, code, ref, B.Cu?, round r) / (rect, ref) / (geom, code, B.Cu?) / (x, y, r, drill r, code)
    for f in b.GetFootprints():
        if f.IsFlipped():
            crts.append((rect_of(f.GetCourtyard(pcbnew.B_CrtYd).BBox()), f.GetReference()))
        for p in f.Pads():
            if p.IsOnCopperLayer() and inwin(MM(p.GetPosition().x), MM(p.GetPosition().y)):
                rnd = MM(p.GetSize(pcbnew.F_Cu).x) / 2 if f is u else 0
                pads.append((rect_of(p.GetBoundingBox()), p.GetNetCode(), f.GetReference(), p.IsOnLayer(pcbnew.B_Cu), rnd))
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            q = t.GetPosition()
            if inwin(MM(q.x), MM(q.y)):
                vias.append((MM(q.x), MM(q.y), MM(t.GetWidth(pcbnew.B_Cu)) / 2, MM(t.GetDrill()) / 2, t.GetNetCode()))
        else:
            pts = [t.GetStart(), t.GetEnd()]; extra = 0.0
            if isinstance(t, pcbnew.PCB_ARC):                 # two chords through the mid point, a little fatter
                pts = [t.GetStart(), t.GetMid(), t.GetEnd()]; extra = 0.05
            for a, c in zip(pts, pts[1:]):
                g = (MM(a.x), MM(a.y), MM(c.x), MM(c.y), MM(t.GetWidth()) / 2 + extra)
                if max(g[0], g[2]) > win[0] and min(g[0], g[2]) < win[2] and max(g[1], g[3]) > win[1] and min(g[1], g[3]) < win[3]:
                    segs.append((g, t.GetNetCode(), t.GetLayer() == pcbnew.B_Cu))
    zones = {}
    for z in b.Zones():
        for l in z.GetLayerSet().Seq():
            zones.setdefault((z.GetNetname(), b.GetLayerName(l)), []).append((z, l))
    gnd = b.FindNet("GND").GetNetCode()

    def on_plane(net, p):
        return any(all(z.HitTestFilledArea(l, pcbnew.VECTOR2I(FM(p[0] + dx), FM(p[1] + dy)))
                       for dx, dy in ((0, 0), (.15, 0), (-.15, 0), (0, .15), (0, -.15))) for z, l in zones.get((net, PLANE[net]), []))

    def via_ok(p, code, ref):
        need = max(VIA / 2 + CLR, DRILL / 2 + HOLE) - 1e-6
        for s, n, o, bcu, rnd in pads:
            if o == ref or n == code or abs(s[0] - p[0]) > 2 or abs(s[1] - p[1]) > 2:
                continue
            g = math.hypot((s[0] + s[2]) / 2 - p[0], (s[1] + s[3]) / 2 - p[1]) - rnd if rnd else gap_pt_rect(s, *p)
            if g < need:
                return False
        for g, n, bcu in segs:
            if n != code and min(g[0], g[2]) - 1 < p[0] < max(g[0], g[2]) + 1 and min(g[1], g[3]) - 1 < p[1] < max(g[1], g[3]) + 1 \
                    and gap_pt_seg(g, *p) < need:
                return False
        for vx, vy, rv, rd, n in vias:
            dd = math.hypot(vx - p[0], vy - p[1])
            if (n != code and dd - rv < need) or dd < rd + DRILL / 2 + H2H - 1e-6:
                return False
        return True

    def pad_ok(r, code, ref):
        for s, n, o, bcu, rnd in pads:
            if bcu and o != ref and abs(s[0] - r[0]) < 3 and abs(s[1] - r[1]) < 3 and gap_rect_rect(r, s) < PADGAP - 1e-6:
                return False
        for g, n, bcu in segs:
            if bcu and n != code and min(g[0], g[2]) - 1 < r[2] and max(g[0], g[2]) + 1 > r[0] and min(g[1], g[3]) - 1 < r[3] \
                    and max(g[1], g[3]) + 1 > r[1] and gap_seg_rect(g, r) < CLR - 1e-6:
                return False
        for x, y, rv, rd, n in vias:
            if n != code and gap_pt_rect(r, x, y) < max(rv + CLR, rd + HOLE) - 1e-6:
                return False
        return True

    ring = []
    x = body[0] - FAR
    while x <= body[2] + FAR + 1e-9:
        y = body[1] - FAR
        while y <= body[3] + FAR + 1e-9:
            if not (body[0] - NEAR < x < body[2] + NEAR and body[1] - NEAR < y < body[3] + NEAR) \
                    and edge[0] + 1 < x < edge[2] - 1 and edge[1] + 1 < y < edge[3] - 1:
                ring.append((round(x, 3), round(y, 3)))
            y += STEP
        x += STEP
    moved, stuck = [], []
    for ref in refs:
        f = b.FindFootprintByReference(ref)
        fp = [p for p in f.Pads() if p.GetNumber()]
        rail_pad = next(p for p in fp if p.GetNetname() in PLANE); gnd_pad = next(p for p in fp if p.GetNetname() == "GND")
        code, rail = rail_pad.GetNetCode(), rail_pad.GetNetname()
        d = math.hypot(MM(rail_pad.GetPosition().x - gnd_pad.GetPosition().x), MM(rail_pad.GetPosition().y - gnd_pad.GetPosition().y))
        here = (MM(f.GetPosition().x), MM(f.GetPosition().y))
        if f.GetOrientationDegrees() % 90:                    # a cap placed at 45 degrees under the BGA
            f.SetOrientationDegrees(0)
        o0 = f.GetOrientationDegrees() % 180
        bb = rail_pad.GetBoundingBox(); w, h = MM(bb.GetWidth()), MM(bb.GetHeight())
        pl, pw = (w, h) if o0 == 0 else (h, w)
        cb = f.GetCourtyard(pcbnew.B_CrtYd).BBox(); cw, ch = MM(cb.GetWidth()), MM(cb.GetHeight())
        cl, cwid = (cw, ch) if o0 == 0 else (ch, cw)
        pads[:] = [x for x in pads if x[2] != ref]; crts[:] = [x for x in crts if x[1] != ref]
        best = None
        for c in sorted(ring, key=lambda q: math.hypot(q[0] - here[0], q[1] - here[1])):
            for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                hx, hy = (cl / 2, cwid / 2) if ay == 0 else (cwid / 2, cl / 2)
                cr = (c[0] - hx, c[1] - hy, c[0] + hx, c[1] + hy)
                if cr[0] < body[2] + NEAR and cr[2] > body[0] - NEAR and cr[1] < body[3] + NEAR and cr[3] > body[1] - NEAR:
                    continue
                if any(r[0] < cr[2] - 1e-6 and r[2] > cr[0] + 1e-6 and r[1] < cr[3] - 1e-6 and r[3] > cr[1] + 1e-6 for r, o in crts):
                    continue
                p1 = (c[0] - ax * d / 2, c[1] - ay * d / 2); p2 = (c[0] + ax * d / 2, c[1] + ay * d / 2)
                px, py = (pl / 2, pw / 2) if ay == 0 else (pw / 2, pl / 2)
                r1 = (p1[0] - px, p1[1] - py, p1[0] + px, p1[1] + py); r2 = (p2[0] - px, p2[1] - py, p2[0] + px, p2[1] + py)
                if not pad_ok(r1, code, ref) or not pad_ok(r2, gnd, ref):
                    continue
                if not via_ok(p1, code, ref) or gap_pt_rect(r2, *p1) < VIA / 2 + CLR - 1e-6 or not on_plane(rail, p1):
                    continue
                if not via_ok(p2, gnd, ref) or gap_pt_rect(r1, *p2) < VIA / 2 + CLR - 1e-6:
                    continue
                best = (c, p1, p2, r1, r2, cr); break
            if best:
                break
        if best is None:
            stuck.append(ref)
            for p in fp:
                pads.append((rect_of(p.GetBoundingBox()), p.GetNetCode(), ref, True, 0))
            crts.append((rect_of(cb), ref))
            continue
        c, p1, p2, r1, r2, cr = best
        f.SetPosition(pcbnew.VECTOR2I(FM(c[0]), FM(c[1])))
        err = None
        for a in (0, 90, 180, 270):
            f.SetOrientationDegrees(a)
            q = rail_pad.GetPosition(); e = math.hypot(MM(q.x) - p1[0], MM(q.y) - p1[1])
            if err is None or e < err[0]:
                err = (e, a)
        f.SetOrientationDegrees(err[1]); assert err[0] < 0.02, (ref, err)
        for p, pad in ((p1, rail_pad), (p2, gnd_pad)):
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(FM(p[0]), FM(p[1]))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(FM(VIA)); v.SetDrill(FM(DRILL)); v.SetNet(pad.GetNet()); b.Add(v)
            vias.append((p[0], p[1], VIA / 2, DRILL / 2, pad.GetNetCode()))
        pads += [(r1, code, ref, True, 0), (r2, gnd, ref, True, 0)]; crts.append((cr, ref))
        side = "W" if c[0] < body[0] else "E" if c[0] > body[2] else "N" if c[1] < body[1] else "S"
        out_d = max(body[0] - c[0], c[0] - body[2], body[1] - c[1], c[1] - body[3])
        moved.append(f"{ref} {rail} {math.hypot(c[0] - here[0], c[1] - here[1]):.1f} mm to ({c[0]:.1f}, {c[1]:.1f}) {side} {out_d:.1f} mm out")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(out, b)
    print(f"decap_perimeter: {len(moved)} moved")
    for m in moved:
        print("  ", m)
    print("  no spot:", " ".join(stuck) or "none")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
