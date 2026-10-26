#!/usr/bin/env python3
"""Analog section placed as on the Agilex card, and the J3 pull-down arrays on B.Cu beside J3 (kipy; IN OUT).

1. The ADC chain (13_adc) and the 3V3_analog LDO copy the Agilex card's layout: the SN74LV4051A mux, OPA365 buffer,
   33 R + 680 p kickback filter, ADS7056 and NCP163 LDO sit just below its J3 baseboard socket, where the isoada
   inputs (J3 pins 1, 3, 4) arrive. Their positions and rotations relative to J3 are taken from
   ~/dev/agilex3_soc_control_card/agilex_3_soc.kicad_pcb (read 2026-10-26; that repository is not modified). Both
   J3s have the same orientation, so the offsets carry over, shifted SHIFT mm east to clear J1 (JTAG).
2. Parts the Agilex card does not have (rail-monitor resistors, SPI series resistors, the extra 1 u caps) go to the
   nearest free spot by the pin they serve.
3. The 8 J3 pull-down arrays (RN1401-RN1408) go to B.Cu in a column beside J3, each level with the J3 pins it pulls
   down, signal pads towards J3, as on the Agilex card (RN1-RN7).
"""
import math
import sys

import pcbnew

mm, FM = pcbnew.ToMM, pcbnew.FromMM
SHIFT = (1.0, 0.0)  # +1.0 mm x: C1305 clears J1 (JTAG), U1301 clears the U1201 translator
# Agilex card (J3 at 127.592, 106.604, rot 0, B.Cu): ref -> (ours, x, y, rot)
AGILEX_J3 = (127.592, 106.604)
COPY = {
    "U3": ("U1301", 131.642, 118.834, 0), "U4": ("U1302", 131.592, 123.922, -90),
    "U5": ("U1303", 126.433, 129.949, 90), "R3": ("R1306", 131.652, 126.912, -90),
    "C3": ("C1302", 130.672, 126.942, 90), "C1": ("C1304", 132.717, 129.579, 90),
    "C4": ("C1303", 132.422, 115.597, 180),
    "U6": ("U101", 131.042, 132.934, 0), "C10": ("C104", 130.767, 135.439, 0),
}
# ours only: ref -> (partner ref, partner pad)
NEAR = {
    "C1301": ("U101", "5"), "C1306": ("U1303", "4"),
    "C1305": ("U1302", "5"),  # the Agilex C2 spot is under our J1 (JTAG): decouple the OPA365 instead
    "R1310": ("U1303", "1"), "R1311": ("U1303", "3"), "R1312": ("U1303", "2"),
    "R1301": ("U1301", "14"), "R1302": ("U1301", "15"), "R1303": ("U1301", "12"), "R1304": ("U1301", "5"),
    "R1305": ("R1303", "2"),
}
EAST = {"R1310", "R1311", "R1312"}
ARRAYS = [f"RN14{i:02d}" for i in range(1, 9)]
CLEAR = 0.0  # courtyards may touch, not overlap (KiCad's rule)

b = pcbnew.LoadBoard(sys.argv[1])
fp = {f.GetReference(): f for f in b.GetFootprints()}
j3 = fp["J3"]; jx, jy = mm(j3.GetPosition().x), mm(j3.GetPosition().y)
edge = b.GetBoardEdgesBoundingBox()
ex0, ey0, ex1, ey1 = mm(edge.GetLeft()) + 0.5, mm(edge.GetTop()) + 0.5, mm(edge.GetRight()) - 0.5, mm(edge.GetBottom()) - 0.5


def court(f):
    side = pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd
    bb = f.GetCourtyard(side).BBox()
    if bb.GetWidth() == 0:
        bb = f.GetBoundingBox(False)
    return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())


def place(f, x, y, rot, flipped=None):
    if flipped is not None and f.IsFlipped() != flipped:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    f.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))


def clashes(f, moved):
    """Courtyard overlap with any footprint on the same side (THT parts count on both), or off the board."""
    a = court(f)
    if a[0] < ex0 or a[1] < ey0 or a[2] > ex1 or a[3] > ey1:
        return True
    for o in b.GetFootprints():
        if o.GetReference() == f.GetReference():
            continue
        tht = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in o.Pads())
        if o.IsFlipped() != f.IsFlipped() and not tht:
            continue
        c = court(o)
        if a[0] < c[2] + CLEAR and c[0] < a[2] + CLEAR and a[1] < c[3] + CLEAR and c[1] < a[3] + CLEAR:
            return True
    return False


moved = set()
dx, dy = jx - AGILEX_J3[0] + SHIFT[0], jy - AGILEX_J3[1] + SHIFT[1]
park = 240.0  # park every part to be placed off the board first, so they do not block each other's old spots
for r in [v[0] for v in COPY.values()] + list(NEAR) + ARRAYS:
    f = fp[r]; f.SetPosition(pcbnew.VECTOR2I(FM(park), FM(150))); park += 4
for ag, (r, x, y, rot) in COPY.items():
    place(fp[r], x + dx, y + dy, rot, flipped=False); moved.add(r)
def relax(refs):
    # relax: nudge any part still overlapping (smallest first) to the nearest free spot within 1.5 mm, same rotation
    area = lambda r: (court(fp[r])[2] - court(fp[r])[0]) * (court(fp[r])[3] - court(fp[r])[1])
    for r in sorted([r for r in refs if clashes(fp[r], moved)], key=area):
        f = fp[r]; x0, y0 = mm(f.GetPosition().x), mm(f.GetPosition().y); ok = False
        r0 = f.GetOrientationDegrees()
        rots = (r0, r0 + 90) if len(f.Pads()) == 2 else (r0,)  # a 2-pad part may also turn
        for rad in [i * 0.05 for i in range(1, 31)]:
            for k in range(16):
                a = 2 * math.pi * k / 16
                for ro in rots:
                    f.SetOrientationDegrees(ro)
                    f.SetPosition(pcbnew.VECTOR2I(FM(x0 + rad * math.cos(a)), FM(y0 + rad * math.sin(a))))
                    if not clashes(f, moved):
                        ok = True; break
                if ok: break
            if ok: break
        if not ok:
            f.SetOrientationDegrees(r0); f.SetPosition(pcbnew.VECTOR2I(FM(x0), FM(y0)))
        print(f"  relax {r}: {'moved %.2f mm' % rad if ok else 'still overlapping'}")


relax(list(moved))  # the copied group first, before the extras take the free spots
bad = [r for r in moved if clashes(fp[r], moved)]
print(f"place_analog: {len(COPY)} parts at the Agilex positions (J3 + offset, +{SHIFT[0]} mm x); overlapping after relax: {bad or 'none'}")

for r, (pr, pad) in NEAR.items():
    p = [q for q in fp[pr].Pads() if q.GetNumber() == pad][0]
    tx, ty = mm(p.GetPosition().x), mm(p.GetPosition().y)
    f = fp[r]; done = False
    for rad in [i * 0.25 for i in range(2, 33)]:          # rings outward from the partner pad
        for k in range(max(8, int(rad * 12))):
            a = 2 * math.pi * k / max(8, int(rad * 12))
            if r in EAST and math.cos(a) < 0.2:  # SPI series resistors: on the FPGA (east) side of the ADC
                continue
            for rot in (0, 90):
                place(f, tx + rad * math.cos(a), ty + rad * math.sin(a), rot, flipped=False)
                if not clashes(f, moved):
                    done = True; break
            if done: break
        if done: break
    moved.add(r)
    print(f"  {r:6} by {pr}.{pad}: {'at %.2f mm' % rad if done else 'NO FREE SPOT'}")

# pull-down arrays: B.Cu, a column just outside J3's courtyard, each level with the mean of its J3 pins
jc = court(j3)
place(fp[ARRAYS[0]], 0, 0, 90, flipped=True); half = (court(fp[ARRAYS[0]])[2] - court(fp[ARRAYS[0]])[0]) / 2
col_x = jc[2] + half + 0.05
want = []
for r in ARRAYS:
    f = fp[r]; ys = []; sig = []
    for p in f.Pads():
        jp = [q for q in j3.Pads() if q.GetNetCode() == p.GetNetCode() and p.GetNetname() != "GND"]
        if jp:
            ys.append(mm(jp[0].GetPosition().y)); sig.append(p.GetNumber())
    want.append((sum(ys) / len(ys) if ys else jy, r, sig))
want.sort()
pitch = 2.7; y = None
for ty, r, sig in want:
    y = ty if y is None else max(ty, y + pitch)
    f = fp[r]
    for rot in (90, 270):  # the rotation that puts the J3-side pads nearest J3
        place(f, col_x, y, rot, flipped=True)
        sx = [mm(p.GetPosition().x) for p in f.Pads() if p.GetNumber() in sig]
        ox = [mm(p.GetPosition().x) for p in f.Pads() if p.GetNumber() not in sig]
        if sx and ox and sum(sx) / len(sx) < sum(ox) / len(ox):
            break
    moved.add(r)
relax(list(moved))
over = [r for r in moved if clashes(fp[r], moved)]
print(f"  arrays on B.Cu at x {col_x:.2f}, y {want[0][0]:.1f}..{y:.1f}; overlapping after relax: {over or 'none'}")
pcbnew.SaveBoard(sys.argv[2], b)
