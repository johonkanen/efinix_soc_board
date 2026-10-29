#!/usr/bin/env python3
"""Sheet 7 clocks: 25 MHz 1.8 V oscillator Y701 (YXC OT322525MJBA4SL, 3225, LCSC C669088; it replaced the SiT8924 of
the Agilex card, which JLC does not stock) fanned out to the three
PLL reference pins that clock the hard RISC-V and the DDR block (TI135_PCB_NOTES.md §6.4):
refclk_bl0 = N7 (PLL_BL0, SoC system clock), refclk_bl1 = R3 (PLL_BL1, SoC memory clock),
refclk_bl2 = L2 (PLL_BL2, DDR). Each of these PLLs has only one 1.8 V reference pin.

Fan-out: one 33 R source-series resistor per branch at the oscillator, three short point-to-point traces
(star, all three pins are close together in bank 4B). A 1:4 LVCMOS buffer is the fallback if the
SI check of the star is poor.
"""
from _common import *  # noqa: F401,F403

sh = sheet("07_clocks.kicad_sch")
sh.text("25 MHz reference: Y701 -> 3 x 33 R (at Y701) -> PLL_BL0/BL1/BL2 reference pins N7/R3/L2 (bank 4B, 1.8 V).\n"
        "Star from the oscillator, one series resistor per branch; keep the branches short and similar in length.",
        g(14), g(14))
y = sh.place("OT322525MJBA4SL", "Y701", g(60), g(50), value="OT322525MJBA4SL", fields={"LCSC": "C669088"})
en, gnd, out, vdd = (y.pin(k) for k in (1, 2, 3, 4))
a = left(en, 2); sh.wire(en, a); sh.wire(a, up(a, 3)); power_at(sh, "1V8", up(a, 3), "up")   # EN high: always on
sh.wire(vdd, up(vdd, 3)); power_at(sh, "1V8", up(vdd, 3), "up")
sh.wire(gnd, down(gnd, 3)); power_at(sh, "GND", down(gnd, 3), "down")
_, ct, cb = vert2(sh, "C", "C701", g(40), g(45), "100n", text="left")
sh.wire(ct, up(ct, 2)); power_at(sh, "1V8", up(ct, 2), "up")
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
node = right(out, 4)
sh.wire(out, node)
for k, net in enumerate(("refclk_bl0", "refclk_bl1", "refclk_bl2")):
    yy = node[1] + (k - 1) * g(8)
    _, a, b = horiz2(sh, "R", f"R70{k + 1}", node[0] + g(12), yy, "33R", text="above")
    sh.wire(node, (node[0], yy), a)
    hlabel_right(sh, net, b, 6, "output")
sh.junction(*node)
sh.save()
print("07_clocks done")
