# Status and handoff

Last updated: **2026-10-27** (phase 3 done: checklist fixes in the schematic and the 84 new parts placed on the board; next is phase 4, CK/CA on one layer; NEXT_SESSION.md). Read this first if you are picking the work up (human or agent).

## What this repository is

A control card for the AC lab power supply (baseboard: `johonkanen/ac_psu_kicad`, locally `~/dev/ac_psu_kicad`)
built around an **Efinix Ti135N484I3** FPGA. It runs Linux on the hardened quad-core RISC-V, with 1 GB LPDDR4,
Gigabit Ethernet and eMMC. It replaces the Agilex 5 card (`~/dev/agilex3_soc_control_card`) and the older Ti60F225
card, and plugs into the same baseboard.

| Document | Content |
|---|---|
| `MIGRATION_PLAN.md` | Overall plan: block mapping, decisions, power tree, phases, open questions |
| `TI135_PCB_NOTES.md` | Ti135 device rules: banks, power sequencing, configuration pins, LPDDR4 wiring and swizzling, routing rules, required pull resistors |
| `KRT_LEARNING.md` | KiCadRoutingTools: the haasoscope LPDDR4 example reproduced, its recipe on our board, grading lessons |
| `HW_CHECKLIST_REVIEW.md` | Efinix hardware checklist (Ti135 N484, SPI x4) item by item against the card: what to change (DDR_CAL 0.1 %, decoupling, 47 µF per regulator, SSU_N) |
| `NEXT_SESSION.md` | **Start here next time:** the plan for the next session (bus router result, learning the tools on their LPDDR4 example, DDR clean-up) |
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
  - translators between J3 and the BGA, PHY between the BGA and J9, eMMC south;
  - **analog section copied from the Agilex card (2026-10-26, `tools/place_analog.py`):** mux, OPA365 buffer,
    33 R + 680 p filter, ADS7056 and the 3V3_analog LDO sit just below J3, where the isoada inputs arrive. Their
    positions are the Agilex card's offsets from its J3, shifted +1.0 mm in x to clear J1. Our extra parts (rail
    monitors, SPI series resistors, extra caps) sit at the nearest free spot by the pin they serve;
  - **J3 pull-down arrays (RN1401–RN1408) on B.Cu** in a column beside J3, each level with its pins, as on the
    Agilex card;
  - **level shifters (U1201–U1204) by hand (2026-10-27)** in a column beside J3, with their decaps partly on B.Cu;
    the analog block moved down ~5.6 mm to make room.
- **LPDDR4**: DQ swizzle within each byte (LPDDR4_SWIZZLE.md: crossings 125 → 45), configured in Efinity
  (`efinity/pinplan/lpddr4_swizzle.json`). 40 Ω / 80 Ω rules (Efinix guide). The Ti135N484**I3** tops out at 2.8 Gbps.
- **Layers** (TI135_PCB_NOTES.md §6.5–6.6): signals on F/In2/In5/B. In1 and In6 GND; In3 VCORE/1V1/3V3; In4 1V8/0V85/5V0.
- **Plan for the rest**: `LAYOUT_PLAN.md`. LPDDR4, eMMC and flash are routed automatically and signed off by hand.
- DRC: schematic parity 0; no courtyard, clearance or short errors; 499 unconnected (unrouted). Silkscreen checks are
  off: the card carries no reference-designator silkscreen, only a few custom markings (user, 2026-10-26).

**Planes, BGA fan-out (via-in-pad) and regulator cell copper done** (TI135_PCB_NOTES.md §6.6–6.8).

**Checklist fixes (2026-10-27, phase 3, done):** R801 240R 0.1 %, SSU_N pull-up R622, Efinix decoupling table in
full (C5001–C5073, sheet 05 now A2), 47u + 22p feed-forward per TLV62585 cell (the data sheet asks for a feed-forward
cap above 47 µF; user decision). On the board all 84 new parts sit on B.Cu: 14 0201s on rail/GND via pairs under
U501, the rest at the nearest free spot to their rail's balls, the 47u/22p in the regulator cells. LPDDR4 copper
untouched (grade.sh as after phase 2), schematic parity 0, ERC unchanged (two known notes); the new caps are not yet
tied to their rails (unconnected 615 → 734, phase 5). Details: NEXT_SESSION.md phase 3.

**LPDDR4 clean-up (2026-10-27, phase 2):** every DDR segment at the 40 Ω width (0 mm below the minimum; 10 nets
re-routed at width, dm0/dq1 meandered, DQS0 re-routed as a pair). Die to die, path model / KiCad: DQ/DM–DQS within
−23.9…+71.0 / −15.6…+73.8 ps, CK–DQS ≤ 79 ps, CA–CK unchanged; DQS P/N 0.53 / 6.64 / 0.07 / 5.61 ps, CK 3.67 ps
(DQS1/DQS3/CK: no room). Cost: byte 0 In2 55 %, byte 3 spread over F/B/In2. Rest of the board unchanged. Details:
NEXT_SESSION.md phase 2.

**LPDDR4 on main = the `ddr-option2` routing (2026-10-27, phase 1, `tools/ddr/transplant.py`):** all DDR nets
connected; die-to-die DQ/DM–DQS −23.9…+60.4 ps, CK–DQS ≤ 86 ps, CA/CKE/CS–CK −57.1…+47.0 ps, all within the checklist
limits (HW_CHECKLIST_REVIEW.md item 6); DQS P/N 4.47 / 6.64 / 0.07 / 5.61 ps, CK 3.67 ps; 88 mm below the width
minimum. Rest of the board unchanged (C528 moved 0.3 mm off a dq2 via). Details: NEXT_SESSION.md phase 1.

**LPDDR4 routing (2026-10-26, superseded by option 2 above): data bytes and CK/CA trunk-and-branch re-routed at the 40 Ω widths and fitted to the JLC rules (`tools/ddr/ddr40_chain.sh`, TI135_PCB_NOTES.md §6.10); all connected, rest of the board DRC-clean; DDR width, hole and edge clearance clean; timing table and next steps in NEXT_SESSION.md.** The notes below describe the earlier draft.
- **On the board:** all 56 DDR nets connected by KiCadRoutingTools `route.py` on F.Cu/In2/In5/B.Cu, 0.1 mm wide,
  0.05 mm grid, free layer choice. 91 vias, 1215 mm. Tag `pre-ddr-routing` is the last clean commit, before this draft.
- **Every DRC error left is in the DDR copper** (the rest of the board is clean):
  - 195 hole clearance: tracks pass vias at 0.1 mm copper, the rule is 0.175 mm from the drill;
  - 76 clearance and 63 crosstalk-spacing warnings (DDR tracks < 0.25 mm apart outside the BGAs);
  - 88 track width: nothing widened to 40 Ω (0.18 mm inner / 0.25 mm outer) outside the BGAs yet;
  - 33 diff-pair gap / uncoupled length on DQS/CK.
- **Quality gaps:** each byte is spread over 3–4 layers (Efinix: one layer per byte). Lengths are not matched yet. The
  U501 pad-to-die delays are on the board (`tools/pad_to_die.py`), so tuning can be die to die.
- **What was tried** (helpers in `tools/ddr/`):
  - one layer per byte, plain router: 8–31 of 56 nets;
  - `route_diff.py` can't start pairs from bare via-in-pad balls (it needs fan-out stubs);
  - U801 rotated 180°: 55/56, 1463 mm, 110 vias, so the current pose stays;
  - the tool's `bga_fanout.py` escapes outer DDR rows on the surface.
- **Bus router (experimental `awx/route_bus.py`)** was still running at wrap-up, on `work/route/bus0.kicad_pcb`: DDR
  signal vias stripped, layers F/B/In2/In5, joint fan-out. Log `work/route/bus1.log`, result `work/route/bus1.kicad_pcb`,
  summary `work/route/bus1.json`. Round 1: 40/40 lanes, 5 open, 74 vias, 1114 mm. It needed `ortools` in the
  KiCadRoutingTools venv (installed). It relaxes the hole clearance to 0.1 mm in its own project copy: check its board
  against ours.
- **Next:**
  1. Read the bus router's result. Compare it with the draft on open nets, layers per byte, DRC (our rules) and pair
     skew; keep the better one as the base.
  2. Fix hole clearance (route at `--clearance 0.1` with hole clearance honoured, or nudge), widen outside the BGAs
     to 40 Ω, couple DQS/CK.
  3. Length/time matching per Efinix §6.3 (DQS pairs 10 mil, CK 5 mil, CA group ±62.5 mil, CA–CK ±30 mil, DQ 0…375 mil
     over DQS), die to die.
  4. Then eMMC, QSPI, RGMII/MDI, the rest (LAYOUT_PLAN.md phases 4–5).

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
- [x] Ti135N484 package net lengths: Efinix Ti135_netlength-v0.5.xlsx in `reference/efinix/` (local, not in git), applied as U501 pad-to-die by `tools/pad_to_die.py`. The BSDL (v1.0) and the package STEP (v1.1) are stored there too.
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
     - R801/R802 at their balls.
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
