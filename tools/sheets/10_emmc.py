#!/usr/bin/env python3
"""Sheet 10 emmc: KIOXIA THGAMVG7T13BAIL (U1001), 16 GB e-MMC 5.1, 8-bit, VCCQ = 1.8 V only.

Values: KIOXIA data sheet (TI135_PCB_NOTES.md §8, SHARED_PARTS.md on the Agilex card) and the Efinix Ti375C529 kit:
CMD and DAT0-7 47 k pull-ups to VCCQ, DS (HS400 strobe) 47 k pull-down, RST_n 47 k pull-up (RST_n function is
disabled by default, EXT_CSD[162]), CLK 10 R series at the FPGA. VCC 3V3 (4u7 + 2 x 100n), VCCQ 1V8 from the same
supply as the FPGA bank (data sheet requirement; 4u7 + 2 x 100n), VDDi 2u2.
"""
from _common import *  # noqa: F401,F403

sh = sheet("10_emmc.kicad_sch")
sh.text("e-MMC on bank 4A (1.8 V). Pull-ups to 1V8 (= VCCQ, same supply as the FPGA I/O as the data sheet requires).",
        g(14), g(14))
UX, UY = g(150), g(80)
u = sh.place("THGAMVG7T13BAIL", "U1001", UX, UY, value="THGAMVG7T13BAIL", fields={"LCSC": "C7599693"})
sig = {"M5": "emmc_cmd", "H5": "emmc_ds", "K5": "emmc_rst_n",
       "A3": "emmc_dat0", "A4": "emmc_dat1", "A5": "emmc_dat2", "B2": "emmc_dat3",
       "B3": "emmc_dat4", "B4": "emmc_dat5", "B5": "emmc_dat6", "B6": "emmc_dat7"}
for pin, net in sig.items():
    q = attach(sh, u, pin, "label", net, 4)
attach(sh, u, "M6", "label", "emmc_clk_r", 4)
for pin in ("E6", "F5", "J10", "K9"):
    attach(sh, u, pin, "power", "3V3", 3)
for pin in ("C6", "M4", "N4", "P3", "P5"):
    attach(sh, u, pin, "power", "1V8", 3)
for pin in ("A6", "E7", "G5", "H10", "J5", "K8", "C4", "N2", "N5", "P4", "P6"):
    attach(sh, u, pin, "power", "GND", 3)
attach(sh, u, "C2", "label", "emmc_vddi", 4)

# FPGA side: hierarchical labels (pin plan names), CLK through 10 R
series_r(sh, "R1001", g(40), g(50), "10R", "hlabel", "emmc_clk", "label", "emmc_clk_r", "input")
for k, net in enumerate(["emmc_cmd", "emmc_ds", "emmc_rst_n"] + [f"emmc_dat{i}" for i in range(8)]):
    p = (g(40), g(58) + k * g(3))
    hlabel(sh, net, *p, 180, {"emmc_ds": "output", "emmc_rst_n": "input"}.get(net, "bidirectional"))
    sh.wire(p, right(p, 6)); sh.label(net, *right(p, 6), 0)

# pulls
sh.text("Pull-ups 47 k to 1V8 (CMD, DAT0-7, RST_n); DS 47 k pull-down", g(30), g(108))
pulls = [("emmc_cmd", "1V8")] + [(f"emmc_dat{i}", "1V8") for i in range(8)] + [("emmc_rst_n", "1V8"), ("emmc_ds", "GND")]
for k, (net, rail) in enumerate(pulls):
    pull_r(sh, f"R10{10 + k:02d}", g(30) + k * g(8), g(122), net, rail, "47k")

# decoupling
cap_row(sh, g(30), g(160), "3V3", [("C1001", "4u7", None), ("C1002", "100n", None), ("C1003", "100n", None)],
        "VCC 3V3: 4u7 + 2 x 100n")
cap_row(sh, g(90), g(160), "1V8", [("C1004", "4u7", None), ("C1005", "100n", None), ("C1006", "100n", None)],
        "VCCQ 1V8: 4u7 + 2 x 100n")
_, ct, cb = vert2(sh, "C", "C1007", g(150), g(160), "2u2", text="right")
sh.wire(ct, up(ct, 2)); sh.label("emmc_vddi", *up(ct, 2), 90)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
sh.text("VDDi: 2u2 (1-4.7 u)", g(146), g(150))
sh.save()
print("10_emmc done")
