#!/usr/bin/env python3
"""3V3 feeds as pours on In4 instead of tracks on the signal layers (user request 2026-11-15):
    tools/p2k/bin/kipy tools/v33_in4_pours.py IN.kicad_pcb OUT.kicad_pcb

In4 is the 1V8 plane with the 0V85 region. Three 3V3 regions are cut into it (priority above both), each stitched
to the 3V3 region of In3 by vias where the two overlap:
  W  translators U1204 / U1202 (they sit over In3's 1V1 region), down to In3's 3V3 at y > 71.5
  M  U501 ball M21 and its capacitors, from In3's 3V3 edge at x 154.9
  S  U501 balls G7 / J7: a finger east of the 0V85 neck, from In3's 3V3 at y > 108.1 up to the balls
The shapes keep clear of every 1V8 via (a 1V8 via inside a 3V3 region would lose its plane).
Then every 3V3 track on F / In2 / In5 / B in those areas that the board no longer needs is removed: longest
first, kept only if removing it opens a connection. Run on a copy that has its project files beside it.
"""
import math
import sys

import pcbnew

SRC, DST = sys.argv[1:3]
b = pcbnew.LoadBoard(SRC)
MM = pcbnew.FromMM
NET = b.FindNet("3V3")
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))

REGIONS = {
    "W": [(145.6, 59.0), (150.5, 59.0), (150.5, 75.2), (148.1, 75.2), (148.1, 69.6), (145.6, 69.6), (145.6, 67.3),
          (146.9, 67.3), (146.9, 61.5), (145.6, 61.5)],
    "M": [(153.05, 78.9), (157.0, 78.9), (157.0, 81.9), (153.05, 81.9)],
    "S": [(164.25, 84.2), (168.0, 84.2), (168.0, 85.0), (166.5, 85.0), (166.5, 90.5), (165.6, 90.5), (165.6, 91.9),
          (166.5, 91.9), (166.5, 109.6), (164.25, 109.6)],
}
# where tracks may be removed: (x0, y0, x1, y1, layer); the PHY, eMMC, flash and regulator 3V3 tracks stay
PRUNE = [(137.0, 56.0, 160.0, 90.0, None), (152.0, 82.0, 168.5, 97.5, "In5.Cu")]  # last: only this layer
# new vias: stitches to In3's 3V3 (searched near these points) and one for U1203 / C1208, which had only the track
STITCH = {"W": [(149.2, 74.6), (148.7, 73.9), (149.9, 72.6)], "S": [(164.7, 108.9), (165.4, 108.9), (166.1, 108.9)]}

tpl = next(z for z in b.Zones() if z.GetNetname() == "0V85" and z.IsOnLayer(pcbnew.In4_Cu))
zones3 = {}
for name, pts in REGIONS.items():
    z = pcbnew.ZONE(b)
    z.SetLayer(pcbnew.In4_Cu); z.SetNet(NET); z.SetAssignedPriority(2); z.SetZoneName("plane:3V3_" + name)
    z.SetLocalClearance(tpl.GetLocalClearance()); z.SetMinThickness(tpl.GetMinThickness())
    z.SetPadConnection(tpl.GetPadConnection()); z.SetThermalReliefGap(tpl.GetThermalReliefGap())
    z.SetThermalReliefSpokeWidth(tpl.GetThermalReliefSpokeWidth())
    z.SetIslandRemovalMode(tpl.GetIslandRemovalMode()); z.SetMinIslandArea(tpl.GetMinIslandArea())
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(MM(x), MM(y))
    b.Add(z); zones3[name] = z


def seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def via_free(x, y, r=0.15, hole=0.075):
    """True if a 0.3 / 0.15 through via at (x, y) clears all foreign copper by 0.1 and holes by the project rules."""
    px, py = MM(x), MM(y)
    for t in b.GetTracks():
        same = t.GetNetCode() == NET.GetNetCode()
        if t.Type() == pcbnew.PCB_VIA_T:
            d = math.hypot(t.GetPosition().x - px, t.GetPosition().y - py)
            if d < MM(0.45) + t.GetWidth(pcbnew.F_Cu) / 2 - MM(0.15):
                return False
        elif not same:
            s, e = t.GetStart(), t.GetEnd()
            if seg_d(px, py, s.x, s.y, e.x, e.y) < MM(r + 0.11) + t.GetWidth() / 2:
                return False
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            dx = max(bb.GetLeft() - px, 0, px - bb.GetRight()); dy = max(bb.GetTop() - py, 0, py - bb.GetBottom())
            lim = MM(r + 0.11) if p.GetNetCode() != NET.GetNetCode() else MM(0.0)
            if p.GetNetCode() != NET.GetNetCode() and math.hypot(dx, dy) < max(lim, MM(hole + 0.18)):
                return False
            if p.GetNetCode() == NET.GetNetCode() and math.hypot(dx, dy) < MM(0.0) and f.GetReference() != "U501":
                pass
    return True


def near_free(x, y, ok, rmax=1.2):
    best = None
    for i in range(-24, 25):
        for j in range(-24, 25):
            cx, cy = x + i * 0.05, y + j * 0.05
            d = math.hypot(i, j) * 0.05
            if d <= rmax and (best is None or d < best[0]) and ok(cx, cy) and via_free(cx, cy):
                best = (d, round(cx, 3), round(cy, 3))
    return best


def add_via(x, y):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(pcbnew.F_Cu, MM(0.3)); v.SetDrill(MM(0.15))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(NET); b.Add(v); return v


def add_track(x1, y1, x2, y2, layer, w=0.2):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetLayer(layer); t.SetWidth(MM(w))
    t.SetNet(NET); b.Add(t); return t


in3 = next(z for z in b.Zones() if z.GetNetname() == "3V3" and z.IsOnLayer(pcbnew.In3_Cu))
for name, wants in STITCH.items():
    zo = zones3[name].Outline()
    for x, y in wants:
        ok = lambda cx, cy: (zo.Contains(P(cx, cy), -1, MM(-0.35)) if False else zo.Contains(P(cx, cy))) and \
            in3.HitTestFilledArea(pcbnew.In3_Cu, P(cx, cy)) and \
            all(in3.HitTestFilledArea(pcbnew.In3_Cu, P(cx + ax, cy + ay)) and zo.Contains(P(cx + ax, cy + ay))
                for ax, ay in ((0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3)))
        got = near_free(x, y, ok)
        if got:
            add_via(got[1], got[2]); print(f"stitch via {name} at ({got[1]}, {got[2]})")
        else:
            print(f"no room for stitch via {name} near ({x}, {y})")

# U1203 pin 23 / 24 and C1208: a via beside C1208 pad 1 into In3's 3V3
c = b.FindFootprintByReference("C1208").FindPadByNumber("1").GetPosition()
cx, cy = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
got = near_free(cx, cy, lambda x, y: in3.HitTestFilledArea(pcbnew.In3_Cu, P(x, y)) and math.hypot(x - cx, y - cy) > 0.45, 1.0)
if got:
    add_via(got[1], got[2]); add_track(cx, cy, got[1], got[2], pcbnew.F_Cu, 0.3)
    print(f"C1208 via at ({got[1]}, {got[2]})")
else:
    print("no room for a via at C1208")


def refill():
    zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)


def opens():
    b.BuildConnectivity()
    return b.GetConnectivity().GetUnconnectedCount(False)


refill()
base = opens()
had_track = lambda pt: any(o.Type() != pcbnew.PCB_VIA_T and o.GetNetCode() == NET.GetNetCode() and
                           seg_d(pt.x, pt.y, o.GetStart().x, o.GetStart().y, o.GetEnd().x, o.GetEnd().y) <= o.GetWidth() // 2 + MM(0.15)
                           for o in b.GetTracks())
tracked = {v.m_Uuid.AsString() for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T and v.GetNetCode() == NET.GetNetCode()
           and had_track(v.GetPosition())}
print("open connections with the pours and all tracks in place:", base)
inbox = lambda p, lay=None: any(x0 <= pcbnew.ToMM(p.x) <= x1 and y0 <= pcbnew.ToMM(p.y) <= y1 and (only is None or lay is None or b.GetLayerName(lay) == only)
                                for x0, y0, x1, y1, only in PRUNE)
SIG = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In5_Cu, pcbnew.B_Cu)
PARK = pcbnew.User_9
total = 0
while True:  # repeated: a dead-end run comes off one segment per pass, from its free end
    cand = [t for t in b.GetTracks() if t.GetNetCode() == NET.GetNetCode() and t.Type() != pcbnew.PCB_VIA_T
            and t.GetLayer() in SIG and inbox(t.GetStart(), t.GetLayer()) and inbox(t.GetEnd(), t.GetLayer())]
    cand.sort(key=lambda t: -t.GetLength())
    removed = 0
    for t in cand:  # parked on a user layer the segment is itself one open item; two or more means it was needed
        lay = t.GetLayer(); t.SetLayer(PARK)
        if opens() > base + 1:
            t.SetLayer(lay)
        else:
            b.Delete(t); removed += 1
    total += removed
    if not removed:
        break
print(f"removed {total} segments, {len(cand)} kept in the pruning areas")

# the diagonal across U1203 pins 23 / 24 used to continue north-west; end it in pin 23
for t in b.GetTracks():
    if t.GetNetCode() == NET.GetNetCode() and t.Type() != pcbnew.PCB_VIA_T and t.GetLayer() == pcbnew.F_Cu:
        for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
            if abs(get().x - MM(145.35)) < 2000 and abs(get().y - MM(83.85)) < 2000:
                put(P(145.744, 84.244)); print("U1203 stub trimmed to pin 23")

# vias that no track or pad uses any more and that do not stitch a pour to In3
for v in [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == NET.GetNetCode() and inbox(t.GetPosition())]:
    pt = v.GetPosition()
    if v.m_Uuid.AsString() not in tracked:
        continue
    used = had_track(pt) or any(p.GetNetCode() == NET.GetNetCode() and p.HitTest(pt) for f in b.GetFootprints() for p in f.Pads())
    stitch = any(z.Outline().Contains(pt) for z in zones3.values()) and in3.HitTestFilledArea(pcbnew.In3_Cu, pt)
    if not used and not stitch:
        x, y = pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y); b.Delete(v)
        if opens() > base:
            add_via(x, y)
        else:
            print("unused via removed at (%.3f, %.3f)" % (x, y))
refill()
print("open connections at the end:", opens())
left = {}
for t in b.GetTracks():
    if t.GetNetCode() == NET.GetNetCode() and t.Type() != pcbnew.PCB_VIA_T:
        left[b.GetLayerName(t.GetLayer())] = left.get(b.GetLayerName(t.GetLayer()), 0) + pcbnew.ToMM(t.GetLength())
print("3V3 track left, mm:", {k: round(v, 1) for k, v in left.items()})
b.Save(DST)
