#!/usr/bin/env python3
"""One regulator cell layout (AP6120x) for every rail: parts and copper from a single template (kipy).

    buck_cell.py --demo OUT.kicad_pcb [OUT.json]      one cell alone on an empty board, for review and DRC
    buck_cell.py --strip IN.kicad_pcb OUT.kicad_pcb   remove the cells' old copper (run first, as its own step)
    buck_cell.py IN.kicad_pcb OUT.kicad_pcb           place and draw the five cells of the card (CELLS below)

On the card (after tools/buck_cell_sch.py, add_parts.py and swap_footprint.py have brought the parts in):
- the old copper of every cell is removed: B.Cu tracks of its SW, FB, rail, GND and 5V0 nets reached from the
  cell's pads, and the vias on them that nothing else uses;
- the regulator is turned so the output edge faces the rail's plane entry (CELLS: N/E/S/W on the board) and stays
  where it is, unless the cell's box hits foreign B.Cu parts, B.Cu tracks or vias: then the nearest free spot
  within 3 mm is taken;
- every via is checked against all layers (0.1 mm copper, 0.175 mm hole clearance). Output vias slide along the
  bus, ground vias move inside the ground area, a via with no legal site is left out and reported;
- rail pads of other parts lying within 1.2 mm beyond the output edge (the LPDDR4 caps at the 1V1 cell) get a
  0.3 mm track straight onto the bus;
- the In4 0V85 region is widened to cover the 0V85 cell's output vias.

The template is written in the regulator's pin frame, taken from the pads themselves, so rotation and the
bottom-side flip come out right:  origin = package centre, +x = pin 3 (VIN) -> pin 4 (SW), +y = pin 1 (FB) -> pin 3.
AP6120x (since 2026-11-13; before: TLV62585, the mirror image of this cell about the y axis):
FB 1, GND 2, VIN 3 are the -x row, SW 4, EN 5, PG 6 the +x row.

    +y   VIN side:  C_HF 100n 0201, then CIN 10u 0603, both VIN pad over pin 3, GND pad on the centre strip side
    +x   L 2520, pads along y, SW pad beside pin 4, VOUT pad toward -y; EN runs out between the two pads
    -y   COUT row: 47u 0805 (VOUT pad under L's VOUT pad) and 22u 0603, GND pads in the middle under the regulator,
         then the VOUT bus with the plane vias: the -y edge is the cell's output edge
    -x   R1, CFF (FB - VOUT) beside the FB pin, R2 (FB - GND) below it
GND is one piece on the cell's layer: pin 2, the strip between the pin rows, both COUT grounds, R2, C_HF and CIN.
PG has a via in its pad (it is fenced by EN and GND).
Every footprint keeps its courtyard clear of the others.
"""
import json
import math
import os
import sys

import pcbnew

FM, MM = pcbnew.FromMM, pcbnew.ToMM
CAP, RES, IND = "Capacitor_SMD", "Resistor_SMD", "Inductor_SMD"
PROJ_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
# role: (library, footprint, pad 1 position, pad 2 position) in the pin frame
PARTS = {
    "L":    ("ti135_card", "L_2520_FTC252012S", (2.64, 0.825), (2.64, -0.825)),  # 1 SW, 2 VOUT
    "CHF":  (CAP, "C_0201_0603Metric", (-0.64, 1.39), (0.00, 1.39)),       # 1 VIN, 2 GND
    "CIN":  (CAP, "C_0603_1608Metric", (-0.71, 2.56), (0.84, 2.56)),       # 1 VIN, 2 GND
    "COUT1": (CAP, "C_0805_2012Metric", (3.29, -3.645), (1.39, -3.645)),    # 47u: 1 VOUT, 2 GND
    "COUT2": (CAP, "C_0603_1608Metric", (-1.705, -3.645), (-0.155, -3.645)),  # 22u: 1 VOUT, 2 GND
    "R2":   (RES, "R_0201_0603Metric", (-0.94, -1.45), (-0.30, -1.45)),    # 1 FB, 2 GND
    "R1":   (RES, "R_0201_0603Metric", (-2.43, -0.5), (-1.79, -0.5)),      # 1 VOUT, 2 FB
    "CFF":  (CAP, "C_0201_0603Metric", (-2.43, -1.29), (-1.79, -1.29)),    # 1 VOUT, 2 FB
}
PADNETS = {"L": ("SW", "VOUT"), "CHF": ("VIN", "GND"), "CIN": ("VIN", "GND"), "COUT1": ("VOUT", "GND"),
           "COUT2": ("VOUT", "GND"), "R2": ("FB", "GND"), "R1": ("VOUT", "FB"), "CFF": ("VOUT", "FB")}
PIN = {"FB": "1", "GND": "2", "VIN": "3", "SW": "4", "EN": "5", "PG": "6"}     # AP6120x, SOT-563
# copper areas (net role, outline); drawn as solid zones on the cell's layer
AREAS = [
    ("SW",   [(0.375, 0.35), (3.69, 0.35), (3.69, 0.65), (0.375, 0.65)]),
    ("VIN",  [(-1.05, 0.325), (-0.375, 0.325), (-0.375, 3.035), (-1.3, 3.035), (-1.3, 1.6), (-1.05, 1.35)]),
    ("GND",  [(-0.17, -0.8), (-0.17, -0.15), (-1.05, -0.15), (-1.05, 0.15), (-0.17, 0.15), (-0.17, 1.19), (-0.23, 1.19),
              (-0.23, 1.59), (-0.1, 1.59), (-0.1, 3.035), (1.29, 3.035), (1.29, 2.085), (0.3, 2.085), (0.23, 1.59),
              (0.23, 1.19), (0.17, 1.19), (0.17, -0.8), (1.3, -0.8), (1.3, -2.6), (1.89, -2.6), (1.89, -4.37),
              (0.32, -4.37), (0.32, -4.12), (-0.63, -4.12), (-0.63, -2.6), (-0.53, -2.1), (-0.53, -0.8)]),
    ("VOUT", [(3.79, -0.35), (1.59, -0.35), (1.59, -1.3), (2.14, -1.3), (2.14, -4.55), (-1.255, -4.55),
              (-1.255, -3.17), (-2.155, -3.17), (-2.155, -5.15), (3.79, -5.15)]),
]
TRACKS = [  # net role, width, points
    ("FB", 0.15, [(-0.7125, -0.5), (-1.79, -0.5), (-1.79, -1.29), (-1.5, -1.45), (-0.94, -1.45)]),
    ("VOUT", 0.2, [(-2.43, -0.5), (-2.43, -1.29), (-2.43, -2.7), (-1.9, -3.25)]),
    ("EN", 0.15, [(0.7125, 0.0), (3.96, 0.0)]),                      # between the inductor's pads
]
VIAS = [  # net role, position, diameter, drill
    ("VOUT", (2.9, -4.85), 0.45, 0.25), ("VOUT", (2.1, -4.85), 0.45, 0.25), ("VOUT", (1.3, -4.85), 0.45, 0.25),
    ("VOUT", (0.5, -4.85), 0.45, 0.25), ("VOUT", (-0.5, -4.85), 0.45, 0.25), ("VOUT", (-1.5, -4.85), 0.45, 0.25),
    ("GND", (0.85, -1.3), 0.45, 0.25), ("GND", (0.85, -2.1), 0.45, 0.25), ("GND", (0.1, -2.1), 0.45, 0.25),
    ("GND", (0.45, -2.8), 0.45, 0.25), ("GND", (0.84, 2.56), 0.3, 0.15),
    ("PG", (0.8, -0.5), 0.3, 0.15),
]
OLD_BBOX = (-4.035, -5.15, 2.975, 3.335)   # the TLV62585 cell, for --strip
BBOX = (-2.975, -5.15, 4.035, 3.335)   # cell extent in the pin frame (courtyards and copper)


class Frame:
    def __init__(self, u):
        p = {q.GetNumber(): (MM(q.GetPosition().x), MM(q.GetPosition().y)) for q in u.Pads()}
        self.o = tuple(sum(p[n][k] for n in "1346") / 4 for k in (0, 1))
        self.ex = self._unit(p["3"], p["4"]); self.ey = self._unit(p["1"], p["3"])

    @staticmethod
    def _unit(a, c):
        d = (c[0] - a[0], c[1] - a[1]); n = math.hypot(*d)
        return d[0] / n, d[1] / n

    def __call__(self, q):
        return (self.o[0] + q[0] * self.ex[0] + q[1] * self.ey[0], self.o[1] + q[0] * self.ex[1] + q[1] * self.ey[1])

    def v(self, q):
        g = self(q)
        return pcbnew.VECTOR2I(FM(g[0]), FM(g[1]))


def place2(f, fr, p1, p2):
    """Move a two-pad footprint so pad 1 lands on p1 and pad 2 on p2 (pin frame)."""
    g1, g2 = fr(p1), fr(p2)
    f.SetPosition(pcbnew.VECTOR2I(FM((g1[0] + g2[0]) / 2), FM((g1[1] + g2[1]) / 2)))
    best = None
    for a in (0, 90, 180, 270):
        f.SetOrientationDegrees(a)
        q = next(x for x in f.Pads() if x.GetNumber() == "1").GetPosition()
        e = math.hypot(MM(q.x) - g1[0], MM(q.y) - g1[1])
        if best is None or e < best[0]:
            best = (e, a)
    f.SetOrientationDegrees(best[1])
    assert best[0] < 0.02, (f.GetReference(), best)


def copper(b, fr, layer, nets):
    """The cell's zones, tracks and vias. nets: role -> NETINFO_ITEM."""
    made = []
    for role, pts in AREAS:
        z = pcbnew.ZONE(b)
        z.SetLayer(layer); z.SetNet(nets[role]); z.SetAssignedPriority(20 + len(made))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetLocalClearance(FM(0.1)); z.SetMinThickness(FM(0.1))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER); z.SetZoneName("buck_cell")
        o = z.Outline(); o.NewOutline()
        for q in pts:
            o.Append(fr.v(q))
        b.Add(z); made.append(z)
    for role, w, pts in TRACKS:
        for a, c in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(fr.v(a)); t.SetEnd(fr.v(c)); t.SetWidth(FM(w)); t.SetLayer(layer); t.SetNet(nets[role])
            b.Add(t); made.append(t)
    for role, q, dia, drill in VIAS:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(fr.v(q)); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetWidth(FM(dia))
        v.SetDrill(FM(drill)); v.SetNet(nets[role])
        b.Add(v); made.append(v)
    return made


CELLS = [  # U, rail, plane layer, output edge faces
    ("U201", "VCORE", "In3.Cu", "N"), ("U301", "1V8", "In4.Cu", "N"), ("U311", "3V3", "In3.Cu", "E"),
    ("U331", "0V85", "In4.Cu", "N"), ("U341", "1V1", "In3.Cu", "E"),
]
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
CLR, HOLE = 0.1, 0.175
SHIFT_HOME = bool(os.environ.get("BUCK_SHIFT_HOME"))


def roles(u):
    b0 = int(u[1:])
    k = (0, 1, 2, 3, 4) if u != "U331" else (0, 1, 4, 2, 3)        # CIN, COUT2, CHF, COUT1, CFF
    r = dict(zip(("CIN", "COUT2", "CHF", "COUT1", "CFF"), (f"C{b0 + j}" for j in k)))
    r.update(L=f"L{b0}", R1=f"R{b0}", R2=f"R{b0 + 1}")
    return r


def _in_poly(q, poly):
    x, y = q; n = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            n = not n
    return n


class Obstacles:
    """Foreign copper: pads of every layer lumped (a through via must clear them all), tracks, vias."""
    def __init__(self, b, skip_refs):
        self.items = []     # kind, geometry, net code, on B.Cu
        for f in b.GetFootprints():
            if f.GetReference() in skip_refs:
                continue
            for p in f.Pads():
                bb = p.GetBoundingBox()
                self.items.append(("rect", (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())),
                                   p.GetNetCode(), p.IsOnLayer(pcbnew.B_Cu)))
        for t in b.GetTracks():
            self.add_track(t)

    def add_track(self, t):
        if isinstance(t, pcbnew.PCB_VIA):
            q = t.GetPosition()
            self.items.append(("circle", (MM(q.x), MM(q.y), MM(t.GetWidth(pcbnew.B_Cu)) / 2), t.GetNetCode(), True))
        else:
            pts = [t.GetStart(), t.GetEnd()]
            if t.GetClass() == "PCB_ARC":                     # two chords through the mid point
                pts.insert(1, pcbnew.Cast_to_PCB_ARC(t).GetMid())
            for a, c in zip(pts, pts[1:]):
                self.items.append(("seg", (MM(a.x), MM(a.y), MM(c.x), MM(c.y), MM(t.GetWidth()) / 2 + (0.02 if len(pts) == 3 else 0)),
                                   t.GetNetCode(), t.GetLayer() == pcbnew.B_Cu))

    @staticmethod
    def gap(kind, g, x, y):
        if kind == "rect":
            return math.hypot(max(g[0] - x, 0, x - g[2]), max(g[1] - y, 0, y - g[3]))
        if kind == "circle":
            return math.hypot(x - g[0], y - g[1]) - g[2]
        ax, ay, cx, cy, hw = g
        l2 = (cx - ax) ** 2 + (cy - ay) ** 2
        t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * (cx - ax) + (y - ay) * (cy - ay)) / l2))
        return math.hypot(x - (ax + t * (cx - ax)), y - (ay + t * (cy - ay))) - hw

    def via_ok(self, p, dia, drill, code):
        need = max(dia / 2 + CLR, drill / 2 + HOLE) - 1e-6
        return all(self.gap(k, g, p[0], p[1]) >= need for k, g, n, _ in self.items if n != code)

    def box_hits(self, x0, y0, x1, y1):
        """Foreign things a cell box must not contain: B.Cu pads and tracks, any via."""
        hits = []
        for k, g, n, on_b in self.items:
            if not on_b:
                continue
            if k == "rect":
                hit = g[0] < x1 and g[2] > x0 and g[1] < y1 and g[3] > y0
            elif k == "circle":
                hit = x0 - g[2] < g[0] < x1 + g[2] and y0 - g[2] < g[1] < y1 + g[2]
            else:
                n_s = 8
                hit = any(x0 < g[0] + (g[2] - g[0]) * i / n_s < x1 and y0 < g[1] + (g[3] - g[1]) * i / n_s < y1 for i in range(n_s + 1))
            if hit:
                hits.append((k, n))
        return hits


def _pt_poly(q, poly):
    if _in_poly(q, poly):
        return 0.0
    return min(Obstacles.gap("seg", (*a, *c, 0.0), q[0], q[1]) for a, c in zip(poly, poly[1:] + poly[:1]))


def cell_shapes(b, fr, refs, nets):
    """The new cell's pads and tracks in board coordinates: (net code, polygon)."""
    out = []                                             # the zones are left out: their fill flows round foreign vias
    for role, w, pts in TRACKS:
        for a, c in zip(pts, pts[1:]):
            (ax, ay), (cx, cy) = fr(a), fr(c); h = w / 2
            out.append((nets[role].GetNetCode(), [(min(ax, cx) - h, min(ay, cy) - h), (max(ax, cx) + h, min(ay, cy) - h),
                                                  (max(ax, cx) + h, max(ay, cy) + h), (min(ax, cx) - h, max(ay, cy) + h)]))
    for ref in refs:
        for p in b.FindFootprintByReference(ref).Pads():
            if p.IsOnLayer(pcbnew.B_Cu):
                bb = p.GetBoundingBox(); x0, y0, x1, y1 = MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom())
                out.append((p.GetNetCode(), [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
    return out


def copper_hits(obst, shapes, bx):
    """Foreign items the cell's copper would touch: B.Cu pads in the box (strict), vias and B.Cu tracks by clearance."""
    hits = []
    for k, g, n, on_b in obst.items:
        if not on_b:
            continue
        if k == "rect":
            if g[0] < bx[2] and g[2] > bx[0] and g[1] < bx[3] and g[3] > bx[1]:
                hits.append((k, n))
            continue
        if k == "circle":
            if not (bx[0] - 1 < g[0] < bx[2] + 1 and bx[1] - 1 < g[1] < bx[3] + 1):
                continue
            pts, need = [(g[0], g[1])], g[2] + CLR
        else:
            if not (min(g[0], g[2]) < bx[2] + 1 and max(g[0], g[2]) > bx[0] - 1 and min(g[1], g[3]) < bx[3] + 1 and max(g[1], g[3]) > bx[1] - 1):
                continue
            m = max(2, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.05) + 1)
            pts, need = [(g[0] + (g[2] - g[0]) * i / m, g[1] + (g[3] - g[1]) * i / m) for i in range(m + 1)], g[4] + CLR
        if any(code != n and _pt_poly(q, poly) < need - 1e-6 for code, poly in shapes for q in pts):
            hits.append((k, n))
    return hits


def strip_old(b, cells):
    """Remove each cell's old B.Cu copper, found by connectivity from its pads."""
    key = lambda v: (round(MM(v.x), 3), round(MM(v.y), 3))
    doomed = []
    for u, rail, *_ in cells:
        refs = [u] + list(roles(u).values())
        fps = [b.FindFootprintByReference(r) for r in refs]
        own = {f"Net-({u}-SW)", f"Net-({u}-FB)"}
        nets = own | {rail, "GND", "5V0"}
        pads = [p for f in fps for p in f.Pads() if p.IsOnLayer(pcbnew.B_Cu)]
        xs = [MM(v) for p in pads for v in (p.GetBoundingBox().GetLeft(), p.GetBoundingBox().GetRight())]
        ys = [MM(v) for p in pads for v in (p.GetBoundingBox().GetTop(), p.GetBoundingBox().GetBottom())]
        x0, x1, y0, y1 = min(xs) - 1.0, max(xs) + 1.0, min(ys) - 1.0, max(ys) + 1.0
        inside = lambda q: x0 < q[0] < x1 and y0 < q[1] < y1
        trk = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.B_Cu
               and t.GetNetname() in nets and inside(key(t.GetStart())) and inside(key(t.GetEnd()))]
        vias = {key(t.GetPosition()): t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() in nets
                and inside(key(t.GetPosition()))}
        take, seeds = [], []                                 # seeds: (net, point) reached so far
        for p in pads:
            bb = p.GetBoundingBox()
            seeds.append((p.GetNetname(), ("rect", MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))))
        grew = True
        while grew:
            grew = False
            for t in list(trk):
                ends = (key(t.GetStart()), key(t.GetEnd()))
                for net, g in seeds:
                    if net != t.GetNetname():
                        continue
                    if g[0] == "rect":
                        touch = any(g[1] - 0.01 <= e[0] <= g[3] + 0.01 and g[2] - 0.01 <= e[1] <= g[4] + 0.01 for e in ends)
                    else:
                        touch = any(math.hypot(e[0] - g[1], e[1] - g[2]) < 0.03 for e in ends)
                    if touch:
                        take.append(t); trk.remove(t); grew = True
                        seeds += [(t.GetNetname(), ("pt", e[0], e[1])) for e in ends]
                        break
        ends = {e for t in take for e in (key(t.GetStart()), key(t.GetEnd()))}
        gone = {t.m_Uuid.AsString() for t in take}            # fresh wrappers each call: compare by uuid
        left = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.m_Uuid.AsString() not in gone]
        used = {e for t in left for e in (key(t.GetStart()), key(t.GetEnd()))}
        for k, v in vias.items():
            near = any(Obstacles.gap("seg", (*key(t.GetStart()), *key(t.GetEnd()), MM(t.GetWidth()) / 2), k[0], k[1]) < 0.05
                       for t in take if not isinstance(t, pcbnew.PCB_VIA))
            on_pad = any(p.GetNetname() == v.GetNetname() and p.HitTest(v.GetPosition()) for p in pads)
            if (near or on_pad) and not any(math.hypot(k[0] - e[0], k[1] - e[1]) < 0.03 for e in used):
                take.append(v)
        doomed += take
        print(f"  {u}: {len(take)} old tracks/vias removed")
    for t in doomed:                                         # SWIG: remove last, then save and reload
        b.Remove(t)
    # what the connectivity walk misses: vias inside the old cell zones, enable fingers. Everything of the cell's
    # nets on B.Cu, and every via of those nets, inside the old cell's box goes.
    gone = {t.m_Uuid.AsString() for t in doomed}
    extra = []
    for u, rail, *_ in cells:
        U = b.FindFootprintByReference(u); fr = Frame(U)
        nets = {p.GetNetname() for p in U.Pads()} | {rail, "GND", "5V0"}
        def inbox(v):
            g = (MM(v.x) - fr.o[0], MM(v.y) - fr.o[1])
            lx, ly = g[0] * fr.ex[0] + g[1] * fr.ex[1], g[0] * fr.ey[0] + g[1] * fr.ey[1]
            return OLD_BBOX[0] - 0.05 < lx < OLD_BBOX[2] + 0.05 and OLD_BBOX[1] - 0.05 < ly < OLD_BBOX[3] + 0.05
        for t in b.GetTracks():
            if t.GetNetname() not in nets or t.m_Uuid.AsString() in gone:
                continue
            if isinstance(t, pcbnew.PCB_VIA):
                hit = inbox(t.GetPosition())
            else:
                loose = t.GetNetname() not in ("GND", "5V0")        # bus ties, enable and PG stubs: one end is enough
                hit = t.GetLayer() == pcbnew.B_Cu and (inbox(t.GetStart()) or inbox(t.GetEnd())) and (loose or (inbox(t.GetStart()) and inbox(t.GetEnd())))
            if hit:
                extra.append(t); gone.add(t.m_Uuid.AsString())
    print(f"  {len(extra)} more tracks/vias inside the old cell boxes removed")
    for t in extra:
        b.Remove(t)
    zs = [z for z in b.Zones() if z.GetZoneName() == "buck_cell"]
    for z in zs:
        b.Remove(z)
    print(f"  {len(zs)} cell zones removed")


def apply(src, out):
    b = pcbnew.LoadBoard(src)
    members = {r for u, *_ in CELLS for r in [u] + list(roles(u).values())}
    obst = Obstacles(b, members)
    zones = {(z.GetNetname(), b.GetLayerName(l)): (z, l) for z in b.Zones() for l in z.GetLayerSet().Seq()}
    taken = []                                               # boxes of the cells placed so far
    for u, rail, plane, face in CELLS:
        U = b.FindFootprintByReference(u)
        for _ in range(4):                                   # turn the output edge (-y) to `face`
            fr = Frame(U)
            if (round(-fr.ey[0]), round(-fr.ey[1])) == DIRS[face]:
                break
            U.SetOrientationDegrees(U.GetOrientationDegrees() + 90)
        else:
            raise SystemExit(f"{u}: cannot face {face}")
        home = home0 = U.GetPosition()
        if SHIFT_HOME:                                       # first run after the TLV62585: put the new box on the old one
            dxf = OLD_BBOX[0] - BBOX[0]
            home = pcbnew.VECTOR2I(home.x + FM(dxf * fr.ex[0]), home.y + FM(dxf * fr.ex[1]))
        pz, pl = zones[(rail, plane)]
        code = {p.GetNumber(): p.GetNet() for p in U.Pads()}
        nets = {role: code[n] for role, n in PIN.items()}
        nets["VOUT"] = b.FindNet(rail)

        def place_parts(fr):
            for role, ref in roles(u).items():
                f = b.FindFootprintByReference(ref)
                if not f.IsFlipped():
                    f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                lib, name, p1, p2 = PARTS[role]
                assert str(f.GetFPID().GetLibItemName()) == name, (ref, name)
                a_net = nets[PADNETS[role][0]].GetNetname()
                pads = {p.GetNumber(): p.GetNetname() for p in f.Pads() if p.GetNumber()}
                assert set(pads.values()) == {a_net, nets[PADNETS[role][1]].GetNetname()}, (ref, pads)
                place2(f, fr, *((p1, p2) if pads["1"] == a_net else (p2, p1)))

        def box(fr):
            cs = [fr((BBOX[i], BBOX[j])) for i in (0, 2) for j in (1, 3)]
            return min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs)

        best = None
        homes = [home, home0] if SHIFT_HOME else [home]
        grid = {(dx * 0.05, dy * 0.05) for dx in range(-12, 13) for dy in range(-12, 13)}      # fine near home, then coarse
        grid |= {(dx * 0.25, dy * 0.25) for dx in range(-12, 13) for dy in range(-12, 13)}
        offs = sorted(((h, dx, dy) for h in range(len(homes)) for dx, dy in grid), key=lambda o: (math.hypot(o[1], o[2]), o[0]))
        for need, (hi, dx, dy) in ((n, o) for n in (5, 4, 3) for o in offs):     # legal output vias wanted
            if best:
                break
            home = homes[hi]
            U.SetPosition(pcbnew.VECTOR2I(home.x + FM(dx), home.y + FM(dy)))
            fr = Frame(U); bx = box(fr)
            if any(bx[0] < t[2] and bx[2] > t[0] and bx[1] < t[3] and bx[3] > t[1] for t in taken):
                continue
            if obst.box_hits(*bx):                           # something in the box: look at the copper itself
                place_parts(fr)
                if copper_hits(obst, cell_shapes(b, fr, [u] + list(roles(u).values()), nets), bx):
                    continue
            vout = [fr(q) for role, q, *_ in VIAS if role == "VOUT"]
            if rail != "0V85" and not all(pz.HitTestFilledArea(pl, pcbnew.VECTOR2I(FM(x), FM(y))) for x, y in vout):
                continue
            if sum(obst.via_ok(v, 0.45, 0.25, nets["VOUT"].GetNetCode()) for v in vout) < need:
                continue
            if not nets["PG"].GetNetname().startswith("unconnected-") and not all(obst.via_ok(fr(q), dia, drill, nets[role].GetNetCode()) for role, q, dia, drill in VIAS if role == "PG"):
                continue                                     # the PG via has no other site
            best = (dx + MM(home.x - home0.x), dy + MM(home.y - home0.y)); spot = pcbnew.VECTOR2I(home.x + FM(dx), home.y + FM(dy))
        if best is None:
            U.SetPosition(home0)
            fr = Frame(U); nn = {n.GetNetCode(): n.GetNetname() for n in b.GetNetInfo().NetsByName().values()}
            import collections
            place_parts(fr)
            hits = collections.Counter((k, nn.get(n, "?")) for k, n in copper_hits(obst, cell_shapes(b, fr, [u] + list(roles(u).values()), nets), box(fr)))
            print(f"  {u}: no free spot within 3 mm; left as it was, NOT rebuilt. In the box at home: {dict(hits)}"); continue
        U.SetPosition(spot)
        fr = Frame(U); taken.append(box(fr))
        place_parts(fr)
        # vias: legal sites only
        skipped = []
        saved = list(VIAS)
        use = []
        gnd_area = AREAS[2][1]
        for role, q, dia, drill in saved:
            if role == "PG" and nets["PG"].GetNetname().startswith("unconnected-"):
                continue                                     # PG not used on this cell: no via
            n = nets[role].GetNetCode()
            cands = [q]
            if role == "VOUT":
                cands += [(q[0] + s * k * 0.05, q[1]) for k in range(1, 8) for s in (1, -1)]
            elif role == "GND" and dia > 0.3:
                cands += [(q[0] + r * math.cos(a * math.pi / 6), q[1] + r * math.sin(a * math.pi / 6))
                          for r in (0.15, 0.3, 0.45, 0.6) for a in range(12)]
                cands = [c for c in cands if all(_in_poly((c[0] + ox, c[1] + oy), gnd_area) for ox in (-0.25, 0.25) for oy in (-0.25, 0.25))]
            for c in cands:
                g = fr(c)
                if not obst.via_ok(g, dia, drill, n):
                    continue
                if any(r2 == role and math.hypot(c[0] - c2[0], c[1] - c2[1]) < d2 / 2 + dia / 2 + 0.2 for r2, c2, d2, _ in use):
                    continue
                if role in ("VOUT", "FB", "PG") and False:
                    continue
                use.append((role, c, dia, drill)); break
            else:
                skipped.append(f"{role} via at ({q[0]:.2f}, {q[1]:.2f})")
        VIAS[:] = use
        made = copper(b, fr, pcbnew.B_Cu, nets)
        VIAS[:] = saved
        for m in made:
            if not isinstance(m, pcbnew.ZONE):
                obst.add_track(m)
        ties = 0                                             # rail pads just beyond the output edge: straight onto the bus
        for f in b.GetFootprints():
            if f.GetReference() in members:
                continue
            for p in f.Pads():
                if p.GetNetCode() != nets["VOUT"].GetNetCode() or not p.IsOnLayer(pcbnew.B_Cu):
                    continue
                g = (MM(p.GetPosition().x) - fr.o[0], MM(p.GetPosition().y) - fr.o[1])
                lx, ly = g[0] * fr.ex[0] + g[1] * fr.ex[1], g[0] * fr.ey[0] + g[1] * fr.ey[1]
                if -2.0 < lx < 3.6 and -6.4 < ly < -5.15:
                    t = pcbnew.PCB_TRACK(b)
                    t.SetStart(fr.v((lx, -4.85))); t.SetEnd(p.GetPosition()); t.SetWidth(FM(0.3)); t.SetLayer(pcbnew.B_Cu)
                    t.SetNet(nets["VOUT"]); b.Add(t); obst.add_track(t); ties += 1
        on_plane = sum(pz.HitTestFilledArea(pl, fr.v(c)) for role, c, *_ in use if role == "VOUT")
        nv = sum(role == "VOUT" for role, *_ in use)
        print(f"  {u} {rail}: output edge {face}, moved ({best[0]:+.2f}, {best[1]:+.2f}) mm, {nv} output vias ({on_plane} on the "
              f"{plane} region as filled now), {sum(r == 'GND' for r, *_ in use)} ground vias" + (f", {ties} rail pads at the output edge tied to the bus" if ties else "") + (f"; left out: {', '.join(skipped)}" if skipped else ""))
        if rail == "0V85":                                   # widen the In4 region over the output vias
            pts = [fr(c) for role, c, *_ in use if role == "VOUT"]
            x0, x1 = min(p[0] for p in pts) - 0.8, max(p[0] for p in pts) + 0.8
            y0, y1 = min(p[1] for p in pts) - 0.8, max(p[1] for p in pts) + 0.8
            o = pz.Outline(); moved = 0
            for i in range(o.TotalVertices()):
                v = o.CVertex(i); x, y = MM(v.x), MM(v.y)
                if abs(y - 98.49) < 0.01 and y > y0:          # the top edge of the box over the buck
                    o.SetVertex(i, pcbnew.VECTOR2I(v.x, FM(y0))); moved += 1
            other = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == "1V8"
                     and 151.53 < MM(t.GetPosition().x) < 160.83 and y0 < MM(t.GetPosition().y) < 98.49]
            print(f"    0V85 In4 region: top edge of the box 98.49 -> {y0:.2f} mm ({moved} corners); 1V8 vias inside the new strip: {len(other)}")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(out, b)
    print("buck_cell:", ", ".join(c[0] for c in CELLS), "->", out)


def demo(out, dump=None):
    libs = os.path.join(os.environ["KICAD_MOUNT"], "share", "kicad", "footprints")
    b = pcbnew.CreateEmptyBoard()
    ds = b.GetDesignSettings()
    ds.m_MinClearance = FM(0.09); ds.m_TrackMinWidth = FM(0.09); ds.m_HoleClearance = FM(0.175)
    ds.m_ViasMinSize = FM(0.25); ds.m_MinThroughDrill = FM(0.15); ds.m_CopperEdgeClearance = FM(0.2)
    ds.m_ViasMinAnnularWidth = FM(0.05); ds.m_HoleToHoleMin = FM(0.2)
    nets = {}
    for role in ("GND", "VIN", "SW", "VOUT", "FB", "EN", "PG"):
        n = pcbnew.NETINFO_ITEM(b, role); b.Add(n); nets[role] = n
    cx, cy = 100.0, 100.0
    u = pcbnew.FootprintLoad(os.path.join(libs, "Package_TO_SOT_SMD.pretty"), "SOT-563")
    u.SetReference("U1"); u.SetValue("AP6120x"); b.Add(u)
    u.SetPosition(pcbnew.VECTOR2I(FM(cx), FM(cy)))
    u.Flip(u.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)            # on B.Cu, as on the card
    for role, p in PIN.items():
        next(q for q in u.Pads() if q.GetNumber() == p).SetNet(nets[role])
    fr = Frame(u)
    for role, (lib, name, p1, p2) in PARTS.items():
        f = pcbnew.FootprintLoad(os.path.join(PROJ_LIB if lib == "ti135_card" else libs, lib + ".pretty"), name)
        f.SetReference(role); f.SetValue(role); b.Add(f)
        f.SetPosition(u.GetPosition()); f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        place2(f, fr, p1, p2)
        for q in f.Pads():
            if q.GetNumber() in ("1", "2"):
                q.SetNet(nets[PADNETS[role][int(q.GetNumber()) - 1]])
    copper(b, fr, pcbnew.B_Cu, nets)
    x0, y0, x1, y1 = cx - 6, cy - 7, cx + 6, cy + 7
    for a, c in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(pcbnew.VECTOR2I(FM(a[0]), FM(a[1]))); s.SetEnd(pcbnew.VECTOR2I(FM(c[0]), FM(c[1]))); s.SetWidth(FM(0.05))
        b.Add(s)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(out, b)
    if dump:
        g = {"pads": [], "crt": [], "zones": [], "tracks": [], "vias": [], "origin": fr.o, "ex": fr.ex, "ey": fr.ey}
        for f in b.GetFootprints():
            c = f.GetCourtyard(pcbnew.B_CrtYd).BBox()
            g["crt"].append([f.GetReference(), MM(c.GetLeft()), MM(c.GetTop()), MM(c.GetRight()), MM(c.GetBottom())])
            for q in f.Pads():
                if q.GetNumber():
                    bb = q.GetBoundingBox()
                    g["pads"].append([f.GetReference(), q.GetNumber(), q.GetNetname(), MM(bb.GetLeft()), MM(bb.GetTop()),
                                      MM(bb.GetRight()), MM(bb.GetBottom())])
        for z in b.Zones():
            polys = z.GetFilledPolysList(pcbnew.B_Cu)
            for i in range(polys.OutlineCount()):
                o = polys.Outline(i)
                g["zones"].append([z.GetNetname(), [(MM(o.CPoint(k).x), MM(o.CPoint(k).y)) for k in range(o.PointCount())]])
        for t in b.GetTracks():
            if isinstance(t, pcbnew.PCB_VIA):
                g["vias"].append([t.GetNetname(), MM(t.GetPosition().x), MM(t.GetPosition().y), MM(t.GetWidth(pcbnew.B_Cu)), MM(t.GetDrill())])
            else:
                g["tracks"].append([t.GetNetname(), MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth())])
        json.dump(g, open(dump, "w"))
    print("buck_cell demo:", out, "cell %.2f x %.2f mm" % (BBOX[2] - BBOX[0], BBOX[3] - BBOX[1]))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--demo":
        demo(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif len(sys.argv) == 4 and sys.argv[1] == "--strip":      # its own run: pcbnew objects go stale after Remove
        bd = pcbnew.LoadBoard(sys.argv[2]); strip_old(bd, CELLS); pcbnew.SaveBoard(sys.argv[3], bd)
    elif len(sys.argv) == 3:
        apply(sys.argv[1], sys.argv[2])
    else:
        sys.exit(__doc__)
