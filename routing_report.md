# Routing report: remaining placement and routing (2026-11-12, branch `ai-place-route`)

Board: `kicad/ti135_card.kicad_pcb`, KiCad 10.0.7. Start: commit 9b6150d on `main`. The plan is
`layout_plan_remaining.md`; this report says what was done, what is still open and what a person should
look at. **The board is not finished: 18 connections are open, among them the VCCA_BL supply.**

## Result

`kicad-cli pcb drc --schematic-parity --severity-all` (report in `reports/drc_final.rpt`, git-ignored):

| | Start | Now |
|---|---|---|
| Unconnected items | 448 | **18** |
| Errors other than unconnected | 26 (8 shorts, 6 hole clearance, 6 mask bridge, 6 courtyard) | **0** |
| Schematic parity | 0 | 0 |
| Warnings | 114 (57 dangling vias, 55 dangling tracks, 2 isolated copper) | 75 (44 dangling vias, 31 dangling tracks) |

`verify_protected.py check`: no differences (2730 LPDDR4 track/via items, 300 rail items next to
LPDDR4 pads, 43 footprints). ERC was not touched (2 items at the start, both schematic matters).

## What is frozen

Only the LPDDR4, by your decision at the phase 0 checkpoint: the flash and eMMC carried shorts and open
connections, so they became remaining work.
- Tier A, fully frozen: the 58 signal nets on U801 (`protected_nets.txt`).
- Tier B, shared rails GND, 1V1, 1V8, 0V85: their copper within 1 mm of a protected pad is frozen; new rail
  copper was allowed.
- 43 footprints: U801, U501, C803–C840, R801–R803 (`protected_footprints.txt`).
- One authorised change to the frozen set: C806, C807, C823, C824 (22 µF, 1V1) were parked 9–11 mm above
  the board edge. You allowed moving them; they are now on B.Cu under U801, 1.1–2.3 mm from 1V1 balls
  U3, F3, U10, F10. The baseline was re-taken after checking that these four footprints were the only
  differences.

## What was done, by phase

| Phase | Commit | Content |
|---|---|---|
| 0 | 2b77de4, 79451bd | Konnect MCP config, Freerouting 2.5.0 + JRE (in `work/mcp`), protected list, `verify_protected.py`, LPDDR4 locked |
| 1 | 2e8ad89 | `layout_plan_remaining.md` |
| 2 | 8850cc3 | Courtyard overlaps cleared; eMMC pull-ups moved from the eMMC to their FPGA-side nets; C5061 to ball R8 |
| 3 | e55a8dc, 58236cd, e711c13 | Rail pads tied to planes (169 vias, 86 stubs), leftover rail pads by trace, 3V3_analog, PHY supplies; PLL ferrites FB501/FB504 and their 1 µ caps moved from beside the PHY to the balls |
| 4 | 9d03fe6 … 1428fb2 | LPDDR4 bulk caps placed; flash re-routed through R623–R628 (cleared all 20 errors); 25 MHz clock; VCCA_BR/TR, DDR PLL supply, DDR_CAL, REF_RES; eMMC, configuration, JTAG, PG chain, ADC, LCD/touch, UART, LEDs; 38 GND stitching vias under the PHY |

Tools written for this (all in `tools/`): `protected_nets.py`, `lock_protected.py`, `place_fix.py`,
`rail_vias.py`, `dump_geom.py`, `grid_router.py`, `apply_ops.py`, `flash_repair.py`, `remove_items.py`,
`work_copy.sh`, `route_batch.sh`, `phase3.sh`, `drc_summary.py`. Every board edit ran on a copy under
`work/`, was checked with `verify_protected.py` and DRC (zones refilled), and only then copied to `kicad/`.

**Tools not used as the brief expected:** Konnect was installed and answers, but all edits were scripted
pcbnew on the closed board (your choice at checkpoint 0; the repo's rule is that KiCad is closed while
files are written). Freerouting was installed and never run: the grid router handled the bulk nets, so no
Specctra round-trip took place. KiCadRoutingTools was skipped as you said.

## Rules used

- Existing net classes and `kicad/ti135_card.kicad_dru` unchanged. No schematic, library, stack-up or
  rule change.
- Signals 0.10 mm (0.12 mm for the clock, PG, ADC); rail stubs 0.2 mm, 0.12 mm under the BGA; 3V3_analog
  0.3 mm. Vias 0.30/0.15 mm through.
- New tracks keep 0.3 mm from LPDDR4 tracks and pads, new vias 0.3 mm from LPDDR4 copper on all layers.
  Two exceptions: B.Cu tracks may pass an LPDDR4 via at 0.1 mm (as the existing decoupling does), and the
  DDR PLL supply and DDR_CAL, which end inside the DDR ball field, were routed at the board's 0.1 mm.
- Nothing new on the plane layers In1, In3, In4, In6. No zone outline was changed.
- Via current assumption: 0.5 A per 0.30/0.15 via, 1 A per 0.45/0.25 via (rule of thumb, not calculated
  for this stack-up). Regulator outputs have 2–5 vias into their planes (1.5–3.5 A by that rule against
  0.45–1.0 A loads), so none were added; the plan had said "at least 4".

## Open: 18 unconnected items

Each was tried at least three ways and then left, as the brief asks.

| Net | What is open | Why |
|---|---|---|
| **`vcca_bl`** (7 items) | PLL analog supply, ball R8, with FB501, C501, C502, C5060–C5063 | R8 sits in the DDR ball rows; the pads are boxed in on B.Cu by decoupling and DDR vias. Four attempts (0.2 mm, 0.12 mm, 0.12 and 0.10 mm at normal DDR clearance). C502 is still beside the PHY, 24 mm away: no legal spot near R8. **The FPGA will not work without this.** |
| `pg_all` | U341 pin 6 (1V1 regulator PG) | pin boxed in on B.Cu; the rest of `pg_all` is routed |
| `adc_cs_n` | ball N1 to R1310 | no free way out of the ball on any layer |
| `uart_tx` | ball H7 stub to R1402 | same |
| `t_irq` | ball L22 to J5 pin 1 | same |
| `fpga_ssu_n` | R622 pin 2 to ball L4 | R622's pad is boxed in |
| 1V1 | C542 pin 1 | boxed in by RGMII on every layer; no other legal spot for the cap |
| 3V3 | C940 / C941 pin 1 (PHY bypass) | joined to each other, boxed in by `phy_rxc` / `phy_rx_ctl` |
| `phy_vdd10` | U901 pin 38 | boxed in |
| `phy_dvdd_rg` (2 items) | U901 pin 28 to C936; the B.Cu pour is in two pieces | pour was already split at the start |
| GND | zone item: small copper islands of the B.Cu GND pour under the PHY | the pour itself now has 38 vias; the islands are slivers inside it |

These need either a hand route in KiCad or moving routed Ethernet/escape tracks, which I was not asked to
change.

## Mistakes made on the way, and how they were caught

- I reported at checkpoints 1 and 2 that all 411 parts were inside the outline without checking; four
  LPDDR4 caps were not. Found in phase 3 from DRC positions.
- The 5V0 B.Cu flood was cut into islands twice by new B.Cu tracks (phase 3b: U301 and U341 inputs;
  phase 4d: U301 input, by `fpga_creset_n` and `jtag_tdo`). DRC showed zone-to-zone unconnected items
  both times; the board was rolled back or the nets rerouted before any commit that kept the cut.
  The router now has a cost for crossing pours and a hard keep-out (`--keep-pours`).
- A via landed 0.1 mm from an LPDDR4 meander arc because arcs were read as straight lines; one DRC
  clearance error, fixed in the geometry dump, batch rerun.
- A 0.07 mm joining stub at a track end violated clearance; fixed in the router, batch rerun.

## Trade-offs and things a person should review

**Signal integrity**
- Flash: FPGA to flash 23–50 mm (SCK 23.1, CS 27.1, IO0 27.7, IO1 32.8, IO2 43.6, IO3 49.9 mm). The plan
  said within 5 mm of SCK; it is 27 mm, about 0.18 ns. IO2/IO3 are long because R627/R628 sit 7–10 mm
  east of U601. No length tuning was done.
- eMMC: CLK 31.3, CMD 33.6, DS 34.4, DAT0–7 21.3–30.4 mm (the data lengths include the pull-up stubs).
  Spread 13 mm, not the 5 mm of the plan. Check against the HS200/HS400 budget you intend to use.
- 25 MHz: `refclk_bl0` 15.0, `bl2` 15.4, `bl1` 33.7 mm. `refclk_bl1` detours; worth a hand route.
- JTAG runs 39–42 mm.
- No impedance control was applied to new nets (0.10 mm everywhere), and no return vias were added at the
  layer changes of the new signals.
- Dangling copper: 31 track ends and 44 vias, mostly old escape stubs and ball vias on nets that are now
  routed another way, plus 3 on unused translator pins. I did not delete any existing copper to tidy them.

**Power**
- `vcca_bl` open (above). The other PLL supplies are routed at 0.12–0.2 mm.
- The rail stubs from `tools/rail_vias.py` run straight from pad to via at whatever angle; the routed
  traces are 45°.
- Via-in-pad on many 0201/0402 and IC pads, as the board already does under the BGAs: the order needs
  filled and capped vias.
- No F.Cu/B.Cu GND flood was added (the plan listed it): on F.Cu and B.Cu it would run beside LPDDR4
  microstrip and change its impedance, which is a decision for you.
- New through vias perforate In3/In4 around U501. The planes were not split (DRC connectivity is clean for
  all plane nets), but look at the In3 1V1/VCORE seam and the 0V85 corridor on In4.

**Regulators and thermal**
- Regulator cells were not changed. Check that the PG/EN chain (`pg_group1`, `pg_all`) takes a sensible
  path past the switch nodes; `pg_group1` has a 44.6 mm leg to U341.
- No thermal analysis was done.

**DFM**
- All copper obeys the board minimums (0.09 mm clearance, 0.175 mm hole clearance, 0.25/0.15 mm via).
- 38 stitching vias and about 350 new vias in total; hole count went from 750 to 1109.
- No Gerbers were generated.

## Repository state

- Branch `ai-place-route`, not pushed. `main` is untouched.
- `tools/kicad_ibis_simulation` (submodule pointer) was modified before I started and is still uncommitted.
- `STATUS.md` and `NEXT_SESSION.md` were not updated; they describe the board before this work.
- `work/` and `reports/` are git-ignored (router inputs/outputs per batch are in `reports/phase3`, `reports/phase4`).
