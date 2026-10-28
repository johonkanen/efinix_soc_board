#!/usr/bin/env python3
"""Sheet 8 lpddr4: U501 unit 1 (DDR) and U801 SK hynix H9HCNNN8KUMLHR-NME (LPDDR4 8 Gb, 2 ch x16, 1 rank).

Wiring as on Efinix's Ti375C529 kit (TI135_PCB_NOTES.md §6.1): one CA bus / CK / CKE0 / RESET shared by
channels A and B; CS_N[0] -> CS0_A, CS_N[2] -> CS0_B; CKE[1], CS_N[1], CS_N[3] unused (single rank).
FPGA byte 0/1 -> channel A byte 0/1, byte 2/3 -> channel B byte 0/1; DQ bits swizzled within each byte per
efinity/pinplan/lpddr4_swizzle.json (LPDDR4_SWIZZLE.md). DDR_CAL 240 R 0.1 % to GND (Efinix checklist),
ZQ0 240 R 1 % to VDDQ (1V1), ODT_CA_A/B to VDD2 (1V1, as on the Agilex card).
Net names ddr_dq0..31 / ddr_dm0..3 / ddr_dqs<n>_P/N / ddr_ck_P/N / ddr_ca0..5 keep the Agilex LPDDR4 net-class
patterns. Swizzling (DQ within a byte, CA) is allowed only as in TI135_PCB_NOTES.md §6.2. A swap made in layout is
entered in lpddr4_swizzle.json; this sheet and the Interface Designer project (PIN_SWIZZLE_*) both follow it.
"""
import json
import os
import re

from _common import *  # noqa: F401,F403

sh = sheet("08_lpddr4.kicad_sch")

# DQ swizzle (LPDDR4_SWIZZLE.md): FPGA DDR_DQ[8n+k] -> DRAM DQ bit SWZ["dq"][n][k] of the DRAM byte wired to FPGA
# byte n. The same file feeds Interface Designer's PIN_SWIZZLE_DQMn in efinity/pinplan/pinplan.py.
with open(os.path.join(ROOT, "efinity", "pinplan", "lpddr4_swizzle.json")) as f:
    SWZ = json.load(f)
assert all(sorted(SWZ["dq"][str(n)]) == list(range(8)) for n in range(4)) and sorted(SWZ["ca"]) == list(range(6))

# FPGA pad -> net, and memory pin name(s) on that net. Nets are named after the FPGA ball (ddr_dq<FPGA index>).
MAP = {}
for n in range(32):
    byte, k = divmod(n, 8)
    ch, mbyte = ("A", byte) if byte < 2 else ("B", byte - 2)
    MAP[f"DDR_DQ[{n}]"] = (f"ddr_dq{n}", [f"DQ{8 * mbyte + SWZ['dq'][str(byte)][k]}_{ch}"])
for n in range(4):
    ch, byte = ("A", n) if n < 2 else ("B", n - 2)
    MAP[f"DDR_DM[{n}]"] = (f"ddr_dm{n}", [f"DMI{byte}_{ch}"])
    MAP[f"DDR_DQS[{n}]"] = (f"ddr_dqs{n}_P", [f"DQS{byte}_T_{ch}"])
    MAP[f"DDR_DQS_N[{n}]"] = (f"ddr_dqs{n}_N", [f"DQS{byte}_C_{ch}"])
for n in range(6):
    MAP[f"DDR_A[{n}]"] = (f"ddr_ca{n}", [f"CA{SWZ['ca'][n]}_A", f"CA{SWZ['ca'][n]}_B"])
MAP["DDR_CK"] = ("ddr_ck_P", ["CK_T_A", "CK_T_B"])
MAP["DDR_CK_N"] = ("ddr_ck_N", ["CK_C_A", "CK_C_B"])
MAP["DDR_CKE[0]"] = ("ddr_cke0", ["CKE0_A", "CKE0_B"])
MAP["DDR_CS_N[0]"] = ("ddr_cs0_n", ["CS0_A"])
MAP["DDR_CS_N[2]"] = ("ddr_cs2_n", ["CS0_B"])
MAP["DDR_RST_N"] = ("ddr_rst_n", ["RESET_N"])
UNUSED_FPGA = {"DDR_CKE[1]", "DDR_CS_N[1]", "DDR_CS_N[3]"}
MEM_NET = {m: net for net, ms in MAP.values() for m in ms}

sh.text("LPDDR4 x32: U501 DDR block -> U801 (2 channels x16, single rank). Wiring per TI135_PCB_NOTES.md §6.1\n"
        "(Efinix Ti375C529 kit). DQ swizzled within each byte (LPDDR4_SWIZZLE.md, efinity/pinplan/lpddr4_swizzle.json,\n"
        "Interface Designer PIN_SWIZZLE_DQM0-3). Never DM/DQS/bytes/channels; CA not swizzled.\n"
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
        _, t, b = vert2(sh, "R", "R801", q[0], q[1] + g(5), "240R 0.1%", text="right",
                       fields={"MPN": "RT0402BRD07240RL", "LCSC": "C852660"})
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


# The Agilex card's U12 set (same DRAM, same footprint), so its placement and escape copy over one to one
# (tools/ddr/copy_dram_escape.py): 0201 100n on the via pairs under the DRAM, 22u 0402 at VDD1, 1u/22u bulk west.
LCSC = {"100n": "C190183", "1u": "C52923", "22u": "C415703"}
rows = [
    (g(150), "1V8", [("22u", 1, None), ("100n", 2, C0201)], "U801 VDD1 (1V8): 22u + 2 x 100n"),
    (g(176), "1V1", [("22u", 2, None), ("1u", 2, None), ("100n", 13, C0201)], "U801 VDD2 (1V1): 2 x 22u + 2 x 1u + 13 x 100n"),
    (g(202), "1V1", [("22u", 2, None), ("1u", 2, None), ("100n", 14, C0201)],
     "U801 VDDQ (1V1): 2 x 22u + 2 x 1u + 14 x 100n (the 100n under the DRAM, the 22u/1u bulk west of it)"),
]
for y, rail, spec, title in rows:
    cap_row(sh, g(105), y, rail, caps(spec), title, pitch=g(6), fields={v: {"LCSC": c} for v, c in LCSC.items()})
sh.save()
print("08_lpddr4 done")
