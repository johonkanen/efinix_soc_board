"""Pin plan for the Ti135N484I3 control card, built with the Efinity Interface Designer API.

Run (Efinity 2026.1):
    source ~/efinity/2026.1/bin/setup.sh
    python3 efinity/pinplan/pinplan.py

Creates efinity/pinplan/build/ti135_pinplan.peri.xml (open it in Interface Designer), runs the design
check, and writes efinity/pinplan/ti135_pinplan.csv (signal -> ball) for the KiCad schematic.

Board orientation assumed (see MIGRATION_PLAN.md and TI135_PCB_NOTES.md): the BGA is rotated 180 deg
relative to the data-sheet ball map, so the DDR balls (rows U-AB) face the LPDDR4 in the north,
banks 2A/2B/2C face west (J3 + level translators, ADC), banks 4A/4B face east (flash, eMMC, Ethernet).

Outputs that pass through the SN74AXC8T245 translators are all the same direction, so any translator
channel may carry any of them: the ball <-> J3 order can be swapped freely during layout.
"""

import csv
import os
import sys

sys.path.append(os.environ["EFXPT_HOME"] + "/bin")
from api_service.design import DesignAPI  # noqa: E402
import api_service.excp.design_excp as DesignException  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
DEVICE = "Ti135N484"

# (name, direction, pad, group, note)
# direction: in, out, inout, clkin (GCLK input), pllref (made by gen_pll_ref_clock)
SIGNALS = [
    # --- bank 4A: SPI flash (dual-purpose configuration pins, user access after configuration) ---
    ("flash_cs_n", "out", "GPIOB_N_25_SSL_N", "flash", "SSL_N: 10k pull-up (active SPI mode)"),
    ("flash_sck", "out", "GPIOB_P_26_CCK", "flash", "CCK"),
    ("flash_io0", "inout", "GPIOB_N_27_CDI0_CLK10_N", "flash", "CDI0"),
    ("flash_io1", "inout", "GPIOB_P_27_CDI1_CLK10_P", "flash", "CDI1"),
    ("flash_io2", "inout", "GPIOB_N_26_CDI2", "flash", "CDI2: 10k pull-up (WP#)"),
    ("flash_io3", "inout", "GPIOB_P_25_CDI3_PLLIN0", "flash", "CDI3: 10k pull-up (HOLD#)"),
    # --- bank 4A: eMMC (1.8 V, KIOXIA THGAMVG7T13BAIL) ---
    ("emmc_clk", "out", "GPIOB_P_20_EXTSPICLK_CLK6_P", "emmc", ""),
    ("emmc_cmd", "inout", "GPIOB_N_18_CLK5_N", "emmc", "4.7-100k pull-up"),
    ("emmc_dat0", "inout", "GPIOB_N_22", "emmc", "10-100k pull-up"),
    ("emmc_dat1", "inout", "GPIOB_N_24_CDI4", "emmc", "10-100k pull-up"),
    ("emmc_dat2", "inout", "GPIOB_P_24_CDI5_EXTFB", "emmc", "10-100k pull-up"),
    ("emmc_dat3", "inout", "GPIOB_P_22_EXTFB", "emmc", "10-100k pull-up"),
    ("emmc_dat4", "inout", "GPIOB_P_23_CDI7_PLLIN0", "emmc", "10-100k pull-up"),
    ("emmc_dat5", "inout", "GPIOB_N_23_CDI6", "emmc", "10-100k pull-up"),
    ("emmc_dat6", "inout", "GPIOB_N_21_CLK7_N", "emmc", "10-100k pull-up"),
    ("emmc_dat7", "inout", "GPIOB_P_18_CLK5_P", "emmc", "10-100k pull-up"),
    ("emmc_ds", "clkin", "GPIOB_P_21_CLK7_P", "emmc", "HS400 data strobe on a GCLK pin; 10-100k pull-down"),
    ("emmc_rst_n", "out", "GPIOB_P_28_CSO_CLK11_P", "emmc", "CSO pin, free after configuration"),
    # --- bank 4A: status ---

    # --- bank 4B: RGMII to RTL8211FDI (1.8 V pads from its internal LDO) ---
    ("rgmii_rxc", "clkin", "GPIOB_P_14_CLK1_P", "eth", "GCLK, clock region B1"),
    ("rgmii_rx_ctl", "in", "GPIOB_N_12_CDI12", "eth", "region B1"),
    ("rgmii_rxd0", "in", "GPIOB_P_12_CDI13", "eth", "region B1"),
    ("rgmii_rxd1", "in", "GPIOB_N_14_CLK1_N", "eth", "region B1"),
    ("rgmii_rxd2", "in", "GPIOB_N_11_CDI14", "eth", "region B0/B1"),
    ("rgmii_rxd3", "in", "GPIOB_P_11_CDI15", "eth", "region B0/B1"),
    ("rgmii_txc", "out", "GPIOB_N_00", "eth", ""),
    ("rgmii_tx_ctl", "out", "GPIOB_N_03", "eth", ""),
    ("rgmii_txd0", "out", "GPIOB_N_04", "eth", ""),
    ("rgmii_txd1", "out", "GPIOB_N_05", "eth", ""),
    ("rgmii_txd2", "out", "GPIOB_N_07_CDI16", "eth", ""),
    ("rgmii_txd3", "out", "GPIOB_P_05", "eth", ""),
    ("eth_mdc", "out", "GPIOB_N_06_CDI18", "eth", ""),
    ("eth_mdio", "inout", "GPIOB_N_08", "eth", "pull-up at the PHY"),
    ("eth_int_n", "in", "GPIOB_N_09", "eth", "pull-up"),
    ("eth_rst_n", "out", "GPIOB_P_08", "eth", "pull-down/RC at the PHY"),
    # --- bank 4B: J3 translator control and one slow translated output ---
    ("j3_oe_n", "out", "GPIOB_P_09", "j3ctl", "OE of all 4 translators, 10k pull-up to 1V8"),
    ("gpio_bypass_rly_isolated", "out", "GPIOB_P_04_EXTFB", "j3out", "via translator"),
    # --- banks 2A/2B/2C: 30 J3 / mux outputs through the translators (order is free) ---
    ("pwm_q5", "out", "GPIOT_P_21", "j3out", ""),
    ("pwm_q6", "out", "GPIOT_N_21", "j3out", ""),
    ("pwm_q7", "out", "GPIOT_P_22_CLK16_P", "j3out", ""),
    ("pwm_q8", "out", "GPIOT_N_22_CLK16_N", "j3out", ""),
    ("pwm_trans1_iso", "out", "GPIOT_P_23_CLK17_P", "j3out", ""),
    ("pwm_trans2_iso", "out", "GPIOT_N_23_CLK17_N", "j3out", ""),
    ("pwm_trans3_iso", "out", "GPIOT_P_24_CLK18_P", "j3out", ""),
    ("pwm_trans4", "out", "GPIOT_N_24_CLK18_N", "j3out", ""),
    ("pwm_trans5", "out", "GPIOT_P_25_CLK19_P", "j3out", ""),
    ("pwm_trans6", "out", "GPIOT_N_25_CLK19_N", "j3out", ""),
    ("pwm_g1_iso", "out", "GPIOT_P_17", "j3out", ""),
    ("pwm_g2_iso", "out", "GPIOT_N_17", "j3out", ""),
    ("pwm_g3_iso", "out", "GPIOT_P_18", "j3out", ""),
    ("pwm_g4_iso", "out", "GPIOT_N_18", "j3out", ""),
    ("dab_pwm_pri_hi_iso", "out", "GPIOT_P_19_EXTFB", "j3out", ""),
    ("dab_pwm_pri_lo_iso", "out", "GPIOT_N_19", "j3out", ""),
    ("dab_pwm_hi_sec", "out", "GPIOT_P_20_PLLIN0", "j3out", ""),
    ("dab_pwm_lo_sec", "out", "GPIOT_N_20", "j3out", ""),
    ("adclk_iso", "out", "GPIOT_P_00_CLK26_P", "j3out", ""),
    ("inu_adclk", "out", "GPIOT_N_01_CLK27_N", "j3out", ""),
    ("adclk_dab", "out", "GPIOT_P_01_CLK27_P", "j3out", ""),
    ("clk1_iso", "out", "GPIOT_N_02", "j3out", ""),
    ("cs1_iso", "out", "GPIOT_P_02", "j3out", ""),
    ("adasel0_iso", "out", "GPIOT_N_04_CLK31_N", "j3out", ""),
    ("adasel1_iso", "out", "GPIOT_P_04_CLK31_P", "j3out", ""),
    ("adasel2_iso", "out", "GPIOT_P_34_PLLIN0", "j3out", ""),
    ("gpio_bypass_rly_iso", "out", "GPIOT_N_34", "j3out", ""),
    ("adbsel0", "out", "GPIOT_P_35", "j3out", "on-board CD4051 mux select (3.3 V via translator)"),
    ("adbsel1", "out", "GPIOT_N_35", "j3out", ""),
    ("adbsel2", "out", "GPIOT_P_39_CLK15_P", "j3out", ""),
    # --- bank 2C: ADS7056 SPI (DVDD = 1V8) ---
    ("adc_cs_n", "out", "GPIOT_N_37_CDI22", "adc", ""),
    ("adc_sclk", "out", "GPIOT_P_37_CDI23_PLLIN0", "adc", ""),
    ("adc_sdo", "in", "GPIOT_N_39_CLK15_N", "adc", ""),
    # --- HVIO TR1 (3.3 V): J3 inputs and LCD/touch inputs ---
    ("mdata_inu", "in", "GPIOR_78_PLLIN1", "j3in", ""),
    ("mdata_dab", "in", "GPIOR_79", "j3in", ""),
    ("mdata_iso", "in", "GPIOR_80_CLK12", "j3in", ""),
    ("sdata1_iso", "in", "GPIOR_81_CLK13", "j3in", ""),
    ("lcd_miso", "in", "GPIOR_82", "lcd", ""),
    ("t_do", "in", "GPIOR_83", "lcd", ""),
    ("t_irq", "in", "GPIOR_84", "lcd", ""),
    # --- HVIO BR0 (3.3 V): LCD outputs ---
    ("lcd_cs_n", "out", "GPIOR_127_CLK8", "lcd", ""),
    ("lcd_reset_n", "out", "GPIOR_128_CLK9", "lcd", ""),
    ("lcd_dc", "out", "GPIOR_129_PLLIN1", "lcd", ""),
    ("lcd_sck", "out", "GPIOR_130_PLLIN1", "lcd", ""),
    ("lcd_mosi", "out", "GPIOR_131_PERST_Q0_N", "lcd", ""),
    ("lcd_led", "out", "GPIOR_132", "lcd", ""),
    # --- HVIO BR1_BL3 (3.3 V): touch outputs, FPGA UART ---
    ("t_cs_n", "out", "GPIOL_26_CLK24", "lcd", ""),
    ("t_clk", "out", "GPIOL_27_CLK25", "lcd", ""),
    ("t_din", "out", "GPIOL_28", "lcd", ""),
    ("uart_tx", "out", "GPIOL_31", "uart", ""),
    ("uart_rx", "in", "GPIOL_33", "uart", "pull-up"),
    # LEDs on 3.3 V HVIO (a green LED does not light from a 1.8 V pin): LED + 1 k from 3V3, pin sinks
    ("led0_n", "out", "GPIOL_32_PLLIN1", "led", "active low"),
    ("led1_n", "out", "GPIOL_34_PLLIN1", "led", "active low"),
]

# PLL resource -> (reference GPIO instance name, outputs {CLKOUTn_FREQ: MHz})
REF_MHZ = "25"
PLLS = {
    # hard RISC-V system clock = Clock 0 = PLL_BL0, plus RGMII TX 125 MHz at 0 and 90 deg.
    # Frequencies are placeholders for the pin plan; the real clock plan comes with the FPGA design.
    # (CLKOUT0 is the local feedback clock: it fixes VCO/M, so keep it at 100 MHz here)
    "PLL_BL0": ("refclk_bl0", {"CLKOUT0_FREQ": "100.0", "CLKOUT1_FREQ": "125.0", "CLKOUT2_FREQ": "125.0",
                               "CLKOUT2_PHASE": "90"}),
    # hard RISC-V memory clock = Clock 1 = PLL_BL1
    "PLL_BL1": ("refclk_bl1", {"CLKOUT0_FREQ": "100.0", "CLKOUT1_FREQ": "200.0"}),
    # DDR (CLKIN 2 = PLL_BL2): CLKOUT3 = 2 x CLKOUT4, 0 deg. Placeholder rate until the LPDDR4 rate is chosen.
    "PLL_BL2": ("refclk_bl2", {"CLKOUT0_FREQ": "100.0", "CLKOUT3_FREQ": "400.0", "CLKOUT4_FREQ": "200.0"}),
}


def resource(pad):
    """Interface Designer GPIO resource name for a package pad name (GPIOB_P_26_CCK -> GPIOB_P_26)."""
    parts = pad.split("_")
    return "_".join(parts[:3] if parts[0] in ("GPIOB", "GPIOT") else parts[:2])


def make_gpio(d, name, direction, pad):
    create = {
        "in": d.create_input_gpio,
        "out": d.create_output_gpio,
        "inout": d.create_inout_gpio,
        "clkin": d.create_input_clock_gpio,
    }[direction]
    g = create(name)
    d.assign_resource(g, resource(pad))
    if pad.startswith(("GPIOL", "GPIOR")):  # HVIO banks run at 3.3 V
        d.set_property(g, "IO_STANDARD", "3.3 V LVCMOS")
    return g


def main():
    os.makedirs(BUILD, exist_ok=True)
    d = DesignAPI(False)
    d.create("ti135_pinplan", DEVICE, BUILD, overwrite=True)

    for name, direction, pad, _grp, _note in SIGNALS:
        make_gpio(d, name, direction, pad)

    for res, (ref, outs) in PLLS.items():
        inst = "pll_" + res[4:].lower()
        d.create_block(inst, block_type="PLL")
        d.gen_pll_ref_clock(inst, pll_res=res, refclk_src="EXTERNAL", refclk_name=ref, ext_refclk_no="0")
        en = {k.replace("_FREQ", "_EN"): "1" for k in outs if k.endswith("_FREQ")}
        en["REFCLK_FREQ"] = REF_MHZ
        d.set_property(inst, en, block_type="PLL")
        d.auto_calc_pll_clock(inst, outs)

    d.create_block("ddr", block_type="DDR")
    d.assign_resource("ddr", "DDR_0", block_type="DDR")
    d.set_property("ddr", {
        "MEMORY_TYPE": "LPDDR4",
        "DQ_WIDTH": "32",
        "PHYSICAL_RANK": "1",
        "MEMORY_DENSITY": "4G",  # per channel: H9HCNNN8KUMLHR = 2 x 4 Gb
        "CLKIN_SEL": "CLKIN 2",
        "TARGET0_EN": "1",
        "TARGET1_EN": "0",  # AXI 1 is not available when the hard RISC-V (QCRV32) is used
        "AXI0_CLK_INPUT_PIN": "ddr_axi0_clk",
        "CTRL_CLK_PIN": "ddr_ctrl_clk",
    }, block_type="DDR")

    d.create_block("soc_jtag", block_type="JTAG")
    d.assign_resource("soc_jtag", "JTAG_USER1", block_type="JTAG")
    d.create_block("soc", block_type="SOC")
    d.assign_resource("soc", "SOC_0", block_type="SOC")
    d.set_property("soc", {"SYS_CLK_SOURCE": "Clock 0", "MEM_CLK_SOURCE": "Clock 1",
                           "IO_PERIPHERALCLK_PIN": "soc_periph_clk"}, block_type="SOC")

    try:
        ok = d.check_design()
    except DesignException.PTDsgCheckException as excp:
        ok = False
        print("design check exception:", excp.get_msg())
    issues = d.get_design_check_issue()
    print("design check passed" if ok else "design check FAILED")
    for i in issues:
        print("  ", i)

    d.save()
    d.export_design(isf_file=os.path.join(BUILD, "ti135_pinplan.isf"))
    try:
        d.generate(enable_bitstream=False)  # constraints + reports in build/outflow
    except Exception as excp:  # noqa: BLE001  (reports are a convenience; the CSV below is the result)
        print("generate failed:", excp)
    for res in PLLS:
        print(res, d.calc_pll_clock("pll_" + res[4:].lower()))

    # signal -> ball table
    pads = {}
    with open(os.path.join(HERE, "..", "..", "reference", "ti135n484_pinout.csv")) as f:
        for row in csv.DictReader(f):
            pads[row["pad"]] = (row["ball"], row["bank"])
    rows = []
    for name, direction, pad, grp, note in SIGNALS:
        ball, bank = pads[pad]
        rows.append([name, direction, ball, pad, bank, grp, note])
    for res, (ref, _outs) in PLLS.items():
        r = d.get_resource(ref)
        pad = next(p for p in pads if p.startswith("GPIO") and resource(p) == r)
        ball, bank = pads[pad]
        rows.append([ref, "pllref", ball, pad, bank, "clock", f"25 MHz reference for {res}"])
    out = os.path.join(HERE, "ti135_pinplan.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["signal", "dir", "ball", "pad", "bank", "group", "note"])
        w.writerows(sorted(rows, key=lambda r: (r[4], r[5], r[0])))
    print("wrote", out, len(rows), "signals")


if __name__ == "__main__":
    main()
