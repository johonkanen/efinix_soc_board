#!/usr/bin/env python3
"""Sheet 05: C508, 100 n 0201 from vddpll_mcb_top_phy_ddr (U501 W11) to GND, beside the 1 u C507 (user, 2026-11-17):
    python3 tools/ddr_pll_cap_sch.py        then tools/add_parts.py and tools/ddr_pll_cap.py for the board
Efinix asks for 1 u + 100 n + 10 n on a PLL supply; the DDR PLL had the 1 u only. Skipped when already done."""
import re
import uuid

exec(open(__file__.replace("ddr_pll_cap_sch.py", "mfg_fixes_sch.py")).read().split("# ---- sheet 08")[0])   # sheet, block, moved, wire, gnd, append

p, t = sheet("05_fpga_power.kicad_sch")
if '"Reference" "C508"' in t:
    print("05_fpga_power: C508 already there")
else:
    X, DX = 300.99, 300.99 - 290.83                        # C507 is at (290.83, 184.15), pins at y 180.34 / 187.96
    c = moved(block(t, r'^\t\t\(property "Reference" "C507"$'), DX, 0).replace('"C507"', '"C508"')
    for k, v in (("Value", "100n"), ("LCSC", "C190183")):
        c, n = re.subn(rf'(\(property "{k}" ")[^"]*(")', rf"\g<1>{v}\g<2>", c, count=1); assert n == 1, k
    j = f'\t(junction\n\t\t(at {X:g} 177.8)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n'
    t = append(t, c + gnd(t, X, 190.5, 0) + wire(X, 177.8, X, 180.34) + wire(X, 187.96, X, 190.5) + j)
    open(p, "w").write(t); print("05_fpga_power: C508 100n on the DDR PLL supply added")
