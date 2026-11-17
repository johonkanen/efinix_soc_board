#!/usr/bin/env python3
"""Schematic side of the fixes from the manufacturability check of 2026-11-17 (reports/mfg_check/):
    python3 tools/mfg_fixes_sch.py           then  python3 tools/io_swap.py   (sheet 11 and the pin plan)
- sheet 08: R804, 10k 0201 from ddr_rst_n to GND (the net had only U501 AA12 and U801 T11; Efinix's Ti375 board
  has a pull-down there, and the pin's state during configuration is not documented);
- sheet 12: U1204 pin 5 (A3, an input with DIR1 high) tied to GND instead of a no-connect flag;
- sheet 14: lcd_mosi and lcd_miso exchanged at J5. Counted from the 3V3 end the MSP2807 / ILI9341 module has
  SDI (MOSI) 6th and SDO (MISO) 9th; the header had them the other way round. The copper stays: balls H6 and L8
  exchange their signals (tools/io_swap.py MOVES), so the two nets only exchange names.
Each step is skipped when already done."""
import os
import re
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sheet(name):
    p = os.path.join(ROOT, "kicad", name); return p, open(p).read()


def block(t, key):
    m = re.search(key, t, re.M)
    a = t.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = t.index("\n\t)\n", m.start()) + 4
    return t[a:e]


def moved(blk, dx, dy):
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: f"(at {float(m.group(1)) + dx:g} {float(m.group(2)) + dy:g}", blk)
    return re.sub(r'\(uuid "[^"]*"\)', lambda m: f'(uuid "{uuid.uuid4()}")', blk)


def wire(x1, y1, x2, y2):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n'
            f'\t\t\t(type default)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n')


def label(name, x, y):
    return (f'\t(label "{name}"\n\t\t(at {x:g} {y:g} 180)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify right bottom)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n')


def gnd(t, x, y, rot=270):
    """a copy of one of the sheet's GND symbols with this rotation, moved to (x, y), with the next free #PWR number"""
    m = re.search(rf'^\t\t\(lib_id "ti135_card:GND"\)\n\t\t\(at ([-\d.]+) ([-\d.]+) {rot}\)', t, re.M) or \
        re.search(r'^\t\t\(lib_id "ti135_card:GND"\)\n\t\t\(at ([-\d.]+) ([-\d.]+) \d+\)', t, re.M)
    blk = block(t, re.escape(m.group(0))); dx, dy = x - float(m.group(1)), y - float(m.group(2))
    old = re.search(r'"(#PWR\d+)"', blk).group(1)
    pw = sorted(set(re.findall(r'"#PWR(\d+)"', t)), key=int)[-1]
    return moved(blk, dx, dy).replace(old, "#PWR" + str(int(pw) + 1).zfill(len(pw)))


def append(t, new):
    i = t.rindex("\n\t(sheet_instances") if "\n\t(sheet_instances" in t else t.rindex("\n)")
    return t[:i + 1] + new + t[i + 1:]


# ---- sheet 08: R804 ------------------------------------------------------------------------------------------
p, t = sheet("08_lpddr4.kicad_sch")
if '"Reference" "R804"' in t:
    print("08_lpddr4: R804 already there")
else:
    DY = 10.16                                             # below R802 (406.4, 101.6), pins at x 402.59 / 410.21
    r = moved(block(t, r'^\t\t\(property "Reference" "R802"$'), 0, DY).replace('"R802"', '"R804"')
    for k, v in (("Value", "10k 1%"), ("Footprint", "Resistor_SMD:R_0201_0603Metric"), ("LCSC", "C106225")):
        r, n = re.subn(rf'(\(property "{k}" ")[^"]*(")', rf"\g<1>{v}\g<2>", r, count=1); assert n == 1, k
    g = gnd(t, 412.75, 101.6 + DY)
    t = append(t, r + g + wire(410.21, 101.6 + DY, 412.75, 101.6 + DY) + label("ddr_rst_n", 402.59, 101.6 + DY))
    open(p, "w").write(t); print("08_lpddr4: R804 10k from ddr_rst_n to GND added")

# ---- sheet 12: U1204 pin 5 to GND ----------------------------------------------------------------------------
p, t = sheet("12_level_shift.kicad_sch")
nc = re.search(r'\t\(no_connect\n\t\t\(at 243\.84 137\.16\)\n\t\t\(uuid "[^"]*"\)\n\t\)\n', t)
if not nc:
    print("12_level_shift: U1204 pin 5 already tied")
else:
    g = gnd(t, 238.76, 137.16)
    t = t[:nc.start()] + t[nc.end():]
    t = append(t, g + wire(243.84, 137.16, 238.76, 137.16))
    open(p, "w").write(t); print("12_level_shift: U1204 pin 5 (A3) tied to GND")

# ---- sheet 14: lcd_mosi <-> lcd_miso at J5 -------------------------------------------------------------------
p, t = sheet("14_connectors.kicad_sch")
MARK = "lcd_mosi / lcd_miso exchanged at J5 2026-11-17"
if MARK in t:
    print("14_connectors: lcd_mosi / lcd_miso already exchanged")
else:
    lab = {n: re.search(rf'\t\(hierarchical_label "{n}"\n\t\t\(shape (\w+)\)', t) for n in ("lcd_mosi", "lcd_miso")}
    sh = {n: m.group(1) for n, m in lab.items()}
    for n, o in sorted((("lcd_mosi", "lcd_miso"), ("lcd_miso", "lcd_mosi")), key=lambda q: -lab[q[0]].start()):
        m = lab[n]; t = t[:m.start()] + f'\t(hierarchical_label "{o}"\n\t\t(shape {sh[o]})' + t[m.end():]
    note = (f'\t(text "{MARK}"\n\t\t(exclude_from_sim no)\n\t\t(at 20 285 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n')
    open(p, "w").write(append(t, note)); print("14_connectors: lcd_mosi and lcd_miso exchanged at J5")
