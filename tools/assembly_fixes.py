#!/usr/bin/env python3
"""Assembly fixes from the pre-order review (2026-11-13).

    python3 tools/assembly_fixes.py lib            ads7056 footprint + sheet 04 (U401), in place
    kipy    tools/assembly_fixes.py board IN OUT   the same on the board

1. ads7056 footprint (U1303, ADS7056IRUGR, X2QFN-8 1.5 x 1.5): the origin was 4.6 mm from the pads, so the
   placement file put the part beside its lands. The origin is now the package centre (the middle of the side
   pads); a courtyard and a fab outline with a pin-1 corner are added. Pads are not moved relative to each
   other, so on the board the copper stays where it was and only the footprint's origin moves.
2. U401: TPS3808G01DBVR (C19653, oversold at JLCPCB) -> TPS3808G01DBVT (C702161), the same part on a small reel.
The third fix, the bottom-side rotation offset sign, is in tools/jlc/jlc_bom_cpl.py.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FP = os.path.join(ROOT, "lib", "ti135_card.pretty", "ads7056.kicad_mod")
DY = 4.608676  # old origin -> package centre
U401 = {"Value": ("TPS3808G01DBVR", "TPS3808G01DBVT"), "LCSC": ("C19653", "C702161")}
EXTRA = """\t(fp_rect
\t\t(start -1.2 -1.2)
\t\t(end 1.2 1.25)
\t\t(stroke
\t\t\t(width 0.05)
\t\t\t(type solid)
\t\t)
\t\t(fill no)
\t\t(layer "F.CrtYd")
\t)
\t(fp_poly
\t\t(pts
\t\t\t(xy -0.375 -0.75) (xy 0.75 -0.75) (xy 0.75 0.75) (xy -0.75 0.75) (xy -0.75 -0.375)
\t\t)
\t\t(stroke
\t\t\t(width 0.1)
\t\t\t(type solid)
\t\t)
\t\t(fill no)
\t\t(layer "F.Fab")
\t)
"""


def lib():
    t = open(FP).read()
    if "F.CrtYd" in t:
        print("ads7056: already fixed")
    else:
        def shift(m):
            return f"{m.group(1)}{float(m.group(2)) - DY:.6g}{m.group(3)}"
        t, n = re.subn(r'(\(pad "\d" smd rect\n\t\t\(at -?[\d.]+ )([\d.]+)((?: 180)?\))', shift, t)
        assert n == 8, n
        t = t.replace("(at 0 -0.5 0)", "(at 0 -2 0)", 1).replace("(at 0 1 0)", "(at 0 2 0)", 1)
        t = t.replace("(at 0 2.5 0)", "(at 0 0 0)", 1).replace("(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n\t(pad",
                                                               "(size 0.4 0.4)\n\t\t\t\t(thickness 0.06)\n\t\t\t)\n\t\t)\n\t)\n\t(pad", 1)
        k = t.index('\t(pad "1"')
        open(FP, "w").write(t[:k] + EXTRA + t[k:])
        print("ads7056: origin moved to the package centre, courtyard and fab outline added")
    p = os.path.join(ROOT, "kicad", "04_pwr_seq.kicad_sch"); s = open(p).read()
    m = re.search(r'^\t\t\(property "Reference" "U401"$', s, re.M)
    a = s.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = s.index("\n\t)\n", m.start()) + 4
    blk = s[a:e]
    for k, (old, new) in U401.items():
        blk, n = re.subn(rf'(\(property "{k}" "){old}(")', rf"\g<1>{new}\g<2>", blk)
        assert n == 1, (k, n)
    open(p, "w").write(s[:a] + blk + s[e:])
    print("04_pwr_seq: U401 ->", {k: v[1] for k, v in U401.items()})


def board(src, dst):
    import subprocess
    import pcbnew
    b = pcbnew.LoadBoard(src)
    f = b.FindFootprintByReference("U1303")
    old = {p.GetNumber(): pcbnew.VECTOR2I(p.GetPosition()) for p in f.Pads()}
    ref_visible = f.Reference().IsVisible()
    u = b.FindFootprintByReference("U401")
    for k, (o, n) in U401.items():
        assert u.GetFieldText(k) == o, (k, u.GetFieldText(k))
        u.SetField(k, n)
    pcbnew.SaveBoard(dst, b)
    subprocess.check_call([sys.executable, os.path.join(ROOT, "tools", "swap_footprint.py"), dst, "ti135_card:ads7056", "U1303"])
    b = pcbnew.LoadBoard(dst)
    f = b.FindFootprintByReference("U1303")
    d = old["1"] - [p for p in f.Pads() if p.GetNumber() == "1"][0].GetPosition()
    f.Move(d)
    f.Reference().SetVisible(ref_visible)  # the card has no reference silk
    worst = max((p.GetPosition() - old[p.GetNumber()]).EuclideanNorm() for p in f.Pads())
    assert worst <= 2, worst  # nm
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    print(f"board: U1303 origin moved by ({pcbnew.ToMM(d.x):.3f}, {pcbnew.ToMM(d.y):.3f}) mm, pads unmoved; U401 fields updated")


if sys.argv[1] == "lib":
    lib()
else:
    board(sys.argv[2], sys.argv[3])
