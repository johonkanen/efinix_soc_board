# Layout plan for the remaining work (2026-11-12, branch `ai-place-route`)

Scope: everything on `kicad/ti135_card.kicad_pcb` except the LPDDR4, which is frozen
(`protected_nets.txt`, `protected_footprints.txt`, checked by `verify_protected.py`). The older
`LAYOUT_PLAN.md` describes how the board got here; this file plans what is left. Numbers are from the
board at commit 79451bd and from `kicad-cli pcb drc --schematic-parity --severity-all`.

How the board is edited: scripted pcbnew (`tools/p2k/bin/kipy`) on the closed board, one script per step,
kept in `tools/`. Konnect (MCP) is used for read-only queries and DRC only. After every write:
`verify_protected.py check`, then DRC, then commit. KiCad must be closed while a script writes.

## 1. Where the board stands

- 411 footprints. Four are not on the board: C806, C807, C823, C824 (22 µF, LPDDR4 1V1 bulk, locked) are
  parked 9–11 mm above the top edge (found in phase 3; the first version of this plan wrongly said all
  parts were inside the outline). The rest are placed; placement work is corrections only.
- 448 open connections on 102 nets: 300 on the 8 rails, 148 on 94 signal and local-supply nets.
- 26 DRC errors (8 shorts, 6 hole clearance, 6 solder-mask bridge, 6 courtyard overlaps), 114 warnings
  (57 dangling vias, 55 dangling tracks, 2 isolated copper). Schematic parity 0.

| Group | Sheet | Parts | Open connections | State |
|---|---|---|---|---|
| LPDDR4 | 08 | 42 | 0 on signals | **frozen** |
| FPGA rails and decoupling | 05 | 143 | most of the 300 rail connections; `vcca_bl/br/tr` 7 each, `vddpll_mcb_top_phy_ddr` 5 | caps placed, few tied to their rail |
| Regulators (5 × TLV62585, LDO) | 01–03 | 52 | 4 FB feed-forward caps, 5V0 4, `pg_group1` 5, `pg_all` 2 | cell copper drawn; EN/PG chain open |
| Supervisor | 04 | 3 | `fpga_creset_n` 2, VCORE sense | open |
| Configuration, JTAG, flash | 06 | 32 | flash 12 nets, JTAG 4 × 2, CDONE, CRESET, CBSEL0, CSI, SSU_N, TEST_N, 3 × REF_RES, 2 LEDs | flash has 6 shorts at U601 |
| Clock | 07 | 5 | `Net-(Y701-OUT)` 3, `refclk_bl0..2` | stubs only |
| Ethernet | 09 | 49 | `phy_vdd10` 6, `phy_avdd33` 5, `phy_dvdd_rg` 2 | signals routed, PHY supplies open |
| eMMC | 10 | 31 | 10 FPGA-side nets, `emmc_vddi` | 2 vias short flash tracks on In2 |
| FPGA I/O, LCD/touch, UART | 11, 14 | 13 | 12 LCD/touch nets to J5 (29–38 mm each), UART 4 | open |
| Level shifters | 12 | 13 | `j3_oe_n` 2, U1201/U1203 GND and 3V3 pins | J3 buses routed |
| ADC | 13 | 28 | about 25 short connections, `adbsel0..2`, `adc_cs_n`, `adc_sdo` (18–39 mm) | open |

## 2. Efinix rails and decoupling

Source: `HW_CHECKLIST_REVIEW.md` (the Efinix *Hardware Design Checklist and Guidelines* generated for
Ti135 N484, SPI x4) and `TI135_PCB_NOTES.md` §2 (Ti135 data sheet, *Pinout Description* and *Recommended
Operating Conditions*). **The vendor originals are not on this machine** (`reference/efinix/` holds only
its README), so the table repeats the repo's review; I have not re-read the checklist itself. Say if you
want it re-verified and put the files there.

| Rail | Ti135 balls | Decoupling on the card | Fed from | Reaches the balls by |
|---|---|---|---|---|
| VCORE 0.95 V | VCC 31, VDD_SOC 3, MIPI analog 2 | checklist table in full since 2026-10-27 (C5001–C5008 bulk, 0201/0402 under U501) | U201 / L201, B.Cu south | In3 VCORE plane |
| `vcca_bl/br/tr` | VCCA R8, G8, J16 | ferrite + 1 µ, 2 × 100 n, 2 × 10 n, 1 n each | FB501–FB503 from VCORE | local traces (open) |
| 0V85 | VDD_PHY_DDR 15 | 10 µ, 4 × 1 µ, 6 × 100 n, 10 n | U331 / L331 | In4 0V85 plane |
| `vddpll_mcb_top_phy_ddr` | W11 | ferrite FB504 + 1 µ, 100 n, 10 n, 1 n | from 0V85 | local trace (open, 5) |
| 1V1 | VDDQ 15, VDDQX 8, VDDQ_CK 1; LPDDR4 VDD2/VDDQ | 10 µ, 3 × 4.7 µ, 4 × 1 µ, 8 × 100 n, 3 × 10 n | U341 / L341, B.Cu north-west | In3 1V1 plane |
| 1V8 | VCCAUX 4, VCCIO 2A/2B/2C/4A/4B 11 | per-bank table (C5019–C5047) | U301 / L301 | In4 1V8 plane |
| 3V3 | VCCIO33 G7, J7, M21 | 3 × (4.7 µ, 1 µ, 100 n) | U311 / L311 | In3 3V3 pour + traces |
| GND | VQPS F9 tied low | – | – | In1, In6 planes |
| unconnected | transceiver supplies | none (unused; to confirm with AN 063, an open item in the review) | – | – |

Power-up order (checklist, power-up groups): VCORE, 1V8, 3V3 first, then 0V85 and 1V1 at least 10 µs
later. On the card that is the EN/PG chain `pg_group1` and `pg_all`, both still unrouted.

## 3. Sensitive nets

| Net(s) | Why | Rule for routing |
|---|---|---|
| `Net-(Y701-OUT)`, `refclk_bl0..2` (25 MHz to N7, R3, L2 through R701–R703) | DDR and SoC PLL references | 0.12 mm on In2/In5 or 0.15 mm on F.Cu (50 Ω), no stubs, each branch from its resistor; `refclk_bl1` crosses the RGMII RX and MDC/MDIO runs on In5: cross at right angles or change layer |
| `vcca_bl/br/tr`, `vddpll_mcb_top_phy_ddr` | PLL analog supplies | ferrite → caps → ball in that order, 0.2–0.3 mm, no shared via with VCORE/0V85 |
| Flash `flash_sck`, `flash_io0..3`, `flash_cs_n` (+ `_r`) | configuration at power-up; currently shorted | series resistor at the FPGA end stays; SCK matched to the data within 5 mm; 0.12 mm inner |
| eMMC `emmc_clk`, `cmd`, `dat0..7`, `ds` (+ `_r`) | HS200/HS400 at 1.8 V | data and CMD within 5 mm of CLK, DS with them; reference GND |
| JTAG TCK/TDI/TDO/TMS | long runs to J1 (27 mm) | TCK away from the 25 MHz clock and buck switch nodes |
| Buck hot loops (U201, U301, U311, U331, U341) | CIN–VIN–GND loop, SW node | cell copper is drawn and stays; no signal under a SW node on B.Cu, and none on In5 beside a cell without In6 GND between |
| ADC inputs (`isoada*_buf`, `adc_ainp`, `adc_mux_out`, `mon_*`) | 14-bit, 2.5 MSPS | F.Cu/B.Cu in the south-west corner only, away from 3V3/0V85 buck cells (U311 is 5 mm east of U1301) |
| Ethernet MDI, RGMII | routed | not touched |

## 4. Free area and routing channels

Board: x 131.5–207.5, y 51.7–116.8 mm. Signal layers F.Cu, In2, In5, B.Cu; planes In1 (GND), In3
(1V1 / VCORE / 3V3 / GND), In4 (1V8 / 0V85), In6 (GND).

**LPDDR4 region (narrowed 2026-11-12): x 152–176.5, y 51.7–77.5.** That is the measured extent of the
LPDDR4 copper (F.Cu x 153.7–175.8, y 52.9–76.9; In2 x 153.3–174.7, y 52.6–76.8; In5 x 152.9–173.2,
y 59.3–76.6; 72 short B.Cu tracks under U801) plus a margin; U501's DDR balls are rows y 72.6–76.6. The
rest of U501 (y 77.5–91) is outside it. In the region:
- In1 and In6 GND are the references of F.Cu/In2 and In5/B.Cu; the In3 1V1 block is In2's second
  reference. **No new tracks on In1, In3, In4, In6 anywhere**, and no zone edit that cuts these planes
  inside the region.
- The rule is enforced by distance, not by the box: `tools/grid_router.py` keeps every new track 0.3 mm
  from LPDDR4 tracks and pads (3h), and every new via 0.3 mm from LPDDR4 copper on all layers. One
  exception: a B.Cu track may pass an LPDDR4 *via* at the normal 0.1 mm, as the decoupling under both
  BGAs already does.
- New vias in the region only for rail/GND at existing parts.
- No new parts in the region on F.Cu. On B.Cu the PLL ferrites and their caps were moved into the strip
  between U801 and U501 (phase 3), next to the balls they feed.
- **C806, C807, C823, C824 (22 µF LPDDR4 bulk caps, locked) lie outside the board outline at y 40–43**
  (the board's top edge is y 51.7). They are protected footprints, so they have not been moved; they
  need a place on the board and the user's go-ahead to move them.

| Area | F.Cu | In2 | In5 | B.Cu |
|---|---|---|---|---|
| West, x 132–150 (J3, U1201–U1204) | J3 buses | J3 buses | J3 buses | J3, 1V1 buck (north-west), series resistors |
| South band, y 93–112 (U501 to J5) | nearly empty | empty | empty | four buck cells, bulk caps |
| South-west corner (ADC) | U1301, U1303, U101 | empty | 5V0 jumper | U1302, U1304 |
| East, x 176–190 (U501 to flash/eMMC) | eMMC/flash resistors | flash, RGMII | eMMC, RGMII | decaps |
| North-east (PHY, J9) | MDI, PHY | RGMII RX | RGMII TX | PHY pours |
| South-east (J1, J2, J101, J6) | empty | empty | empty | 5V0 flood |

Channels that follow from this: LCD/touch (12 nets) leave U501's south edge and run south on **In2** to
J5 (In5 there sits over the buck cells with only In6 between; In2 is three planes away). JTAG and UART
go south-east on In5/F.Cu to J1/J2. ADC digital (`adbsel`, `adc_cs_n`, `adc_sdo`) runs south-west on In5.
PG/EN chain on B.Cu/In5 along the south band.

## 5. Placement corrections (phase 2)

No part is unplaced. Planned moves, none in the LPDDR4 region and none of a locked part:

1. Courtyard overlaps: C105 off U101; C1004/C1005 apart; R1009, R1022, R1023 off U501's courtyard and
   each other (they belong beside their eMMC balls on the east side).
2. eMMC pull-ups R1011–R1013, R1015, R1017, R1018 and the DS pull-down R1020 (47 k, on the FPGA-side
   nets but placed at the eMMC, 15–21 mm away): move them next to the 33R series resistors.
3. Flash R623–R628: keep at the FPGA end; positions adjusted only if the U601 re-fan-out needs it.
4. `vcca_bl` caps (C5060–C5062, 5–6 mm from R8): try once to bring them closer; the area is full, so this
   may stay as it is.
5. Mechanical parts (J1, J2, J3, J5, J6, J9) are locked and stay. **I need your constraints only if you
   want any connector or J101 moved; otherwise I assume none.**

## 6. Power distribution (phase 3)

Planes stay as drawn. Changes are additions:

| Rail | High-case current (`POWER_BUDGET.md`) | Plan |
|---|---|---|
| VCORE | 1.0 A (1.5 A inrush) | In3 plane exists; tie every open decap (21) by via-in-pad or a ≤ 1 mm stub + via; U401 sense and FB501–FB503 by 0.2 mm trace from a plane via |
| 0V85 | 0.45 A | In4 corridor exists; 9 open cap pads + FB504 |
| 1V1 | 0.7 A | In3 block exists; 13 open pads incl. the frozen LPDDR4 caps |
| 1V8 | 0.5 A | In4 plane; 67 open pads, mostly one via each |
| 3V3 | 0.67 A | In3 pour + F/B traces 0.3 mm; U501's three VCCIO33 balls sit in the VCORE area of In3 and go to their B.Cu decaps by trace; 37 open pads |
| 3V3_analog | 0.02 A | F/B traces 0.3 mm, star from U101 |
| 5V0 | 1.25 A at J6 | B.Cu flood exists; 4 open pads |
| PHY `phy_vdd10`, `phy_avdd33`, `phy_dvdd_rg` | PHY-internal LDOs, < 0.3 A | existing pours; pins and caps by short 0.2–0.25 mm traces and one via each |
| GND | – | 137 open pads: one via per pad to In1/In6; F/B GND flood last |

Via sizing (assumption, stated as the brief asks): a 0.3/0.15 mm via carries 0.5 A, a 0.45/0.25 mm
via 1 A (plated 18 µm, 10 °C rise, rule of thumb from IPC-2152 charts, not a calculation for this
stack-up). Buck outputs to their plane: at least 4 × 0.45/0.25 (VCORE 6). Each decap: one via per pad.
Buck cells already have their vias from `tools/buck_copper.py`; phase 3 counts them and adds what is short.

## 7. Routing order (phase 4)

1. **Repair first:** the six U601 via-in-pad shorts (the vias belong to `/flash_*` but sit in the `_r`
   pads since the series resistors were added) and the two eMMC vias on the flash In2 tracks. This means
   ripping up and re-routing flash from R623–R628 to U601.
2. Clock: Y701 → R701–R703 → N7, R3, L2.
3. PLL supplies: `vcca_*`, `vddpll_mcb_top_phy_ddr`; DDR_CAL to R801; REF_RES resistors.
4. Flash, then eMMC FPGA side (matched to their clocks).
5. Configuration and JTAG: CRESET_N, CDONE, CSI, SSU_N, TEST_N, CBSEL0, TCK/TDI/TDO/TMS.
6. PG/EN chain, FB feed-forward caps, supervisor.
7. ADC block.
8. Bulk: LCD/touch, UART, LEDs, `j3_oe_n`, `adbsel`. Scripted first; Freerouting 2.5.0 through a Specctra
   DSN round-trip only for what is left, with every existing track exported as fixed, and
   `verify_protected.py check` straight after the import.
9. GND stitching and the F/B GND flood; return vias next to signal layer changes outside the LPDDR4 region.
10. Clean-up of the 57 dangling vias and 55 dangling tracks that are not on protected nets.

A net that fails three times is reported, not forced.

## 8. Net classes and rules for the remaining nets

Existing classes are used as they are (`kicad/ti135_card.kicad_pro`, `kicad/ti135_card.kicad_dru`);
no rule or stack-up change is planned.

| Class | Width / clearance | Via | Used for |
|---|---|---|---|
| Default | 0.10 / 0.10 mm (0.12 mm on In2/In5 for 50 Ω runs, 0.15 mm on F/B) | 0.30 / 0.15 | signals |
| rgmii | as set | 0.30 / 0.15 | routed, untouched |
| PWR | 0.30 mm | 0.45 / 0.25 | 3V3, 3V3_analog, PHY supplies, 5V0 stubs |
| PWR_CORE | 0.50 mm | 0.45 / 0.25 | VCORE, buck outputs |
| lpddr_* | – | – | frozen |

Board minimums: clearance 0.09 mm, hole clearance 0.175 mm, hole to hole 0.2 mm, copper to edge 0.5 mm
(J3 0.3 mm), via 0.25 / 0.15 mm.

## 9. Things for you to decide or know

- The file is `layout_plan_remaining.md`, not `layout_plan.md`: the repo already has `LAYOUT_PLAN.md`,
  and the two names would collide on a case-insensitive file system (Windows, macOS).
- C1311/C1312 (old OPA365 decaps, STATUS.md says they "can go") stay: removing them is a schematic change.
- ERC has 2 items (U401 `~MR` not driven, a pin-type warning on U1301). Both are schematic matters; I
  leave them.
- The 1V1 buck (U341/L341 at x 148, y 56–60, B.Cu) is 8–9 mm west of U801. Efinix asks for ≥ 100 mil
  from switching nodes to DDR traces; that holds, and the cell is not moved.

## 10. Phase 3 as built (2026-11-12)

- Rail pads tied: 448 → 149 open connections in total; the rails went from 300 open to 12 (below).
  `tools/rail_vias.py` (169 vias in or beside pads, 86 stubs), then `tools/grid_router.py` for pads with
  no fill of their rail under them (0.2 mm, 0.12 mm under the BGA), 3V3_analog (0.3 mm on F/B) and the PHY
  supplies. `tools/phase3.sh` reruns the trace part on a work copy.
- Regulator output vias found (within 6 mm of the inductor's output pad, all in the rail's fill):
  VCORE 5, 1V8 4, 3V3 3, 0V85 2, 1V1 3. With the assumption of section 6 that is 1.5–3.5 A per rail
  against 0.45–1.0 A high-case loads, so none were added. This is fewer than the "at least 4 × 0.45/0.25"
  written in section 6.
- Moved in phase 3: FB501/C501 (vcca_bl) and FB504/C507/C508 (DDR PLL supply) from beside the PHY to
  B.Cu north of U501, 3–6 mm from balls R8 and W11 (they were 17–23 mm away).
- Left open on the rails, each tried three ways (via in pad, stub or via beside the pad, routed trace) and
  boxed in by routed Ethernet signals on every layer:
  - C542.1 (1V1 decap at U501's east edge);
  - C940.1 / C941.1 (PHY 3V3 bypass, joined to each other but not to 3V3);
  - U901.38 (`phy_vdd10`), U901.28 / C936.1 (`phy_dvdd_rg`), and the `phy_dvdd_rg` B.Cu pour is in two pieces;
  - the B.Cu GND pour under the PHY has no via to the GND planes (stitching, phase 4 step 9);
  - C806, C807, C823, C824: off the board (above).
- The rail stubs drawn by `tools/rail_vias.py` run straight from pad to via at whatever angle that is,
  not at 45°. Electrically fine; tidy by hand if wanted.
