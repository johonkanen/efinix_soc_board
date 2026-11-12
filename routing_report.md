# Routing report: remaining placement and routing (2026-11-12, branch `ai-place-route`)

Board: `kicad/ti135_card.kicad_pcb`, KiCad 10.0.7. Start: commit 9b6150d on `main`. The plan is
`layout_plan_remaining.md`; this report says what was done, what is still open and what a person should
look at. **The board is not finished: 12 connections are open** (list below and the last section). VCCA_BL reaches its ball
since the follow-up of the same day (section "Follow-up: vcca_bl").

## Result

`kicad-cli pcb drc --schematic-parity --severity-all` (report in `reports/drc_final.rpt`, git-ignored):

| | Start | Now |
|---|---|---|
| Unconnected items | 448 | **12** |
| Errors other than unconnected | 26 (8 shorts, 6 hole clearance, 6 mask bridge, 6 courtyard) | **0** |
| Schematic parity | 0 | 0 |
| Warnings | 114 (57 dangling vias, 55 dangling tracks, 2 isolated copper) | 74 (43 dangling vias, 31 dangling tracks) |

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

## Open: 12 unconnected items (the table below is the state before the second follow-up; see the last section)

Each was tried at least three ways and then left, as the brief asks.

| Net | What is open | Why |
|---|---|---|
| `vcca_bl` (4 items) | four small filter caps: C5060 (100 n), C5062 (10 n), C5063, and C502 beside the PHY | their pads are boxed in on B.Cu by the 0V85 and VCORE feeds to the two ferrites and by GND stubs; routing them first boxes the ferrite inputs in instead. The supply itself is connected: VCORE → FB501 → C501 (1 µ) → ball R8, with C5061 (10 n) 1.6 mm from the ball |
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
- `vcca_bl` is fed but has only 1 µ + 10 n of its filter connected (above); the Efinix checklist row for
  VCCA is 2 × 100 n, 2 × 10 n, 1 n. The other PLL supplies are routed at 0.12–0.2 mm.
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

## Follow-up: vcca_bl (2026-11-12, after the report)

You asked me to move Ethernet tracks to get `vcca_bl` through. **No Ethernet track was moved**: Ethernet
was not what blocked it. Ball R8 was boxed in on B.Cu by copper I had added myself in phases 3 and 4 (the
DDR PLL supply looped around R8's via, and the VCORE and 0V85 feeds to FB501 and FB504 ran beside it).
I lifted those traces (`tools/remove_ops.py` removes exactly what an earlier router run added) and routed
in this order: `vcca_bl` core, VCORE to FB501, 0V85 to FB504 and its caps, then the DDR PLL supply.
- Connected now: FB501.2 – C501 – ball R8 (0.2 mm and 0.12 mm, B.Cu, 4.0 + 4.6 mm), C5061 – R8 (1.9 mm).
- Re-routed and connected as before: VCORE → FB501.1 (7.9 mm), 0V85 → FB504.1, C531, C533, the whole DDR
  PLL supply (`vddpll_mcb_top_phy_ddr`; its 10 n cap C5072 now has a 20.8 mm trace, C5073 10.7 mm).
- These nets run at the board's 0.1 mm clearance to LPDDR4 vias and pads in the ball field (static nets).
- Still open on `vcca_bl`: C5060, C5062, C5063, C502.
- DRC: 0 errors, 15 unconnected; `verify_protected.py check`: no differences.
The Ethernet-boxed pads (C542, C940/C941, U901 pins 28 and 38) are unchanged and still open.

## Follow-up 2: the pads boxed in by Ethernet (2026-11-12)

You allowed moving Ethernet tracks for C542, C940/C941 and U901 pins 28 and 38. Result: three of four
fixed, unconnected 15 -> 12, DRC 0 errors, `verify_protected.py check` no differences.

| Pad | Result | What moved |
|---|---|---|
| U901 pin 38 (`phy_vdd10`) | connected to C934 pin 1 | nothing: a hand-placed 0.09 mm F.Cu stub, 1.3 mm, passes the `phy_xo` via at the minimum clearance |
| C940 / C941 pin 1 (3V3) | connected to the 3V3 via at U901 pin 29 (1.4 mm, F.Cu) | `phy_rx_ctl` lifted between the caps and the PHY and re-routed: U901 pin 26 -> 1.7 mm F.Cu, then 4.2 mm with one new via to its In2 run. Its PHY-side length is now 8.5 mm (`phy_rxc` 8.0, `phy_rxd1` 8.6, `phy_rxd2` 8.7) |
| U901 pin 28 (`phy_dvdd_rg`) | connected: 0.8 mm F.Cu and one via into its B.Cu pour (which holds C936) | nothing more; the space came from moving `phy_rx_ctl` |
| C542 pin 1 (1V1) | **still open** | connecting it needs the gap that `rgmii_txd1` and `eth_rst_n` use on B.Cu beside ball via R1; with those two lifted the cap connects (1.8 mm), but neither signal can then leave its ball (P3, K2) on any layer. The attempt was discarded; nothing of it is on the board |

Tools: `tools/rip_box.py` (lifts named nets inside a box), `tools/fix_area.sh` (lift, route the power pad,
re-route the lifted nets, check). Router results are in `reports/phase7/`.

Open now (12): `vcca_bl` caps C5060, C5062, C5063, C502 (4 items); C542 pin 1; `adc_cs_n`; `uart_tx`;
`t_irq`; `fpga_ssu_n`; `pg_all` (U341 pin 6); and two zone items: the `phy_dvdd_rg` B.Cu pour is still in
two pieces (the smaller piece carries no pad) and slivers of the PHY GND pour.

## Follow-up 3: moving the PLL filter parts to the top side (2026-11-12, tried and discarded)

The user found the B.Cu strip north-east of U501 messy and pointed out free room on F.Cu. Tried on a work
copy (`tools/place_fix.py` set `pll_top`): FB501, C501, C502, C5060 and FB504 to F.Cu east of the DDR
corridor (x 176–179, y 71–77), with the wiring of `vcca_bl`, the DDR PLL supply and the ferrite feeds
lifted and re-routed. **Result worse than the board as committed, so nothing was accepted:**
- FB501 on F.Cu could not be reached on either pad, and neither top-side group could be joined to its
  ball. Balls R8 and W11 sit in the middle of the DDR ball rows (x 166.8 and 164.4); a feed from the east
  has to cross the whole DDR field on B.Cu, which is what the parts next to the balls avoid.
- The ferrite inputs need VCORE (In3, x <= 173.7, y >= 76) and 0V85 (In4, x <= 172.9); neither plane
  reaches the free F.Cu area, so each input became a 10 mm trace.
The board is unchanged from commit 442cbe1.

## Follow-up 4: B.Cu strip north-east of U501 tidied; bulk caps to the top (2026-11-12)

User request (options 1 and 2). `tools/tidy_strip.sh` on a work copy, then accepted:
- Lifted the copper this project's scripts had added in x 160–181.5, y 66–84 (131 rail stubs, vias and
  feeds, plus all of `vcca_bl` and the DDR PLL supply) and routed it again with the grid router in a fixed
  order (vcca_bl core, ferrite feeds, DDR PLL supply, then the rail pads), so the new traces are at
  45 degrees. Nothing that was on the board before phase 3 was removed.
- Moved to F.Cu east of the DDR corridor, each tied by vias to its plane: C538 (10 u, 1V1) to
  (178.6, 71.2), C5023 (10 u, 1V8) to (182.75, 70.0), C5020 (47 u, 1V8) to (180.65, 69.05). They are now
  6–12 mm from where they were, further from U501's balls; acceptable for bulk capacitance, not for
  the small caps, which stayed.
- C542 was not moved: its GND pad carries older copper.
- New vias keep 0.3 mm from LPDDR4 copper on every layer whatever the track setting (router change).
- DRC: 0 errors, 12 unconnected, the same twelve as before the tidy. `verify_protected.py check`: no
  differences. `pg_all`: not routed further at the user's word; it stays listed until the net leaves
  the schematic.

## Follow-up 5: 0805 bulk caps moved out from under U501 (2026-11-12)

User request. `tools/bulk_out.sh`: the tie-ins this project had added at the caps' old pads were lifted,
the caps flipped to F.Cu and placed south of the BGA, and tied to their planes again by the grid router.

| Cap | Rail | Was (B.Cu, under U501) | Now (F.Cu) |
|---|---|---|---|
| C509 22 u | VCORE | (157.34, 86.52) | (159.70, 93.25) |
| C5005 10 u | VCORE | (159.15, 89.30) | (160.00, 96.05) |
| C5004 10 u | VCORE | (162.95, 87.20) | (162.85, 95.85) |
| C5021 47 u | 1V8 | (166.95, 89.10) | (167.25, 97.20) |
| C5026 10 u | 1V8 | (170.00, 89.25) | (171.90, 96.80) |

- Not moved: C5003 (47 u, VCORE) and C5024 (10 u, 1V8). Their pads carry copper from before this work,
  which the scripts do not remove. The 4.7 u 0402 caps under the BGA were not counted as large.
- Each moved cap is tied with 0.2–0.3 mm stubs and 0.30/0.15 vias, one per connection; for 22–47 u bulk
  caps a second via per pad would be better and is easy to add by hand.
- The new spots are on F.Cu above the B.Cu regulator cells (y 93–97); In1/In3/In4/In6 lie between.
- DRC: 0 errors, 12 unconnected (the same twelve). `verify_protected.py check`: no differences.

## Follow-up 6: C5003 and C5024 moved out as well (2026-11-12)

The user allowed lifting the older copper on their pads: 15 unlocked items (5 VCORE, 7 1V8, 3 GND tracks
and vias ending in the four pads) were removed with `tools/rip_box.py`, then the caps were flipped to F.Cu
(`tools/place_fix.py` set `bulk_out2`) and the rails tied again by the grid router, including the
neighbouring pads that had hung on the lifted copper (C5002 among them).

| Cap | Rail | Was (B.Cu, under U501) | Now (F.Cu) |
|---|---|---|---|
| C5003 47 u | VCORE | (155.10, 89.30) | (150.70, 93.30), south-west of the BGA |
| C5024 10 u | 1V8 | (153.35, 78.00) | (150.40, 79.00), west of the BGA |

All seven 0805 bulk caps are now outside U501's outline. DRC: 0 errors, 12 unconnected (the same
twelve). `verify_protected.py check`: no differences.

## Follow-up 7: the fifteen 4.7 u 0402 caps moved out from under U501 (2026-11-12)

`tools/bulk47.sh` (`tools/place_fix.py` set `bulk47`). Each cap went to the nearest free spot outside
U501's courtyard and outside the LPDDR4 region that has its rail's plane underneath (survey of both
sides). 21 unlocked B.Cu tracks ending on the old pads were lifted with `tools/rip_box.py`; vias were
left because they may also serve a ball. Ties were made by the grid router (`--plane-vias`, 0.3 then
0.2 mm) and `tools/rail_vias.py`; ops in `reports/phase12/`.

| Cap | Rail | Was (B.Cu, under U501) | Now |
|---|---|---|---|
| C562 | 3V3 | (153.01, 84.55) | B.Cu (150.27, 84.50) |
| C5056 | 1V1 | (154.20, 75.70) | B.Cu (150.98, 69.00) |
| C5055 | 1V1 | (154.55, 74.20) | B.Cu (150.50, 65.77) |
| C5027 | 1V8 | (154.70, 72.00) | F.Cu (150.50, 75.52) |
| C5029 | 1V8 | (155.00, 77.70) | B.Cu (150.50, 80.02) |
| C513 | VCORE | (157.23, 89.81) | B.Cu (156.75, 93.48) |
| C5030 | 1V8 | (160.05, 86.45) | B.Cu (164.73, 92.50) |
| C512 | VCORE | (160.40, 84.20) | B.Cu (161.00, 92.98) |
| C511 | VCORE | (162.40, 79.00) | B.Cu (164.98, 95.25) |
| C514 | VCORE | (164.00, 83.00) | B.Cu (172.25, 96.98) |
| C5048 | 3V3 | (165.50, 86.45) | F.Cu (151.25, 88.52) |
| C5049 | 3V3 | (167.50, 87.55) | F.Cu (180.77, 87.50) |
| C553 | 1V8 | (169.98, 80.29) | F.Cu (177.50, 80.73) |
| C5054 | 1V1 | (171.70, 72.10) | B.Cu (179.75, 72.27) |
| C5028 | 1V8 | (173.00, 85.85) | B.Cu (177.25, 88.02) |

- C5056, C5055, C5027 and C5054 had frozen (locked, tier B) 1V1/1V8/GND stubs ending on their old pads.
  That copper was not touched: eight stubs (0.02–1.5 mm) now end in nothing under the BGA and show as
  `track_dangling` warnings (31 -> 40 in total, with one 3V3 stub whose via still carries a connection).
  Deleting them needs the user's permission.
- C5055 is tied to 1V1 through C5056's pad (2.8 mm of 0.3 mm track), C5056's GND runs 3.8 mm to a via;
  every other tie is at most 2.5 mm, one 0.30/0.15 via per connection.
- C5056/C5055 sit at x 150.5, just west of the narrowed LPDDR4 region (x 152–176.5).
- No 4.7 u cap is left inside U501's courtyard; the 0201 (100 n/10 n/1 n) and 1 u 0402 caps stay.
- DRC: 0 errors, 12 unconnected (the same twelve nets). `verify_protected.py check`: no differences.

## Follow-up 8: frozen stubs at the old 4.7 u pads deleted (2026-11-12)

With the user's permission, eleven locked tier B segments on B.Cu that ended in nothing after Follow-up 7
were deleted with `tools/remove_frozen_stubs.py` (only tracks that DRC reported as dangling, near the old
pads of C5056, C5055, C5027, C5054 and one GND stub at (156.0, 77.0); no vias): 3 on 1V1, 2 on 1V8, 6 on
GND. `verify_protected.py check` showed exactly these eleven as removed and nothing else; the baseline
`protected_baseline.json` was then re-taken. DRC: 0 errors, 12 unconnected (the same twelve),
`track_dangling` 40 -> 32, `via_dangling` 43.

## Follow-up 9: fifteen 1 u 0402 rail caps moved out from under U501 (2026-11-12)

`tools/bulk47.sh work/NAME bulk1u "REFS"` (`tools/place_fix.py` set `bulk1u`), same method as Follow-up 7:
36 unlocked B.Cu tracks lifted at the old pads, ties by the grid router (ops in `reports/phase14/`), then
16 unlocked leftovers that DRC reported as dangling removed with `tools/remove_dangling.py`.

| Cap | Rail | Was (B.Cu, under U501) | Now | Moved |
|---|---|---|---|---|
| C5051 | 3V3 | (153.95, 80.70) | B.Cu (150.02, 82.25) | 3.6 mm |
| C5052 | 3V3 | (154.55, 82.65) | F.Cu (150.00, 85.52) | 5.4 mm |
| C5050 | 3V3 | (154.95, 80.78) | B.Cu (147.75, 80.52) | 7.2 mm |
| C5032 | 1V8 | (155.28, 79.08) | B.Cu (147.00, 74.02) | 9.0 mm |
| C5007 | VCORE | (155.85, 84.95) | B.Cu (166.50, 92.77) | 13.9 mm |
| C5008 | VCORE | (157.10, 88.10) | F.Cu (165.27, 100.25) | 14.6 mm |
| C540 | 1V1 | (160.41, 72.97) | B.Cu (149.00, 66.52) | 13.1 mm |
| C5006 | VCORE | (163.70, 84.85) | F.Cu (172.27, 99.75) | 17.0 mm |
| C5031 | 1V8 | (169.60, 86.40) | F.Cu (177.25, 88.98) | 7.8 mm |
| C541 | 1V1 | (172.00, 75.80) | B.Cu (179.00, 77.48) | 6.6 mm |
| C5035 | 1V8 | (173.00, 83.90) | B.Cu (177.75, 81.27) | 5.4 mm |
| C542 | 1V1 | (173.30, 79.10) | B.Cu (180.02, 81.50) | 7.5 mm |
| C5034 | 1V8 | (173.75, 81.20) | B.Cu (178.50, 85.27) | 6.3 mm |
| C539 | 1V1 | (174.33, 74.47) | B.Cu (178.52, 79.00) | 6.2 mm |
| C5033 | 1V8 | (174.35, 79.00) | B.Cu (181.75, 77.77) | 7.5 mm |

- C542 pin 1 (1V1), open since Phase 4, is now tied to the 1V1 plane: unconnected 12 -> 11.
- Not moved: C528, C529, C530, C531 (0V85). Outside the BGA the 0V85 plane is a 3 mm corridor to its
  regulator; the nearest free spots with the plane underneath are 23-31 mm from the old positions.
- Not moved: C501 (vcca_bl), C507 (vddpll), C503 (vcca_br). They are the PLL filter caps behind the
  ferrites, not rail bulk; C503 already sits outside U501's courtyard.
- Two frozen (locked) stubs now end in nothing: 1V1 0.87 mm at (160.41, 73.45) (C540's old pad) and GND
  1.05 mm at (173.30, 78.62) (C542's old pad). Not touched; deleting them needs the user's permission.
- Baseline correction: re-taking `protected_baseline.json` in Follow-up 8 had also pulled in eight unlocked
  GND segments that were routed during this work (snapshot takes all rail copper within 1 mm of protected
  pads). One of them was C539's own stub, so the check flagged its removal. The eight were dropped again:
  the baseline is the earlier one minus the eleven segments deleted in Follow-up 8, nothing else.
- DRC: 0 errors, 11 unconnected, `track_dangling` 33, `via_dangling` 43. `verify_protected.py check`: OK.
