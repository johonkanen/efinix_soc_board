#!/usr/bin/env python3
"""Sheet 5 fpga_power: U501 unit 7 (POWER) and unit 8 (GND) with decoupling.

Rails (TI135_PCB_NOTES.md §2): VCORE 0.95 V -> VCC, VDD_SOC, VCC18A_MIPI1_TX/RX (unused MIPI: to VCC),
VCCA_BL/BR/TR through ferrites; 0V85 -> VDD_PHY_DDR, VDDPLL_MCB_TOP_PHY_DDR through a ferrite;
1V1 -> VDDQ_PHY_DDR, VDDQX_PHY_DDR, VDDQ_CK_PHY_DDR; 1V8 -> VCCAUX, VCCIO2A/2B/2C/4A/4B; 3V3 -> VCCIO33_*.
Supply pins of the same name are stacked in the symbol (one visible pin, the rest hidden at the same spot).
Decoupling values are a starting point: check against Efinix's "Titanium Hardware Design Checklist and
Guidelines" (Support Center) and place the 100 n caps under the BGA on the matching balls.
"""
from _common import *  # noqa: F401,F403

sh = sheet("05_fpga_power.kicad_sch")
sh.text("U501 power and ground. Decoupling: starting values, to be checked against the Titanium Hardware Design\n"
        "Checklist; 100 n / 1 u under the BGA at the balls of their rail, bulk next to the BGA.", g(14), g(14))

UX, UY = g(110), g(66)
u = place_unit(sh, "Ti135N484I3", "U501", UX, UY, 7)
P = {}
from p2k.sexpr import find, walk  # noqa: E402
from p2k.sch_builder import lib  # noqa: E402
sym = lib()["Ti135N484I3"]
for sub in sym[2:]:
    if isinstance(sub, list) and str(sub[0]) == "symbol" and sub[1] == "Ti135N484I3_7_1":
        for p in walk(sub, "pin"):
            if not find(p, "hide"):
                P[find(p, "name")[1]] = u.pin(find(p, "number")[1])

RAIL = {"VCC": "VCORE", "VDD_SOC": "VCORE", "VCC18A_MIPI1_RX": "VCORE", "VCC18A_MIPI1_TX": "VCORE",
        "VDD_PHY_DDR": "0V85", "VDDQ_PHY_DDR": "1V1", "VDDQX_PHY_DDR": "1V1", "VDDQ_CK_PHY_DDR": "1V1",
        "VCCAUX": "1V8", "VCCIO2A": "1V8", "VCCIO2B": "1V8", "VCCIO2C": "1V8", "VCCIO4A": "1V8", "VCCIO4B": "1V8",
        "VCCIO33_BR0": "3V3", "VCCIO33_BR1_BL3": "3V3", "VCCIO33_TR1": "3V3"}
FERRITE = {"VCCA_BL": ("FB501", "VCORE"), "VCCA_BR": ("FB502", "VCORE"), "VCCA_TR": ("FB503", "VCORE"),
           "VDDPLL_MCB_TOP_PHY_DDR": ("FB504", "0V85")}
cn = [500]


def cref():
    cn[0] += 1
    return f"C{cn[0]}"


for name, p in P.items():
    left_side = p[0] < UX
    if name in RAIL:
        q = left(p, 4) if left_side else right(p, 4)
        sh.wire(p, q)
        power_at(sh, RAIL[name], q, "left" if left_side else "right")
    elif name in FERRITE:
        sh.wire(p, left(p, 4)); sh.label(name.lower(), *left(p, 4), 180)
    else:
        sh.no_connect(*p)

# ferrite-filtered PLL rails: rail -> ferrite -> label, 1 u + 100 n at the ball side
x0, y0 = g(215), g(92)
sh.text("Ferrite-filtered PLL rails (BLM15PX121SN1D, as on the Agilex card): 1 u + 100 n at the ball side", x0 - g(2), y0 - g(10))
for k, name in enumerate(("VCCA_BL", "VCCA_BR", "VCCA_TR", "VDDPLL_MCB_TOP_PHY_DDR")):
    fb, rail = FERRITE[name]
    y = y0 + k * g(16)
    _, a, b = horiz2(sh, "FerriteBead_Small", fb, x0 + g(8), y, "BLM15PX121SN1D", text="above")
    sh.wire(a, left(a, 3)); power_at(sh, rail, left(a, 3), "left")
    node = right(b, 4)
    sh.wire(b, node)
    for j, val in enumerate(("1u", "100n")):
        cx = node[0] + j * g(8)
        _, ct, cb = vert2(sh, "C", cref(), cx, y + g(5), val, text="right")
        sh.wire((cx, y), ct)
        sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
    sh.wire(node, (node[0] + g(8), y), (node[0] + g(14), y))
    sh.junction(*node); sh.junction(node[0] + g(8), y)
    sh.label(name.lower(), node[0] + g(14), y, 0)
    sh.wire((node[0] + g(14), y), (node[0] + g(14), y - g(3))); sh.pwr_flag(node[0] + g(14), y - g(3), 0)

# GND unit
gu = place_unit(sh, "Ti135N484I3", "U501", g(270), g(50), 8)
gp = next(iter(gu.pins.values()))
sh.wire(gp, left(gp, 4)); power_at(sh, "GND", left(gp, 4), "down")
sh.text("U501 GND: 131 balls (stacked pin). Every GND ball to the GND plane with its own via.", g(240), g(38))


# unused transceiver / MIPI balls (pin type no-connect: leave open, TI135_PCB_NOTES.md §9)
place_unit(sh, "Ti135N484I3", "U501", g(300), g(110), 9)
sh.text("U501 unused: transceivers Q0/Q1 and MIPI1 (pins typed no-connect, leave open; their supplies too)", g(256), g(84))

# decoupling rows (rail above, GND below). The 100n are 0201: under U501 their pads sit straight on a rail/GND
# via pair (0.8 mm pitch, via-in-pad), which an 0402 does not leave room for between the vias (2026-10-27)
def caps(spec):
    out = []
    for val, n, fp in spec:
        out += [(cref(), val, fp) for _ in range(n)]
    return out


ROWS = [
    ("VCORE", "VCORE (VCC x31, VDD_SOC x3, VCC18A_MIPI x2): 2 x 22u, 4 x 4u7, 12 x 100n",
     [("22u", 2, C0805), ("4u7", 4, None), ("100n", 12, C0201)]),
    ("0V85", "0V85 VDD_PHY_DDR x15: 10u, 4 x 1u, 6 x 100n", [("10u", 1, C0805), ("1u", 4, None), ("100n", 6, C0201)]),
    ("1V1", "1V1 VDDQ/VDDQX/VDDQ_CK_PHY_DDR x24: 10u, 4 x 1u, 8 x 100n",
     [("10u", 1, C0805), ("1u", 4, None), ("100n", 8, C0201)]),
    ("1V8", "1V8 VCCAUX x4, VCCIO 2A/2B/2C/4A/4B x11: 10u, 2 x 4u7, 8 x 100n",
     [("10u", 1, C0805), ("4u7", 2, None), ("100n", 8, C0201)]),
    ("3V3", "3V3 VCCIO33 BR0 / BR1_BL3 / TR1: 4u7, 3 x 100n", [("4u7", 1, None), ("100n", 3, C0201)]),
]
for k, (rail, title, spec) in enumerate(ROWS):
    x, y = (g(30), g(112) + k * g(26)) if k < 3 else (g(205), g(172) + (k - 3) * g(26))
    cap_row(sh, x, y, rail, caps(spec), title)
sh.save()
print("05_fpga_power done, caps up to", f"C{cn[0]}")
