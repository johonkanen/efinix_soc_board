#!/usr/bin/env python3
"""Pad-to-die length and delay on U501 from Efinix's package net-length table (tools/p2k/bin/kipy tools/pad_to_die.py [BOARD]).

reference/efinix/ti135n484_netlength.csv (the N484 sheet of Ti135_netlength-v0.5.xlsx, Efinix Support Center; not in
git, see reference/efinix/README.md): ball -> package length (mm) and delay (ps). KiCad 10 adds these to every
length/time measurement and to the tuning rules, so the LPDDR4 skew budgets (TI135_PCB_NOTES.md §6.3) are met die to
die. Delay is stored in fs internally (87.7 ps -> 87700). Skips quietly when the CSV is absent.
"""
import csv
import os
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "reference", "efinix", "ti135n484_netlength.csv")
PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb")
if not os.path.exists(CSV):
    print("pad_to_die: reference/efinix/ti135n484_netlength.csv not found -- pad-to-die values left as they are")
    sys.exit(0)
table = {r["ball"]: (float(r["netlength_mm"]), float(r["delay_ps"])) for r in csv.DictReader(open(CSV))}
b = pcbnew.LoadBoard(PCB)
n = 0
for p in b.FindFootprintByReference("U501").Pads():
    if p.GetNumber() in table:
        mm, ps = table[p.GetNumber()]
        p.SetPadToDieLength(pcbnew.FromMM(mm))
        p.SetPadToDieDelay(int(round(ps * 1000)))
        n += 1
pcbnew.SaveBoard(PCB, b)
print(f"pad_to_die: {n} U501 pads set from the Efinix N484 net-length table (v0.5)")
