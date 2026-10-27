#!/usr/bin/env python3
"""Sheet 2 pwr_vcore: VCORE 0.95 V for the Ti135 VCC, VCCA and VDD_SOC (I3 grade: 0.92-0.98 V).

TLV62585PDRL (3 A; the data sheet asks for >= 1.5 A VCC inrush). R1 59.0 k / R2 100 k -> 0.954 V.
Use 0.5 % divider resistors. Soft start 900 us -> about 1 V/ms (limit 0.095-10 V/ms). EN tied to 5V0 (group 1).
PG -> pg_group1 (wired AND with 1V8 and 3V3 PG) enables the group-2 DDR rails (sheet 4).
C204 47 u: one of the two 47 u of Efinix's VCORE decoupling, placed at the regulator (checklist: >= 47 uF at each
regulator output). C205 22 p feed-forward: the rail carries far more than 47 uF (_power.py).
"""
from _common import *  # noqa: F401,F403
from _power import buck

sh = sheet("02_pwr_vcore.kicad_sch")
sh.text("VCORE 0.95 V: Ti135 VCC (31 balls), VCCA_BL/BR/TR (through ferrites, sheet 5), VDD_SOC, VCC18A_MIPI (unused MIPI).\n"
        "Estimate about 0.6 A typical, 1.0 A high, >= 1.5 A inrush (POWER_BUDGET.md).", g(14), g(14))
buck(sh, {"U": "U201", "L": "L201", "R1": "R201", "R2": "R202", "CIN": "C201", "COUT": ["C202", "C203", ("C204", "47u")],
      "CFF": "C205"}, g(60), g(50), "VCORE", "59.0k 0.5%", pg="pg_group1", couts=3, title="VCORE 0.95 V (group 1)")
set_field(sh, "R202", "Value", "100k 0.5%")
sh.save()
print("02_pwr_vcore done")
