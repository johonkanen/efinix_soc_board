#!/usr/bin/env python3
"""Sheet 13 adc: 8:1 mux -> unity-gain buffer -> ADS7056 (14 bit, 2.5 MSPS), front end from the Agilex 3 card
(~/dev/ti60f225_control_card docs/design-notes.md, "ADC front end for 2.5 MSPS"):

- SN74LV4051A mux on 3V3_analog, selects adbsel0..2_3v3 from the translators (3.3 V), INH to GND (the Agilex 5
  card tied INH to 3V3_analog, which disables the mux). X0 = GND as a zero reference.
- OPA365 buffer (50 MHz; the ADS7056 kickback RC needs UGB >= 28 MHz, the Agilex 5 AD8603 was far too slow).
- Kickback RC at AINP: 33 R + 680 p C0G (ADS7056 data sheet 2.5 MSPS design).
- AVDD = reference: 4u7 0603 + 100 n at the pin. DVDD = 1V8 (SPI on bank 2C at 1.8 V).
- CS / SCLK / SDO 33 R series (60 MHz SCLK). Capture SDO with a phase-shifted clock (design note).
Mux inputs: X1..X3, X5 monitor card rails (as on the Agilex 5 card); X4/X6/X7 = isoada2/3/1 from J3.
"""
from _common import *  # noqa: F401,F403

sh = sheet("13_adc.kicad_sch")
sh.text("ADC chain: mux U1301 -> buffer U1302 -> ADS7056 U1303 (front end as on the Agilex 3 card, 2.5 MSPS design).\n"
        "Mux: X0 GND (zero ref), X1 VCORE, X2 1V8, X3 3V3/2, X4 isoada2, X5 1V1, X6 isoada3, X7 isoada1.\n"
        "Full scale 0..3.3 V (AVDD = reference). The FPGA maps the channel numbers.", g(14), g(14))

# mux
m = sh.place("CD4051B", "U1301", g(80), g(80), value="SN74LV4051APWR", fields={"LCSC": "C7793"})
attach(sh, m, "13", "power", "GND", 3)                         # X0 = zero reference
for pin, net in (("14", "mon_vcore"), ("15", "mon_1v8"), ("12", "mon_3v3"), ("1", "isoada2"),
                 ("5", "mon_1v1"), ("2", "isoada3"), ("4", "isoada1")):
    attach(sh, m, pin, "hlabel" if net.startswith("isoada") else "label", net, 4)
for pin, net in (("11", "adbsel0_3v3"), ("10", "adbsel1_3v3"), ("9", "adbsel2_3v3")):
    attach(sh, m, pin, "hlabel", net, 4, shape="input")
for pin in ("6", "7", "8"):
    attach(sh, m, pin, "power", "GND", 3)
attach(sh, m, "16", "power", "3V3_analog", 3)
attach(sh, m, "3", "label", "adc_mux_out", 4)
cap_row(sh, g(60), g(120), "3V3_analog", [("C1301", "1u", None)], "U1301 VDD")

# rail monitors (series R limits current into the mux when unpowered)
sh.text("Rail monitors", g(14), g(140))
for k, (rail, net, val) in enumerate((("VCORE", "mon_vcore", "100R"), ("1V8", "mon_1v8", "1k"),
                                      ("3V3", "mon_3v3", "1k"), ("1V1", "mon_1v1", "1k"))):
    pull_r(sh, f"R13{k + 1:02d}", g(18) + k * g(8), g(152), net, rail, val)
pull_r(sh, "R1305", g(18) + 4 * g(8), g(152), "mon_3v3", "GND", "1k")
sh.text("3V3 via 1k/1k divider", g(46), g(166))

# buffer
b = sh.place("OPA365xxDBV", "U1302", g(160), g(80), value="OPA365AIDBVR", fields={"LCSC": "C96626"})
attach(sh, b, "3", "label", "adc_mux_out", 4)
out = b.pin("1")
nin = b.pin("4")
node = right(out, 4)
sh.wire(out, node)
sh.wire(nin, (nin[0], nin[1] + g(4)), (node[0], nin[1] + g(4)), node)
sh.junction(*node)
attach(sh, b, "5", "power", "3V3_analog", 2)
attach(sh, b, "2", "power", "GND", 2)
_, a, r = horiz2(sh, "R", "R1306", node[0] + g(6), node[1], "33R", text="above")
sh.wire(node, a)
ainp = right(r, 4)
sh.wire(r, ainp)
_, ct, cb = vert2(sh, "C", "C1302", ainp[0], ainp[1] + g(5), "680p C0G", text="right")
sh.wire(ainp, ct); sh.junction(*ainp)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
sh.wire(ainp, right(ainp, 4)); sh.label("adc_ainp", *right(ainp, 4), 0)
cap_row(sh, g(150), g(120), "3V3_analog", [("C1303", "100n", None)], "U1302 V+")

# ADC
a7 = sh.place("ADS7056", "U1303", g(250), g(80), value="ADS7056IRUGR", fields={"LCSC": "C2669798"})
attach(sh, a7, "7", "label", "adc_ainp", 4)
attach(sh, a7, "8", "power", "GND", 3)
attach(sh, a7, "5", "power", "GND", 3)
attach(sh, a7, "6", "power", "3V3_analog", 3)
attach(sh, a7, "4", "power", "1V8", 7)
for pin, net in (("1", "adc_cs_n_r"), ("3", "adc_sclk_r"), ("2", "adc_sdo_r")):
    attach(sh, a7, pin, "label", net, 4)
cap_row(sh, g(230), g(120), "3V3_analog", [("C1304", "4u7", "Capacitor_SMD:C_0603_1608Metric"), ("C1305", "100n", None)],
        "AVDD = reference: 4u7 0603 + 100n at the pin")
cap_row(sh, g(290), g(120), "1V8", [("C1306", "1u", None)], "DVDD 1V8")
sh.text("SPI series 33 R (60 MHz SCLK)", g(220), g(140))
for k, (fpga, local, shape) in enumerate((("adc_cs_n", "adc_cs_n_r", "input"), ("adc_sclk", "adc_sclk_r", "input"),
                                          ("adc_sdo", "adc_sdo_r", "output"))):
    series_r(sh, f"R13{10 + k:02d}", g(240), g(148) + k * g(5), "33R", "hlabel", fpga, "label", local, shape)
sh.save()
print("13_adc done")
