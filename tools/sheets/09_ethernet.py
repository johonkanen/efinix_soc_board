#!/usr/bin/env python3
"""Sheet 9 ethernet: RTL8211FDI-CG (U901) gigabit PHY, RGMII to the FPGA at 1.8 V, magjack J9 (HanRun HR911130A, C54408).

Realtek RTL8211F(I)/FD(I) data sheet Rev. 1.7 (2026-10-25: replaces the KSZ9031RNX, 16 orderable at JLC; the
RTL8211FDI-CG C692886 has ~8.5k, and the Agilex 5 card makes the same change):
- One 3.3 V supply. LDO_OUT (pin 30, FD(I) = LDO, no inductor) feeds only AVDD10/DVDD10, caps only.
- RGMII and MDIO pads run from the internal pad LDO at 1.8 V: CFG_EXT (LED0) = 0, CFG_LDO[1:0] (LED2, LED1) = 10.
  DVDD_RG (pin 28) is that LDO's output: caps only. The defaults (CFG_LDO = 01) would give 2.5 V, so all three
  straps are fitted. All other pins (PHYRSTB, INTB, LEDs, clock) are 3.3 V pins (Table 58).
- Straps 4k7 (Table 11: an external pull is required): PHYAD = 001 (RXD3 up, RXC/RXCTL down), PLLOFF 0, TXDLY 0,
  RXDLY 1 (the chip defaults). Linux realtek.c sets both RGMII delays from phy-mode = "rgmii-id" anyway.
- PHYRSTB: VIH 2.0 V (3.3 V pin), so the FPGA's 1.8 V eth_rst_n drives it through U902 (74LVC1G07, open drain,
  10 k to 3V3). R933 holds eth_rst_n low -> PHY in reset until the FPGA is configured (>= 10 ms low required).
- INTB is open drain ("supports 3.3 V pull-up"): pulled up to 1V8 for the bank 4B input.
- RSET 2.49 k 1 %, 25 MHz crystal with 27 p (Agilex card values), AVDD33 behind a ferrite.
- 3V3 rise time must be >= 0.5 ms (Table 53): the TLV62585 soft start is ~1 ms.
Jack LED: LED2 strapped high -> active low, so it sinks the green LED directly (anode via R950 330 R to 3V3).
LED2's default function is link-at-1000 only: set LCR (page 0xd04 reg 0x10) for link/activity at all speeds.
"""
from _common import *  # noqa: F401,F403

sh = sheet("09_ethernet.kicad_sch")
sh.text("RTL8211FDI-CG gigabit PHY, RGMII at 1.8 V (internal pad LDO) to bank 4B, PHY address 1. 3.3 V only: core 1.0 V\n"
        "from its own LDO. J9 = HanRun HR911130A magjack (green LED from LED2, yellow spare), placed per MECHANICAL.md.",
        g(14), g(14))

UX, UY = g(120), g(90)
u = sh.place("RTL8211FD", "U901", UX, UY, value="RTL8211FDI-CG", fields={"LCSC": "C692886"})
P = {11: ("label", "phy_avdd33"), 40: ("label", "phy_avdd33"), 29: ("power", "3V3"),
     3: ("label", "phy_vdd10"), 8: ("label", "phy_vdd10"), 38: ("label", "phy_vdd10"), 21: ("label", "phy_vdd10"),
     30: ("label", "phy_vdd10"), 28: ("label", "phy_dvdd_rg"), 41: ("power", "GND"),
     35: ("nc", None), 39: ("label", "phy_rset"), 36: ("label", "phy_xi"), 37: ("label", "phy_xo"),
     1: ("label", "eth_mdi_a_P"), 2: ("label", "eth_mdi_a_N"), 4: ("label", "eth_mdi_b_P"), 5: ("label", "eth_mdi_b_N"),
     6: ("label", "eth_mdi_c_P"), 7: ("label", "eth_mdi_c_N"), 9: ("label", "eth_mdi_d_P"), 10: ("label", "eth_mdi_d_N"),
     18: ("label", "phy_txd0"), 17: ("label", "phy_txd1"), 16: ("label", "phy_txd2"), 15: ("label", "phy_txd3"),
     19: ("label", "phy_tx_ctl"), 20: ("label", "phy_txc"),
     25: ("label", "phy_rxd0"), 24: ("label", "phy_rxd1"), 23: ("label", "phy_rxd2"), 22: ("label", "phy_rxd3"),
     26: ("label", "phy_rx_ctl"), 27: ("label", "phy_rxc"),
     13: ("hlabel", "eth_mdc"), 14: ("hlabel", "eth_mdio"), 31: ("hlabel", "eth_int_n"), 12: ("label", "phy_rstb"),
     32: ("label", "phy_led0"), 33: ("label", "phy_led1"), 34: ("label", "eth_led_k")}
SHAPE = {"eth_mdc": "input", "eth_mdio": "bidirectional", "eth_int_n": "output"}
for pin, (kind, name) in P.items():
    attach(sh, u, pin, kind, name, n=4, shape=SHAPE.get(name, "passive"))

# RGMII series resistors 22 R: FPGA side = hierarchical label (pin plan names), PHY side = local label
RG = [("rgmii_txc", "phy_txc", "input"), ("rgmii_tx_ctl", "phy_tx_ctl", "input"),
      ("rgmii_txd0", "phy_txd0", "input"), ("rgmii_txd1", "phy_txd1", "input"),
      ("rgmii_txd2", "phy_txd2", "input"), ("rgmii_txd3", "phy_txd3", "input"),
      ("rgmii_rxc", "phy_rxc", "output"), ("rgmii_rx_ctl", "phy_rx_ctl", "output"),
      ("rgmii_rxd0", "phy_rxd0", "output"), ("rgmii_rxd1", "phy_rxd1", "output"),
      ("rgmii_rxd2", "phy_rxd2", "output"), ("rgmii_rxd3", "phy_rxd3", "output")]
sh.text("RGMII series 22 R: TX at the FPGA, RX at the PHY (source side)", g(14), g(36))
for k, (fpga, phy, shape) in enumerate(RG):
    series_r(sh, f"R9{k + 1:02d}", g(30), g(42) + k * g(5), "22R", "hlabel", fpga, "label", phy, shape)


def pull_to_net(ref, x, y, net, top_net, value):
    """Vertical resistor between two labels (a strap to the PHY's own DVDD_RG pad supply)."""
    _, t, b = vert2(sh, "R", ref, x, y, value, text="right")
    sh.wire(t, up(t, 2)); sh.label(top_net, *up(t, 2), 90)
    sh.wire(b, down(b, 2)); sh.label(net, *down(b, 2), 270)


# straps and pulls (labels connect to the nets above)
sh.text("Straps 4k7: PHYAD = 001 (RXD3 up, RXC/RXCTL down), PLLOFF/TXDLY = 0, RXDLY = 1 (RX pins to DVDD_RG);\n"
        "CFG_EXT = 0 (LED0 down), CFG_LDO = 10 (LED1 down, LED2 up to 3V3) -> 1.8 V RGMII pads. MDIO/INT_N pull-ups.",
        g(14), g(112))
pulls = [("R920", "phy_rxd3", "phy_dvdd_rg", "4k7"), ("R921", "phy_rxc", "GND", "4k7"),
         ("R922", "phy_rx_ctl", "GND", "4k7"), ("R923", "phy_rxd2", "GND", "4k7"),
         ("R924", "phy_rxd1", "GND", "4k7"), ("R925", "phy_rxd0", "phy_dvdd_rg", "4k7"),
         ("R926", "phy_led0", "GND", "4k7"), ("R927", "phy_led1", "GND", "4k7"),
         ("R928", "eth_led_k", "3V3", "4k7"), ("R929", "eth_mdio", "1V8", "4k7"),
         ("R930", "eth_int_n", "1V8", "4k7"), ("R931", "phy_rset", "GND", "2.49k 1%")]
for k, (ref, net, rail, val) in enumerate(pulls):
    x, y = g(16) + (k % 7) * g(9), g(124) + (k // 7) * g(34)
    if rail.startswith("phy_"):
        pull_to_net(ref, x, y, net, rail, val)
    else:
        pull_r(sh, ref, x, y, net, rail, val)

# reset level shift: eth_rst_n (1.8 V, FPGA) -> U902 open drain -> PHYRSTB (3.3 V input, VIH 2.0 V)
b = sh.place("74LVC1G07", "U902", g(90), g(158), value="74LVC1G07GW", fields={"LCSC": "C282345"})
attach(sh, b, "2", "hlabel", "eth_rst_n", 4, shape="input")
attach(sh, b, "4", "label", "phy_rstb", 4)
attach(sh, b, "5", "power", "1V8", 2)
attach(sh, b, "3", "power", "GND", 2)
attach(sh, b, "1", "nc")
pull_r(sh, "R932", g(108), g(150), "phy_rstb", "3V3", "10k")
pull_r(sh, "R933", g(70), g(150), "eth_rst_n", "GND", "10k")
for ref, x, top in (("C901", g(116), ("label", "phy_rstb")), ("C951", g(124), ("power", "1V8"))):
    _, ct, cb = vert2(sh, "C", ref, x, g(150), "100n", text="right")
    sh.wire(ct, up(ct, 2))
    if top[0] == "label":
        sh.label(top[1], *up(ct, 2), 90)
    else:
        power_at(sh, top[1], up(ct, 2), "up")
    sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
sh.text("PHYRSTB is a 3.3 V input: U902 74LVC1G07 (1V8 supply) open drain, R932 10k to 3V3, C901 filter.\n"
        "R933 holds eth_rst_n low until the FPGA drives it (PHY in reset during configuration).", g(66), g(140))

# crystal
y = sh.place("Crystal_GND24", "Y901", g(110), g(186), value="25MHz")
attach(sh, y, "1", "label", "phy_xi", 3)
attach(sh, y, "3", "label", "phy_xo", 3)
for pin in ("2", "4"):
    attach(sh, y, pin, "power", "GND", 2)
for k, net in enumerate(("phy_xi", "phy_xo")):
    _, ct, cb = vert2(sh, "C", f"C9{10 + k:02d}", g(130) + k * g(8), g(186), "27p", text="right")
    sh.wire(ct, up(ct, 2)); sh.label(net, *up(ct, 2), 90)
    sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
sh.text("25 MHz crystal 3225, 27 p load (Agilex card values), +/-50 ppm total; place at the PHY", g(96), g(174))


def label_caps(x, y, net, caps, title):
    """Decoupling row on a local net (label above, GND below)."""
    sh.text(title, x + g(4), y - g(10))
    top = bot = None
    for k, (ref, val, fp) in enumerate(caps):
        cx = x + k * g(7)
        _, ct, cb = vert2(sh, "C", ref, cx, y, val, text="right")
        t, bb = up(ct, 2), down(cb, 2)
        sh.wire(ct, t); sh.wire(cb, bb)
        if top:
            sh.wire(top, t); sh.wire(bot, bb)
            if k < len(caps) - 1:
                sh.junction(*t); sh.junction(*bb)
        else:
            sh.wire(t, up(t, 2)); sh.label(net, *up(t, 2), 90)
            sh.wire(bb, down(bb, 2)); power_at(sh, "GND", down(bb, 2), "down")
            if len(caps) > 1:
                sh.junction(*t); sh.junction(*bb)
        top, bot = t, bb
        if fp:
            set_field(sh, ref, "Footprint", fp)


# AVDD33 through a ferrite
yy = g(184)
_, a, bb = horiz2(sh, "FerriteBead_Small", "FB901", g(30), yy, "BLM15PX121SN1D", text="above")
sh.wire(a, left(a, 2)); power_at(sh, "3V3", left(a, 2), "left")
node = right(bb, 4); sh.wire(bb, node); sh.label("phy_avdd33", *right(node, 16), 0)
sh.wire(node, right(node, 16))
for j, (val, fp) in enumerate((("10u", C0805), ("100n", None), ("100n", None))):
    cx = node[0] + j * g(6)
    cref = f"C9{20 + j:02d}"
    _, ct, cb = vert2(sh, "C", cref, cx, yy + g(5), val, text="right")
    sh.wire((cx, yy), ct)
    if j:
        sh.junction(cx, yy)
    sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
    if fp:
        set_field(sh, cref, "Footprint", fp)
sh.junction(*node)
sh.wire(right(node, 16), up(right(node, 16), 3)); sh.pwr_flag(*up(right(node, 16), 3), 0)
sh.text("AVDD33 (pins 11, 40) through a ferrite: 10u + 2 x 100n", g(14), g(174))

# PHY decoupling
label_caps(g(200), g(150), "phy_vdd10", [("C930", "1u", None)] + [(f"C9{31 + i}", "100n", None) for i in range(4)],
           "LDO_OUT 1.0 V -> AVDD10 (3, 8, 38) + DVDD10 (21) only: 1u + 4 x 100n (>= 0.1u, Table 9.2)")
label_caps(g(200), g(176), "phy_dvdd_rg", [("C935", "1u", None), ("C936", "100n", None)],
           "DVDD_RG: RGMII pad LDO output (1.8 V), caps only")
cap_row(sh, g(240), g(176), "3V3", [("C940", "1u", None), ("C941", "100n", None)], "DVDD33 (pin 29)")

# magjack HanRun HR911130A (LCSC C54408, chosen 2026-10-25 for stock; MECHANICAL.md J9)
J = sh.place("HR911130A", "J9", g(260), g(90), value="HR911130A", fields={"LCSC": "C54408"})
for pin, net in (("2", "eth_mdi_a_P"), ("3", "eth_mdi_a_N"), ("4", "eth_mdi_b_P"), ("7", "eth_mdi_b_N"),
                 ("5", "eth_mdi_c_P"), ("6", "eth_mdi_c_N"), ("8", "eth_mdi_d_P"), ("9", "eth_mdi_d_N")):
    attach(sh, J, pin, "label", net, 4)
attach(sh, J, "1", "label", "eth_ct", 4)
attach(sh, J, "10", "power", "GND", 3)
attach(sh, J, "SH", "power", "GND", 3)
attach(sh, J, "11", "label", "eth_led_a", 4)
attach(sh, J, "12", "label", "eth_led_k", 4)
attach(sh, J, "14", "nc")
attach(sh, J, "13", "nc")
_, ct, cb = vert2(sh, "C", "C950", g(258), g(130), "100n", text="right")
sh.wire(ct, up(ct, 2)); sh.label("eth_ct", *up(ct, 2), 90)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
pull_r(sh, "R950", g(268), g(130), "eth_led_a", "3V3", "330R")
sh.text("Jack LED: green anode via R950 to 3V3, cathode on PHY LED2 (3.3 V pin, active low with its CFG_LDO1\n"
        "pull-up R928). Program LCR for link/activity.", g(236), g(114))
sh.save()
print("09_ethernet done")
