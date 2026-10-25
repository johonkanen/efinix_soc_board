# Status and handoff

Last updated: **2026-10-25** (placement with power on the underside, LPDDR4 swizzle, layer and plane plan). Read this first if you are picking the work up (human or agent).

## What this repository is

A control card for the AC lab power supply (baseboard: `johonkanen/ac_psu_kicad`, locally `~/dev/ac_psu_kicad`)
built around an **Efinix Ti135N484I3** FPGA. It runs Linux on the hardened quad-core RISC-V, with 1 GB LPDDR4,
Gigabit Ethernet and eMMC. It replaces the Agilex 5 card (`~/dev/agilex3_soc_control_card`) and the older Ti60F225
card, and plugs into the same baseboard.

| Document | Content |
|---|---|
| `MIGRATION_PLAN.md` | Overall plan: block mapping, decisions, power tree, phases, open questions |
| `TI135_PCB_NOTES.md` | Ti135 device rules: banks, power sequencing, configuration pins, LPDDR4 wiring and swizzling, routing rules, required pull resistors |
| `LAYOUT_PLAN.md` | Placement and routing plan: phases, which tool does each step, the fixed design inputs |
| `MECHANICAL.md` | **Hard mechanical requirements**: outline, J3/J6 (bottom-side baseboard connectors), RJ45 position, all in the Ti60 / KiCad frames |
| `POWER_BUDGET.md` | Rail estimate, 5V_ISOL input limit, regulator choice (TLV62585PDRLR), divider values |
| `reference/` | `ti135n484_pinout.csv` (all 484 balls, from the Efinity device DB), `baseboard_j11_pinout.csv` (baseboard signal header, the authority for J3) |
| `efinity/pinplan/` | `pinplan.py` builds the Interface Designer project for the pin plan; `ti135_pinplan.csv` is the signal → ball result |

## Where we left off

**Phase 2 (schematic): all 14 sheets are drawn. Phase 3 (PCB): every part is placed (2026-10-25)** in
`kicad/ti135_card.kicad_pcb`.
- The outline is in place, and J3 / J6 / J9 sit on their MECHANICAL.md pads (checked by the script). J3, J6, J9, J5,
  U501 (rotated 180°) and U801 are locked.
- 8-layer JLC08161H-3313 stack-up, net classes and DRC rules are set up.
- **Ethernet PHY changed to the RTL8211FDI-CG** (user decision 2026-10-25, stock; the Agilex 5 card does the same).
  The 1V2 buck went with the KSZ9031, so there are now 5 × TLV62585.
- **Placement** (KiCadRoutingTools, §Next phases 3; applied 2026-10-25, seed 8 of 12):
  - power supplies on the underside, as on the Ti60 card: 5 TLV62585 cells held to TI's Figure 24 layout, plus J6's caps;
  - BGA/LPDDR4 decaps on B.Cu under their packages;
  - J1/J2 at the west edge below J3 (MECHANICAL.md);
  - translators between J3 and the BGA, PHY between the BGA and J9, eMMC south, ADC south-east.
- **LPDDR4**: DQ swizzle within each byte (LPDDR4_SWIZZLE.md: crossings 125 → 45), configured in Efinity
  (`efinity/pinplan/lpddr4_swizzle.json`). 40 Ω / 80 Ω rules (Efinix guide). The Ti135N484**I3** tops out at 2.8 Gbps.
- **Layers** (TI135_PCB_NOTES.md §6.5–6.6): signals on F/In2/In5/B. In1 and In6 GND; In3 VCORE/1V1/3V3; In4 1V8/0V85/5V0.
- **Plan for the rest**: `LAYOUT_PLAN.md`. LPDDR4, eMMC and flash are routed automatically and signed off by hand.
- DRC: schematic parity 0; no courtyard, clearance or short errors; 499 unconnected (unrouted). Silkscreen warnings
  (overlapping reference labels, the jack overhanging the edge) remain to be tidied.

**Planes and BGA fan-out done** (TI135_PCB_NOTES.md §6.6–6.7): via-in-pad on every connected U501/U801 ball, plane regions by
script, under-BGA decaps cleared. Next: LAYOUT_PLAN.md step 12 (buck cell copper) and phase 4 (LPDDR4 routing).

| Sheet | State |
|---|---|
| 01 pwr_input | done: J6 (baseboard 5V_ISOL / ISOGND), bulk caps, 3V3_analog LDO |
| 02 pwr_vcore | done: VCORE 0.95 V, TLV62585PDRLR |
| 03 pwr_rails | done: 1V8, 3V3 (group 1), 0V85, 1V1 (group 2, EN = pg_group1). The 1V2 cell went with the KSZ9031 (2026-10-25) |
| 04 pwr_seq | done: power-good chain, TPS3808 → fpga_creset_n (20 ms) |
| 05 fpga_power | done: U501 power / GND / unused units, ferrite-filtered PLL rails, decoupling rows |
| 06 fpga_config | done: CDONE, CRESET_N, JTAG + header J1, REF_RES, straps, QSPI flash U601, LEDs |
| 07 clocks | done: 25 MHz SiT8924 → 3 × 33 R → PLL_BL0/1/2 reference pins N7/R3/L2 |
| 08 lpddr4 | done: U501 DDR unit ↔ U801 H9HCNNN8KUMLHR-NME. Connectivity checked against the netlist (0 mismatches) |
| 09 ethernet | done, **redone 2026-10-25 for the RTL8211FDI-CG** (C692886, 8,537 orderable; the KSZ9031 had 16; the Agilex 5 card makes the same change). 3V3 only, internal 1.0 V core LDO and 1.8 V RGMII pad LDO (CFG_EXT = 0, CFG_LDO = 10 strapped). All nine straps fitted: PHY address 1, TXDLY 0, RXDLY 1. PHYRSTB is a 3.3 V input, so U902 74LVC1G07 drives it open drain. Jack LED sinks directly into LED2 (active low). 22 R RGMII series, RSET 2.49 k, 25 MHz crystal, magjack J9 |
| 10 emmc | done: THGAMVG7T13BAIL, CMD/DAT0-7/RST_n 47 k pull-ups to 1V8, DS 47 k pull-down, CLK 10 R, VCC 3V3, VCCQ 1V8, VDDi 2u2 |
| 11 fpga_io | done: U501 bank units with labels from the pin plan |
| 12 level_shift | done: 4 × SN74AXC8T245, OE pulled up (outputs disabled until the FPGA enables them) |
| 13 adc | done. Front end from the **Agilex 3 card** (`~/dev/ti60f225_control_card`, design-notes "ADC front end for 2.5 MSPS"): SN74LV4051A (INH to GND, X0 = GND reference, rail monitors, isoada1..3 from J3), then an OPA365 buffer, a 33 R + 680 p C0G kickback filter and an ADS7056. AVDD 4u7 + 100n, DVDD 1V8, 33 R SPI series. The Agilex 5 card's AD8603 was too slow and its INH was tied high |
| 14 connectors | done: J3 (baseboard J11) + 32 × 10 k pull-downs, J5 LCD, J2 UART |

ERC shows two known, harmless notes and nothing else:
- `pin_not_driven` on U401 ~MR: it is driven only by open-drain PG outputs and has an internal pull-up.
- `pin_to_pin` on U1301 X0: the mux's zero-reference input is intentionally tied to GND.

The netlist check passes: each of the 92 pin-plan signals reaches its load, and the LPDDR4 wiring matches §6.1 of the notes.

## How to build (everything is scripted, do not hand-edit the .kicad_sch files)

```
git submodule update --init          # tools/p2k = johonkanen/proteus2kicad (schematic helpers, KiCad env)
tools/build_schematic.sh             # symbols + all sheets + root sheet pins + ERC -> reports/erc.rpt
tools/p2k/bin/p2k render_sheet kicad/08_lpddr4.kicad_sch   # PNG check -> reports/render/
```

- KiCad 10 AppImage at `~/kicad/kicad-10.0.7-x86_64.AppImage` (see `tools/p2k/bin/kicad_env.sh`).
- `tools/gen_symbols.py` writes `lib/ti135_card.kicad_sym`, including the 9-unit Ti135N484I3 symbol generated from
  `reference/ti135n484_pinout.csv`.
- Each `tools/sheets/NN_name.py` rebuilds one sheet from scratch. Shared helpers are in `tools/sheets/_common.py`
  (`hlabel`, `place_unit`, `cap_row`, `set_field`, pin plan readers) and `_power.py` (the TLV62585 block).
- `tools/sync_root.py` regenerates the root sheet's sheet pins from each sub-sheet's hierarchical labels.
- Pin plan: `source ~/efinity/2026.1/bin/setup.sh && python3 efinity/pinplan/pinplan.py` (Efinity 2026.1; runs the
  Interface Designer design check). Then re-run `tools/build_schematic.sh` so sheet 11 picks up the changes.

**Conventions:**
- No global labels: sheets connect through hierarchical labels on the root.
- Rails only through power symbols.
- Signal nets are lower snake_case; active-low signals end in `_n`; differential pairs end in `_P` / `_N`.
- Reference designators use sheet number × 100 (R1201 is on sheet 12). The baseboard/user connectors keep their old
  names: J1 JTAG, J2 UART, J3 baseboard J11, J5 LCD, J6 baseboard J12, J9 RJ45.
- Hidden power-input pins are converted to passive in every symbol, so KiCad does not turn them into implicit
  global nets.

## Decisions made (do not reopen without the user)

- Ti135N**484**I3 (not N676), hard RISC-V SoC, Linux.
- 3.3 V I/O shortage: inputs and LCD on HVIO, J3 outputs through 4 × SN74AXC8T245, the same scheme as the working
  Ti60 card but with OE gated, plus 10 k pull-downs on every J3 signal pin.
- Shared parts with the Agilex 3 / Agilex 5 cards:
  - LPDDR4 SK hynix H9HCNNN8KUMLHR-NME (C2912103)
  - eMMC KIOXIA THGAMVG7T13BAIL (C7599693)
  - QSPI ISSI IS25WP128-RHLE (C1349419)
- Board: the Ti60/Agilex outline, 8 layers (JLC08161H-3313 stack-up), JTAG header + Efinix cable (no on-board FTDI).
- J3 and J6 are bottom-side sockets, numbered like the baseboard (pin n = baseboard pin n). The RJ45 is the HanRun
  HR911130A magjack (C54408; the UDE RB1-125B8G1A had no stock), aligned to the Ti60 jack's front face and centreline (MECHANICAL.md).
- Regulators: 5 × TLV62585PDRLR (3 A) instead of the TDA38812 / AP61202; 3V3_analog NCP163 LDO.
- Ethernet PHY: RTL8211FDI-CG (C692886), RGMII at 1.8 V from its internal pad LDO (2026-10-25; it replaced the KSZ9031).
- 5 V budget: the baseboard U8 (VXO7805-1000, 1 A) is to be upgraded to 1.5–2 A in the baseboard redraw. This is being
  worked on in the `ac_psu_kicad` session. Its options: TRACO TSR 2-2450 (10.2 mm tall), Mornsun K7805-2000R3L
  (bent leads), or the upright K7805-2000R3 (17.5 mm, collides with the card edge).
- User LEDs on the two spare 3.3 V HVIO pins (H9, F5).

## Open items

- [ ] **Measure the card-to-baseboard gap on the Ti60 card**: it decides the baseboard U8 replacement height.
- [ ] **Stock at JLC, orderable quantity (2026-10-25):**
  - ADS7056IRUGR **18**;
  - RTL8211FDI-CG 8,537 (it replaced the KSZ9031RNXCA, 16);
  - QSPI flash 68, LPDDR4 106, eMMC 177.

  Order these early or source them elsewhere. Check with `jlc-tools/stock_check.py` (judge by the orderable "free"
  quantity, not stockCount). The magjack is now the HR911130A (9,124 orderable); the RB1 had 0.
- [ ] Bring-up: the PHY is at MDIO address 1 (device tree `reg = <1>`, `phy-mode = "rgmii-id"`). Program the RTL8211F LCR
      (page 0xd04, reg 0x10) so LED2 shows link/activity at all speeds (its default is link-at-1000 only).
- [ ] Verify against the **Titanium Hardware Design Checklist** (Efinix Support Center, login): decoupling values,
      the supply that CDONE/CRESET_N are pulled up to (1V8 assumed, as on the Ti375C529 kit), unused transceiver pins,
      DDR PHY rail group (TI135_PCB_NOTES.md §10).
- [ ] Run the **Efinix Power Estimator** (spreadsheet, Support Center) and update POWER_BUDGET.md.
- [ ] Download the **Ti135N484 package net-length file** (Support Center) for LPDDR4 length matching.
- [ ] Verify the Ti60 jack front face against the Würth 615008140121 drawing (MECHANICAL.md, J9; the HR911130A
      body is the same 21.3 mm deep).
- [ ] Choose the LPDDR4 data rate (sets the PLL_BL2 frequencies in `efinity/pinplan/pinplan.py`; the current values are
      placeholders).
- [ ] Ti135N484I3 sourcing: not stocked at JLC; it needs global sourcing.

## Next phases

1. **Schematic review and BOM pass.** All sheets are drawn. Review the renders (`reports/render/`), fill in the LCSC/MPN fields, and check JLC stock.
2. ~~Footprints and PCB setup~~ **done 2026-10-25:**
   - `tools/gen_footprints.py`: the HR911130A footprint.
   - `tools/build_pcb.sh` runs all three below, then DRC.
   - `tools/make_board.py` (run with kipy): builds the board from the netlist with the fixed parts placed and checked.
     It rebuilds from scratch. `tools/build_pcb.sh --rebuild` runs it and then puts every footprint back where it was
     (`tools/apply_placement.py`), which works until routing starts. After that, use pcbnew's "Update PCB from
     Schematic". Plain `tools/build_pcb.sh` leaves the board alone and only refreshes the rules and runs DRC.
   - `tools/board_setup.py`: Agilex stack-up, net classes (LPDDR4, RGMII, power), DRC rules (U501/U801), and a J3
     edge exception.
3. ~~Placement~~ **done 2026-10-25** with KiCadRoutingTools (https://github.com/drandyhaas/KiCadRoutingTools, local
   `~/dev/KiCadRoutingTools` with its venv; its skills are linked into `.claude/skills/`, gitignored):
   - Inputs are in `placement/`:
     - `groups.json`: 20 functional groups. The power groups have `side: B`.
     - `sketches/U*.json`: the TLV62585 templates (TI SLVSDE5F Figure 24).
     - `prep.sh` does the prep in order:
       1. locks J3/J6/J9/J5/J1/J2/U501/U801 and unplaces the rest;
       2. flips the decaps and power cells to B.Cu (`flip_bottom.py`);
       3. emits the intent and applies `fix_intent.py`;
       4. fits the templates.
     - `make_board.py` sets pad pin functions/types. Without them the placer read the Y701 oscillator as a crystal.
   - Run: `placement/prep.sh`, then from `work/place`:
     - place: `$P $K/py_placer/place_simple.py fixed.kicad_pcb 'wk/s{seed}.kicad_pcb' --groups groups.json --intent intent.json --jobs 4 --json 'wk/s{seed}.json'`
       (12 seeds, about 2.5 min each);
     - judge: `$P $K/py_placer/judge_seeds.py wk/judge.json --chain ../../placement/judge_chain.txt --intent intent.json --seeds 1,7,8 --jobs 1`
       (its route uses the §6.6 planes and the 4 signal layers).
   - Result: seed 8 (placer cost 13,801). Its level-2 quick route left 24 nets open, with 711 vias and 7.2 m of copper;
     seed 7 left 34 open and seed 1 left 38.
   - Applied with `tools/p2k/bin/kipy tools/apply_placement.py work/place/wk/s8.kicad_pcb`. Checks: no assembly
     blocking, no floorplan errors, all five templates as drawn.
   - Still to do by hand (LAYOUT_PLAN.md step 4):
     - RGMII series resistors: TX at the FPGA, RX at the PHY;
     - Y901 tight to the PHY;
     - R801/R802 at their balls;
     - silkscreen labels (`beautify_labels.py`).
   - Watch at sign-off: the 0V85/1V1 cells (B.Cu) sit at the east end of the DDR corridor. Efinix asks for ≥ 100 mil
     between switching nodes and DDR traces; In6 GND shields In5.
4. **LPDDR4 routing** (TI135_PCB_NOTES.md §6.3), then the rest. DRC, then the JLC order checklist.
5. **In parallel (software):** bring up Linux on a Ti375C529 dev kit with the hard SoC + TSEMAC + eMMC host
   (MIGRATION_PLAN.md phase 1).

## Related sessions and repositories

- `~/dev/agilex3_soc_control_card` (Agilex 5 card): **do not modify from here**. Send notes to its session instead (user
  rule). Its J3 / J6 / pull-down changes for the same baseboard are done there.
- `~/dev/ac_psu_kicad` (baseboard KiCad redraw): the source of the J11 / J12 pinout and the U8 upgrade.
- `~/dev/proteus2kicad` (tools, submodule `tools/p2k`).
