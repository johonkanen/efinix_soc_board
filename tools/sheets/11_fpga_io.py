#!/usr/bin/env python3
"""Sheet 11 fpga_io: U501 units 2-5 (HSIO banks 4A, 4B, 2A/2B/2C and the HVIO banks) with one hierarchical
label per used pin, named after the signal in efinity/pinplan/ti135_pinplan.csv. Unused pins: no-connect flag.

Configuration-related dual-purpose pins in bank 4A that are not in the pin plan but need a strap go to sheet 6
(fpga_config): CSI (pull-up), TEST_N (pull-up), CBSEL0/1 (DNP pull-downs).
U501 is the Ti135; its power/config/DDR units are on sheets 5, 6 and 8.
"""
from _common import *  # noqa: F401,F403

sh = sheet("11_fpga_io.kicad_sch")
pp = pinplan()
by_ball = {r["ball"]: (s, r) for s, r in pp.items()}
SHAPE = {"out": "output", "in": "input", "clkin": "input", "pllref": "input", "inout": "bidirectional"}
STRAPS = {"A2": "fpga_csi", "L7": "fpga_test_n", "J1": "fpga_cbsel0", "H1": "fpga_cbsel1"}

sh.text("U501 Ti135N484I3 I/O banks. Signal <-> ball assignment from efinity/pinplan/pinplan.py\n"
        "(Interface Designer project, design check passed). Change pins there, then re-run this script.\n"
        "HSIO banks (4A, 4B, 2A-2C) are 1.8 V; HVIO banks (BR1_BL3, BR0, TR1) are 3.3 V.", g(14), g(14))

UNITS = [(2, g(80), g(52)), (3, g(250), g(52)), (4, g(80), g(150)), (5, g(250), g(150))]
used = 0
for unit, x, y in UNITS:
    u = place_unit(sh, "Ti135N484I3", "U501", x, y, unit)
    for ball, p in u.pins.items():
        side_left = p[0] < x
        if ball in by_ball:
            sig, r = by_ball[ball]
            (hlabel_left if side_left else hlabel_right)(sh, sig, p, 4, SHAPE[r["dir"]])
            used += 1
        elif ball in STRAPS:
            (hlabel_left if side_left else hlabel_right)(sh, STRAPS[ball], p, 4, "passive")
        else:
            sh.no_connect(*p)

sh.save()
print("11_fpga_io:", used, "signals")
