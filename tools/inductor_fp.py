#!/usr/bin/env python3
"""2520 inductors (FTC252012S) from KiCad's generic land pattern to the data-sheet one (user decision 2026-11-13).

    python3 tools/inductor_fp.py        writes the library footprint and edits sheets 02 and 03 in place

Data sheet (cjiang FTC series, "Recommend Land Pattern Dimensions"): A 2.60 overall, B 0.70 gap, C 2.10 wide,
so two pads 0.95 x 2.10 at +-0.825. The generic Inductor_SMD:L_1008_2520Metric has 1.25 x 2.20 at +-1.075
(3.40 overall, 0.90 gap). The new footprint is ti135_card:L_2520_FTC252012S, made from the generic file:
pads and courtyard changed, silk lines dropped (the card has no reference silk).
Board: tools/swap_footprint.py BOARD ti135_card:L_2520_FTC252012S L201 L301 L311 L331 L341, refill, DRC.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "L_1008_2520Metric", "L_2520_FTC252012S"
stock = os.path.join(os.environ["KICAD_MOUNT"], "share/kicad/footprints/Inductor_SMD.pretty", OLD + ".kicad_mod")
t = open(stock).read()


def sub(pat, rep, n):
    global t
    t, k = re.subn(pat, rep, t, flags=re.S)
    assert k == n, (pat, k)


sub(re.escape(OLD), NEW, 3)  # footprint name, Value; the 3D model line is restored below
sub(r'\(descr "[^"]*"\)', '(descr "Molded power inductor 2.5 x 2.0 x 1.2 mm, cjiang FTC252012S, '
    'data-sheet land pattern: 2.60 overall, 0.70 gap, 2.10 wide")', 1)
sub(r'\t\(fp_line\n.*?\(layer "F\.SilkS"\)\n\t\)\n', "", 2)
sub(r'\(start -1\.95 -1\.35\)\n\t\t\(end 1\.95 1\.35\)', "(start -1.55 -1.3)\n\t\t(end 1.55 1.3)", 1)
sub(r'\(at -1\.075 0\)\n\t\t\(size 1\.25 2\.2\)', "(at -0.825 0)\n\t\t(size 0.95 2.1)", 1)
sub(r'\(at 1\.075 0\)\n\t\t\(size 1\.25 2\.2\)', "(at 0.825 0)\n\t\t(size 0.95 2.1)", 1)
t = t.replace("generator \"kicad-footprint-generator\"", "generator \"inductor_fp.py\"")
out = os.path.join(ROOT, "lib", "ti135_card.pretty", NEW + ".kicad_mod")
# the only other occurrence of the name was the 3D model; point it back at the stock body
t = t.replace(f"Inductor_SMD.3dshapes/{NEW}.step", f"Inductor_SMD.3dshapes/{OLD}.step")
open(out, "w").write(t)
print("wrote", os.path.relpath(out, ROOT))

for name, n in (("02_pwr_vcore.kicad_sch", 1), ("03_pwr_rails.kicad_sch", 4)):
    p = os.path.join(ROOT, "kicad", name); s = open(p).read()
    s, k = re.subn(rf'(\(property "Footprint" ")Inductor_SMD:{OLD}(")', rf"\g<1>ti135_card:{NEW}\g<2>", s)
    assert k == n, (name, k)
    open(p, "w").write(s)
    print(f"{name}: {k} inductors -> ti135_card:{NEW}")
