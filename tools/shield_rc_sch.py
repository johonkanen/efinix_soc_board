#!/usr/bin/env python3
"""Ethernet jack shield through an RC to GND (user, 2026-11-17: the jack isolates the card galvanically):
    python3 tools/shield_rc_sch.py      then tools/add_parts.py and tools/shield_rc.py on the board
Sheet 09: J9's CHS pin (10) and its shield tabs (SH) leave GND for the new net eth_shield; C952 1 nF 2 kV X7R 1206
(C9196) and R951 1 M 1206 (C17927, 200 V) in parallel join eth_shield to GND."""
import os
import re
import uuid

p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kicad", "09_ethernet.kicad_sch")
t = open(p).read()
if '"Reference" "C952"' in t:
    raise SystemExit("09_ethernet: shield RC already there")


def span(key):
    m = re.search(key, t, re.M)
    return t.rfind("\n\t(symbol\n", 0, m.start()) + 1, t.index("\n\t)\n", m.start()) + 4


def moved(blk, x, y):
    m = re.search(r"\(at ([-\d.]+) ([-\d.]+)", blk); dx, dy = x - float(m.group(1)), y - float(m.group(2))
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: f"(at {float(m.group(1)) + dx:g} {float(m.group(2)) + dy:g}", blk)
    return re.sub(r'\(uuid "[^"]*"\)', lambda m: f'(uuid "{uuid.uuid4()}")', blk)


def wire(x1, y1, x2, y2):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n'
            f'\t\t\t(type default)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n')


def label(x, y, rot, just):
    return (f'\t(label "eth_shield"\n\t\t(at {x:g} {y:g} {rot})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify {just} bottom)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n')


def part(src, ref, x, y, fields):
    a, e = span(rf'^\t\t\(property "Reference" "{src}"$')
    blk = moved(t[a:e], x, y).replace(f'"{src}"', f'"{ref}"')
    for k, v in fields.items():
        blk, n = re.subn(rf'(\(property "{k}" ")[^"]*(")', rf"\g<1>{v}\g<2>", blk, count=1); assert n == 1, k
    return blk


X1, X2, Y = 327.66, 340.36, 190.5
for a, c in re.findall(r"\(at ([\d.]+) ([\d.]+)", t) + re.findall(r"\(xy ([\d.]+) ([\d.]+)\)", t):
    assert not (X1 - 8 < float(a) < X2 + 8 and Y - 8 < float(c) < Y + 8), ("not free", a, c)
new = part("C950", "C952", X1, Y, {"Value": "1n 2kV", "Footprint": "Capacitor_SMD:C_1206_3216Metric", "LCSC": "C9196"})
new += part("R950", "R951", X2, Y, {"Value": "1M", "Footprint": "Resistor_SMD:R_1206_3216Metric", "LCSC": "C17927"})
a, e = span(r'^\t\t\(lib_id "ti135_card:GND"\)\n\t\t\(at 327\.66 171\.45 0\)')
pw = sorted(set(re.findall(r'"#PWR(\d+)"', t)), key=int)[-1]
old = re.search(r'"(#PWR\d+)"', t[a:e]).group(1)
new += moved(t[a:e], X1, Y + 3.81).replace(old, "#PWR" + str(int(pw) + 1).zfill(len(pw)))
new += wire(X1, Y - 3.81, X2, Y - 3.81) + wire(X1, Y + 3.81, X2, Y + 3.81) + label(X1, Y - 3.81, 0, "left")
# the two GND symbols at J9 (pin 10 CHS at 317.5 / 127, SH at 342.9 / 116.84) become labels
for key, lab in ((r'^\t\t\(lib_id "ti135_card:GND"\)\n\t\t\(at 346\.71 116\.84 90\)', label(346.71, 116.84, 0, "left")),
                 (r'^\t\t\(lib_id "ti135_card:GND"\)\n\t\t\(at 313\.69 127 270\)', label(313.69, 127, 180, "right"))):
    a, e = span(key); t = t[:a] + t[e:]; new += lab
i = t.rindex("\n\t(sheet_instances") if "\n\t(sheet_instances" in t else t.rindex("\n)")
open(p, "w").write(t[:i + 1] + new + t[i + 1:])
print("09_ethernet: J9 CHS / SH on eth_shield; C952 1n 2kV and R951 1M from eth_shield to GND")
