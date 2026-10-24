#!/usr/bin/env python3
"""Sheet 3 pwr_rails: 1V8, 3V3, 1V2 (group 1, EN = 5V0) and 0V85, 1V1 (group 2, EN = pg_group1).

All TLV62585PDRL, R2 = 100 k (POWER_BUDGET.md). Ti135 power-up (TI135_PCB_NOTES.md §5): group 1 = VCC, VCCA,
VDD_SOC, VCCAUX, VCCIO, VCCIO33 in any order; group 2 (DDR PHY rails) >= 10 us after group 1 reached 90 %.
pg_group1 (VCORE/1V8/3V3 PG, wired AND) only goes high at 95 % of every group-1 rail, so 0V85/1V1 start after it.
LPDDR4: VDD1 (1V8) before VDD2/VDDQ (1V1) holds by construction.
"""
from _common import *  # noqa: F401,F403
from _power import buck

sh = sheet("03_pwr_rails.kicad_sch")
sh.text("Group 1: 1V8 (VCCAUX, HSIO, LPDDR4 VDD1, eMMC VCCQ, flash), 3V3 (HVIO, eMMC VCC, PHY, translators), 1V2 (PHY core).\n"
        "Group 2 (EN = pg_group1): 0V85 (DDR PHY VDD_PHY / VDDPLL), 1V1 (DDR VDDQ/VDDQX/VDDQ_CK, LPDDR4 VDD2/VDDQ).",
        g(14), g(14))
X = [g(50), g(160), g(270)]
buck(sh, {"U": "U301", "L": "L301", "R1": "R301", "R2": "R302", "CIN": "C301", "COUT": ["C302", "C303"]},
     X[0], g(48), "1V8", "200k", pg="pg_group1", couts=2, title="1V8 (group 1)")
buck(sh, {"U": "U311", "L": "L311", "R1": "R311", "R2": "R312", "CIN": "C311", "COUT": ["C312", "C313"]},
     X[1], g(48), "3V3", "453k", pg="pg_group1", couts=2, title="3V3 (group 1)")
buck(sh, {"U": "U321", "L": "L321", "R1": "R321", "R2": "R322", "CIN": "C321", "COUT": ["C322"]},
     X[2], g(48), "1V2", "100k", pg="pg_all", couts=1, title="1V2 KSZ9031 core (group 1)")
buck(sh, {"U": "U331", "L": "L331", "R1": "R331", "R2": "R332", "CIN": "C331", "COUT": ["C332"]},
     X[0], g(110), "0V85", "41.2k", en="pg_group1", pg="pg_all", couts=1, title="0V85 DDR PHY (group 2)")
buck(sh, {"U": "U341", "L": "L341", "R1": "R341", "R2": "R342", "CIN": "C341", "COUT": ["C342", "C343"]},
     X[1], g(110), "1V1", "82.5k", en="pg_group1", pg="pg_all", couts=2, title="1V1 DDR I/O + LPDDR4 VDD2/VDDQ (group 2)")
sh.save()
print("03_pwr_rails done")
