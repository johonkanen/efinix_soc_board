#!/usr/bin/env python3
"""Remove the pg_all net (user decision 2026-11-13: not needed).

    python3 tools/drop_pg_all.py sch                       edit sheets 03, 04 and the root sheet in place
    tools/p2k/bin/kipy tools/drop_pg_all.py board IN OUT   drop the net with its tracks and vias

pg_all was the wired-AND of PG(0V85, U331) and PG(1V1, U341) into ~MR of the TPS3808 (U401). Without it the two PG
pins are open (open-drain outputs, no-connect flags) and ~MR floats on its internal pull-up, which the TPS3808
allows. U401 still holds fpga_creset_n low until VCORE is up (SENSE) plus its delay; it no longer waits for group 2.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NC = '\t(no_connect\n\t\t(at {} {})\n\t\t(uuid "{}")\n\t)\n'
# sheet: wires to delete (the far end carries the label), no-connect flags to add (the pin end), uuids for them
EDITS = {
    "03_pwr_rails.kicad_sch": ([((213.36, 142.24), (217.17, 142.24)), ((73.66, 142.24), (77.47, 142.24))],
                               [((213.36, 142.24), "5d0c1a3e-9b1f-5a57-8c1e-03a1f0e4d001"),
                                ((73.66, 142.24), "5d0c1a3e-9b1f-5a57-8c1e-03a1f0e4d002")]),
    "04_pwr_seq.kicad_sch": ([((142.24, 76.2), (124.46, 76.2))], [((142.24, 76.2), "5d0c1a3e-9b1f-5a57-8c1e-03a1f0e4d003")]),
    "ti135_card.kicad_sch": ([((358.14, 33.02), (363.22, 33.02)), ((492.76, 35.56), (497.84, 35.56))], []),
}
NOTE = ("-> pg_all -> U401 TPS3808 (20 ms) -> fpga_creset_n", "; U401 TPS3808 (VCORE good + 20 ms) -> fpga_creset_n")


def cut(t, pat, n, what):
    t, k = re.subn(pat, "", t)
    assert k == n, (what, k)
    return t


def sch():
    f = lambda v: f"{v:g}"
    for name, (wires, ncs) in EDITS.items():
        path = os.path.join(ROOT, "kicad", name); t = open(path).read()
        if '"pg_all"' not in t:
            print(f"{name}: already done"); continue
        for a, c in wires:
            t = cut(t, rf'\t\(wire\n\t\t\(pts\n\t\t\t\(xy {f(a[0])} {f(a[1])}\) \(xy {f(c[0])} {f(c[1])}\)\n\t\t\)\n(?:\t\t.*\n|\t\t\t.*\n)*?\t\)\n', 1, (name, a))
        n_lab = len(re.findall(r'^\t\((?:hierarchical_)?label "pg_all"$', t, re.M))
        t = cut(t, r'\t\((?:hierarchical_)?label "pg_all"\n(?:\t\t.*\n)*?\t\)\n', n_lab, name)
        n_pin = len(re.findall(r'^\t\t\(pin "pg_all" passive$', t, re.M))
        t = cut(t, r'\t\t\(pin "pg_all" passive\n(?:\t\t\t.*\n)*?\t\t\)\n', n_pin, name)
        for (x, y), u in ncs:
            i = t.index("\t(no_connect\n") if "\t(no_connect\n" in t else t.index("\t(wire\n")
            t = t[:i] + NC.format(f(x), f(y), u) + t[i:]
        if NOTE[0] in t:
            t = t.replace(NOTE[0], NOTE[1])
        assert "pg_all" not in t, name
        open(path, "w").write(t)
        print(f"{name}: {len(wires)} wires, {n_lab} labels, {n_pin} sheet pins removed, {len(ncs)} no-connect flags")


def board(src, out):
    import pcbnew
    b = pcbnew.LoadBoard(src)
    gone = [t for t in b.GetTracks() if t.GetNetname().endswith("pg_all")]
    mm = sum(pcbnew.ToMM(t.GetLength()) for t in gone if not isinstance(t, pcbnew.PCB_VIA))
    nv = sum(isinstance(t, pcbnew.PCB_VIA) for t in gone)
    for t in gone:
        b.Remove(t)
    old = [n for name, n in b.GetNetsByName().items() if str(name).endswith("pg_all")]
    for f in b.GetFootprints():                               # the pads get the net names KiCad gives open pins
        for p in f.Pads():
            if p.GetNetname().endswith("pg_all"):
                fn = p.GetPinFunction()
                fn = fn[:-len(p.GetNumber()) - 1] if fn.endswith("_" + p.GetNumber()) else fn
                n = pcbnew.NETINFO_ITEM(b, f"unconnected-({f.GetReference()}-{fn}-Pad{p.GetNumber()})"); b.Add(n); p.SetNet(n)
                print(f"  {f.GetReference()}.{p.GetNumber()} -> {n.GetNetname()}")
    for n in old:
        b.Remove(n)
    pcbnew.SaveBoard(out, b)
    print(f"drop_pg_all: {len(gone) - nv} segments ({mm:.1f} mm) and {nv} vias removed")


if __name__ == "__main__":
    if sys.argv[1:] == ["sch"]:
        sch()
    elif len(sys.argv) == 4 and sys.argv[1] == "board":
        board(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
