#!/usr/bin/env python3
"""Sheet 14 connectors: J3 (baseboard J11, 2x19 1.27 mm socket on the bottom) with 10 k pull-downs,
J5 LCD/touch header (Ti60 J4 pinout), J2 FPGA UART header (Ti60 J8 pinout).

J3 pin n = baseboard J11 pin n (reference/baseboard_j11_pinout.csv, MECHANICAL.md).
Net names: FPGA outputs reach J3 through the level translators (sheet 12); the J3 side is <name>_3v3.
The four modulator/ADC data inputs go straight to 3.3 V HVIO pins (sheet 11). ISOADA1..3 are the
analog inputs of the on-board mux (sheet 13). J5 and J2 are wired straight to 3.3 V HVIO pins.
Connector refs J2/J3/J5 are kept from the Ti60/Agilex cards (MECHANICAL.md uses them).
"""
from _common import *  # noqa: F401,F403

sh = sheet("14_connectors.kicad_sch")
bb = baseboard_j11()


def j3_net(pin):
    r = bb[pin]
    sig, d = r["signal"], r["direction_from_control_card"]
    if d == "out":
        return sig.lower() + "_3v3", "input"
    if d == "in":
        return sig.lower(), "output"
    if d == "analog":
        return sig.lower(), "passive"
    return None, d


sh.text("J3 = baseboard J11 (2x19 1.27 mm socket on B.Cu, pin n = baseboard pin n, see MECHANICAL.md).\n"
        "Every signal pin has a 10 k pull-down so the power board sees low while the FPGA is unconfigured\n"
        "and the translators are disabled (MIGRATION_PLAN.md 3.2).", g(14), g(14))

# ---- J3
JX, JY = g(70), g(34)
j3 = sh.place("Conn_02x19_Odd_Even", "J3", JX, JY, value="2x19 1.27mm socket (bottom)")
pulled = []
for pin in range(1, 39):
    p = j3.pin(pin)
    net, kind = j3_net(pin)
    side = "left" if pin % 2 else "right"
    if kind == "gnd":
        q = left(p, 4) if side == "left" else right(p, 4)
        sh.wire(p, q)
        power_at(sh, "GND", q, side)
    elif kind == "nc":
        sh.no_connect(*p)
    else:
        (hlabel_left if side == "left" else hlabel_right)(sh, net, p, 6, kind)
        if kind != "passive":
            pulled.append(net)

# ---- pull-down packs: 8 x 4 x 10 k (4D02WGJ0103TCE), signal on pins 1-4, GND on 5-8
PX, PY = g(140), g(34)
for k in range(0, len(pulled), 4):
    nets = pulled[k:k + 4]
    i = k // 4
    x, y = PX + (i % 4) * g(24), PY + (i // 4) * g(44)
    rn = sh.place("R_Pack04", f"RN14{i + 1:02d}", x, y, value="4x10k",
                  fields={"MPN": "4D02WGJ0103TCE", "LCSC": "C25725"})
    for j, net in enumerate(nets):
        top = rn.pin(1 + j)        # pins 1..4 at the bottom of the symbol
        q = down(top, 2 + 2 * j)
        sh.wire(top, q)
        sh.label(net, *q, 270)
    gnds = [rn.pin(n) for n in (5, 6, 7, 8)]
    ytop = up(gnds[0], 2)
    for gp in gnds:
        sh.wire(gp, (gp[0], ytop[1]))
    sh.wire((gnds[-1][0], ytop[1]), (gnds[0][0], ytop[1]))
    for gp in gnds[1:-1]:
        sh.junction(gp[0], ytop[1])
    sh.junction(gnds[0][0], ytop[1])
    q = up((gnds[0][0], ytop[1]), 2)
    sh.wire((gnds[0][0], ytop[1]), q)
    power_at(sh, "GND", q, "up")

# ---- J5 LCD + touch (2.8" SPI TFT module), Ti60 J4 pinout, 3.3 V straight from HVIO
lcd = ["t_irq", "t_do", "t_din", "t_cs_n", "t_clk", "lcd_mosi", "lcd_led", "lcd_sck", "lcd_miso",
       "lcd_dc", "lcd_reset_n", "lcd_cs_n"]
shape = {"t_irq": "output", "t_do": "output", "lcd_miso": "output"}
j5 = sh.place("Conn_01x14", "J5", g(60), g(120), value="LCD 1x14 2.54mm")
for i, net in enumerate(lcd, 1):
    hlabel_left(sh, net, j5.pin(i), 6, shape.get(net, "input"))
p = j5.pin(13)
sh.wire(p, left(p, 4)); power_at(sh, "GND", left(p, 4), "left")
p = j5.pin(14)
sh.wire(p, left(p, 4)); power_at(sh, "3V3", left(p, 4), "left")
sh.text("J5: LCD/touch header, Ti60 J4 pinout (wired to the LCD with jumper wires).", g(30), g(104))

# ---- J2 FPGA UART (3.3 V), Ti60 J8 pinout: 1 = RX into the FPGA, 2 = TX, 3 = GND; 1 k series
j2 = sh.place("Conn_01x03", "J2", g(150), g(140), value="UART 3.3V")
_, a, b = horiz2(sh, "R", "R1401", g(132), j2.pin(1)[1], "1k", text="above")
sh.wire(b, j2.pin(1))
hlabel_left(sh, "uart_rx", a, 4, "output")
_, a, b = horiz2(sh, "R", "R1402", g(132), j2.pin(2)[1], "1k", text="below")
sh.wire(b, j2.pin(2))
hlabel_left(sh, "uart_tx", a, 4, "input")
p = j2.pin(3)
sh.wire(p, left(p, 2), down(left(p, 2), 2)); power_at(sh, "GND", down(left(p, 2), 2), "down")
sh.text("J2: FPGA UART, Ti60 J8 pinout.", g(124), g(131))

sh.save()
print("14_connectors:", len(pulled), "pull-downs")
