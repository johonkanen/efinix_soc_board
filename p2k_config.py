"""proteus2kicad (tools/p2k) configuration of the Ti135N484I3 control card.

This board is a new design, not a Proteus conversion: only the schematic/symbol helpers
(make_skeleton, symgen, sheetkit/sch_builder, render_sheet) and later build_pcb are used.
Mechanical reference coordinates (outline, J3/J6/J9 positions) are in MECHANICAL.md.
"""

PROJECT = "ti135_card"  # KiCad project / library name

# (sheet number, sheet name, file). Reference designators use sheet x 100 ranges (R101.. on sheet 1).
SHEETS = [
    (1, "pwr_input", "01_pwr_input.kicad_sch"),
    (2, "pwr_vcore", "02_pwr_vcore.kicad_sch"),
    (3, "pwr_rails", "03_pwr_rails.kicad_sch"),
    (4, "pwr_seq", "04_pwr_seq.kicad_sch"),
    (5, "fpga_power", "05_fpga_power.kicad_sch"),
    (6, "fpga_config", "06_fpga_config.kicad_sch"),
    (7, "clocks", "07_clocks.kicad_sch"),
    (8, "lpddr4", "08_lpddr4.kicad_sch"),
    (9, "ethernet", "09_ethernet.kicad_sch"),
    (10, "emmc", "10_emmc.kicad_sch"),
    (11, "fpga_io", "11_fpga_io.kicad_sch"),
    (12, "level_shift", "12_level_shift.kicad_sch"),
    (13, "adc", "13_adc.kicad_sch"),
    (14, "connectors", "14_connectors.kicad_sch"),
]
SCH_TITLE = "Ti135 control card"
SCH_COMPANY = "Jari Honkanen"
SCH_REV = "0.1"
SCH_COMMENT = "Efinix Ti135N484I3 control card for the AC lab PSU baseboard"
SCH_NOTE = ("Ti135N484I3 control card. Plan: MIGRATION_PLAN.md, device rules: TI135_PCB_NOTES.md,\n"
            "mechanics: MECHANICAL.md, FPGA pin plan: efinity/pinplan/ti135_pinplan.csv.")
