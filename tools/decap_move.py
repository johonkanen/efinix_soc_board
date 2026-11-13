#!/usr/bin/env python3
"""Move loose decaps under U501 next to a ball via of their rail and connect them (kipy):

    decap_move.py --strip IN OUT REF [REF ...]    remove the copper hanging on these caps (its own run)
    decap_move.py IN OUT REF [REF ...]            move and connect them
    decap_move.py --pads IN OUT REF [REF ...]     the same, but courtyards may overlap: 0.2 mm between the pads of
                                                  different parts instead (user decision 2026-11-12, under U501 only);
                                                  45 degree orientations are tried too (rail pad on its ball via,
                                                  ground pad in the gap between four balls)

For each cap the rail pad goes onto, or within 0.9 mm of, a U501 ball via of its rail, in one of four orientations;
the ground pad must then sit on a GND via or reach one with a straight track of at most 1.0 mm. A spot is legal if
the pads keep 0.1 mm to foreign copper on B.Cu and to every other part's pads, 0.175 mm from foreign holes, and the
courtyard overlaps no other B.Cu courtyard. Of the legal spots the one with the least track is taken, then the
nearest. Tracks are 0.2 mm. Caps with no legal spot within 7 mm stay where they are and are reported.
--strip removes the tracks ending on the caps' pads, the vias in those pads and the via at the far end of such a
track, unless the via is a ball via or something else uses it.
"""
import math
import sys

import pcbnew

MM, FM = pcbnew.ToMM, pcbnew.FromMM
RAILS = ("VCORE", "1V8", "3V3", "0V85", "1V1")
CLR, HOLE, TRK = 0.1, 0.175, 0.2
key = lambda v: (round(MM(v.x), 3), round(MM(v.y), 3))


def strip(src, out, refs):
    b = pcbnew.LoadBoard(src)
    balls = [p for p in b.FindFootprintByReference("U501").Pads()]
    is_ball = lambda v: any(p.HitTest(v.GetPosition()) for p in balls)
    tracks = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
    vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
    doomed, gone = [], set()
    for r in refs:
        f = b.FindFootprintByReference(r)
        for p in f.Pads():
            if not p.GetNumber():
                continue
            for t in tracks:
                if t.GetNetCode() == p.GetNetCode() and t.IsOnLayer(f.GetLayer()) and (p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd())) \
                        and t.m_Uuid.AsString() not in gone:
                    doomed.append(t); gone.add(t.m_Uuid.AsString())
            for v in vias:
                if v.GetNetCode() == p.GetNetCode() and p.HitTest(v.GetPosition()) and not is_ball(v) and v.m_Uuid.AsString() not in gone:
                    doomed.append(v); gone.add(v.m_Uuid.AsString())
    grew = True
    while grew:                                              # chains (two-segment tracks) and their end vias
        grew = False
        ends = {e for t in doomed if not isinstance(t, pcbnew.PCB_VIA) for e in (key(t.GetStart()), key(t.GetEnd()))}
        live = [t for t in tracks if t.m_Uuid.AsString() not in gone]
        used = {}
        for t in live:
            for e in (key(t.GetStart()), key(t.GetEnd())):
                used[e] = used.get(e, 0) + 1
        for t in live:                                       # a track whose one end hangs on a removed track's free end
            for e, o in ((key(t.GetStart()), key(t.GetEnd())), (key(t.GetEnd()), key(t.GetStart()))):
                if e in ends and used[e] == 1 and not any(key(v.GetPosition()) == e for v in vias) \
                        and not any(q.HitTest(pcbnew.VECTOR2I(FM(e[0]), FM(e[1]))) for fp in b.GetFootprints() for q in fp.Pads() if q.GetNetCode() == t.GetNetCode()):
                    doomed.append(t); gone.add(t.m_Uuid.AsString()); grew = True
                    break
        for v in vias:
            k = key(v.GetPosition())
            if v.m_Uuid.AsString() in gone or is_ball(v) or k not in ends or used.get(k, 0):
                continue
            if any(q.HitTest(v.GetPosition()) for fp in b.GetFootprints() if fp.GetReference() not in refs for q in fp.Pads() if q.GetNetCode() == v.GetNetCode()):
                continue
            doomed.append(v); gone.add(v.m_Uuid.AsString()); grew = True
    for t in doomed:
        b.Remove(t)
    pcbnew.SaveBoard(out, b)
    print(f"decap_move --strip: {len(doomed)} tracks/vias removed")


def gap_pt_rect(r, x, y):
    return math.hypot(max(r[0] - x, 0, x - r[2]), max(r[1] - y, 0, y - r[3]))


def gap_rect_rect(r, s):
    return math.hypot(max(r[0] - s[2], s[0] - r[2], 0), max(r[1] - s[3], s[1] - r[3], 0))


def gap_seg_rect(g, r):
    n = max(2, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.04))
    return min(gap_pt_rect(r, g[0] + (g[2] - g[0]) * i / n, g[1] + (g[3] - g[1]) * i / n) for i in range(n + 1)) - g[4]


def gap_pt_seg(g, x, y):
    ax, ay, cx, cy, hw = g
    l2 = (cx - ax) ** 2 + (cy - ay) ** 2
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
    return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay))) - hw


class Pad:
    """A pad rectangle turned by its part's axis (ux, uy): half length hl along the axis, half width hw across."""
    def __init__(self, c, hl, hw, ux, uy):
        self.c, self.hl, self.hw, self.ux, self.uy = c, hl, hw, ux, uy

    def pt(self, x, y):
        dx, dy = x - self.c[0], y - self.c[1]
        a, w = dx * self.ux + dy * self.uy, -dx * self.uy + dy * self.ux
        return math.hypot(max(abs(a) - self.hl, 0), max(abs(w) - self.hw, 0))

    def rect(self, r):
        if r[0] <= self.c[0] <= r[2] and r[1] <= self.c[1] <= r[3]:
            return 0.0
        n = 8
        pts = [(r[0] + (r[2] - r[0]) * i / n, y) for i in range(n + 1) for y in (r[1], r[3])] + \
              [(x, r[1] + (r[3] - r[1]) * i / n) for i in range(n + 1) for x in (r[0], r[2])]
        return min(self.pt(*q) for q in pts)

    def seg(self, g):
        n = max(2, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.04))
        return min(self.pt(g[0] + (g[2] - g[0]) * i / n, g[1] + (g[3] - g[1]) * i / n) for i in range(n + 1)) - g[4]

    def box(self):
        ex = abs(self.ux) * self.hl + abs(self.uy) * self.hw; ey = abs(self.uy) * self.hl + abs(self.ux) * self.hw
        return (self.c[0] - ex, self.c[1] - ey, self.c[0] + ex, self.c[1] + ey)


def move(src, out, refs, pads_rule=False):
    b = pcbnew.LoadBoard(src)
    u = b.FindFootprintByReference("U501").GetBoundingBox(False)
    ux0, uy0, ux1, uy1 = MM(u.GetLeft()) - 0.5, MM(u.GetTop()) - 0.5, MM(u.GetRight()) + 0.5, MM(u.GetBottom()) + 0.5
    pads, crts, segs, vias = [], [], [], []     # (rect, net code, ref) / (rect, ref) / (geom, net code) / (x, y, r, drill r, code)
    for f in b.GetFootprints():
        if f.IsFlipped():
            c = f.GetCourtyard(pcbnew.B_CrtYd).BBox()
            crts.append(((MM(c.GetLeft()), MM(c.GetTop()), MM(c.GetRight()), MM(c.GetBottom())), f.GetReference()))
        for p in f.Pads():
            if p.IsOnCopperLayer() and p.IsOnLayer(pcbnew.B_Cu):
                bb = p.GetBoundingBox()
                pads.append(((MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())), p.GetNetCode(), f.GetReference()))
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            q = t.GetPosition()
            vias.append((MM(q.x), MM(q.y), MM(t.GetWidth(pcbnew.B_Cu)) / 2, MM(t.GetDrill()) / 2, t.GetNetCode()))
        elif t.GetLayer() == pcbnew.B_Cu:
            segs.append(((MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth()) / 2), t.GetNetCode()))
    gnd = b.FindNet("GND").GetNetCode()

    def pad_ok(r, code, ref):
        for s, n, o in pads:
            if o != ref and abs(s[0] - r.c[0]) < 2 and abs(s[1] - r.c[1]) < 2 and r.rect(s) < (0.2 if pads_rule else CLR) - 1e-6:
                return False
        for g, n in segs:
            if n != code and min(abs(g[0] - r.c[0]), abs(g[2] - r.c[0])) < 3 and r.seg(g) < CLR - 1e-6:
                return False
        for x, y, rv, rd, n in vias:
            if n != code and r.pt(x, y) < max(rv + CLR, rd + HOLE) - 1e-6:
                return False
        return True

    def seg_ok(a, c, code, ref):
        n_s = max(2, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.04)); need = TRK / 2 + CLR - 1e-6
        for i in range(n_s + 1):
            x, y = a[0] + (c[0] - a[0]) * i / n_s, a[1] + (c[1] - a[1]) * i / n_s
            if any(n != code and gap_pt_rect(s, x, y) < need for s, n, o in pads if o != ref) \
                    or any(n != code and gap_pt_seg(g, x, y) < need for g, n in segs) \
                    or any(n != code and math.hypot(x - vx, y - vy) - rv < need for vx, vy, rv, rd, n in vias):
                return False
        return True

    def link(p, rect, code, ref, reach):
        """(track length, via) to the nearest reachable via of the net: 0 if one lies in the pad."""
        best = None
        for vx, vy, rv, rd, n in vias:
            if n != code:
                continue
            d = math.hypot(vx - p[0], vy - p[1])
            if d > reach or (best and d >= best[0]):
                continue
            if rect.pt(vx, vy) == 0:
                return 0.0, None
            if seg_ok(p, (vx, vy), code, ref):
                best = (d, (vx, vy))
        return best

    moved, stuck = [], []
    for ref in refs:
        f = b.FindFootprintByReference(ref)
        fp = [p for p in f.Pads() if p.GetNumber()]
        rail_pad = next(p for p in fp if p.GetNetname() in RAILS); gnd_pad = next(p for p in fp if p.GetNetname() == "GND")
        code = rail_pad.GetNetCode()
        d = math.hypot(MM(rail_pad.GetPosition().x - gnd_pad.GetPosition().x), MM(rail_pad.GetPosition().y - gnd_pad.GetPosition().y))
        bb = rail_pad.GetBoundingBox(); along = max(MM(bb.GetWidth()), MM(bb.GetHeight())) if False else None
        o0 = f.GetOrientationDegrees() % 180
        w, h = MM(bb.GetWidth()), MM(bb.GetHeight())
        pl, pw = (w, h) if o0 == 0 else (h, w)               # pad size along / across the part's axis
        cb = f.GetCourtyard(pcbnew.B_CrtYd).BBox(); cw, ch = MM(cb.GetWidth()), MM(cb.GetHeight())
        cl, cwid = (cw, ch) if o0 == 0 else (ch, cw)
        here = (MM(f.GetPosition().x), MM(f.GetPosition().y))
        pads[:] = [x for x in pads if x[2] != ref]; crts[:] = [x for x in crts if x[1] != ref]
        cands = []
        for vx, vy, rv, rd, n in vias:
            if n != code or not (ux0 < vx < ux1 and uy0 < vy < uy1) or math.hypot(vx - here[0], vy - here[1]) > 7.0:
                continue
            for ox, oy in [(0, 0)] + [(i * 0.2, j * 0.2) for i in range(-4, 5) for j in range(-4, 5) if (i or j) and math.hypot(i, j) * 0.2 <= 0.9]:
                p1 = (vx + ox, vy + oy)
                q = math.sqrt(0.5)
                for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)) + (((q, q), (q, -q), (-q, q), (-q, -q)) if pads_rule else ()):
                    p2 = (p1[0] + ax * d, p1[1] + ay * d)
                    r1 = Pad(p1, pl / 2, pw / 2, ax, ay); r2 = Pad(p2, pl / 2, pw / 2, ax, ay)
                    cx, cy = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                    chx, chy = (cl / 2, cwid / 2) if ay == 0 else (cwid / 2, cl / 2)
                    cr = (cx - chx, cy - chy, cx + chx, cy + chy)
                    cands.append((math.hypot(ox, oy), math.hypot(cx - here[0], cy - here[1]), p1, p2, r1, r2, cr))
        cands.sort(key=lambda c: (c[0] > 0, c[1]))
        best = None; why = {}
        for off, dist, p1, p2, r1, r2, cr in cands:
            if best and (best[0] == 0 or off > 0 and dist > best[1] + 3):
                break
            if not pads_rule and any(o != ref and r[0] < cr[2] - 1e-6 and r[2] > cr[0] + 1e-6 and r[1] < cr[3] - 1e-6 and r[3] > cr[1] + 1e-6 for r, o in crts):
                why["courtyard"] = why.get("courtyard", 0) + 1; continue
            if not pad_ok(r1, code, ref) or not pad_ok(r2, gnd, ref):
                why["pad clearance"] = why.get("pad clearance", 0) + 1; continue
            l1 = link(p1, r1, code, ref, 0.95)
            if not l1:
                why["rail link"] = why.get("rail link", 0) + 1; continue
            l2 = link(p2, r2, gnd, ref, 1.0)
            if not l2:
                why["gnd link"] = why.get("gnd link", 0) + 1; continue
            tot = l1[0] + l2[0]
            if best is None or (tot, dist) < (best[0], best[1]):
                best = (tot, dist, p1, p2, r1, r2, cr, l1, l2)
        if best is None:
            stuck.append(f"{ref} {why or 'no ball via of the rail within 7 mm'}")
            for p in fp:
                bb = p.GetBoundingBox()
                pads.append(((MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())), p.GetNetCode(), ref))
            crts.append(((MM(cb.GetLeft()), MM(cb.GetTop()), MM(cb.GetRight()), MM(cb.GetBottom())), ref))
            continue
        tot, dist, p1, p2, r1, r2, cr, l1, l2 = best
        f.SetPosition(pcbnew.VECTOR2I(FM((p1[0] + p2[0]) / 2), FM((p1[1] + p2[1]) / 2)))
        err = None
        for a in range(0, 360, 45):
            f.SetOrientationDegrees(a)
            q = rail_pad.GetPosition(); e = math.hypot(MM(q.x) - p1[0], MM(q.y) - p1[1])
            if err is None or e < err[0]:
                err = (e, a)
        f.SetOrientationDegrees(err[1]); assert err[0] < 0.02, (ref, err)
        pads += [(r1.box(), code, ref), (r2.box(), gnd, ref)]; crts.append((cr, ref))
        for (ln, v), p, n in ((l1, p1, rail_pad.GetNet()), (l2, p2, gnd_pad.GetNet())):
            if v:
                t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(p[0]), FM(p[1]))); t.SetEnd(pcbnew.VECTOR2I(FM(v[0]), FM(v[1])))
                t.SetWidth(FM(TRK)); t.SetLayer(pcbnew.B_Cu); t.SetNet(n); b.Add(t)
                segs.append(((p[0], p[1], v[0], v[1], TRK / 2), n.GetNetCode()))
        moved.append(f"{ref} {dist:.1f} mm, track {tot:.2f} mm")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(out, b)
    print(f"decap_move: {len(moved)} moved:", "; ".join(moved))
    print("  no legal spot:", "; ".join(stuck) or "none")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 4 and a[0] == "--strip":
        strip(a[1], a[2], a[3:])
    elif len(a) >= 4 and a[0] == "--pads":
        move(a[1], a[2], a[3:], pads_rule=True)
    elif len(a) >= 3:
        move(a[0], a[1], a[2:])
    else:
        sys.exit(__doc__)
