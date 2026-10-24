#!/usr/bin/env python3
"""Sheet 8 lpddr4: U501 unit 1 (DDR) and U801 SK hynix H9HCNNN8KUMLHR-NME (LPDDR4 8 Gb, 2 ch x16, 1 rank).

Wiring as on Efinix's Ti375C529 kit (TI135_PCB_NOTES.md §6.1): one CA bus / CK / CKE0 / RESET shared by
channels A and B; CS_N[0] -> CS0_A, CS_N[2] -> CS0_B; CKE[1], CS_N[1], CS_N[3] unused (single rank).
FPGA byte 0/1 -> channel A byte 0/1, byte 2/3 -> channel B byte 0/1. DDR_CAL 240 R 1 % to GND,
ZQ0 240 R 1 % to VDDQ (1V1), ODT_CA_A/B to VDD2 (1V1, as on the Agilex card).
Net names ddr_dq0..31 / ddr_dm0..3 / ddr_dqs<n>_P/N / ddr_ck_P/N / ddr_ca0..5 keep the Agilex LPDDR4 net-class
patterns. Swizzling (DQ within a byte, CA) is allowed only as in TI135_PCB_NOTES.md §6.2 and must be entered in
the Interface Designer (PIN_SWIZZLE_*); any swap made in layout is redrawn here by changing MAP below.
"""
import re

from _common import *  # noqa: F401,F403

sh = sheet("08_lpddr4.kicad_sch")

# FPGA pad -> net, and memory pin name(s) on that net
MAP = {}
for n in range(32):
    ch, bit = ("A", n) if n < 16 else ("B", n - 16)
    MAP[f"DDR_DQ[{n}]"] = (f"ddr_dq{n}", [f"DQ{bit}_{ch}"])
for n in range(4):
    ch, byte = ("A", n) if n < 2 else ("B", n - 2)
    MAP[f"DDR_DM[{n}]"] = (f"ddr_dm{n}", [f"DMI{byte}_{ch}"])
    MAP[f"DDR_DQS[{n}]"] = (f"ddr_dqs{n}_P", [f"DQS{byte}_T_{ch}"])
    MAP[f"DDR_DQS_N[{n}]"] = (f"ddr_dqs{n}_N", [f"DQS{byte}_C_{ch}"])
for n in range(6):
    MAP[f"DDR_A[{n}]"] = (f"ddr_ca{n}", [f"CA{n}_A", f"CA{n}_B"])
MAP["DDR_CK"] = ("ddr_ck_P", ["CK_T_A", "CK_T_B"])
MAP["DDR_CK_N"] = ("ddr_ck_N", ["CK_C_A", "CK_C_B"])
MAP["DDR_CKE[0]"] = ("ddr_cke0", ["CKE0_A", "CKE0_B"])
MAP["DDR_CS_N[0]"] = ("ddr_cs0_n", ["CS0_A"])
MAP["DDR_CS_N[2]"] = ("ddr_cs2_n", ["CS0_B"])
MAP["DDR_RST_N"] = ("ddr_rst_n", ["RESET_N"])
UNUSED_FPGA = {"DDR_CKE[1]", "DDR_CS_N[1]", "DDR_CS_N[3]"}
MEM_NET = {m: net for net, ms in MAP.values() for m in ms}

sh.text("LPDDR4 x32: U501 DDR block -> U801 (2 channels x16, single rank). Wiring per TI135_PCB_NOTES.md §6.1\n"
        "(Efinix Ti375C529 kit). Swizzle rules §6.2: DQ only within its byte, CA only with the same permutation on\n"
        "both channels, never DM/DQS/bytes/channels; enter every swap in Interface Designer PIN_SWIZZLE_*.\n"
        "Routing: §6.3 (40 R SE / 80 R diff, include package net lengths).", g(14), g(16))

# ---------------------------------------------------------------- FPGA DDR unit
FX, FY = g(70), g(110)
fu = place_unit(sh, "Ti135N484I3", "U501", FX, FY, 1)
from p2k.sch_builder import lib  # noqa: E402
from p2k.sexpr import find, walk  # noqa: E402


def pin_names(symname, unit):
    out = {}
    for sub in lib()[symname][2:]:
        if isinstance(sub, list) and str(sub[0]) == "symbol" and re.match(rf"{re.escape(symname)}_{unit}_\d", str(sub[1])):
            for p in walk(sub, "pin"):
                out[find(p, "number")[1]] = find(p, "name")[1]
    return out


for ball, name in pin_names("Ti135N484I3", 1).items():
    p = fu.pin(ball)
    side_left = p[0] < FX
    if name in MAP:
        q = left(p, 4) if side_left else right(p, 4)
        sh.wire(p, q)
        sh.label(MAP[name][0], *q, 180 if side_left else 0)
    elif name == "DDR_CAL":
        q = right(p, 20)
        sh.wire(p, q)
        _, t, b = vert2(sh, "R", "R801", q[0], q[1] + g(5), "240R 1%", text="right")
        sh.wire(q, t); sh.wire(b, down(b, 2)); power_at(sh, "GND", down(b, 2), "down")
    elif name in UNUSED_FPGA:
        sh.no_connect(*p)
    else:
        raise SystemExit(f"unmapped FPGA DDR pin {name}")

# ---------------------------------------------------------------- memory
RAILS = {"VDD1": "1V8", "VDD2": "1V1", "VDDQ": "1V1", "VSS": "GND"}
stagger = [0]
for unit, (mx, my) in ((1, (g(210), g(100))), (2, (g(290), g(100)))):
    mu = sh.place("H9HCNNN8KUMLHR-NME", "U801", mx, my, unit=unit, value="H9HCNNN8KUMLHR-NME",
                  fields={"LCSC": "C2912103"})
    for num, name in pin_names("H9HCNNN8KUMLHR-NME", unit).items():
        p = mu.pin(num)
        side_left = p[0] < mx
        if name in MEM_NET:
            q = left(p, 4) if side_left else right(p, 4)
            sh.wire(p, q)
            sh.label(MEM_NET[name], *q, 180 if side_left else 0)
        elif name in RAILS:
            top = p[1] < my - g(10)
            bottom = p[1] > my + g(10) and abs(p[0] - mx) < g(12)
            if top or bottom:
                stagger[0] += 1
                q = up(p, 3 + 4 * (stagger[0] % 2)) if top else down(p, 3)
                sh.wire(p, q)
                power_at(sh, RAILS[name], q, "up" if top else "down")
            else:
                q = left(p, 3) if side_left else right(p, 3)
                sh.wire(p, q)
                power_at(sh, RAILS[name], q, "left" if side_left else "right")
        elif name.startswith("ODT_CA"):
            q = left(p, 3) if side_left else right(p, 3)
            sh.wire(p, q)
            power_at(sh, "1V1", q, "left" if side_left else "right")
        elif name == "ZQ0":
            _, a, b = horiz2(sh, "R", "R802", p[0] + g(14), p[1], "240R 1%", text="below")
            sh.wire(p, a); sh.wire(b, right(b, 2)); power_at(sh, "1V1", right(b, 2), "right")
        elif name in ("NC", "DNU"):
            sh.no_connect(*p)
        else:
            raise SystemExit(f"unmapped memory pin {name}")

# ---------------------------------------------------------------- memory decoupling (rail above, GND below)
cn = [802]


def caps(spec):
    out = []
    for val, n, fp in spec:
        for _ in range(n):
            cn[0] += 1
            out.append((f"C{cn[0]}", val, fp))
    return out


cap_row(sh, g(105), g(150), "1V8", caps([("4u7", 1, None), ("1u", 2, None), ("100n", 4, None)]),
        "U801 VDD1 (1V8): 4u7 + 2 x 1u + 4 x 100n")
cap_row(sh, g(105), g(176), "1V1", caps([("10u", 1, C0805), ("1u", 4, None), ("100n", 8, None)]),
        "U801 VDD2 (1V1): 10u + 4 x 1u + 8 x 100n")
cap_row(sh, g(105), g(202), "1V1", caps([("10u", 1, C0805), ("1u", 4, None), ("100n", 8, None)]),
        "U801 VDDQ (1V1): 10u + 4 x 1u + 8 x 100n (place at the VDDQ balls)")
sh.save()
print("08_lpddr4 done")
