# Status and handoff

Last updated: **2026-11-12** (power cells rebuilt, decoupling reworked; see "Where we left off (2026-11-12)" below). Read this first if you are picking the work up (human or agent).

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

## Where we left off (2026-11-12)

Power-supply rework, step 1 of 2: **the five TLV62585 cells are rebuilt from one template** (f2638d2).
- **One cell, 6.9 x 8.5 mm, for every rail** (`tools/buck_cell.py`, template in the regulator's pin frame; `--demo`
  draws it alone on an empty board): L 1 uH 2520 (FTC252012S1R0MBCA, C5832370), CIN 10 u 0603 + 100 n 0201 at VIN,
  COUT 47 u 0805 + 22 u 0603, R1/R2/CFF 0201 (1 % dividers, also VCORE: worst case about +-2.7 % against the +-3.2 %
  VCC window). The output edge is a VOUT bus with up to six 0.45/0.25 plane vias; GND is one piece on B.Cu with
  vias to In6; PG has a 0.3/0.15 via in its pad; EN leaves sideways (5V0 flood, or pg_group1 left to route).
- **Schematic** (`tools/buck_cell_sch.py`, edits sheets 02/03 in place; the sheet generators no longer run on the
  hand-saved sheets): the second 22 u of each cell became its 100 n input capacitor (C203, C303, C313, C343; new
  C335 on 0V85). ERC unchanged, schematic parity clean.
- **Board:** output edges face the plane entry: VCORE, 1V8, 0V85 north; 3V3, 1V1 east. Regulators moved: U201
  0.5 mm south, U311 0.5 mm south, U331 0.25 mm south, U341 2.25 mm east / 0.25 mm south (clears C1204 and the
  j3_oe_n / 3V3 vias), U301 not at all. The In4 0V85 region's box over the buck now starts at y 96.71 (was 98.49).
  C808, C809, C825, C826 (LPDDR4 1V1 caps) are tied straight to the 1V1 cell's bus. 1V1 has 5 output vias and no
  via in CIN's ground pad (F.Cu traces above); 0V85 has 5 output vias.
- DRC against the board before: no new violations except the open EN stubs (pg_group1 at U331, U341) and the PG
  vias, which are not routed yet. Opens per net went down or stayed, except phy_vdd10 6 -> 7 (all zones were
  refilled; that pour is on the open Ethernet list).
- Recipe: `buck_cell_sch.py`, `add_parts.py`, `swap_footprint.py` (L, CIN/22 u to 0603, 100 n/CFF/R to 0201),
  `buck_cell.py --strip IN OUT`, `buck_cell.py IN OUT`.

**Step 2, decoupling (same day, `tools/decap_rework.py`; 70d0dce).** User decision: bulk is counted per
rail, not per VCCIO bank as the Efinix checklist lists it.
- **0402 -> 0201** (47 parts): the 1 u and 4.7 u on VCORE, 0V85, 1V1, 1V8, the 1 u on 3V3, and the 0402 100 n at the
  level shifters, U401, Y701 and the PHY. Nine of the caps under U501 moved onto free rail/GND via pairs
  (`place_bga_decaps.py`: VCORE 7 of 7, 1V1 2 of 5); the other 17 kept their spots, because 0V85, 1V8 and 3V3 have
  no free pair left under U501. Kept in 0402: C562 (4.7 u on 3V3: a 6.3 V 0201 loses most of its capacitance at
  3.3 V) and C5033 (eth_rst_n runs between its pads). C5048 and C5049 (4.7 u on 3V3) went to 0201 on 2026-11-13,
  see follow-up (c) below.
- **Bulk outside the cells:** VCORE 2 x 100 u 1206 (C5001, C5002), 1V8 2 x 47 u (C5019 west, C5020 east of U501),
  1V1 1 x 47 u (C538, was 10 u; still east of U501, not moved between the BGA and the LPDDR4). C551 (10 u at the
  eMMC) and C803 (22 u at the LPDDR4, routed) are unchanged.
- **Removed from the board, DNP / not on board in the schematic** (symbols stay drawn; clear the flags to bring one
  back): C5003, C509, C510, C5004, C5005 (VCORE), C5021-C5026 (1V8), C527 (0V85), C806, C807, C823, C824 (1V1).
- Rails now carry 9 x 0805 and 2 x 1206 in all (cells included), down from about 30. DRC: no new violations,
  parity clean, opens 432 -> 399.

**Open:**
1. **Done 2026-11-12:** pg_group1 and pg_all routed with `route.py` (0.15 mm, the Ethernet recipe's options, In2/In5
   cheap): pg_group1 56 mm on In2 + 20 mm on In5 to R401 and all five cells, pg_all 48 mm on B.Cu + In2/In5 to
   U401. 9 new vias. No new DRC violations; review the long B.Cu run of pg_all in KiCad.
   **pg_all removed 2026-11-13** (user decision: not needed; `tools/drop_pg_all.py`): labels, sheet pins and 86 mm
   of track with 5 vias are gone. PG of U331 (0V85) and U341 (1V1) and ~MR of U401 carry no-connect flags; ~MR
   floats on the TPS3808's internal pull-up. U401 now releases fpga_creset_n on VCORE (SENSE) + delay only and no
   longer waits for group 2. pg_group1 is unchanged.
   **Short local nets routed 2026-11-13** (`route.py`, the Ethernet recipe's options, costs F 1 / In2 3 / In5 3 /
   B 1, 0.12 mm): 35 nets - flash_cs_n, flash_io0-3, flash_sck, flash_io0_r, flash_io1_r, flash_sck_r,
   fpga_cbsel0, fpga_csi, fpga_ssu_n, fpga_test_n, emmc_cmd, emmc_dat3, emmc_dat5, emmc_vddi, REF_RES_4A/4B,
   Y701 OUT, D601/D602 anodes, and on the ADC sheet adc_ainp, adc_mux_out, isoada1-3_buf, mon_1v1/1v8/3v3,
   adc_cs_n_r, adc_sclk_r, adc_sdo_r, U1302/U1304A feedback. Old partial copper on these nets was replaced.
   **Failed, still open: flash_cs_n_r, flash_io2_r, flash_io3_r** (blocked by flash_io1/io3 at R624; their stubs
   were removed again). No new DRC violations; opens 269 -> 223.
   **Long signal runs routed 2026-11-13** (same recipe, costs F 3 / In2 1 / In5 1 / B 3): 43 nets - JTAG (4),
   fpga_cdone, fpga_creset_n, LCD (7) and touch (5) to J5, eMMC dat0/1/2/4/6/7 and ds, adbsel0-2, adc_cs_n, adc_sdo,
   mon_vcore, j3_oe_n, led0_n/led1_n, refclk_bl0-2, uart_rx/tx and the J2 side, DDR_CAL, REF_RES_2A. Mostly In2/In5,
   30-50 mm for the J5 nets. flash_io0, flash_io1, flash_io3 and emmc_dat5 were re-routed on the way.
   **Every signal net is now connected except flash_cs_n_r, flash_io2_r, flash_io3_r** (failed again; stubs
   removed). One new 0.57 mm dangling stub on j3_oe_n (In5). No other new DRC violations; opens 223 -> 174, all
   of them supply pins (GND, 1V8, 3V3, 3V3_analog, VCORE, 5V0, VCCA filters, PHY supplies) plus those three.
   **R801 and R601 moved to their balls 2026-11-13** (user decision; the 15 mm / 14 mm runs are gone). Both are
   now on B.Cu under U501 (0402, `decap_move.py --pads`, which now takes any part with one GND pad): R801 (240R,
   DDR_CAL) with pad 1 on ball via Y9 and a new GND via 0.55 mm from pad 2; R601 (10k, REF_RES_2A) with pad 1 on a
   new via in ball P16 and pad 2 on GND ball via P15. No new DRC violations; opens 174 -> 172.
2. Check the 2520 inductor's land pattern (KiCad's generic L_1008_2520Metric) against the FTC252012S data sheet.
3. **Mostly done 2026-11-12 (`tools/decap_connect.py`, a991e16):** of the 127 rail-decap pads without
   copper, 97 are connected: 42 by a via in the pad, 30 by a via beside the pad (also between four balls under
   U501), 19 by a straight track to a via of the net, 6 by a two-segment track. No new DRC violations; opens
   388 -> 296 (1V8 59 -> 33, GND 121 -> 71, VCORE 10 -> 6, 1V1 6 -> 2, 3V3 33 -> 25).
   **Moving the loose caps to their rail's ball vias (`tools/decap_move.py`, same day, 5780038):** only
   4 of 22 found a legal spot (C5029, C5035, C5036, C5039, all 1V8, 2.8-6.6 mm moved, at most 1.6 mm of track).
   For the others every spot within 0.9 mm of a ball via of the rail overlaps another cap's courtyard (the 0201
   courtyard is 1.49 x 0.79 mm on a 0.8 mm ball grid). Opens 296 -> 288.
   **Follow-up (user decision 2026-11-12, not committed yet):** (a) caps beyond the checklist counts that had no
   spot were dropped: C528, C529, C531 (1 u) and C533 (100 n) on 0V85, DNP / not on board in the schematic
   (`decap_rework.py`); 0V85 keeps C530 1 u, 5 x 100 n, 10 n against the checklist's 1 u + 100 n + 10 n. The other
   rails have no surplus among the stuck caps. (b) `decap_move.py --pads`: courtyards may overlap under U501,
   0.2 mm pad to pad instead, 45 degree placements allowed (rail pad on its ball via, ground pad between four
   balls). Moved: C530, C5032, C5038, C5043, C5055. **KiCad DRC now shows 5 more courtyards_overlap (11 in all),
   accepted by that decision.** Opens 288 -> 277 (0V85 6 -> 1).
   **Left open, 11 pads** (place by hand):
   - under U501: C5046.1 (1V8, 1 n), C5033.2 (GND; 1 u 0402), C553.2 (GND), C5056.1 (1V1, 4.7 u), and the 3V3
     pads of C5048, C5049 (4.7 u 0402) and C563: 3V3 exists there only at the three VCCIO33 ball vias
     (**C5048 and C563 solved, C5049.1 still open: see (c)**);
   - C401.2 (GND, U401);
   - C5002.1 (100 u VCORE): the cap sits west of U501, outside the In3 VCORE region (starts at x 155.2);
   - C940.1, C941.1 (3V3 at the PHY, F.Cu): part of the open PHY supply connections.
   **(c) 2026-11-13, user decision: C5048 and C5049 to 0201** (4u7 6.3 V, C47117441; sheet 05, `decap_rework.py`).
   The 3V3 balls of U501 are G7, J7 and M21. No new GND via fits beside G7 / J7: In2 carries lcd_sck in the
   x 167.2 channel and lcd_reset_n in the x 168.0 channel. So:
   - `decap_connect.py --gnd C5064 C5065 C5066` first ties the GND pads of those three VCCA_BR filter caps to the
     GND ball vias E7 / E8 (their vcca_br pads are still open, like the rest of that net);
   - **C563** (100 n) sits at 45 degrees with its 3V3 pad on **G7**, GND by a 0.93 mm track to C5064.2;
   - **C5048** moved 12.4 mm (`DECAP_RANGE=13`) to the 3V3 via at (153.83, 81.45) just west of U501, the one C5050,
     C5051 and C565 use, 2.6 mm from M21; GND to the via at (154.4, 82.18);
   - **C5049** has no spot: J7 has C556 to the west and no GND within reach to the east. It is seated with its GND
     pad on ball via **C7** (as 0201 in the old spot its 3V3 pad came 0.08 mm from that via); **C5049.1 stays open**,
     nearest 3V3 is G7 at 3.7 mm. To finish by hand: move C556 off J8/K8 or accept a 3.7 mm track.
   **(d) 2026-11-13: C556 moved so C5049 fits at J7** (user decision). C5049 sits at 45 degrees with its 3V3 pad
   0.28 mm from ball via J7 and its GND pad on ball via K8, where C556 was. C556 (100 n, 1V8) went 2.6 mm from
   J8/K8 to the 1V8 ball N8, with a new GND via between four balls 0.75 mm away; J8 has no cap of its own any
   more. Two more courtyards_overlap (C556 with C5017, C524; 13 in all). C5049.1 is closed: **8 pads remain**.
   **(e) 2026-11-13: the 4.7 u and 1 u 0201 caps left the BGA** (user decision: more room under U501;
   `tools/decap_perimeter.py` after `decap_move.py --strip`). 19 caps sit 0.7 ... 3.7 mm outside the body outline
   on B.Cu, each with a via in both pads (rail via on its filled plane): VCORE C511-C514, C5006-C5008 and 1V8
   C5030, C5031 south; 1V8 C5029, C5032 and 1V1 C5054, C540 north; 1V8 C553, C5035 and 1V1 C541, C542 east;
   3V3 C5049 west (J7 is free again). C530 (0V85, 1 u) only found a spot 17 mm from its balls at the south
   edge, so by user decision it went **back under the BGA** to its old place at the 0V85 ball via (169.4, 76.4)
   (`decap_move.py --strip`, then `--pads`). Under U501 now: 63 caps (100 n, 10 n, 1 n and C530); 18 moved out. C5027.1, C5044.2, C5041.1 shared copper with moved caps and were
   reconnected. No new DRC violations, courtyards_overlap 13 -> 11, opens 271 -> 269; **7 pads remain open**
   (C553.2 is closed).
   `decap_move.py --pads` now also ties a ground pad to a connected GND pad of a neighbour, or drills a new GND via
   in the pad / between four balls when every layer is free there. No new DRC violations; opens 277 -> 272;
   9 pads of the list above remain (C5048.1, C563.1 done).

## Where we left off (2026-11-11)

J3 I/O routing and the pin plan that follows it are pushed (4aa3eb8). **Ethernet is routed on the board (committed 9b6150d)** (`tools/eth_route.sh` is the recipe, `tools/eth_fanout.py` and `tools/eth_finish.py` its parts):
- **MDI pairs** copied from the Agilex card (same PHY, same HR911130A, same offset within 0.05 mm): F.Cu, 0.12 mm,
  no vias, P/N within 0.1 mm (A 8.3, B 13.8/13.9, C 6.8, D 7.4 mm). Pair B loops around jack pin 6 as there.
- **PHY passives as on the Agilex card** (`tools/eth_place.py`): RX series R907–R912, the bypass caps C921, C922,
  C930–C936, C940, C941 and the straps R920–R925 are now **0201** (22R C155743, 4k7 C270346, 1u C272877, 100n
  C190183, the Agilex card's parts; sheet 09 and board, parity clean) and sit on their Agilex counterparts' spots.
  C940 has no counterpart and sits beside C941. C920 (10u 0805) moved 0.7 mm north to clear C921.
- **R931 (RSET) moved 3.0 mm south** to (189.16, 66.7): it sat in pair A's path.
- **U901 pins 12–20** (reset, MDC, MDIO, TX) face north: a 0.1 mm F.Cu stub and a via each, two staggered rows
  that clear R912/R920, R929 and C920.
- **RGMII** by `route.py`: TX on In5 as one bus (28.5–36.5 mm from ball to pin, through R901–R906), RX on In2/In5
  (27.0–38.8 mm). No length tuning: the 12 mm spread is about 80 ps. 3–6 vias per signal, counting the ball via.
- MDC, MDIO, INT on In5; the jack LED on In2; reset, crystal (XI 6.4 mm, XO 7.6 mm), RSET, LEDs, CT on F.Cu/B.Cu.
- DRC: no new violations against the board before (KiCad lists at most 499 unconnected items, so compare per net).

**Open on the Ethernet block:**
1. `phy_vdd10` (6), `phy_avdd33` (5), `phy_dvdd_rg` (2) pin and capacitor connections to their pours, and the GND
   pads. `route.py` on these nets also added copper on GND/VCORE/1V1 and put a via beside J9 pin 3; that run was
   dropped. Do them by hand or with a script like `tools/buck_copper.py`.
2. `refclk_bl0..2` (R701–R703 to N7/R3/L2) are still stubs. `refclk_bl1`'s In5 stub leaves the BGA between the RX
   and MDC/MDIO runs on In5; check the crossing when routing it.
3. Review in KiCad: the RX runs near R907–R912 are autorouted and not tidy; `phy_rstb` crosses under the
   MDI pairs on B.Cu; `rgmii_rxd3` runs on In5
   beside the outermost DDR trace (at the 0.2 mm class clearance).

## Where we left off (2026-11-04)

Done since 2026-11-01 (all pushed, last commit e61a61c):
- **0201** for the eMMC/QSPI 33R terminations, eMMC caps and pull-ups, flash cap/pull-ups, FPGA config and JTAG pulls.
- **U1203/U1204 swapped**; U1204's breakout copied to U1201–U1203 by translation (nets from each chip's pads).
  U1201 and U1203 have no via-in-pad on pin 13 (GND) / pin 24 (3V3): isoada2 (B.Cu) runs under U1201's B row,
  U1304/C1312 sit under U1203's. Those two pins still need a GND / 3V3 connection off the pad.
- **ADC mux = TI TMUX1308PWR** (LCSC C970231, JLC Extended, 4051 pinout, CD(ON) 11 pF typ / 40 pF max,
  VIH 1.15 V). adbsel0–2 come straight from the FPGA at 1.8 V; U1204 channels 5–8 are spare (the user removed their
  no-connect flags on sheet 12 for the I/O reorder: ERC shows 5 pin_not_connected on U1204 until they are used).
- Free FPGA I/O: 8 HSIO on bank B (3 P/N pairs CLK0/2/3 + R6, L6). MIPI1 hard D-PHY pins are not usable as GPIO
  (data sheet table 136). Pinout checked against Efinix v0.8 / ADV-2604-001 (K8 already GND).

**ADC front-end simulation** (`sim/adc_mux/adc_mux_sim.py`; `fetch` then `run -j 2`, ~50 s). KiCad's bundled
libngspice 45.2 through ctypes, TI OPA365 PSpice model (git-ignored `sim/adc_mux/models/`), the mux as a data-sheet
behavioural model. 2.5 MSPS round-robin over all 8 channels, 100 cycles; worst error at the sampling instant vs the
DC value, last cycle, in LSB (14 bit, 201 uV):

| scenario | GND | vcore | 1v8 | 3v3 | iso2 | 1v1 | iso3 | iso1 |
|---|---|---|---|---|---|---|---|---|
| TMUX1308 typ caps, followers, 1k monitors | 2.8 | 1.0 | 1.1 | 0.1 | 1.5 | 2.0 | 0.4 | 1.3 |
| TMUX1308 max caps, followers, 1k monitors | 4.2 | 1.0 | 38 | 0.1 | 1.5 | 74 | 0.4 | 1.4 |
| NX3L4051, followers | 2.8 | 0.8 | 1552 | 64 | 3.3 | 3246 | 1.7 | 3.2 |
| SN74LV4051A, followers | 2.8 | 1.0 | 1.1 | 0.1 | 1.5 | 2.0 | 0.5 | 1.3 |
| TMUX1308 max, no isoada followers | 4.0 | 1.0 | 38 | 0.1 | 851 | 68 | 260 | 698 |
| same, baseboard 100R/470n + 100n at the mux pin | 4.2 | 1.0 | 38 | 0.1 | 7.8 | 74 | 2.4 | 6.6 |
| **as built since 2026-11-05: TMUX1308 max caps, followers, monitors at 100R** | 4.2 | 1.0 | 1.1 | 0.1 | 1.5 | 2.0 | 0.5 | 1.4 |

Conclusions: keep the isoada followers (U1304–U1306; since 2026-11-05 one OPA4322AIPWR quad, U1304 A–C, D spare;
the sim still uses the OPA365 model for them: TI's OPAx322 model runs too slowly in ngspice to sweep); the NX3L4051 would have failed on the 1k monitor channels.
At the TMUX1308's max capacitance the 1 kOhm rail-monitor resistors (R1302 1V8, R1304 1V1, R1303/R1305 3V3 divider)
leave 38–74 LSB after a large step from the previous channel; ~100 Ohm source resistance (as mon_vcore's R1301)
brings them to ~1–2 LSB. **Done 2026-11-05:** R1302/R1304 100R (C25076), R1303/R1305 200R/200R (C25087;
the divider draws 8.25 mA from 3V3); the sim's defaults follow, the old values are scenario `tmux1308_max_rmon1k`. GND channel: the post-mux OPA365 bottoms out ~6.5 mV above 0 V (static) and recovers to
within ~3–4 LSB after the 0.3 V isoada1 channel. Error grows with the step from the previous channel, so the channel
order matters too.

**Open, next time:**
0. U1304 (OPA4322AIPWR) is placed at (8.95, 32.9) mm on B.Cu between the old U1304/U1306 spots, C1310 moved next to
   its V+ (pin 4); old SOT-23 breakouts removed. Gate swap 2026-11-05: isoada1 on unit B (pins 5-7, left top, by R1307),
   isoada3 on C (8-10, right top, by R1309), isoada2 on D (12-14, right bottom, toward R1308), spare follower on A (1-3). Still to route: + inputs from R1307/R1309/R1308, outputs to the mux
   (the In5 drops for isoada1/2_buf at (8.99, 44.51)/(15.93, 42.71) remain; isoada3_buf's via was removed, its In5
   trace ends at (10.83, 34.91)), V-/GND, unit D. C1311/C1312 (old per-OPA365 decaps) can go.
1. Reorder the level-shifter I/O so each part is closest to its J3 pin; route U1201–U1204 to the FPGA and J3;
   connect U1201/U1203 pin 13 and pin 24.
2. The 6 flash via-in-pad shorts at U601 (vias now on the `_r` side of R623–R628); place/route the eMMC resistors.
3. The 2026-11-01 list below (VCCIO33 balls, FB501/FB504/U401 sense, buck ties, escapes, 3D models).

## Where we left off (2026-11-01)

The Agilex 3 card (`~/dev/agilex3_soc_control_card`, read only) is ready for its final pre-fab check, so its
placement was copied here (commits 12341e2, 167fdc8, 21cb082; all pushed):
- **Copied from the Agilex card:** U901 PHY (rotated 180° as there) with its passives matched by function, U1001 eMMC
  with its caps and pull-ups on B.Cu under it, U601 QSPI, J1 JTAG, J2 UART, JTAG pull-ups R607–R610, and the five
  TLV62585 cells moved rigidly onto the Agilex regulator spots (VCORE exact; 1V1/3V3/0V85 near; 1V8 next to VCORE,
  because the Agilex 1V8 spot is fenced by the routed isoada2/isoada3 B.Cu traces). The user then moved parts by
  hand (U601 to the top right, eMMC, J1/J2, J101, power parts); the board as committed is the user's placement.
- **Pours copied:** PHY GND / phy_dvdd_rg / phy_vdd10 on B.Cu, phy_avdd33 on In2 (isolated until its vias are
  routed). B.Cu 5V0 = the Agilex flood plus a box per buck cell and the input parts.
- **Planes reshaped for the new regulator spots:** In3 1V1 (left over the 1V1 buck and the LPDDR4 caps; east block to
  x 49 for its decaps), In3 VCORE (south over the VCORE buck), **new In3 3V3** (left column, bottom strip, right
  side: eMMC, JTAG, PHY; kept out of the DDR area), In4 0V85 (corridor south between the GND/VCORE ball columns, no
  1V8 vias in it, to the 0V85 buck). Every VCORE/1V1/0V85/1V8 via lands in its plane.
- **5V0 to the 1V1 buck:** its piece of the B.Cu flood was cut off by the isoada traces; one 0.5 mm In5 jumper with a
  0.6/0.3 via at each end, (12.6, 22.8) → (10.0, 26.0) mm from the top-left corner.
- DRC: no clearance/short/courtyard errors; only dangling/unrouted warnings and the isolated phy_avdd33 pour.

**Open, next time:**
1. U501's three VCCIO33 balls (3V3) sit inside the VCORE plane area: route them to their B.Cu decaps.
2. Small loads off the planes need traces: U401 VCORE sense pin, FB501 (VCORE) and FB504 (0V85) ferrites.
3. Buck cell outputs/GND to the planes (cell copper moved with the cells; check every cell is tied in).
4. U501 sits rotated 180° compared with the Agilex FPGA, so eMMC/RGMII/flash breakout stubs now point away from
   where those parts went: re-plan the escapes, then route eMMC, QSPI, RGMII/MDI (LAYOUT_PLAN.md phases 4–5).
5. Still no 3D models for J9 (RJ45), U1303 (ADS7056), Y701.

## Where we left off (before 2026-11-01)

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
    the analog block moved down ~5.6 mm to make room;
  - **isoada buffers (U1304–U1306, 2026-10-31)** on B.Cu between J3 and the mux, routed: J3 pins 1/3/4 leave
    south (away from MDATA/ADCLK on 6/7), 1k + 1n C0G to GND, OPA365 follower, vias under U1301's body to X4/X6/X7.
    J3's order (iso1, iso3, iso2 west to east) is the mux's reversed, so isoada2_buf and isoada3_buf cross on In5.
    3V3_analog joins the three decaps on In2; its feed from the LDO is still open.
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
| 07 clocks | done: 25 MHz YXC OT322525MJBA4SL (3225, C669088; replaced the unstocked SiT8924) → 3 × 33 R → PLL_BL0/1/2 reference pins N7/R3/L2 |
| 08 lpddr4 | done: U501 DDR unit ↔ U801 H9HCNNN8KUMLHR-NME. Connectivity checked against the netlist (0 mismatches) |
| 09 ethernet | done, **redone 2026-10-25 for the RTL8211FDI-CG** (C692886, 8,537 orderable; the KSZ9031 had 16; the Agilex 5 card makes the same change). 3V3 only, internal 1.0 V core LDO and 1.8 V RGMII pad LDO (CFG_EXT = 0, CFG_LDO = 10 strapped). All nine straps fitted: PHY address 1, TXDLY 0, RXDLY 1. PHYRSTB is a 3.3 V input, so U902 74LVC1G07 drives it open drain. Jack LED sinks directly into LED2 (active low). 22 R RGMII series, RSET 2.49 k, 25 MHz crystal, magjack J9 |
| 10 emmc | done: THGAMVG7T13BAIL, CMD/DAT0-7/RST_n 47 k pull-ups to 1V8, DS 47 k pull-down, CLK 10 R, VCC 3V3, VCCQ 1V8, VDDi 2u2 |
| 11 fpga_io | done: U501 bank units with labels from the pin plan |
| 12 level_shift | done: 4 × SN74AXC8T245, OE pulled up (outputs disabled until the FPGA enables them) |
| 13 adc | done. Front end from the **Agilex 3 card** (`~/dev/ti60f225_control_card`, design-notes "ADC front end for 2.5 MSPS"): TMUX1308PWR mux (was SN74LV4051A, briefly NX3L4051PW; 11 pF typ / 40 pF max on-capacitance vs the NX3L's 350 pF; since 2026-11-04 its 1.8 V-compatible selects (VIH 1.15 V) come straight from the FPGA, no translator; INH/E to GND, X0 = GND reference, rail monitors, isoada1..3 from J3 through followers U1304A–C (OPA4322AIPWR quad, LCSC C486027, since 2026-11-05; was 3x OPA365; unit D spare follower, + to GND), 1k + 1n C0G at their inputs, added 2026-10-31 because the baseboard now filters them with 8.2k + 4.7n/10n), then an OPA365 buffer, a 33 R + 680 p C0G kickback filter and an ADS7056. AVDD 4u7 + 100n, DVDD 1V8, 33 R SPI series. The Agilex 5 card's AD8603 was too slow and its INH was tied high |
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
- 5 V budget: the baseboard U8 (VXO7805-1000, 1 A) becomes the **Mornsun K7805-2000R3 (5 V / 2 A), upright**, with
  C93 10 µF / 50 V 1210 in and C94 22 µF / 10 V 0805 out (2026-10-29, `ac_psu_kicad` 732c9b1). The card gets 2 A minus
  the gate-driver logic and U10. Whether 20V_ISO_SEC delivers the extra ~2.5 W has to be measured on a built board.
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
