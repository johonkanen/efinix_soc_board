# Status and handoff

Last updated: **2026-10-25**. Read this first if you are picking the work up (human or agent).

## What this repository is

A control card for the AC lab power supply (baseboard: `johonkanen/ac_psu_kicad`, locally `~/dev/ac_psu_kicad`)
built around an **Efinix Ti135N484I3** FPGA. It runs Linux on the hardened quad-core RISC-V, with 1 GB LPDDR4,
Gigabit Ethernet and eMMC. It replaces the Agilex 5 card (`~/dev/agilex3_soc_control_card`) and the older Ti60F225
card, and plugs into the same baseboard.

| Document | Content |
|---|---|
| `MIGRATION_PLAN.md` | Overall plan: block mapping, decisions, power tree, phases, open questions |
| `TI135_PCB_NOTES.md` | Ti135 device rules: banks, power sequencing, configuration pins, LPDDR4 wiring and swizzling, routing rules, required pull resistors |
| `MECHANICAL.md` | **Hard mechanical requirements**: outline, J3/J6 (bottom-side baseboard connectors), RJ45 position, all in the Ti60 / KiCad frames |
| `POWER_BUDGET.md` | Rail estimate, 5V_ISOL input limit, regulator choice (TLV62585PDRLR), divider values |
| `reference/` | `ti135n484_pinout.csv` (all 484 balls, from the Efinity device DB), `baseboard_j11_pinout.csv` (baseboard signal header, the authority for J3) |
| `efinity/pinplan/` | `pinplan.py` builds the Interface Designer project for the pin plan; `ti135_pinplan.csv` is the signal → ball result |

## Where we left off

**Phase 2 (schematic): all 14 sheets are drawn (2026-10-25).** Next is footprints and PCB setup (see Next phases).

| Sheet | State |
|---|---|
| 01 pwr_input | done: J6 (baseboard 5V_ISOL / ISOGND), bulk caps, 3V3_analog LDO |
| 02 pwr_vcore | done: VCORE 0.95 V, TLV62585PDRLR |
| 03 pwr_rails | done: 1V8, 3V3, 1V2 (group 1), 0V85, 1V1 (group 2, EN = pg_group1) |
| 04 pwr_seq | done: power-good chain, TPS3808 → fpga_creset_n (20 ms) |
| 05 fpga_power | done: U501 power / GND / unused units, ferrite-filtered PLL rails, decoupling rows |
| 06 fpga_config | done: CDONE, CRESET_N, JTAG + header J1, REF_RES, straps, QSPI flash U601, LEDs |
| 07 clocks | done: 25 MHz SiT8924 → 3 × 33 R → PLL_BL0/1/2 reference pins N7/R3/L2 |
| 08 lpddr4 | done: U501 DDR unit ↔ U801 H9HCNNN8KUMLHR-NME. Connectivity checked against the netlist (0 mismatches) |
| 09 ethernet | done: KSZ9031RNX with the Agilex values/straps (PHY address 0, RGMII mode, single-LED mode), 22 R RGMII series, ferrite-fed AVDDH/AVDDL_PLL, 25 MHz crystal, magjack J9. The jack LED goes through a 74LVC1G06; **verify LED1 polarity at bring-up** |
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
- J3 and J6 are bottom-side sockets, numbered like the baseboard (pin n = baseboard pin n). The RJ45 is the UDE
  RB1-125B8G1A magjack, aligned to the Ti60 jack's front face and centreline (MECHANICAL.md).
- Regulators: 6 × TLV62585PDRLR (3 A) instead of the TDA38812 / AP61202; 3V3_analog NCP163 LDO.
- 5 V budget: the baseboard U8 (VXO7805-1000, 1 A) is to be upgraded to 1.5–2 A in the baseboard redraw. This is being
  worked on in the `ac_psu_kicad` session. Its options: TRACO TSR 2-2450 (10.2 mm tall), Mornsun K7805-2000R3L
  (bent leads), or the upright K7805-2000R3 (17.5 mm, collides with the card edge).
- User LEDs on the two spare 3.3 V HVIO pins (H9, F5).

## Open items

- [ ] **Measure the card-to-baseboard gap on the Ti60 card**: it decides the baseboard U8 replacement height.
- [ ] **Stock at JLC (2026-10-25):** RB1-125B8G1A magjack **0** (C363353); ADS7056IRUGR 44; KSZ9031RNXCA 17 + 42 (-TR).
      Order early or source elsewhere. A different magjack changes MECHANICAL.md §J9 (keep the front face and centreline).
- [ ] Verify the KSZ9031 LED1 polarity (strap-dependent) on the first board; U902 is an inverting buffer.
- [ ] Verify against the **Titanium Hardware Design Checklist** (Efinix Support Center, login): decoupling values,
      the supply that CDONE/CRESET_N are pulled up to (1V8 assumed, as on the Ti375C529 kit), unused transceiver pins,
      DDR PHY rail group (TI135_PCB_NOTES.md §10).
- [ ] Run the **Efinix Power Estimator** (spreadsheet, Support Center) and update POWER_BUDGET.md.
- [ ] Download the **Ti135N484 package net-length file** (Support Center) for LPDDR4 length matching.
- [ ] Check the inductor WPN4020H1R0MT (C98359) saturation current is at least 4 A (the TLV62585 switch limit).
- [ ] Verify the Ti60 jack front face against the Würth 615008140121 drawing and the UDE RB1 front against its own
      drawing (MECHANICAL.md, J9).
- [ ] Choose the LPDDR4 data rate (sets the PLL_BL2 frequencies in `efinity/pinplan/pinplan.py`; the current values are
      placeholders).
- [ ] Ti135N484I3 sourcing: not stocked at JLC; it needs global sourcing.

## Next phases

1. **Schematic review and BOM pass.** All sheets are drawn. Review the renders (`reports/render/`), fill in the LCSC/MPN fields, and check JLC stock.
2. **Footprints for the hard-placed parts:** J3 / J6 (PinSocket on B.Cu) and J9 (RB1 magjack) at the
   MECHANICAL.md coordinates. The outline is 76.000 × 65.127 mm with the aux origin at KiCad (100, 100).
3. **PCB setup (Phase 3):**
   - **First, check KiCadRoutingTools** (user request): https://github.com/drandyhaas/KiCadRoutingTools/discussions/1364
   - Use the proteus2kicad `build_pcb` flow, or pcbnew scripts, to create the board from the netlist with the fixed parts
     placed.
   - Copy the stack-up, net classes and LPDDR4 rules from the Agilex card.
   - Placement: BGA rotated 180° (DDR edge toward U801 in the north, banks 2A–2C west toward J3 and the translators,
     4A/4B east toward flash, eMMC and Ethernet). Then decoupling under the BGA and the dog-bone fan-out.
   - Pin-swap loop through `efinity/pinplan/pinplan.py` (Interface Designer check) → schematic.
4. **LPDDR4 routing** (TI135_PCB_NOTES.md §6.3), then the rest. DRC, then the JLC order checklist.
5. **In parallel (software):** bring up Linux on a Ti375C529 dev kit with the hard SoC + TSEMAC + eMMC host
   (MIGRATION_PLAN.md phase 1).

## Related sessions and repositories

- `~/dev/agilex3_soc_control_card` (Agilex 5 card): **do not modify from here**. Send notes to its session instead (user
  rule). Its J3 / J6 / pull-down changes for the same baseboard are done there.
- `~/dev/ac_psu_kicad` (baseboard KiCad redraw): the source of the J11 / J12 pinout and the U8 upgrade.
- `~/dev/proteus2kicad` (tools, submodule `tools/p2k`).
