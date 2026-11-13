#!/usr/bin/env python3
"""Three changes from the peripherals review (2026-11-13), sheets edited in place:
    python3 tools/seq_fixes.py

1. U401: TPS3808G01DBVT -> TPS3808G09DBVR (C24584). SENSE sits directly on VCORE; the G01 trips at 0.405 V there
   (43 % of 0.95 V), the G09 has a fixed 0.84 V threshold (88 %). Same SOT-23-6, no other change.
2. R929 (MDIO pull-up): 4k7 -> 1k5 (C25867), the value Realtek asks for (RTL8211F data sheet, MDIO).
3. New C402 100 n from pg_group1 to GND beside R401 (100 k to 5V0): tau 10 ms. The AP6120x data sheet does not say
   what PG does below the start-up voltage; if it floats while 5V0 ramps, pg_group1 would follow 5V0 and enable
   group 2 (0V85, 1V1) before group 1 is up. With the capacitor EN reaches its 0.91 V threshold about 2 ms after
   pg_group1 is released, long after group 1's own PG outputs are valid. Group 2 then starts 2 ms after group 1.
Board: tools/add_parts.py, tools/place_free.py C402@..., a track to R401, a GND via.
"""
import os
import re
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def set_fields(t, ref, fields):
    m = re.search(rf'^\t\t\(property "Reference" "{re.escape(ref)}"$', t, re.M)
    a = t.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = t.index("\n\t)\n", m.start()) + 4
    blk = t[a:e]
    for k, v in fields.items():
        blk, n = re.subn(rf'(\(property "{k}" ")[^"]*(")', rf"\g<1>{v}\g<2>", blk, count=1)
        assert n == 1, (ref, k)
    return t[:a] + blk + t[e:]


def block(t, ref):
    m = re.search(rf'^\t\t\(property "Reference" "{re.escape(ref)}"$', t, re.M)
    a = t.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = t.index("\n\t)\n", m.start()) + 4
    return t[a:e], e


def clone(blk, old, new, dx, dy):
    def at(m):
        return f"(at {float(m.group(1)) + dx:g} {float(m.group(2)) + dy:g}"
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", at, blk)
    blk = re.sub(r'\(uuid "[^"]*"\)', lambda m: f'(uuid "{uuid.uuid4()}")', blk)
    return blk.replace(f'"{old}"', f'"{new}"')


def wire(x1, y1, x2, y2):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n'
            f'\t\t\t(type default)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n')


p = os.path.join(ROOT, "kicad", "04_pwr_seq.kicad_sch"); t = open(p).read()
t = set_fields(t, "U401", {"Value": "TPS3808G09DBVR", "LCSC": "C24584"})
t = t.replace("U401 TPS3808 (VCORE good + 20 ms)", "U401 TPS3808G09 (VCORE above 0.84 V + 20 ms)")
if '"Reference" "C402"' not in t:
    DX, DY = 66.04 - 190.5, 67.31 - 63.5
    c, _ = block(t, "C401"); g, end = block(t, "#PWR04006")
    new = clone(c, "C401", "C402", DX, DY) + clone(g, "#PWR04006", "#PWR04007", DX, DY)
    new += wire(55.88, 63.5, 66.04, 63.5) + wire(66.04, 71.12, 66.04, 73.66)
    new += f'\t(junction\n\t\t(at 55.88 63.5)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n'
    t = t[:end] + new + t[end:]
    print("04_pwr_seq: C402 100n added on pg_group1")
open(p, "w").write(t)
print("04_pwr_seq: U401 -> TPS3808G09DBVR C24584")
p = os.path.join(ROOT, "kicad", "09_ethernet.kicad_sch"); t = open(p).read()
t = set_fields(t, "R929", {"Value": "1k5", "LCSC": "C25867"})
open(p, "w").write(t)
print("09_ethernet: R929 -> 1k5 C25867")
