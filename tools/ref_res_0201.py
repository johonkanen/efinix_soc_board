#!/usr/bin/env python3
"""R801 (DDR_CAL) and R601 (REF_RES_2A) to 0201 so they take less room under U501 (user decision 2026-11-13).

    python3 tools/ref_res_0201.py        edits sheets 06 and 08 in place

R801: 240R 0.1 % 0402 (C852660) -> 240R 0.5 % 0201 RC0201DR-07240RL (C851687). The 0.1 % 0201 parts had no stock
at JLCPCB; the user accepted the looser tolerance (the Efinix checklist asks for 0.1 %, thick film 200 ppm/K).
R601: 10k 1 % 0402 -> 0201 RC0201FR-0710KL (C106225).
Board: tools/add_parts.py, tools/swap_footprint.py, then decap_move.py --strip / --pads for the two parts.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FP = "Resistor_SMD:R_0201_0603Metric"
JOBS = {"08_lpddr4.kicad_sch": ("R801", {"Value": "240R 0.5%", "Footprint": FP, "MPN": "RC0201DR-07240RL", "LCSC": "C851687"}),
        "06_fpga_config.kicad_sch": ("R601", {"Value": "10k 1%", "Footprint": FP, "LCSC": "C106225"})}

for name, (ref, fields) in JOBS.items():
    path = os.path.join(ROOT, "kicad", name); t = open(path).read()
    m = re.search(rf'^\t\t\(property "Reference" "{ref}"$', t, re.M)
    s = t.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = t.index("\n\t)\n", m.start()) + 4
    b = t[s:e]
    for k, v in fields.items():
        b, n = re.subn(rf'(\(property "{k}" ")[^"]*(")', rf"\g<1>{v}\g<2>", b, count=1)
        assert n == 1, (ref, k)
    open(path, "w").write(t[:s] + b + t[e:])
    print(f"{name}: {ref} -> {fields}")
