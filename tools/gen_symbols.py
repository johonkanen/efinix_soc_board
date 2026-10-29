#!/usr/bin/env python3
"""Project symbol library lib/ti135_card.kicad_sym (tools/p2k symgen).

    tools/gen_symbols.py           write the library
    tools/gen_symbols.py --check   fail if it is out of date

Sources: KiCad 10 standard symbols (copied and renamed), symbols from the Agilex 5 card project
(~/dev/agilex3_soc_control_card), and generated ones: the Ti135N484I3 (from
reference/ti135n484_pinout.csv), SN74AXC8T245 and the KIOXIA eMMC (from their data sheets).
"""
import collections
import copy
import csv
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from p2k.symgen import (IN, OUT, PAS, PI, PO, Sym, box, find, find_all, from_std, load,  # noqa: E402
                        power, rename, run, set_prop, std_symbol)

AGILEX = os.path.expanduser("~/dev/agilex3_soc_control_card")
BIDI, NC = "bidirectional", "no_connect"
G = 2.54


def from_file(path, name, new, ref, value=None, desc=None):
    """Copy symbol `name` from a .kicad_sym library or a schematic's lib_symbols cache."""
    tree = load(path)
    cache = find(tree, "lib_symbols") or tree
    sym = next(s for s in find_all(cache, "symbol") if s[1] in (name, name.split(":")[-1]) or s[1].endswith(":" + name))
    sym = copy.deepcopy(sym)
    sym[1] = sym[1].split(":")[-1]  # cached copies are named "lib:name"; their units "name_u_s"
    rename(sym, new)
    set_prop(sym, "Reference", ref)
    set_prop(sym, "Value", value or new)
    set_prop(sym, "Footprint", "")
    if desc:
        set_prop(sym, "Description", desc)
    return sym


# ------------------------------------------------------------------ Ti135N484I3

def _font():
    return [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]


def _pin(num, name, etype, x, y, rot, hide=False):
    p = [Sym("pin"), Sym(etype), Sym("line"), [Sym("at"), x, y, rot], [Sym("length"), G]]
    if hide:
        p.append([Sym("hide"), Sym("yes")])
    p += [[Sym("name"), name, _font()], [Sym("number"), num, _font()]]
    return p


def ball_key(b):
    """Sort balls A1, A2 ... AB22 in row-major order."""
    i = 0
    while b[i].isalpha():
        i += 1
    return (len(b[:i]), b[:i], int(b[i:]))


def fpga_units():
    """[(unit name, left pins, right pins)], pins = [(ball(s), name, etype)]; a tuple of balls
    is a stack of same-name pins drawn at one position."""
    rows = list(csv.DictReader(open(os.path.join(ROOT, "reference", "ti135n484_pinout.csv"))))
    by = collections.defaultdict(list)
    for r in rows:
        p, bank = r["pad"], r["bank"]
        if p.startswith("DDR_"):
            by["ddr"].append(r)
        elif p.startswith("GPIO"):
            by[{"BL3": "hvio", "BR0": "hvio", "TR1": "hvio", "BR1_BL3": "hvio"}.get(bank, bank)].append(r)
        elif p in ("GND",):
            by["gnd"].append(r)
        elif p.startswith(("Q0_", "Q1_", "MIPI1_", "VCC_SERDES", "VDDA_")) or p == "NC":
            by["unused"].append(r)
        elif p.startswith(("VCC", "VDD")):
            by["power"].append(r)
        else:
            by["config"].append(r)

    def stacks(rs, etype):
        d = collections.OrderedDict()
        for r in sorted(rs, key=lambda r: r["pad"]):
            d.setdefault(r["pad"], []).append(r["ball"])
        return [(tuple(sorted(b, key=ball_key)), n, etype) for n, b in d.items()]

    def gpio_sort(r):
        p = r["pad"].split("_")  # GPIOB_P_12_... / GPIOR_78_...
        if p[0] in ("GPIOB", "GPIOT"):
            return (p[0], int(p[2]), p[1] != "P")
        return (p[0], int(p[1]), False)

    def split(pins):
        h = (len(pins) + 1) // 2
        return pins[:h], pins[h:]

    units = []
    # DDR: data on the left, CA/control on the right
    ddr = sorted(by["ddr"], key=lambda r: r["pad"])
    data = [r for r in ddr if r["pad"].startswith(("DDR_DQ", "DDR_DM"))]

    def dq_key(r):
        p = r["pad"]
        n = int(p[p.index("[") + 1:p.index("]")])
        grp = n // 8 if p.startswith("DDR_DQ[") else n
        order = 0 if p.startswith("DDR_DQ[") else (1 if p.startswith("DDR_DM") else 2)
        return (grp, order, n, p)
    data.sort(key=dq_key)
    ctrl = [r for r in ddr if r not in data]
    ctrl.sort(key=lambda r: (not r["pad"].startswith("DDR_CK"), r["pad"]))
    units.append(("DDR", [((r["ball"],), r["pad"], BIDI) for r in data],
                  [((r["ball"],), r["pad"], PAS if r["pad"] == "DDR_CAL" else OUT) for r in ctrl]))
    for key, title in (("4A", "BANK_4A"), ("4B", "BANK_4B")):
        pins = [((r["ball"],), r["pad"], BIDI) for r in sorted(by[key], key=gpio_sort)]
        units.append((title, *split(pins)))
    top = [((r["ball"],), r["pad"], BIDI) for r in sorted(by["2A"] + by["2B"] + by["2C"], key=gpio_sort)]
    units.append(("BANK_2ABC", *split(top)))
    hv = sorted(by["hvio"], key=gpio_sort)
    units.append(("HVIO", [((r["ball"],), r["pad"], BIDI) for r in hv if r["pad"].startswith("GPIOL")],
                  [((r["ball"],), r["pad"], BIDI) for r in hv if r["pad"].startswith("GPIOR")]))
    cfg = by["config"]
    left = [((r["ball"],), r["pad"], IN if r["pad"] in ("CRESET_N", "TCK", "TDI", "TMS", "JTAG_VCCIO_SEL") else
             OUT if r["pad"] == "TDO" else BIDI if r["pad"] == "CDONE" else PAS)
            for r in sorted(cfg, key=lambda r: r["pad"]) if not r["pad"].startswith(("REF_RES", "VQPS"))]
    right = [((r["ball"],), r["pad"], PAS) for r in sorted(cfg, key=lambda r: r["pad"])
             if r["pad"].startswith(("REF_RES", "VQPS"))]
    units.append(("CONFIG", left, right))
    pw = stacks(by["power"], PI)
    core = [p for p in pw if p[1] in ("VCC", "VDD_SOC") or p[1].startswith(("VCCA_", "VCC18A"))]
    io = [p for p in pw if p not in core and not "PHY_DDR" in p[1]]
    ddrp = [p for p in pw if "PHY_DDR" in p[1]]
    units.append(("POWER", core + [None] + ddrp, io))
    units.append(("GND", stacks(by["gnd"], PI), []))
    un = [((r["ball"],), r["pad"], NC) for r in sorted(by["unused"], key=lambda r: r["pad"])]
    units.append(("UNUSED", *split(un)))
    return units


def fpga_symbol():
    name = "Ti135N484I3"
    units = fpga_units()
    sym = [Sym("symbol"), name, [Sym("pin_names"), [Sym("offset"), 1.016]],
           [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")]]
    body = []
    top_max = 0
    for u, (title, left, right) in enumerate(units, 1):
        def ml(pl):
            return max([len(p[1]) for p in pl if p] + [0])
        width = max(20.32, (ml(left) + ml(right)) * 1.27 + 7.62)
        hw = -(-width / 2 // G) * G
        rows = max(len(left), len(right), 1)
        ytop = -(-(rows - 1) // 2) * G
        top_y, bot_y = ytop + G, ytop - rows * G
        top_max = max(top_max, top_y)
        pins = []
        for side, pl in (("L", left), ("R", right)):
            for i, p in enumerate(pl):
                if not p:
                    continue
                balls, pname, et = p
                x = -hw - G if side == "L" else hw + G
                y = ytop - i * G
                for k, b in enumerate(balls):
                    # stacked duplicates are hidden *passive* pins: a hidden power-input pin would become an
                    # implicit global net named after the pin (KiCad), joining unrelated nets by name
                    pins.append(_pin(b, pname, et if k == 0 else PAS, x, y, 0 if side == "L" else 180, hide=k > 0))
        body.append([Sym("symbol"), f"{name}_{u}_1",
                     [Sym("rectangle"), [Sym("start"), -hw, top_y], [Sym("end"), hw, bot_y],
                      [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
                      [Sym("fill"), [Sym("type"), Sym("background")]]],
                     [Sym("text"), title, [Sym("at"), 0, top_y - 1.5, 0], _font()],
                     *pins])
    sym += [
        [Sym("property"), "Reference", "U", [Sym("at"), 0, top_max + 5.08, 0], _font()],
        [Sym("property"), "Value", name, [Sym("at"), 0, top_max + 2.54, 0], _font()],
        [Sym("property"), "Footprint", "Package_BGA:LFBGA-484_18x18mm_Layout22x22_P0.8mm", [Sym("at"), 0, 0, 0],
         [Sym("hide"), Sym("yes")], _font()],
        [Sym("property"), "Datasheet", "https://www.efinixinc.com/docs-html/dsti135/", [Sym("at"), 0, 0, 0],
         [Sym("hide"), Sym("yes")], _font()],
        [Sym("property"), "Description",
         "Efinix Titanium Ti135 FPGA, 484-ball FBGA 18x18 mm 0.8 mm, industrial grade 3. Units: "
         + ", ".join(f"{i}={u[0]}" for i, u in enumerate(units, 1)), [Sym("at"), 0, 0, 0],
         [Sym("hide"), Sym("yes")], _font()],
        *body, [Sym("embedded_fonts"), Sym("no")]]
    return sym


# ------------------------------------------------------------------ boxes

def axc8t245():
    left = [(1, "VCCA", PI), (2, "DIR1", IN), (11, "DIR2", IN), (22, "~{OE}", IN), None] + \
        [(2 + i, f"A{i}", BIDI) for i in range(1, 9)] + [None, (12, "GND", PI), (13, "GND", PI)]
    right = [(24, "VCCB", PI), (23, "VCCB", PI), None, None, None] + \
        [(22 - i, f"B{i}", BIDI) for i in range(1, 9)]
    s = box("SN74AXC8T245", "U", left, right, value="SN74AXC8T245PWR",
            desc="8-bit dual-supply bus transceiver, 0.65-3.6 V, TSSOP-24 (TI SCES875C). DIR1 sets bits 1-4, DIR2 bits 5-8")
    set_prop(s, "Datasheet", "https://www.ti.com/lit/ds/symlink/sn74axc8t245.pdf")
    return s


def emmc():
    left = [("M6", "CLK", IN), ("M5", "CMD", BIDI), ("H5", "DS", OUT), ("K5", "RST_n", IN), None] + \
        [(b, f"DAT{i}", BIDI) for i, b in enumerate(["A3", "A4", "A5", "B2", "B3", "B4", "B5", "B6"])]
    right = [("E6", "VCC", PI), ("F5", "VCC", PI), ("J10", "VCC", PI), ("K9", "VCC", PI), None,
             ("C6", "VCCQ", PI), ("M4", "VCCQ", PI), ("N4", "VCCQ", PI), ("P3", "VCCQ", PI), ("P5", "VCCQ", PI), None,
             ("C2", "VDDi", PO), None,
             ("A6", "VSS", PI), ("E7", "VSS", PI), ("G5", "VSS", PI), ("H10", "VSS", PI), ("J5", "VSS", PI),
             ("K8", "VSS", PI), ("C4", "VSSQ", PI), ("N2", "VSSQ", PI), ("N5", "VSSQ", PI), ("P4", "VSSQ", PI),
             ("P6", "VSSQ", PI)]
    s = box("THGAMVG7T13BAIL", "U", left, right,
            desc="KIOXIA e-MMC 5.1, 16 GB, 153-ball 11.5x13 mm 0.5 mm. VCCQ 1.8 V only. NC/RFU/VSF balls not shown (leave open)")
    set_prop(s, "Datasheet", "https://www.lcsc.com/datasheet/C7599693.pdf")
    return s


def hr911130a():
    left = [(2, "MDI0+", PAS), (3, "MDI0-", PAS), (4, "MDI1+", PAS), (7, "MDI1-", PAS), (5, "MDI2+", PAS),
            (6, "MDI2-", PAS), (8, "MDI3+", PAS), (9, "MDI3-", PAS), None, (1, "TCT", PAS), (10, "CHS", PAS)]
    right = [(11, "LEDG_A", PAS), (12, "LEDG_K", PAS), None, (14, "LEDY_A", PAS), (13, "LEDY_K", PAS), None,
             ("SH", "SHIELD", PAS)]
    s = box("HR911130A", "J", left, right, value="HR911130A",
            desc="HanRun RJ45 with 10/100/1000Base-T magnetics, green (11 A / 12 K) and yellow (14 A / 13 K) LEDs. "
                 "TCT = chip-side centre taps, CHS = 75 R / 1000 p Bob Smith common (LCSC C54408)")
    set_prop(s, "Datasheet", "https://datasheet.lcsc.com/datasheet/pdf/d9b1e130e54a44fe9872ced55aa393e4.pdf")
    return s


def rtl8211fd():
    """Realtek RTL8211FD(I)-CG, 40-pin QFN 5x5 0.4 mm, from the data sheet Rev. 1.7 (Table 1-9). Strap functions
    in the pin names: RXD3/RXC/RXCTL = PHYAD0..2, RXD2 = PLLOFF, RXD1 = TXDLY, RXD0 = RXDLY, LED0 = CFG_EXT,
    LED1/LED2 = CFG_LDO0/1."""
    left = [(20, "TXC", IN), (19, "TXCTL", IN), (18, "TXD0", IN), (17, "TXD1", IN), (16, "TXD2", IN),
            (15, "TXD3", IN), None,
            (27, "RXC/PHYAD1", BIDI), (26, "RXCTL/PHYAD2", BIDI), (25, "RXD0/RXDLY", BIDI),
            (24, "RXD1/TXDLY", BIDI), (23, "RXD2/PLLOFF", BIDI), (22, "RXD3/PHYAD0", BIDI), None,
            (13, "MDC", IN), (14, "MDIO", BIDI), (31, "INTB/PMEB", "open_collector"), (12, "PHYRSTB", IN), None,
            (36, "XTAL_IN", IN), (37, "XTAL_OUT", OUT), (35, "CLKOUT", OUT)]
    right = [(1, "MDIP0", BIDI), (2, "MDIN0", BIDI), (4, "MDIP1", BIDI), (5, "MDIN1", BIDI), (6, "MDIP2", BIDI),
             (7, "MDIN2", BIDI), (9, "MDIP3", BIDI), (10, "MDIN3", BIDI), None,
             (32, "LED0/CFG_EXT", BIDI), (33, "LED1/CFG_LDO0", BIDI), (34, "LED2/CFG_LDO1", BIDI), None,
             (39, "RSET", PAS), (30, "LDO_OUT", PO), (28, "DVDD_RG", PO)]
    top = [(11, "AVDD33", PI), (40, "AVDD33", PI), (29, "DVDD33", PI), (3, "AVDD10", PI), (8, "AVDD10", PI),
           (38, "AVDD10", PI), (21, "DVDD10", PI)]
    s = box("RTL8211FD", "U", left, right, top=top, bottom=[(41, "GND", PI)], value="RTL8211FDI-CG",
            desc="Realtek 10/100/1000 PHY, RGMII, 3.3 V single supply with 1.0 V core LDO (LDO_OUT -> AVDD10/DVDD10) "
                 "and RGMII pad LDO (DVDD_RG), QFN-40 5x5 (LCSC C692886)")
    set_prop(s, "Datasheet", "https://static.chipdip.ru/lib/595/DOC042595102.pdf")
    return s


def tlv62585p():
    left = [(3, "VIN", PI), (4, "EN", IN)]
    right = [(2, "SW", PO), (5, "FB", IN), (6, "PG", "open_collector")]
    s = box("TLV62585PDRL", "U", left, right, bottom=[(1, "GND", PI)], value="TLV62585PDRLR",
            desc="TI 3 A synchronous buck, 2.5-5.5 V in, 0.6 V FB, power good, SOT-563 (PDRL)")
    set_prop(s, "Datasheet", "https://www.ti.com/lit/ds/symlink/tlv62585.pdf")
    return s


def qspi_flash():
    """IS25WP128-RHLE, 24-ball TFBGA 6x8 mm (same ball map as MX25U25645G / MT25QU). NC/DNU balls omitted."""
    left = [("C2", "CS#", IN), ("B2", "SCLK", IN), ("A4", "RESET#", IN)]
    right = [("D3", "SI/IO0", BIDI), ("D2", "SO/IO1", BIDI), ("C4", "WP#/IO2", BIDI), ("D4", "HOLD#/IO3", BIDI)]
    s = box("IS25WP128-RHLE", "U", left, right, top=[("B4", "VCC", PI)], bottom=[("B3", "GND", PI)],
            desc="ISSI 128 Mbit 1.8 V QSPI NOR flash, 24-ball TFBGA 6x8 mm, dedicated RESET# on A4")
    set_prop(s, "Datasheet", "https://www.issi.com/WW/pdf/25LP-WP128F.pdf")
    return s


def build():
    std = [
        from_std("Device", "R", "R", "R"),
        from_std("Device", "C", "C", "C"),
        from_std("Device", "L", "L", "L"),
        from_std("Device", "L", "L_Power", "L", desc="Power inductor 4x4 mm (regulator output)"),
        from_std("Device", "FerriteBead_Small", "FerriteBead_Small", "FB"),
        from_std("Device", "LED", "LED", "D"),
        from_std("Device", "R_Pack04", "R_Pack04", "RN"),
        from_std("Device", "Crystal_GND24", "Crystal_GND24", "Y"),
        from_std("Connector_Generic", "Conn_02x19_Odd_Even", "Conn_02x19_Odd_Even", "J"),
        from_std("Connector_Generic", "Conn_02x03_Odd_Even", "Conn_02x03_Odd_Even", "J"),
        from_std("Connector_Generic", "Conn_01x14", "Conn_01x14", "J"),
        from_std("Connector_Generic", "Conn_01x05", "Conn_01x05", "J"),
        from_std("Connector_Generic", "Conn_01x03", "Conn_01x03", "J"),
        from_std("Connector_Generic", "Conn_01x02", "Conn_01x02", "J"),
        from_std("Oscillator", "ASE-xxxMHz", "OT322525MJBA4SL", "Y",
                 desc="YXC OT322525MJBA4SL 25 MHz CMOS oscillator, 1.8-3.3 V, 3225 (LCSC C669088); pin 1 EN"),
        from_std("Analog_Switch", "CD4051B", "CD4051B", "U"),
        from_std("Amplifier_Operational", "AD8603", "AD8603", "U"),
        from_std("Amplifier_Operational", "OPA365xxDBV", "OPA365xxDBV", "U"),
        from_std("74xGxx", "74LVC1G07", "74LVC1G07", "U"),
        from_std("Regulator_Switching", "AP61202Z6", "AP61202Z6", "U"),
        from_std("Regulator_Linear", "NCP163ASN330T1G", "NCP163ASN330T1G", "U"),
        from_std("Power_Supervisor", "TPS3808DBV", "TPS3808DBV", "U"),
        from_std("Memory_RAM", "IS43LQ32256A-062BLI", "H9HCNNN8KUMLHR-NME", "U",
                 desc="SK hynix LPDDR4 8 Gb, 2 channels x16, 1 rank, 200-ball 10x15 mm. Same ball map as "
                      "IS43LQ32256A (symbol copied from it)"),
    ]
    lib = os.path.join(AGILEX, "agilex_5_lib", "agilex_5_lib.kicad_sym")
    clk = os.path.join(AGILEX, "a5e_kicad", "clk.kicad_sch")
    agx = [
        from_file(lib, "ADS7056", "ADS7056", "U"),
        from_file(lib, "TDA38812", "TDA38812", "U"),
        from_file(clk, "SIT8924BA-73-18N-25.000000", "SIT8924BA-73-18N-25.000000", "Y"),
    ]
    pwr = [power(n, n == "GND") for n in ("GND", "5V0", "VCORE", "0V85", "1V1", "1V8", "3V3", "3V3_analog")]
    pwr.append(rename(std_symbol("power", "PWR_FLAG"), "PWR_FLAG"))
    syms = std + agx + [fpga_symbol(), axc8t245(), emmc(), qspi_flash(), tlv62585p(), rtl8211fd(), hr911130a()] + pwr
    for sym in syms:
        # hidden power-input pins become implicit global nets named after the pin in KiCad; they are stacked on a
        # visible pin anyway, so make them passive (same treatment as the generated Ti135 symbol)
        from p2k.symgen import walk
        for pin in walk(sym, "pin"):
            if find(pin, "hide") and str(pin[1]) == "power_in":
                pin[1] = Sym("passive")
        if sym[1] in FOOTPRINT:
            set_prop(sym, "Footprint", FOOTPRINT[sym[1]])
    return syms


# Default footprint per symbol (the Agilex card's choices where the part is the same). Per-refdes overrides
# go into lib/footprint_map.csv.
FOOTPRINT = {
    "R": "Resistor_SMD:R_0402_1005Metric",
    "C": "Capacitor_SMD:C_0402_1005Metric",
    "L": "Inductor_SMD:L_0805_2012Metric",
    "L_Power": "Inductor_SMD:L_Coilcraft_XxL4020",
    "TLV62585PDRL": "Package_TO_SOT_SMD:SOT-563",
    "FerriteBead_Small": "Inductor_SMD:L_0402_1005Metric",
    "LED": "LED_SMD:LED_0603_1608Metric",
    "R_Pack04": "Resistor_SMD:R_Array_Convex_4x0402",
    "Crystal_GND24": "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    "Conn_02x19_Odd_Even": "ti135_card:PinSocket_2x19_P1.27mm_Vertical_Drill0.6",   # 0.9/0.6 pads: a track fits between pins
    "Conn_02x03_Odd_Even": "Connector_PinSocket_1.27mm:PinSocket_2x03_P1.27mm_Vertical",
    "Conn_01x14": "Connector_PinHeader_2.54mm:PinHeader_1x14_P2.54mm_Vertical",
    "Conn_01x05": "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
    "Conn_01x03": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    "Conn_01x02": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    "OT322525MJBA4SL": "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm",
    "RTL8211FD": "Package_DFN_QFN:QFN-40-1EP_5x5mm_P0.4mm_EP3.6x3.6mm_ThermalVias",
    "HR911130A": "ti135_card:RJ45_Hanrun_HR911130A_Horizontal",
    "CD4051B": "Package_SO:TSSOP-16_4.4x5mm_P0.65mm",
    "AD8603": "Package_TO_SOT_SMD:TSOT-23-5",
    "OPA365xxDBV": "Package_TO_SOT_SMD:SOT-23-5",
    "74LVC1G07": "Package_TO_SOT_SMD:SOT-353_SC-70-5",
    "AP61202Z6": "Package_TO_SOT_SMD:SOT-563",
    "NCP163ASN330T1G": "Package_TO_SOT_SMD:SOT-23-5",
    "TPS3808DBV": "Package_TO_SOT_SMD:SOT-23-6",
    "H9HCNNN8KUMLHR-NME": "ti135_card:BGA-200_10x15mm_Layout12x22_P0.8x0.65mm",
    "ADS7056": "ti135_card:ads7056",
    "TDA38812": "ti135_card:TDA38812",
    "IS25WP128-RHLE": "ti135_card:MX25U25645G_CSP24_6x8mm_P1.0mm",
    "SIT8924BA-73-18N-25.000000": "Oscillator:Oscillator_SMD_SiT_PQFN-4Pin_2.0x1.6mm",
    "SN74AXC8T245": "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm",
    "THGAMVG7T13BAIL": "Package_BGA:LFBGA-153_11.5x13mm_Layout14x14_P0.5mm",
}


if __name__ == "__main__":
    sys.exit(run(build))
