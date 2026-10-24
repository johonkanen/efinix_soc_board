#!/usr/bin/env python3
"""Sheet 12 level_shift: 4 x SN74AXC8T245 (1.8 V FPGA -> 3.3 V J3 / mux selects), all channels A->B.

DIR1 = 1V8 (H), DIR2 = GND (L): bits 1-4 and 5-8 both A->B (TI SCES875C Table 7-1), same as the Ti60 card.
~OE is NOT tied low (Ti60 card did): j3_oe_n from the FPGA with a 10 k pull-up to 1V8, so the outputs stay
Hi-Z (pulled low by the 10 k pull-downs on sheet 14) until the FPGA logic enables them.
All channels carry outputs of the same direction, so the channel <-> signal order can be changed freely during
layout (and this script re-run).
"""
from _common import *  # noqa: F401,F403

sh = sheet("12_level_shift.kicad_sch")
pp = pinplan()
bb = baseboard_j11()
bb_pin = {r["signal"].lower(): n for n, r in bb.items()}

outs = [s for s, r in pp.items() if r["group"] == "j3out"]
outs.sort(key=lambda s: (bb_pin.get(s, 100), s))   # J3 pin order, mux selects (not on J3) last
chunks = [outs[i:i + 8] for i in range(0, len(outs), 8)]

sh.text("4 x SN74AXC8T245PWR (LCSC C882718). DIR1 = H, DIR2 = L: all 8 bits A (1V8, FPGA) -> B (3V3).\n"
        "~OE: from the FPGA (j3_oe_n) with R1201 10 k to 1V8, outputs Hi-Z until user logic drives it low.\n"
        "Channel order is free (all outputs): reorder for layout and re-run tools/sheets/12_level_shift.py.",
        g(14), g(14))

# OE pull-up
_, rt, rb = vert2(sh, "R", "R1201", g(30), g(36), "10k")
sh.wire(rt, up(rt, 2)); power_at(sh, "1V8", up(rt, 2), "up")
sh.wire(rb, down(rb, 2)); sh.junction(*down(rb, 2))
oe_node = down(rb, 2)
hlabel_left(sh, "j3_oe_n", oe_node, 4, "input")
sh.label("j3_oe_n", *right(oe_node, 4), 0)
sh.wire(oe_node, right(oe_node, 4))

for k, sigs in enumerate(chunks):
    ref = f"U12{k + 1:02d}"
    ux, uy = g(70) + (k % 2) * g(130), g(48) + (k // 2) * g(62)
    u = sh.place("SN74AXC8T245", ref, ux, uy, value="SN74AXC8T245PWR", fields={"LCSC": "C882718"})
    P = u.pin
    # supplies
    sh.wire(P(1), left(P(1), 4)); power_at(sh, "1V8", left(P(1), 4), "up")
    sh.wire(P(2), left(P(2), 4)); power_at(sh, "1V8", left(P(2), 4), "left")       # DIR1 = H
    sh.wire(P(11), left(P(11), 4)); power_at(sh, "GND", left(P(11), 4), "left")    # DIR2 = L
    sh.wire(P(22), left(P(22), 4)); sh.label("j3_oe_n", *left(P(22), 4), 180)
    for n in (12, 13):
        sh.wire(P(n), left(P(n), 4)); power_at(sh, "GND", left(P(n), 4), "left")
    sh.wire(P(24), right(P(24), 4)); power_at(sh, "3V3", right(P(24), 4), "up")
    sh.wire(P(23), right(P(23), 2), right(P(24), 2)); sh.junction(*right(P(24), 2))
    for i in range(8):
        a, b = P(3 + i), P(21 - i)
        if i < len(sigs):
            s = sigs[i]
            hlabel_left(sh, s, a, 6, "input")
            hlabel_right(sh, s + "_3v3", b, 6, "output")
        else:
            sh.no_connect(*b)       # spare channel: the I/Os have internal 288 k pull-downs (may float)
            sh.no_connect(*a)
    # decoupling: 100 n on VCCA and on VCCB
    for j, (rail, cref) in enumerate((("1V8", f"C12{2 * k + 1:02d}"), ("3V3", f"C12{2 * k + 2:02d}"))):
        cx = ux + g(44) + j * g(8)
        _, ct, cb = vert2(sh, "C", cref, cx, uy - g(10), "100n")
        sh.wire(ct, up(ct, 2)); power_at(sh, rail, up(ct, 2), "up")
        sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")

sh.save()
print("12_level_shift:", len(outs), "outputs on", len(chunks), "translators")
