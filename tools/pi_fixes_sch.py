#!/usr/bin/env python3
"""Schematic part of the power-integrity fixes of 2026-11-15, sheet 05:
- S6: two more 3V3 capacitors for U501 balls G7 / J7, C5074 4u7 and C5075 1u (0201), beside C5052 in the 3V3 row;
- PLL filters as on the Agilex card (0201, 1 u on the ball, 4.7 u beside it; user request): the 0402 filter
  capacitors at the ferrites become 0201 so that they fit at the balls. C501 / C503 / C505 / C507 stay 1 u,
  C502 / C504 / C506 change from 100 n to 4u7. C508 (100 n 0402 at FB504) stays: no room for it at ball W11.
Then, for the board (source tools/p2k/bin/kicad_env.sh first):
    python3 tools/pi_fixes_sch.py
    tools/p2k/bin/kipy tools/swap_footprint.py BOARD Capacitor_SMD:C_0201_0603Metric C501 C502 C503 C504 C505 C506 C507
    tools/p2k/bin/kipy tools/add_parts.py BOARD BOARD        (stages C5074 / C5075, updates values and fields)
    tools/p2k/bin/kipy tools/pi_fixes.py BOARD BOARD         (places everything)
"""
import os
import re
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "kicad", "05_fpga_power.kicad_sch"); t = open(p).read()


def block(ref):
    m = re.search(rf'^\t\t\(property "Reference" "{re.escape(ref)}"$', t, re.M)
    a = t.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = t.index("\n\t)\n", m.start()) + 4
    return t[a:e], e


def clone(blk, old, new, dx):
    blk = re.sub(r"\(at ([-\d.]+) ", lambda m: f"(at {float(m.group(1)) + dx:g} ", blk)
    blk = re.sub(r'\(uuid "[^"]*"\)', lambda m: f'(uuid "{uuid.uuid4()}")', blk)
    return blk.replace(f'"{old}"', f'"{new}"')


def wire(x1, y1, x2, y2):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n'
            f'\t\t\t(type default)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n')


def junction(x, y):
    return f'\t(junction\n\t\t(at {x:g} {y:g})\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n'


def set_fields(ref, fields):
    global t
    blk, e = block(ref); a = e - len(blk); new = blk
    for k, v in fields.items():
        new, n = re.subn(rf'(\(property "{k}" ")[^"]*(")', rf"\g<1>{v}\g<2>", new, count=1)
        assert n == 1, (ref, k)
    t = t[:a] + new + t[e:]


F0201 = "Capacitor_SMD:C_0201_0603Metric"
for ref in ("C501", "C503", "C505", "C507"):
    set_fields(ref, {"Footprint": F0201, "LCSC": "C272877"})
for ref in ("C502", "C504", "C506"):
    set_fields(ref, {"Value": "4u7", "Footprint": F0201, "LCSC": "C47117441"})
print("05_fpga_power: C501 / C503 / C505 / C507 1u 0201, C502 / C504 / C506 4u7 0201")
# 2026-11-16: the 0201s left over on the old PLL feeds, 6.5-9.3 mm from their balls on long stubs, are not fitted
for ref in ("C5061", "C5062", "C5063", "C5073"):
    if f'"Reference" "{ref}"' not in t:      # C5061-C5063 were later deleted from the design by the user
        continue
    blk, e = block(ref); a = e - len(blk)
    new, n = re.subn(r"\(dnp (yes|no)\)", "(dnp yes)", blk, count=1); assert n == 1, ref
    t = t[:a] + new + t[e:]
print("05_fpga_power: C5061 / C5062 / C5063 / C5073 DNP")
# 2026-11-16: the PLL ferrites as on the Agilex card (0201, MPZ0603S121HT000) so that they fit under U501
for ref in ("FB501", "FB502", "FB503", "FB504"):
    set_fields(ref, {"Value": "MPZ0603S121HT000", "Footprint": "Inductor_SMD:L_0201_0603Metric", "LCSC": "C695597"})
print("05_fpga_power: FB501-FB504 MPZ0603S121HT000 0201")
if '"Reference" "C5074"' in t:
    print("05_fpga_power: C5074 / C5075 already there"); open(p, "w").write(t)
else:
    X0, PITCH, TOP, BOT = 295.91, 8.89, 278.13, 290.83   # C5052's column, row pitch, 3V3 and GND rails of the row
    c47, _ = block("C5049"); c1, end = block("C5052")
    new = clone(c47, "C5049", "C5074", X0 + PITCH - 269.24) + clone(c1, "C5052", "C5075", 2 * PITCH)
    for i in (1, 2):
        x = X0 + i * PITCH
        new += wire(x - PITCH, TOP, x, TOP) + wire(x - PITCH, BOT, x, BOT) + wire(x, TOP + 2.54, x, TOP) + wire(x, BOT - 2.54, x, BOT)
        new += junction(x - PITCH, TOP) + junction(x - PITCH, BOT)
    t = t[:end] + new + t[end:]
    open(p, "w").write(t)
    print("05_fpga_power: C5074 4u7 and C5075 1u added on 3V3")
