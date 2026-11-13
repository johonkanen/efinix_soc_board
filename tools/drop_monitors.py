#!/usr/bin/env python3
"""Rail voltage monitors off the board for now (user decision 2026-11-13; they may come back later).

    python3 tools/drop_monitors.py sch                       sheet 13: R1301-R1305 DNP, not in BOM, not on board
    tools/p2k/bin/kipy tools/drop_monitors.py board IN OUT   remove the five footprints and the mon_* copper

The monitors feed four inputs of the ADC mux U1301 through 100R / a 200R:200R divider: X1 VCORE (R1301), X2 1V8
(R1302), X3 3V3/2 (R1303, R1305), X5 1V1 (R1304). The symbols and the mon_* nets stay drawn, so the monitors come
back by clearing the three flags and running tools/add_parts.py. Until then the mux inputs X1, X2, X3, X5 float:
do not select them (X0 is GND, X4 / X6 / X7 are the isoada buffers).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = "R1301 R1302 R1303 R1304 R1305".split()
NETS = ("mon_vcore", "mon_1v8", "mon_3v3", "mon_1v1")


def sch():
    path = os.path.join(ROOT, "kicad", "13_adc.kicad_sch"); t = open(path).read()
    for r in REFS:
        m = re.search(rf'^\t\t\(property "Reference" "{r}"$', t, re.M)
        s = t.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = t.index("\n\t)\n", m.start()) + 4
        b = t[s:e]
        for pat, rep in ((r"\(in_bom (yes|no)\)", "(in_bom no)"), (r"\(on_board (yes|no)\)", "(on_board no)"), (r"\(dnp (yes|no)\)", "(dnp yes)")):
            b, n = re.subn(pat, rep, b, count=1)
            assert n == 1, (r, pat)
        t = t[:s] + b + t[e:]
    if '(text "Rail monitors"' in t:
        t = t.replace('(text "Rail monitors"', '(text "Rail monitors: NOT FITTED (2026-11-13), may return; mux X1/X2/X3/X5 float"')
    open(path, "w").write(t)
    print("13_adc.kicad_sch:", " ".join(REFS), "DNP / not on board")


def board(src, out):
    import pcbnew
    b = pcbnew.LoadBoard(src)
    gone = [t for t in b.GetTracks() if t.GetNetname().endswith(NETS)]
    fps = [f for f in (b.FindFootprintByReference(r) for r in REFS) if f is not None]
    print(f"drop_monitors: {len(fps)} footprints, {len(gone)} tracks/vias removed")
    for x in gone + fps:
        b.Remove(x)
    pcbnew.SaveBoard(out, b)


if __name__ == "__main__":
    if sys.argv[1:] == ["sch"]:
        sch()
    elif len(sys.argv) == 4 and sys.argv[1] == "board":
        board(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
