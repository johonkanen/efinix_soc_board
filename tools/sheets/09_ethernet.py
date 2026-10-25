#!/usr/bin/env python3
"""Sheet 9 ethernet: KSZ9031RNX (U901) gigabit PHY, RGMII to the FPGA at 1.8 V, magjack J9 (UDE RB1-125B8G1A).

Values from the Agilex 5 card (a5e_kicad/eth.kicad_sch, ETH_PHY_REVIEW.md):
- RGMII 22 R series resistors (TX at the FPGA end, RX at the PHY end in layout), DVDDH = 1V8.
- Straps: RXD0..3 (MODE0..3) 4k7 pull-ups = RGMII mode with all capabilities; RX_CLK/PHYAD2 and
  RX_DV/CLK125_EN left at their internal pull-downs (PHYAD2 = 0, CLK125 off); LED2/PHYAD1 and LED1/PHYAD0
  1 k to GND -> PHY address 0; CLK125_NDO/LED_MODE 4k7 pull-up = single-LED mode.
- ISET 12.1 k 1 %, 25 MHz crystal with 27 p, AVDDH and AVDDL_PLL behind ferrites.
- RESET_N from the FPGA with a 10 k pull-down: the PHY stays in reset until the FPGA is configured.
Jack LED: LED1 polarity follows its strap (pulled down -> active high), so a 74LVC1G06 (inverting, open drain,
1.8 V input) sinks the 3.3 V jack LED. Verify the polarity at bring-up (MDIO LED override as fallback).
"""
from _common import *  # noqa: F401,F403

sh = sheet("09_ethernet.kicad_sch")
sh.text("KSZ9031RNX gigabit PHY, RGMII at 1.8 V to bank 4B. Values and straps from the Agilex 5 card (address 0,\n"
        "RGMII mode, single-LED mode). J9 = UDE RB1-125B8G1A magjack, placed per MECHANICAL.md.", g(14), g(14))

UX, UY = g(120), g(90)
u = sh.place("KSZ9031RNXCA", "U901", UX, UY, value="KSZ9031RNXCA", fields={"LCSC": "C58758"})
P = {1: ("label", "phy_avddh"), 12: ("label", "phy_avddh"), 44: ("label", "phy_avddl_pll"),
     4: ("power", "1V2"), 9: ("power", "1V2"), 14: ("power", "1V2"), 18: ("power", "1V2"), 23: ("power", "1V2"),
     26: ("power", "1V2"), 30: ("power", "1V2"), 39: ("power", "1V2"),
     16: ("power", "1V8"), 34: ("power", "1V8"), 40: ("power", "1V8"),
     29: ("power", "GND"), 49: ("power", "GND"),
     13: ("nc", None), 47: ("nc", None), 43: ("nc", None),
     48: ("label", "phy_iset"), 45: ("label", "phy_xo"), 46: ("label", "phy_xi"),
     2: ("label", "eth_mdi_a_P"), 3: ("label", "eth_mdi_a_N"), 5: ("label", "eth_mdi_b_P"), 6: ("label", "eth_mdi_b_N"),
     7: ("label", "eth_mdi_c_P"), 8: ("label", "eth_mdi_c_N"), 10: ("label", "eth_mdi_d_P"), 11: ("label", "eth_mdi_d_N"),
     19: ("label", "phy_txd0"), 20: ("label", "phy_txd1"), 21: ("label", "phy_txd2"), 22: ("label", "phy_txd3"),
     25: ("label", "phy_tx_ctl"), 24: ("label", "phy_txc"),
     32: ("label", "phy_rxd0"), 31: ("label", "phy_rxd1"), 28: ("label", "phy_rxd2"), 27: ("label", "phy_rxd3"),
     33: ("label", "phy_rx_ctl"), 35: ("label", "phy_rxc"),
     36: ("hlabel", "eth_mdc"), 37: ("hlabel", "eth_mdio"), 38: ("hlabel", "eth_int_n"), 42: ("hlabel", "eth_rst_n"),
     41: ("label", "phy_led_mode"), 15: ("label", "phy_led2"), 17: ("label", "phy_led1")}
SHAPE = {"eth_mdc": "input", "eth_mdio": "bidirectional", "eth_int_n": "output", "eth_rst_n": "input"}
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

# straps and pulls (labels connect to the nets above)
sh.text("Straps / pulls (1V8): MODE0..3 = 1 (RGMII), LED_MODE = 1 (single LED), PHYAD = 0, MDIO/MDC/INT pull-ups,\n"
        "RESET_N pull-down (PHY held in reset until the FPGA drives it).", g(14), g(112))
pulls = [("rgmii_rxd0", "1V8", "4k7"), ("rgmii_rxd1", "1V8", "4k7"), ("rgmii_rxd2", "1V8", "4k7"),
         ("rgmii_rxd3", "1V8", "4k7"), ("phy_led_mode", "1V8", "4k7"), ("eth_mdio", "1V8", "4k7"),
         ("eth_mdc", "1V8", "4k7"), ("eth_int_n", "1V8", "4k7"), ("phy_led2", "GND", "1k"),
         ("phy_led1", "GND", "1k"), ("eth_rst_n", "GND", "10k"), ("phy_iset", "GND", "12.1k 1%")]
for k, (net, rail, val) in enumerate(pulls):
    pull_r(sh, f"R9{20 + k:02d}", g(16) + (k % 7) * g(9), g(124) + (k // 7) * g(34), net, rail, val)
_, ct, cb = vert2(sh, "C", "C901", g(16) + 5 * g(9), g(158), "100n", text="right")
sh.wire(ct, up(ct, 2)); sh.label("eth_rst_n", *up(ct, 2), 90)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")

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
sh.text("25 MHz crystal 3225, 27 p load (Agilex card values); place at the PHY", g(96), g(174))

# ferrite-fed analog rails
for k, (fb, rail, net) in enumerate((("FB901", "3V3", "phy_avddh"), ("FB902", "1V2", "phy_avddl_pll"))):
    yy = g(184) + k * g(20)
    _, a, b = horiz2(sh, "FerriteBead_Small", fb, g(30), yy, "BLM15PX121SN1D", text="above")
    sh.wire(a, left(a, 2)); power_at(sh, rail, left(a, 2), "left")
    node = right(b, 4); sh.wire(b, node); sh.label(net, *right(node, 16), 0)
    sh.wire(node, right(node, 16))
    for j, (val, fp) in enumerate((("22u", C0805), ("100n", None), ("100n", None))):
        if net == "phy_avddl_pll" and j == 2:
            break
        cx = node[0] + j * g(6)
        cref = f"C9{20 + 3 * k + j:02d}"
        _, ct, cb = vert2(sh, "C", cref, cx, yy + g(5), val, text="right")
        sh.wire((cx, yy), ct)
        if j:
            sh.junction(cx, yy)
        sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
        if fp:
            set_field(sh, cref, "Footprint", fp)
    sh.junction(*node)
    sh.wire(right(node, 16), up(right(node, 16), 3)); sh.pwr_flag(*up(right(node, 16), 3), 0)
sh.text("AVDDH (3V3) and AVDDL_PLL (1V2) through ferrites (Agilex FB1/FB2)", g(14), g(174))

# PHY decoupling
cap_row(sh, g(200), g(150), "1V2", [(f"C9{30 + i:02d}", v, fp) for i, (v, fp) in
                                    enumerate([("10u", C0805)] + [("100n", None)] * 6)],
        "1V2 DVDDL/AVDDL (8 pins): 10u + 6 x 100n")
cap_row(sh, g(200), g(176), "1V8", [(f"C9{40 + i:02d}", v, fp) for i, (v, fp) in
                                    enumerate([("4u7", None)] + [("100n", None)] * 3)],
        "1V8 DVDDH (3 pins): 4u7 + 3 x 100n")

# magjack
J = sh.place("RJ45_RB1-125B8G1A", "J9", g(260), g(90), value="RB1-125B8G1A", fields={"LCSC": "C363353"})
for pin, net in (("R2", "eth_mdi_a_P"), ("R3", "eth_mdi_a_N"), ("R4", "eth_mdi_b_P"), ("R5", "eth_mdi_b_N"),
                 ("R6", "eth_mdi_c_P"), ("R7", "eth_mdi_c_N"), ("R8", "eth_mdi_d_P"), ("R9", "eth_mdi_d_N")):
    attach(sh, J, pin, "label", net, 4)
attach(sh, J, "R1", "label", "eth_ct", 4)
attach(sh, J, "R10", "power", "GND", 3)
attach(sh, J, "SH", "power", "GND", 3)
attach(sh, J, "L1", "nc")
attach(sh, J, "L2", "nc")
attach(sh, J, "L3", "label", "eth_led_a", 4)
attach(sh, J, "L4", "label", "eth_led_k", 4)
_, ct, cb = vert2(sh, "C", "C950", g(258), g(130), "100n", text="right")
sh.wire(ct, up(ct, 2)); sh.label("eth_ct", *up(ct, 2), 90)
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
pull_r(sh, "R950", g(268), g(130), "eth_led_a", "3V3", "330R")
# LED driver: 74LVC1G06 at 1V8, input LED1 (active high with its pull-down strap), output sinks the LED
b = sh.place("74LVC1G06", "U902", g(294), g(130), value="74LVC1G06GW")
attach(sh, b, "2", "label", "phy_led1", 4)
attach(sh, b, "4", "label", "eth_led_k", 4)
attach(sh, b, "5", "power", "1V8", 2)
attach(sh, b, "3", "power", "GND", 2)
_, ct, cb = vert2(sh, "C", "C951", g(312), g(130), "100n", text="right")
sh.wire(ct, up(ct, 2)); power_at(sh, "1V8", up(ct, 2), "up")
sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
sh.text("Jack LED: LED1 (1.8 V, active high with its PHYAD0 pull-down) -> U902 open-drain inverter -> LED cathode;\n"
        "anode via R950 to 3V3. Verify LED1 polarity at bring-up.", g(236), g(114))
sh.save()
print("09_ethernet done")
