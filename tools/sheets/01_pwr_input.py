#!/usr/bin/env python3
"""Sheet 1 pwr_input: J6 = baseboard J12 (5V_ISOL / ISOGND), input bulk capacitance, 3V3_analog LDO.

J6 pin n = baseboard J12 pin 42 + n: pins 1/3/5 = GND (baseboard ISOGND), 2/4/6 = 5V0 (baseboard 5V_ISOL,
from baseboard U8, see POWER_BUDGET.md). Card GND is the baseboard's ISOGND domain.
"""
from _common import *  # noqa: F401,F403

sh = sheet("01_pwr_input.kicad_sch")
sh.text("J6 = baseboard J12 (2x3 1.27 mm on B.Cu, MECHANICAL.md): 5V0 = baseboard 5V_ISOL, GND = ISOGND.\n"
        "Supply budget and limits: POWER_BUDGET.md (baseboard U8 to be upgraded to 1.5-2 A).", g(14), g(14))

j6 = sh.place("Conn_02x03_Odd_Even", "J6", g(40), g(50), value="2x3 1.27mm (bottom)")
for pin in (1, 3, 5):
    p = j6.pin(pin); sh.wire(p, left(p, 4)); power_at(sh, "GND", left(p, 4), "left")
rail = right(j6.pin(2), 6)
for pin in (2, 4, 6):
    p = j6.pin(pin); sh.wire(p, (rail[0], p[1]))
sh.wire((rail[0], j6.pin(2)[1]), (rail[0], j6.pin(6)[1]))
sh.junction(rail[0], j6.pin(4)[1]); sh.junction(*rail)
top = up(rail, 6)
sh.wire(rail, top)
power_at(sh, "5V0", top, "up")
sh.wire(top, right(top, 2)); sh.pwr_flag(*right(top, 2), 270)
gf = (g(24), g(60)); power_at(sh, "GND", gf, "down"); sh.wire(gf, up(gf, 2)); sh.pwr_flag(*up(gf, 2), 0)

# J101: 2.54 mm 1x2 bench supply input next to J6 (female jumpers), for running the card without the baseboard
j = sh.place("Conn_01x02", "J101", g(40), g(76), value="5V0 bench input")
a = left(j.pin("1"), 4); sh.wire(j.pin("1"), a); sh.wire(a, up(a, 2)); power_at(sh, "5V0", up(a, 2), "up")
b = left(j.pin("2"), 8); sh.wire(j.pin("2"), b); sh.wire(b, down(b, 2)); power_at(sh, "GND", down(b, 2), "down")
sh.text("J101: 2.54 mm 1x2 header near J6 to power the card from a bench supply with female jumpers,\n"
        "without the baseboard (pin 1 = 5V0, pin 2 = GND). Do not feed it while the baseboard powers J6.", g(14), g(86))

# bulk input capacitance on 5V0
for k, (ref, val, fp) in enumerate((("C101", "47u", C1206), ("C102", "22u", C0805), ("C103", "100n", None))):
    x = g(70) + k * g(8)
    _, ct, cb = vert2(sh, "C", ref, x, g(52), val, text="right")
    sh.wire(ct, up(ct, 2)); power_at(sh, "5V0", up(ct, 2), "up")
    sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
    if fp:
        set_field(sh, ref, "Footprint", fp)
sh.text("Input bulk (the regulators also have their own 10u).", g(66), g(40))

# 3V3_analog for the ADC block (as on the Agilex card)
u = sh.place("NCP163ASN330T1G", "U101", g(140), g(52), value="NCP163ASN330T1G")
vin, gnd, en, nc, vout = u.pin(1), u.pin(2), u.pin(3), u.pin(4), u.pin(5)
n = left(vin, 6)
sh.wire(vin, n); sh.wire(n, up(n, 2)); power_at(sh, "5V0", up(n, 2), "up")
sh.wire(en, (n[0], en[1]), n); sh.junction(*n)
sh.no_connect(*nc)
sh.wire(gnd, down(gnd, 2)); power_at(sh, "GND", down(gnd, 2), "down")
_, ct, cb = vert2(sh, "C", "C104", n[0] - g(4), n[1] + g(6), "1u", text="left")
sh.wire(n, (ct[0], n[1]), ct)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
o = right(vout, 6)
sh.wire(vout, o)
_, ct, cb = vert2(sh, "C", "C105", o[0], o[1] + g(6), "1u", text="right")
sh.wire(o, ct); sh.junction(*o)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
sh.wire(o, up(o, 3)); power_at(sh, "3V3_analog", up(o, 3), "up")
sh.text("3V3_analog: LDO for the ADC block (sheet 13).", g(124), g(40))
sh.save()
print("01_pwr_input done")
