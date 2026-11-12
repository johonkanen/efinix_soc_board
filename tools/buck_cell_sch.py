#!/usr/bin/env python3
"""Uniform parts for the five TLV62585 cells, edited into the hand-maintained sheets 02/03 in place:
    python3 tools/buck_cell_sch.py

Every cell gets the same parts (tools/buck_cell.py is the layout): L 1 uH 2520, CIN 10 u 0603 + 100 n 0201 at VIN,
COUT 47 u 0805 + 22 u 0603, R1/R2/CFF 0201 (1 % dividers, also on VCORE). The second 22 u output capacitor of a
cell becomes its 100 n input capacitor: the symbol, its two wires and its GND symbol move as a column to the left of
CIN and a wire joins it to the 5V0 node. The 0V85 cell had no second 22 u: C335 is a copy of C332's column.
Run once; a second run finds nothing to move and only rewrites the same fields.
"""
import os
import re
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP, RES = "Capacitor_SMD:", "Resistor_SMD:"
#        ref suffix: value, footprint, LCSC, MPN
L_NEW = ("1u", "Inductor_SMD:L_1008_2520Metric", "C5832370", "FTC252012S1R0MBCA")   # 35 mOhm, 4 A rms / 5.6 A sat
CIN = ("10u", CAP + "C_0603_1608Metric", "C109457")       # CC0603MRX5R7BB106, 16 V X5R (on 5V0)
CHF = ("100n", CAP + "C_0201_0603Metric", "C190183")      # 10 V X5R (on 5V0)
C22 = ("22u", CAP + "C_0603_1608Metric", "C109447")       # CC0603MRX5R6BB226, 10 V X5R (rails <= 3V3)
C47 = ("47u", CAP + "C_0805_2012Metric", "C16780")        # unchanged
CFF = ("22p", CAP + "C_0201_0603Metric", "C76924")        # GRM0335C1H220JA01D, C0G
R0201 = RES + "R_0201_0603Metric"
R2 = ("100k", R0201, "C106224")                           # RC0201FR-07100KL
R1 = {"59.0k": "C320978", "200k": "C138163", "453k": "C423509", "41.2k": "C473480", "82.5k": "C423422"}   # 1 %
CELLS = [  # sheet, base, R1 value, has a second 22 u to turn into the 100 n
    ("02_pwr_vcore.kicad_sch", 201, "59.0k", True), ("03_pwr_rails.kicad_sch", 301, "200k", True),
    ("03_pwr_rails.kicad_sch", 311, "453k", True), ("03_pwr_rails.kicad_sch", 331, "41.2k", False),
    ("03_pwr_rails.kicad_sch", 341, "82.5k", True),
]
DX = 10.16   # the 100 n column sits this far left of CIN


def u():
    return str(uuid.uuid4())


def sym_span(t, ref):
    m = re.search(rf'^\t\t\(property "Reference" "{re.escape(ref)}"$', t, re.M)
    if not m:
        raise SystemExit(f"{ref} not found")
    s = t.rfind("\n\t(symbol\n", 0, m.start()) + 1
    return s, t.index("\n\t)\n", m.start()) + 4


def set_fields(t, ref, value, fp, lcsc, mpn=None):
    s, e = sym_span(t, ref)
    b = t[s:e]
    for key, val in (("Value", value), ("Footprint", fp), ("LCSC", lcsc), ("MPN", mpn)):
        if val is not None:
            b, n = re.subn(rf'(\(property "{key}" ")[^"]*(")', rf"\g<1>{val}\g<2>", b, count=1)
            assert n == 1, (ref, key)
    return t[:s] + b + t[e:]


def at(t, ref):
    s, e = sym_span(t, ref)
    m = re.search(r"\(at ([\d.]+) ([\d.]+) \d+\)", t[s:e])
    return float(m.group(1)), float(m.group(2))


def fmt(v):
    return f"{round(v, 4):g}"


def shift_x(b, dx):
    return re.sub(r"\((at|xy) ([\d.]+) ([\d.]+)", lambda m: f"({m.group(1)} {fmt(float(m.group(2)) + dx)} {m.group(3)}", b)


def column(t, x, y):
    """Spans of the capacitor column at (x, y): the symbol, the wire above, the wire below, the GND symbol."""
    spans = []
    for pat in (rf'\n\t\(symbol\n\t\t\(lib_id "ti135_card:C"\)\n\t\t\(at {fmt(x)} {fmt(y)} 0\)',
                rf'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy {fmt(x)} {fmt(y - 6.35)}\) \(xy {fmt(x)} {fmt(y - 3.81)}\)',
                rf'\n\t\(wire\n\t\t\(pts\n\t\t\t\(xy {fmt(x)} {fmt(y + 3.81)}\) \(xy {fmt(x)} {fmt(y + 6.35)}\)',
                rf'\n\t\(symbol\n\t\t\(lib_id "ti135_card:GND"\)\n\t\t\(at {fmt(x)} {fmt(y + 6.35)} 0\)'):
        m = re.search(pat, t)
        assert m, pat
        spans.append((m.start() + 1, t.index("\n\t)\n", m.start() + 1) + 4))
    return spans


def wire(a, b):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {fmt(a[0])} {fmt(a[1])}) (xy {fmt(b[0])} {fmt(b[1])})\n\t\t)\n'
            f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "{u()}")\n\t)\n')


def insert(t, text):
    i = t.index("\n\t(wire\n") + 1
    return t[:i] + text + t[i:]


def main():
    for sheet, base, r1, has_c3 in CELLS:
        path = os.path.join(ROOT, "kicad", sheet)
        t = open(path).read()
        r = lambda k, p="C": f"{p}{base + k}"
        cin, c22 = r(0), r(1)
        chf = r(2) if has_c3 else r(4)                       # C2x3, or the new C335
        c47, cff = (r(3), r(4)) if has_c3 else (r(2), r(3))
        cx, cy = at(t, cin)
        nx = cx - DX
        if not re.search(rf'"Reference" "{chf}"', t) or abs(at(t, chf)[0] - nx) > 0.01:
            if has_c3:                                        # move the column
                ox, oy = at(t, chf)
                assert abs(oy - cy) < 0.01, (chf, oy, cy)
                for s, e in sorted(column(t, ox, oy), reverse=True):
                    t = t[:s] + shift_x(t[s:e], nx - ox) + t[e:]
                t = re.sub(rf'\n\t\(junction\n\t\t\(at {fmt(ox)} {fmt(oy - 6.35)}\)(?:(?!\n\t\)\n).)*\n\t\)', "", t, flags=re.S)
            else:                                             # copy C332's column as C335
                ox, oy = at(t, c22)
                pwr = max(int(n) for n in re.findall(r'"Reference" "#PWR(\d+)"', t)) + 1
                new = ""
                for s, e in column(t, ox, oy):
                    b = shift_x(t[s:e], nx - ox)
                    b = re.sub(r'\(uuid "[^"]+"\)', lambda m: f'(uuid "{u()}")', b)
                    b = b.replace(f'"{c22}"', f'"{chf}"')
                    b = re.sub(r'#PWR\d+', f"#PWR{pwr:04d}" if False else f"#PWR{pwr}", b)
                    new += b
                t = insert(t, new)
            t = insert(t, wire((nx, cy - 6.35), (cx, cy - 6.35)))
            print(f"{sheet}: {chf} is the 100 n at VIN, left of {cin}")
        t = set_fields(t, cin, *CIN)
        t = set_fields(t, chf, *CHF)
        t = set_fields(t, c22, *C22)
        t = set_fields(t, c47, *C47)
        t = set_fields(t, cff, *CFF)
        t = set_fields(t, r(0, "R"), r1, R0201, R1[r1])
        t = set_fields(t, r(1, "R"), *R2)
        t = set_fields(t, r(0, "L"), *L_NEW[:3], mpn=L_NEW[3])
        open(path, "w").write(t)
    print("buck_cell_sch: 5 cells")


if __name__ == "__main__":
    main()
