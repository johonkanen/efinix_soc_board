#!/usr/bin/env python3
"""Sheet 6 fpga_config: U501 unit 6 (CONFIG: CDONE, CRESET_N, JTAG, JTAG_VCCIO_SEL, REF_RES, VQPS),
configuration straps, SPI flash U601 (active x4), JTAG header J1, LEDs.

Values from TI135_PCB_NOTES.md §4/§8 (AN 033: 10 k for every unspecified configuration pull):
CDONE / CRESET_N pull-ups to 1V8 as on Efinix's Ti375C529 kit (supply still [verify] for Ti135),
JTAG at 3.3 V (VCCIO33_BR1_BL3 = 3V3, JTAG_VCCIO_SEL open), REF_RES 10 k 1 % to GND, VQPS to GND.
J1 keeps the Ti60 card's JTAG pinout (1 TDI, 2 TCK, 3 TMS, 4 TDO, 5 GND).
"""
from _common import *  # noqa: F401,F403

sh = sheet("06_fpga_config.kicad_sch")
n = [0]


def ref(prefix):
    n[0] += 1
    return f"{prefix}6{n[0]:02d}"


def pull_row(x, y, items, title=None):
    """A row of vertical resistors. items: (net, rail, value). The net is a label below the resistor when the
    rail is a supply (pull-up), above it when the rail is GND (pull-down)."""
    if title:
        sh.text(title, x - g(2), y - g(12))
    for k, (net, rail, value) in enumerate(items):
        cx = x + k * g(10)
        _, t, b = vert2(sh, "R", ref("R"), cx, y, value, text="right")
        if rail == "GND":
            sh.wire(t, up(t, 2)); sh.label(net, *up(t, 2), 90)
            sh.wire(b, down(b, 2)); power_at(sh, "GND", down(b, 2), "down")
        else:
            sh.wire(t, up(t, 2)); power_at(sh, rail, up(t, 2), "up")
            sh.wire(b, down(b, 2)); sh.label(net, *down(b, 2), 270)


sh.text("FPGA configuration: SPI active x4 from U601 (SSL_N pulled up = active mode), JTAG on J1.\n"
        "Pull resistors per AN 033 (10 k unless noted) and TI135_PCB_NOTES.md §8.\n"
        "CDONE/CRESET_N pull-ups to 1V8 as on the Efinix Ti375C529 kit - [verify] for Ti135.", g(14), g(14))

# ---------------------------------------------------------------- U501 unit 6
UX, UY = g(110), g(60)
u = place_unit(sh, "Ti135N484I3", "U501", UX, UY, 6)
P = {name: u.pin(ball) for ball, name in
     (("H10", "CDONE"), ("G10", "CRESET_N"), ("F8", "TCK"), ("G9", "TDI"), ("F6", "TDO"), ("F7", "TMS"),
      ("H11", "JTAG_VCCIO_SEL"), ("P16", "REF_RES_2A"), ("L16", "REF_RES_2C"), ("G5", "REF_RES_4A"),
      ("M7", "REF_RES_4B"), ("F9", "VQPS"))}
for name, net in (("CDONE", "fpga_cdone"), ("TCK", "jtag_tck"), ("TDI", "jtag_tdi"), ("TDO", "jtag_tdo"),
                  ("TMS", "jtag_tms")):
    sh.wire(P[name], left(P[name], 6)); sh.label(net, *left(P[name], 6), 180)
hlabel_left(sh, "fpga_creset_n", P["CRESET_N"], 6, "input")
sh.no_connect(*P["JTAG_VCCIO_SEL"])
sh.text("JTAG_VCCIO_SEL open = JTAG at 3.3 V", UX - g(52), P["JTAG_VCCIO_SEL"][1] + 0.5)
rr = ["REF_RES_2A", "REF_RES_2C", "REF_RES_4A", "REF_RES_4B"]
rr.sort(key=lambda k: P[k][1])
for k, name in enumerate(rr):
    xr = P[name][0] + g(4 + 9 * (len(rr) - 1 - k))
    sh.wire(P[name], (xr, P[name][1]))
    _, t, b = vert2(sh, "R", ref("R"), xr, P[rr[-1]][1] + g(8), "10k 1%", text="right")
    sh.wire((xr, P[name][1]), t)
    sh.wire(b, down(b, 2)); power_at(sh, "GND", down(b, 2), "down")
sh.wire(P["VQPS"], right(P["VQPS"], 2), down(right(P["VQPS"], 2), 2))
power_at(sh, "GND", down(right(P["VQPS"], 2), 2), "down")

pull_row(g(30), g(100), [("fpga_cdone", "1V8", "10k"), ("fpga_creset_n", "1V8", "10k"),
                         ("jtag_tck", "3V3", "10k"), ("jtag_tdi", "3V3", "10k"),
                         ("jtag_tdo", "3V3", "10k"), ("jtag_tms", "3V3", "10k")],
         "Config / JTAG pull-ups")

# JTAG header J1 (Ti60 J1 pinout)
j1 = sh.place("Conn_01x05", "J1", g(120), g(110), value="JTAG 3.3V")
for pin, net in ((1, "jtag_tdi"), (2, "jtag_tck"), (3, "jtag_tms"), (4, "jtag_tdo")):
    p = j1.pin(pin)
    sh.wire(p, left(p, 6)); sh.label(net, *left(p, 6), 180)
p = j1.pin(5); sh.wire(p, left(p, 2), down(left(p, 2), 2)); power_at(sh, "GND", down(left(p, 2), 2), "down")
sh.text("J1: JTAG (Ti60 J1 pinout), Efinix cable", g(104), g(102))

# ---------------------------------------------------------------- configuration straps (bank 4A pins, sheet 11)
SX, SY = g(30), g(140)
sh.text("Dual-purpose configuration straps (pins on sheet 11). CBSEL only matters for multi-image boot:\n"
        "fit R615/R616 (pull-downs) only if multi-image boot is used.", SX - g(2), SY - g(16))
for k, net in enumerate(("fpga_csi", "fpga_test_n", "fpga_cbsel0", "fpga_cbsel1")):
    p = (SX + k * g(10), SY + g(14))
    hlabel(sh, net, *p, 270)
    sh.wire(p, up(p, 2)); sh.label(net, *up(p, 2), 90)
pull_row(SX + g(50), SY, [("fpga_csi", "1V8", "10k"), ("fpga_test_n", "1V8", "10k"),
                          ("fpga_cbsel0", "GND", "10k DNP"), ("fpga_cbsel1", "GND", "10k DNP")])

# ---------------------------------------------------------------- SPI flash
FX, FY = g(230), g(60)
f = sh.place("IS25WP128-RHLE", "U601", FX, FY, value="IS25WP128-RHLE", fields={"LCSC": "C1349419"})
F = f.pin
for ball, net, shape in (("C2", "flash_cs_n", "input"), ("B2", "flash_sck", "input")):
    hlabel_left(sh, net, F(ball), 10, shape)
sh.wire(F("A4"), left(F("A4"), 5)); sh.label("flash_rst_n", *left(F("A4"), 5), 180)
for ball, net in (("D3", "flash_io0"), ("D2", "flash_io1"), ("C4", "flash_io2"), ("D4", "flash_io3")):
    hlabel_right(sh, net, F(ball), 10, "bidirectional")
sh.wire(F("B4"), up(F("B4"), 2)); power_at(sh, "1V8", up(F("B4"), 2), "up")
sh.wire(F("B3"), down(F("B3"), 2)); power_at(sh, "GND", down(F("B3"), 2), "down")
_, ct, cb = vert2(sh, "C", ref("C"), FX + g(40), FY - g(4), "100n")
sh.wire(ct, up(ct, 2)); power_at(sh, "1V8", up(ct, 2), "up")
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
pull_row(FX - g(20), FY + g(34), [("flash_cs_n", "1V8", "10k"), ("flash_io2", "1V8", "10k"),
                                  ("flash_io3", "1V8", "10k"), ("flash_rst_n", "1V8", "10k")],
         "U601: SSL_N pull-up selects active SPI mode; WP#/HOLD# pulled up (AN 033 Fig. 4); RESET# has no\n"
         "configuration role on the Ti135 (pulled up). 128 Mbit = 24-bit addressing.")

# ---------------------------------------------------------------- LEDs (3.3 V HVIO pins sink the current)
for k, net in enumerate(("led0_n", "led1_n")):
    x, y = g(250) + k * g(14), g(140)
    _, rt, rb = vert2(sh, "R", ref("R"), x, y, "1k", text="right")
    sh.wire(rt, up(rt, 2)); power_at(sh, "3V3", up(rt, 2), "up")
    _, dt, db = vert2(sh, "LED", f"D6{k + 1:02d}", x, y + g(8), "red", top=2, text="right")
    sh.wire(rb, dt)
    sh.wire(db, down(db, 2))
    hlabel(sh, net, *down(db, 2), 270, "input")
sh.text("User LEDs on 3.3 V HVIO pins (active low)", g(244), g(128))

sh.save()
print("06_fpga_config done")
