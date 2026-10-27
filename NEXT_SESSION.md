# Next session plan (phases, 2026-10-27)

Written for an agent starting with a fresh context. Work **one phase at a time**: finish it, commit, push, update
this file and `STATUS.md`, then stop and report to the user, who reviews each phase before the next starts.

## Read first

- `STATUS.md`: what the card is, where everything stands, how to build.
- `HW_CHECKLIST_REVIEW.md`: Efinix's hardware checklist for this exact part (Ti135 N484, SPI x4) against the card.
- `TI135_PCB_NOTES.md`: device and layout rules (§6 LPDDR4: §6.3 routing rules, §6.5 stack-up, §6.7 BGA fan-out
  and decaps, §6.10 the 40 Ω routing and width fit).
- `KRT_LEARNING.md`: how to drive KiCadRoutingTools, its gotchas and possible bugs. Read before any routing.

## Rules (from the user; do not break)

- **Never modify `~/dev/agilex3_soc_control_card`** (another session owns it). Reading is fine. `tools/board_setup.py`
  copies the LPDDR4 rules from it; that is intended.
- **KiCad must be closed** before writing any file under `kicad/`. Check for `kicad/~ti135_card.kicad_pro.lck` and
  for board/schematic files newer than the last commit; if either, stop and ask.
- Schematics are **generated**: change `tools/sheets/*.py`, run `tools/build_schematic.sh`, never edit `.kicad_sch`.
  A footprint change reaches the board with `tools/swap_footprint.py` (keeps nets, fields, schematic link).
- Efinix files (copyright) live in `reference/efinix/` (gitignored; only its README is in git).
- No silkscreen on this card beyond a few custom markings: ignore silkscreen DRC.
- Commit trailer (always):
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01DJMRtrVk88ZxPrcLoqXbjd
  ```
  Push with plain `git push`. Ask the user before anything outward beyond that (orders, upstream bug reports).
- Keep `STATUS.md` and this file current at every stopping point.

## Decisions taken (user, 2026-10-27)

1. **LPDDR4 acceptance = the checklist's skew limits** (HW_CHECKLIST_REVIEW.md item 6): DQ/DM–DQS ≤ 75 ps,
   CK–DQS ≤ 350 ps, A/CKE/CS–CK ≤ 100 ps, die to die (package delays included). DQS P/N skew: aim ≤ 1.8 ps
   (user guide), report what is reached. Base: the routing on branch **`ddr-option2`** (DQ–DQS −24…+60 ps).
2. **U801 stays where it is.**
3. **Decoupling follows Efinix's table in full** (HW_CHECKLIST_REVIEW.md, "Decoupling").
4. One phase at a time, the user reviews each. The user may route parts of the memory by hand later.

## Tools (all in the repo)

| Task | Command |
|---|---|
| Build schematic / PCB checks | `tools/build_schematic.sh`; `tools/build_pcb.sh` (no `--rebuild`: that drops routing) |
| KiCad Python / CLI | `tools/p2k/bin/kipy script.py`; `tools/p2k/bin/kicad-cli`; `source tools/p2k/bin/kicad_env.sh` for `$KICAD_MOUNT` |
| KRT (router) | `~/dev/KiCadRoutingTools/.venv/bin/python -X utf8 ~/dev/KiCadRoutingTools/py_router/route.py ...`; always `KICAD_RIP_PREEXISTING=0` |
| DDR grade (refill, DRC, per-byte) | `tools/ddr/grade.sh NAME BOARD` → `work/grade/NAME/drc.rpt` |
| DDR timing / plan | `tools/p2k/bin/kipy tools/ddr/ddr_timing.py BOARD [--nets] [--plan FILE]` |
| Width fit, clearance repair | `tools/p2k/bin/kipy tools/ddr/widen.py IN OUT [--why]` (also nudges, splits at courtyards) |
| Meander top-up | `tools/ddr/polish.sh IN OUT` (`ONLY="ddr_dq9 ..."`); `tools/ddr/tune_meander.py` + `tune_apply.py` |
| Re-route a few DDR nets | `tools/ddr/reroute_nets.sh IN WORKDIR dq9 dm1` (`PAIR=1` for DQS pairs, `EXTRA="--rip-existing-nets ..."`) |
| Re-route bytes | `tools/ddr/byte_seq.sh` (`MODE=net NET_ORDER=far RIP_BYTES=..`); CA/CK: `tools/ddr/ca_tb_chain.sh` |
| Decaps on BGA via pairs | `tools/p2k/bin/kipy tools/place_bga_decaps.py IN OUT REF...` (smallest caps first) |
| Pictures | `tools/render_ddr.py BOARD OUT.png U501 U801`; `tools/render_board.py BOARD OUT.png` (KRT venv python) |
| IO routing sketch | `tools/io_sketch.sh IN WORKDIR` |
| Zone refill | `tools/p2k/bin/kipy work/grade/<any>/refill.py BOARD` (written by grade.sh) |
| JLC parts | `python3 -I tools/jlc/jlc_search.py "<keywords>"` |

Work on copies under `work/` (gitignored) and copy the result into `kicad/` only when it grades clean. DRC with
schematic parity must run on the board **in `kicad/`** (a copy elsewhere has no sub-sheets).

## Phase 1: LPDDR4 from `ddr-option2` onto main — **done 2026-10-27**

Result (on main, `kicad/ti135_card.kicad_pcb`):
- `tools/ddr/transplant.py` replaced main's LPDDR4 copper (2684 items, 139 vias) with option 2's (3569, 148 vias).
  Only clash: C528 (1 µF 0402, 0V85, B.Cu) sat on a `ddr_dq2` via; `place_bga_decaps.py C528` moved it 0.3 mm
  (+x). Nothing else changed outside the DDR copper (footprints, non-DDR tracks/vias, zones compared by script).
- `widen.py` changed nothing (option 2 was already fitted): **88 mm below the width minimum**, per net dq25 18.9,
  dm3 17.3, dq1 16.0, dq24 12.9, dm0 8.3, dq26 6.9, dm1 3.2, dq29 2.1, dq6 1.6, dq10 0.6 (KiCad: 199 `track_width`,
  capped; all `min`; one is dm3 below the 0.09 neck-down inside a BGA).
- DRC (`tools/build_pcb.sh`): schematic parity 0; non-DDR entries identical to main before the change; all DDR
  nets connected (615 unconnected items board-wide, same as before, all unrouted non-DDR). DDR: 4
  `skew_out_of_range` (DQS0/1/3, CK P/N), 2 `diff_pair_uncoupled_length_too_long` (DQS0 19.1 mm vs 12), 199
  `track_width`, 499 crosstalk-spacing warnings (`lpddr_xtalk_*`, warnings only), 1 `via_dangling` warning on
  ddr_ca5 (already on main).
- Timing (`ddr_timing.py --nets`, die to die): DQ/DM–DQS byte 0 +13.5…+57.1, byte 1 −23.9…+55.8, byte 2
  +7.2…+44.8, byte 3 +10.9…+60.4 ps (≤ 75 ✓); CK–DQS max 86 ps (DQS 338.9/226.6/240.3/194.3, CK 252.6; ≤ 350 ✓);
  CA/CKE/CS–CK −57.1…+47.0 ps (≤ 100 ✓). P/N skew: DQS 4.47 / 6.64 / 0.07 / 5.61 ps, CK 3.67 ps (phase 2).
  KiCad's own readout (`kicad_delays.sh`) agrees with the path model as before (0…+28 ps, shared CA nets more).
- Layers per byte: B0 In2 81 %, B1 F 39 % / In2 38 %, B2 In5 75 %, B3 B.Cu 76 %, CA In5 51 %.
- Gotcha: `widen.py` (and anything reading net classes through pcbnew) needs the `.kicad_pro`/`.kicad_dru` copied
  beside the board under `work/`; without them DQS is taken as single-ended and widened to 0.18 mm.

The original plan, for reference:

Main has newer placement (analog section, level shifters, 0201 decaps on via pairs under U501, hand moves) but
the older, untuned LPDDR4. `ddr-option2` has the better LPDDR4 on the older placement. Same U501/U801 poses.
This comes before the decoupling work because byte 3 runs on B.Cu under U501, where more decaps will go.

1. Write `tools/ddr/transplant.py IN_MAIN FROM_BOARD OUT`: remove every track and via of the LPDDR4 nets
   (`ddr_` in the name, not `DDR_CAL`) from main, copy those of the other board in (same net names, layers,
   widths), keep everything else. pcbnew SWIG: remove last (KRT_LEARNING.md).
2. Grade it (`tools/ddr/grade.sh`). Expect clashes where main's new parts sit on option-2 copper. The most likely
   are the 0201/0402 decaps under U501 (B.Cu, byte 3 runs there). Fix by moving the caps
   (`tools/place_bga_decaps.py` re-placement, or a nudge), not the DDR copper, where possible.
3. `tools/ddr/widen.py` (fit + clearance repair), `tools/pad_to_die.py`, grade, `ddr_timing.py --nets`.

Done when: all DDR nets connected; no DDR DRC errors except the known `skew_out_of_range` /
`diff_pair_uncoupled` on DQS/CK pairs and `track_width` (listed with mm per net); timing within decision 1
(report the numbers); rest of the board unchanged (DRC parity clean, no new non-DDR errors). Commit on main.

## Phase 2: LPDDR4 clean-up on main

- Width: 88 mm below the minimum (`widen.py --why` lists it; per net in phase 1 above). Re-route those nets at width
  (`reroute_nets.sh`, `--escalation off`, allow ripping their byte's other nets), then re-check timing.
- DQS P/N skew (4.5 / 6.6 / 0.07 / 5.6 ps on option 2): try `polish.sh` with `ONLY` on the DQS legs, or a
  `reroute_nets.sh PAIR=1`; accept and report what remains if the room is not there.
- Keep decision 1 satisfied after every step (`ddr_timing.py --nets`).

Done when: no `track_width` DDR errors; timing within decision 1; DQS skews reported.

## Phase 3: checklist fixes (HW_CHECKLIST_REVIEW.md "To act on")

1. **DDR_CAL**: R801 240 Ω **0.1 %** (sheet 08 generator; find an LCSC part with `jlc_search.py`).
2. **SSU_N** (U501 L4): 10 k pull-up to 1V8 (sheet 06 generator; net from the ball).
3. **Decoupling** to Efinix's table, per rail (the "Missing" column): add the 10 nF and 1 nF parts as 0201, the
   rest at the sizes in use (1 µF/4.7 µF 0402, 10 µF+ 0805 or larger). Generators: `tools/sheets/05_fpga_power.py`
   (`ROWS`; `C0201` exists in `_common.py`). Then rebuild the schematic and add the new parts to the board without
   `--rebuild` (that drops routing): build each new footprint the way `tools/make_board.py` does (library
   footprint, fields, schematic path, pad nets), or ask the user to run KiCad's "Update PCB from Schematic".
   Place them: 0201s on rail/GND via pairs under U501 (`place_bga_decaps.py`, smallest first), bulk at the BGA
   edge on B.Cu.
4. **47 µF at each regulator output** (the five TLV62585 cells): in the regulator sheet generators, placed in the
   cells on B.Cu next to the existing output caps; check the TLV62585 data sheet's output-capacitance limit first.

Done when: each item in HW_CHECKLIST_REVIEW.md "To act on" 1–4 is done or explained there; ERC as before
(two known notes); DRC parity clean; LPDDR4 untouched (grade.sh: same result as after phase 2).

## Phase 4: CK/CA/CKE/CS on one layer (checklist)

Today the CA trunk runs over In5/In2/F. Re-route CK/CA as trunk-and-branch on one layer (`ca_tb_chain.sh` with
`--layers` restricted; the T vias stay in U801's free columns), then match CA–CK within 100 ps (decision 1).
The bytes stay. Try a few runs (KRT is not deterministic) and keep the best.

Done when: ≥ 90 % of CA/CK copper on one layer, CA–CK within ±100 ps, CK P/N skew reported, no new DRC errors.

## Phase 5: rest of the routing

Starting point: `tools/io_sketch.sh` (185/198 nets in the sketch on branch `io-sketch`). Make it real:
eMMC (length-matched to its CLK), QSPI flash, RGMII (TX series resistors at the FPGA, RX at the PHY), MDI pairs to
J9 (100 Ω), 3V3 / 3V3_analog power, everything else. Then fix every hole-clearance hit and dangling stub.

Done when: 0 unconnected items (planes refilled), no DRC errors, LPDDR4 unchanged.

## Phase 6: return paths and stitching

- GND return vias within ±250 mil of every DDR layer change (DDR user guide); GND stitching around the board edge
  and between the planes; F/B GND pours where free.
- Check the ≥ 100 mil distance from the 0V85/1V1 switch nodes (B.Cu cells) to DDR traces (Efinix).

Done when: those checks are scripted and pass; DRC clean.

## Phase 7: review and fab outputs (user decides on ordering)

`/review-routed-board` skill; a last pass over HW_CHECKLIST_REVIEW.md; Gerbers, BOM and CPL with `tools/jlc`
(`fab_outputs.sh`), stock check for 5–10 boards. Do not order: hand the files to the user.

## Reference material

- Efinix dev boards imported to KiCad (`reference/efinix/devboards/`): Ti375 C529 is the closest (0.8 mm FPGA,
  one x32 LPDDR4 of the same package). Its plan: two bytes per inner layer, CA/CK alone on a third inner layer,
  big meanders in an open band between the parts (`tools/render_ddr.py ... U20 U23`).
- Branches: `ddr-option2` (LPDDR4 candidate), `io-sketch` (IO sketch); tag `ddr40-before-reroute` (the LPDDR4
  before option 2).
