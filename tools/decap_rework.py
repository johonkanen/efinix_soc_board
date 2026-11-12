#!/usr/bin/env python3
"""Rail decoupling rework (2026-11-12): bypass caps to 0201, bulk counted per rail instead of per bank.

    python3 tools/decap_rework.py sch                     edit the sheets in place (fields, DNP flags)
    tools/p2k/bin/kipy tools/decap_rework.py board IN OUT  drop the removed caps' footprints from the board

Between the two: tools/add_parts.py (values, fields) and tools/swap_footprint.py for TO_0201 and nothing else;
after them tools/place_bga_decaps.py for the caps under U501 (UNDER_BGA) puts them on rail/GND via pairs.

- 1 u and 4.7 u on VCORE, 0V85, 1V1, 1V8 and 1 u on 3V3: 0402 -> 0201. The 4.7 u on 3V3 stay 0402: a 6.3 V 0201
  loses most of its capacitance at 3.3 V bias.
- 100 n still in 0402 on 1V8 / 3V3 (level shifters, supervisor, oscillator, PHY): 0201.
- Bulk per rail, on top of each cell's 47 u + 22 u: VCORE 2 x 100 u 1206 (C5001, C5002); 1V8 2 x 47 u (C5019 west,
  C5020 east of U501); 1V1 1 x 47 u (C538, was 10 u). Everything else in REMOVED is marked DNP, not in BOM and not
  on the board in the schematic: the symbols stay drawn, so a cap can come back by clearing the flags.
- Kept as they are: C551 (10 u at the eMMC), C803 (22 u at the LPDDR4 VDD1, routed by hand), C5033 (1 u 0402:
  eth_rst_n runs between its pads on B.Cu, an 0201 does not leave the gap).
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C0201 = "Capacitor_SMD:C_0201_0603Metric"
LCSC = {"1u": "C272877", "4u7": "C47117441", "100n": "C190183"}        # 6.3 V, 6.3 V, 10 V X5R
TO_0201 = {
    "1u": "C528 C529 C530 C531 C539 C540 C541 C542 C808 C809 C825 C826 C5031 C5032 C5034 C5035 C1306 "
          "C5050 C5051 C5052 C5006 C5007 C5008".split(),
    "4u7": "C511 C512 C513 C514 C5054 C5055 C5056 C5027 C5028 C5029 C5030 C552 C553".split(),
    "100n": "C1201 C1202 C1203 C1204 C1205 C1206 C1207 C1208 C401 C701 C951".split(),
}
REMOVED = ("C5003 C509 C510 C5004 C5005 "          # VCORE: 47 u, 2 x 22 u, 2 x 10 u
           "C5021 C5022 C5023 C5024 C5025 C5026 "  # 1V8: 2 x 47 u, 4 x 10 u
           "C527 "                                 # 0V85: 10 u
           "C806 C807 C823 C824").split()          # 1V1: 4 x 22 u 0402 at the LPDDR4 (never placed)
RETYPED = {"C538": ("47u", "Capacitor_SMD:C_0805_2012Metric", "C16780")}   # 1V1 bulk, 6.3 V X5R
UNDER_BGA = ("C528 C529 C531 C541 C542 C5054 C5055 C5056 C5031 C5032 C5034 C5035 C5027 C5028 C5029 C5030 C553 "
             "C5050 C5052 C5006 C5007 C5008 C511 C512 C513 C514").split()   # no tracks on them: free to move


def span(t, ref):
    m = re.search(rf'^\t\t\(property "Reference" "{ref}"$', t, re.M)
    if not m:
        return None
    s = t.rfind("\n\t(symbol\n", 0, m.start()) + 1
    return s, t.index("\n\t)\n", m.start()) + 4


def sub1(b, pat, rep, what):
    b, n = re.subn(pat, rep, b, count=1)
    assert n == 1, what
    return b


def sch():
    todo = {}
    for val, refs in TO_0201.items():
        for r in refs:
            todo[r] = ("fields", val, C0201, LCSC[val])
    for r, (val, fp, lcsc) in RETYPED.items():
        todo[r] = ("fields", val, fp, lcsc)
    for r in REMOVED:
        todo[r] = ("remove",)
    for path in sorted(glob.glob(os.path.join(ROOT, "kicad", "[0-9][0-9]_*.kicad_sch"))):
        t = open(path).read(); n = 0
        for r, job in list(todo.items()):
            sp = span(t, r)
            if not sp:
                continue
            b = t[sp[0]:sp[1]]
            if job[0] == "fields":
                _, val, fp, lcsc = job
                b = sub1(b, r'(\(property "Value" ")[^"]*(")', rf"\g<1>{val}\g<2>", r)
                b = sub1(b, r'(\(property "Footprint" ")[^"]*(")', rf"\g<1>{fp}\g<2>", r)
                b = sub1(b, r'(\(property "LCSC" ")[^"]*(")', rf"\g<1>{lcsc}\g<2>", r)
            else:
                b = sub1(b, r"\(in_bom (yes|no)\)", "(in_bom no)", r)
                b = sub1(b, r"\(on_board (yes|no)\)", "(on_board no)", r)
                b = sub1(b, r"\(dnp (yes|no)\)", "(dnp yes)", r)
            t = t[:sp[0]] + b + t[sp[1]:]; n += 1; del todo[r]
        if n:
            open(path, "w").write(t)
            print(f"{os.path.basename(path)}: {n} symbols")
    assert not todo, todo


def board(src, out):
    import pcbnew
    b = pcbnew.LoadBoard(src)
    gone = []
    for r in REMOVED:
        f = b.FindFootprintByReference(r)
        if f is None:
            continue
        for p in f.Pads():                                   # nothing may hang on a removed cap
            for t in b.GetTracks():
                if t.GetNetCode() == p.GetNetCode() and not isinstance(t, pcbnew.PCB_VIA) and t.IsOnLayer(f.GetLayer()) \
                        and (p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd())):
                    raise SystemExit(f"{r}: a track ends on pad {p.GetNumber()}; remove it by hand first")
        gone.append(f)
    for f in gone:
        b.Remove(f)
    pcbnew.SaveBoard(out, b)
    print(f"decap_rework: {len(gone)} footprints removed")


if __name__ == "__main__":
    if sys.argv[1:] == ["sch"]:
        sch()
    elif len(sys.argv) == 4 and sys.argv[1] == "board":
        board(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
