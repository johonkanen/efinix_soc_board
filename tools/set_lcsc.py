#!/usr/bin/env python3
"""Fill empty LCSC fields in the schematic from one table, keyed by (value, footprint name):
    python3 tools/set_lcsc.py [--dry-run]

Only symbols without an LCSC number get one; parts that already have one are left alone. Edits the sheet files in
place (kicad/*.kicad_sch), as fields, so the hand edits stay. Then run tools/add_parts.py on the board so the
footprint fields follow. Choices checked with tools/jlc/jlc_search.py on 2026-10-29 (JLC basic parts where there is
one; voltage ratings checked against the rail each value is used on: 5V0 caps >= 10 V).
"""
import glob
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from p2k.sch_builder import _eff  # noqa: E402
from p2k.sexpr import Sym, find, find_all, load, save  # noqa: E402

LCSC = {
    # 0201 decoupling (rails <= 3V3)
    ("100n", "C_0201_0603Metric"): "C190183",     # 10 V X5R (as the U801 caps)
    ("10n", "C_0201_0603Metric"): "C76941",       # GRM033R71A103KA01D 10 V X7R
    ("1n", "C_0201_0603Metric"): "C66942",        # 50 V X7R
    # 0402 caps
    ("100n", "C_0402_1005Metric"): "C1525",       # basic, 16 V X7R
    ("1u", "C_0402_1005Metric"): "C52923",        # basic, 25 V X5R (also on 5V0)
    ("2u2", "C_0402_1005Metric"): "C12530",       # basic, 6.3 V X5R (eMMC VDDI)
    ("4u7", "C_0402_1005Metric"): "C23733",       # basic, 10 V X5R (rails <= 3V3)
    ("22p", "C_0402_1005Metric"): "C1555",        # basic, C0G
    ("27p", "C_0402_1005Metric"): "C1557",        # C0G (PHY crystal)
    ("680p C0G", "C_0402_1005Metric"): "C126514",  # GCM1555C1H681JA16D C0G
    ("1n C0G", "C_0402_1005Metric"): "C76947",     # GRM1555C1H102JA01D C0G (isoada buffer inputs)
    ("4u7", "C_0603_1608Metric"): "C19666",       # basic, 16 V X5R
    # bulk
    ("10u", "C_0805_2012Metric"): "C15850",       # basic, 25 V X5R (also on 5V0)
    ("22u", "C_0805_2012Metric"): "C45783",       # basic, 25 V X5R (also on 5V0)
    ("47u", "C_0805_2012Metric"): "C16780",       # basic, 6.3 V X5R (rails <= 3V3)
    ("100u", "C_1206_3216Metric"): "C15008",      # basic, 6.3 V X5R (VCORE)
    ("47u", "C_1206_3216Metric"): "C96123",       # basic, 10 V X5R (5V0)
    # 0402 resistors, 1 %
    ("10R", "R_0402_1005Metric"): "C25077",
    ("22R", "R_0402_1005Metric"): "C25092",
    ("33R", "R_0402_1005Metric"): "C25105",
    ("100R", "R_0402_1005Metric"): "C25076",
    ("240R 1%", "R_0402_1005Metric"): "C25094",
    ("330R", "R_0402_1005Metric"): "C25104",
    ("1k", "R_0402_1005Metric"): "C11702",
    ("2.49k 1%", "R_0402_1005Metric"): "C25884",
    ("4k7", "R_0402_1005Metric"): "C25900",
    ("10k", "R_0402_1005Metric"): "C25744",
    ("10k 1%", "R_0402_1005Metric"): "C25744",
    ("10k DNP", "R_0402_1005Metric"): "C25744",
    ("41.2k", "R_0402_1005Metric"): "C26978",
    ("47k", "R_0402_1005Metric"): "C25792",
    ("82.5k", "R_0402_1005Metric"): "C11717",
    ("100k", "R_0402_1005Metric"): "C25741",
    ("200k", "R_0402_1005Metric"): "C25764",
    ("453k", "R_0402_1005Metric"): "C27009",
    # VCORE divider: no 0.5 % part in stock; 0.1 % thin film
    ("59.0k 0.5%", "R_0402_1005Metric"): "C2684527",  # ARG02BTC5902 0.1 %
    ("100k 0.5%", "R_0402_1005Metric"): "C136979",    # RT0402BRE07100KL 0.1 %
    # others
    ("BLM15PX121SN1D", "L_0402_1005Metric"): "C88970",
    ("red", "LED_0603_1608Metric"): "C2286",
    ("25MHz", "Crystal_SMD_3225-4Pin_3.2x2.5mm"): "C70593",   # X322525MRB4SI 18 pF (27 p caps + strays)
    ("NCP163ASN330T1G", "SOT-23-5"): "C603656",
    ("TPS3808G01DBVR", "SOT-23-6"): "C19653",
    ("OT322525MJBA4SL", "Oscillator_SMD_SiT_PQFN-4Pin_3.2x2.5mm"): "C669088",  # Y701, EN tied to 1V8
    # connectors (THT)
    ("JTAG 3.3V", "PinHeader_1x05_P2.54mm_Vertical"): "C492404",
    ("UART 3.3V", "PinHeader_1x03_P2.54mm_Vertical"): "C2937625",
    ("LCD 1x14 2.54mm", "PinHeader_1x14_P2.54mm_Vertical"): "C22465874",
    ("5V0 bench input", "PinHeader_1x02_P2.54mm_Vertical"): "C492401",
    ("2x19 1.27mm socket (bottom)", "PinSocket_2x19_P1.27mm_Vertical_Drill0.6"): "C27985219",  # HC-PM127-4.3H-2x19PZ
    ("2x3 1.27mm (bottom)", "PinSocket_2x03_P1.27mm_Vertical"): "C22373841",   # HC-PM127-4.3H-2x3PZ-02A
}


def main():
    dry = "--dry-run" in sys.argv
    used, missing, total = set(), {}, 0
    for path in sorted(glob.glob(os.path.join(ROOT, "kicad", "*.kicad_sch"))):
        tree = load(path)
        n = 0
        for s in find_all(tree, "symbol"):
            if not find(s, "lib_id"):
                continue                      # lib_symbols entries
            props = {p[1]: p for p in find_all(s, "property")}
            ref = props.get("Reference", [0, 0, ""])[2]
            if not ref or ref.startswith("#") or props.get("LCSC", [0, 0, ""])[2]:
                continue
            key = (props["Value"][2], props.get("Footprint", [0, 0, ""])[2].split(":")[-1])
            if key not in LCSC:
                missing.setdefault(key, []).append(ref)
                continue
            if "LCSC" in props:
                props["LCSC"][2] = LCSC[key]
            else:
                at = find(s, "at")
                prop = [Sym("property"), "LCSC", LCSC[key], [Sym("at"), at[1], at[2], 0], _eff(hide=True)]
                i = max(k for k, c in enumerate(s) if isinstance(c, list) and c[0] == Sym("property"))
                s.insert(i + 1, prop)
            used.add(key)
            n += 1
        if n and not dry:
            save(path, tree)
        if n:
            print(f"{os.path.basename(path)}: {n}")
        total += n
    print(f"{total} symbols {'would get' if dry else 'got'} an LCSC number")
    for key, refs in sorted(missing.items()):
        print(f"no table entry: {key} {sorted(set(refs))}")
    for key in sorted(set(LCSC) - used):
        print(f"table entry not used: {key}")


if __name__ == "__main__":
    main()
