#!/usr/bin/env python3
"""Sheet 4 pwr_seq: power-good chain and the FPGA CRESET_N supervisor.

pg_group1 = PG(VCORE) & PG(1V8) & PG(3V3) (open drain, wired AND), R401 100 k to 5V0. It drives EN of the
group-2 regulators 0V85 / 1V1 (sheet 3).
pg_all = PG(0V85) & PG(1V1) & PG(1V2) -> U401 TPS3808 ~MR (internal pull-up to VDD). Group 2 only starts after
group 1 is good, so pg_all high means every rail is good. SENSE watches VCORE directly (G01: 0.405 V threshold).
RESET (open drain, R602 10 k to 1V8 on sheet 6) = fpga_creset_n, released t_D = 20 ms (CT open) after the last
condition: meets ">= 10 us after all supplies at 90 %" and ">= 4.5 ms before configuration" (TI135_PCB_NOTES.md §5).
Power-down: any PG falling (<90 %) pulls ~MR low -> CRESET_N low at once, resetting the LPDDR4 controller first.
"""
from _common import *  # noqa: F401,F403

sh = sheet("04_pwr_seq.kicad_sch")
sh.text("Power-up order (TI135_PCB_NOTES.md §5): group 1 (VCORE, 1V8, 3V3, 1V2) -> pg_group1 -> group 2 (0V85, 1V1)\n"
        "-> pg_all -> U401 TPS3808 (20 ms) -> fpga_creset_n -> SPI active configuration.", g(14), g(14))

# pg_group1 pull-up
n = (g(40), g(50))
hlabel_left(sh, "pg_group1", n, 4)
_, rt, rb = vert2(sh, "R", "R401", n[0] + g(4), n[1] - g(5), "100k", text="right")
sh.wire(n, (rb[0], n[1]), rb)
sh.wire(rt, up(rt, 2)); power_at(sh, "5V0", up(rt, 2), "up")
sh.text("pg_group1: wired AND of the VCORE/1V8/3V3 PG outputs = EN of 0V85 and 1V1", g(30), g(58))

# supervisor
u = sh.place("TPS3808DBV", "U401", g(120), g(60), value="TPS3808G01DBVR")
rst, gnd, mr, ct, sense, vdd = (u.pin(k) for k in (1, 2, 3, 4, 5, 6))
hlabel_left(sh, "pg_all", mr, 14)
sh.no_connect(*ct)
sh.text("CT open: t_D = 20 ms", ct[0], ct[1] + g(8))
sh.wire(sense, left(sense, 4)); power_at(sh, "VCORE", left(sense, 4), "left")
sh.wire(vdd, up(vdd, 2)); power_at(sh, "1V8", up(vdd, 2), "up")
sh.wire(gnd, down(gnd, 2)); power_at(sh, "GND", down(gnd, 2), "down")
hlabel_right(sh, "fpga_creset_n", rst, 6, "output")
_, ct2, cb2 = vert2(sh, "C", "C401", g(150), g(50), "100n", text="right")
sh.wire(ct2, up(ct2, 2)); power_at(sh, "1V8", up(ct2, 2), "up")
sh.wire(cb2, down(cb2, 2)); power_at(sh, "GND", down(cb2, 2), "down")
sh.save()
print("04_pwr_seq done")
