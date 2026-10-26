# Next session plan

Written 2026-10-26 (updated during phase 4). Background:
- `STATUS.md`: the overall state;
- `LAYOUT_PLAN.md`: the phases;
- `KRT_LEARNING.md`: how to drive KiCadRoutingTools, and every gotcha found so far.

Tools: `~/dev/KiCadRoutingTools` (venv `.venv`, with `ortools`); the skills are linked into `.claude/skills/`.

## Where we are

- **Main** holds the LPDDR4 re-routed at the 40 Ω widths (2026-10-26, phase 4): data bytes with `byte_chain.sh`
  and CK/CA trunk-and-branch with `ca_tb_chain.sh`, both with `--impedance 40`, then fitted to the JLC widths by
  `tools/ddr/widen.py` (TI135_PCB_NOTES.md §6.10). Every DDR net is connected, with no shorts, and the rest of the
  board is DRC-clean. The whole flow is `tools/ddr/ddr40_chain.sh IN WORKDIR`. KRT is not deterministic here, so
  re-runs differ; main is the `work/fit_cd1.0` candidate, plus four nets re-routed at width with
  `tools/ddr/reroute_nets.sh` (dq18 and rst_n; dm0 with byte 0 rippable; dm1 with byte 1 rippable) and re-fitted.
- **Measure timing** with `tools/p2k/bin/kipy tools/ddr/ddr_timing.py`: die to die, along each path, U501
  pad-to-die included.
- **Grade** with `tools/ddr/grade.sh NAME BOARD`: our rules, planes refilled, KiCad DRC. KiCad caps each DRC type at
  199 reports; `widen.py` prints the real narrow length per net.

| Check (Efinix §6.3) | Rule | Now (40 Ω board) |
|---|---|---|
| CA/CKE/CS − CK | ±5.3 ps (30 mil); budget ±100 ps | −64.5 … +39.1 ps; channels A/B equal |
| CK P/N | ≤ 0.9 ps | 3.7 ps |
| DQS P/N | ≤ 1.8 ps | 7.9 / 1.9 / 13.1 / 2.2 ps (bytes 0–3; DQS1/DQS2 routed as singles) |
| DQ/DM − DQS | 0 … 66 ps | −83…9 / −42…68 / −60…102 / 6…59 ps |
| Width (DDR, outside the BGAs) | 0.17–0.19 inner, 0.23–0.27 F/B; pairs 0.13–0.15 / 0.19–0.21 | clean |
| Other DDR DRC | – | 0 hole, 0 edge; 4 skew, 3 uncoupled (phase 3); 180 xtalk-spacing warnings |

## 1. ~~KiCad time-domain tuning setup~~ (done 2026-10-26, TI135_PCB_NOTES.md §6.9)

Done as planned: profiles on the net classes, `tools/ddr/kicad_delays.sh` (KiCad's own delay per net),
`ddr_timing.py --kicad` (per-net targets in KiCad terms). CA/CK targets: add +8 … +50 ps (CA4 is the longest).
Byte 0 needs up to +98 ps on DQ6, so the data bytes are better re-routed (step 2) than tuned.

Original plan:

1. In `tools/board_setup.py`, add two tuning profiles to `kicad/ti135_card.kicad_pro`, copied in form from the
   Agilex card's (`tuning_profiles.tuning_profiles_impedance_geometric`):
   - `LPDDR4 SE 40R JLC08161H-3313`: F/B 0.25 mm at 6.11 ps/mm, In2/In5 0.18 mm at 7.01 ps/mm.
   - `LPDDR4 DIFF 80R`: F/B 0.20/0.20 mm, In2/In5 0.14/0.15 mm.
   - Both: via 7.2 ps/mm, time-domain tuning on.

   Then set `tuning_profile` on the net classes `lpddr_dq` / `lpddr_ca` (SE) and `lpddr_diff` (DIFF).
2. Teach `tools/ddr/ddr_timing.py` to print **per-net targets in KiCad's own terms**. KiCad sums a net's whole copper,
   so a shared CA/CK net reads path + one branch. Then each net can be dialled to its number with the pcbnew tuner.
3. Check one net: KiCad's delay readout (net inspector or tuner) against `ddr_timing.py` (path + branch).

## 2. ~~Data bytes: clean re-route~~ (done 2026-10-26, `tools/ddr/byte_chain.sh`)

Best variant on main: `DQ_EXTRA="--ordering inside_out" tools/ddr/byte_chain.sh` (DQS via route_diff, DQ/DM per
byte group incl. DQS, `--time-matching`, tolerance 3 ps). All connected, no shorts. Rest of the board clean.
- **DQS P/N skew, KiCad readout:** 9.1 / 1.3 / 1.5 / 0.2 ps. Byte 0 still needs about 9 ps on DQS0_P.
- **DQ/DM − DQS, path model:** −12.7…81 / −1.8…68 / −20.9…79 / −0.9…47.5 ps. Most DQ need +5…+54 ps.
- **Tried and worse:** `--bus` (bus corridors); DQS halves as singles in the byte groups (meanders ran out of
  room, 12 misses); a horizontal DQS escape at U501 (no change).
- **Limit:** physical room for meanders in the corridor. DQS1/DQS2 can't couple: their U501 balls are stacked in
  one column, and the fan-out itself falls back to single-ended for them.

**Next: interactive tuning in pcbnew** with `tools/ddr/kicad_delays.sh > d.csv; kipy tools/ddr/ddr_timing.py --kicad
d.csv`. It lists every net with its target in KiCad's readout. As of 2026-10-26: CA/CK +8…+50 ps on 10 nets, about
20 DQ/DM +5…+54 ps, and DQS P/N on byte 0/1/2. Remake room where a meander does not fit.

Original plan:

Same method as the CK/CA work (KRT_LEARNING.md):
1. Rip each byte whole (DQ, DM, DQS P/N), so every net is point to point.
2. Fan out the DQS pairs with `bga_fanout.py --diff-pairs --diff-pair-gap <clearance>` on both BGAs. That gives
   coupled pair stubs, which `route_diff.py` needs.
3. Route DQS with `route_diff.py`, then DQ/DM with `route.py`. Include DQS in the byte's group (`[..]` patterns, never
   `?`) and use `--time-matching` (the U501 pad-to-die delays are now stored correctly, in ps).
4. Try one layer per byte with per-byte `--layers` (Efinix: keep a byte group on one layer).
5. Target: DQS P/N ≤ 1.8 ps, DQ/DM 0 … 66 ps over their DQS. Script it like `ca_tb_chain.sh` (`tools/ddr/byte_chain.sh`).

## 3. Delay tuning (started 2026-10-26; blocked on meander room, decision needed)

Tools:
- `ddr_timing.py --nets` lists every DQ/DM against its DQS. `--plan FILE` writes the delay each net must gain
  (CA/CKE/CS and both CK legs to the group's longest; per byte DQS P/N to max(P, N, longest DQ − 58), DQ/DM to at
  least DQS + 8). That keeps every DQ in 8…58 ps over DQS, inside Efinix's 0…66 ps.
- `tools/ddr/tune_meander.py` (KRT venv) meanders each net's same-layer chains outside the BGAs with KRT's trombone
  generator, which clearance-checks every bump, and writes edits. `tools/ddr/tune_apply.py` (kipy) applies them;
  then `widen.py` and `grade.sh`.

Findings on the 40 Ω board (main):
- The plan asks for **1453 ps (about 220 mm of meander)** on 37 nets, up to 112 ps on one net.
- **The tuner places 230–540 ps of it** (best: 0.8 mm amplitude, 2W arm pitch). The bundles are packed at the
  routing clearance, so a trace inside a bundle has no side free; there is free copper beside the bundles, but not
  next to the inner traces. KRT's own in-route matching hit the same wall ("No straight run with clearance").
- A test application (`work/p3/tuned_fit`): DQS2 P/N 13 → 1.1 ps, byte 0's dq0/2/5/7 to +3…+17 ps; byte 0's
  dq1/3/4 stay at −60…−65 ps, and dq16 goes to −105 ps (DQS2 moved up). 2 board-edge hits (KRT's meanders don't
  check the edge).
- **Re-routing to make room did not converge:**
  - routing clearance 0.15 / 0.2 (`byte_chain.sh` `RCL`): opens and spreads to 160–170 ps;
  - a matched byte-2 re-route (`reroute_nets.sh` `MATCH=1`): the router ripped and lost other nets.
- **Outliers set much of the plan:** DQS0 is ~50 ps longer than its byte needs. dq18/dq21 (+77/+102) and ca3 (−64.5)
  are the phase-4 re-routes, routed without matching.

Options (for the user):
1. **Accept the timing budget, not the length rule.** Efinix's ±75 ps DQ−DQS and ±100 ps CA−CK at 3.7 Gbps; the I3
   part runs ≤ 2.8 Gbps, so the real budget is larger. Then only a few nets need work: dq16, byte 2's top, byte 0's
   −83, and the DQS/CK P/N skews. The tuner can do most of that.
2. **Re-route the LPDDR4 with meander room**: one layer per byte (Efinix), a spaced corridor, re-routing the
   outliers short; then the tuner. A day's work, and the router's results vary run to run.
3. Tune by hand in pcbnew, pushing neighbours aside (KiCad's tuner does not shove).

## 4. LPDDR4 DRC clean-up (in progress 2026-10-26)

Done:
- **40 Ω.** In-place widening of the 0.1 mm routes failed: 77 % of the length had no room. So the LPDDR4 is now
  routed at the impedance width and fitted (`tools/ddr/ddr40_chain.sh`, `tools/ddr/widen.py`; TI135_PCB_NOTES.md
  §6.10). Narrow copper outside the BGAs: 1444 → 70 mm.
- **Pair-gap errors (8 → 0):** `lpddr_bga_neckdown` now has an explicit `diff_pair_gap` max; KiCad was carrying over
  the 0.22 mm max of `lpddr_diff_outer`.
- **Hole clearance:** the U801 DQS fan-out pair gap is now 0.1 mm, which centres the pair in its channel (0.175 mm to
  both via holes; route_diff then runs at the class clearance 0.1, `DQS_CL`). Re-runs with it have 2–4 hole hits
  instead of 7–8. The board on main predates this change (7 hits).

- **Narrow nets (2026-10-26, later):** `widen.py` now models the clearances exactly (0.1 mm copper for every net
  class, 0.175 mm via holes, 0.28 mm PTH holes, round pads as circles) and fits in three steps: every segment to the
  minimum, a sideways nudge of the runs still narrow (polyline offset between anchors), then to the target. `--why`
  names the blocker of each narrow segment. What still did not fit was re-routed at width with
  `tools/ddr/reroute_nets.sh` (`--impedance 40 --escalation off`). dm0 and dm1 fit only when their byte's other
  nets may be ripped and re-routed (`EXTRA="--rip-existing-nets ..."`). 115 width errors → 1.
- **Hole clearance 7 → 0, edge 1 → 0:** a clearance-repair step in `widen.py` nudges any DDR segment that does not
  clear, inside the BGAs too. A DQS stub in U801's 0.8 mm channel goes to the 0.09 mm neck-down minimum first: at 0.1
  mm, two legs with a 0.1 gap and 0.175 mm to both holes fill the channel exactly. The thin 0.0898 mm neck-down
  segments KRT leaves are raised to 0.09.

Left:
- ~~cs2_n~~ done: R801 moved 10 µm in −x (DDR_CAL resistor, nothing routed to it yet); the nudge centres cs2_n in
  the 0.431 mm opening with 0.5 µm steps. DDR width errors: 0.
- 4 skew and 3 uncoupled (DQS/CK pairs; these go with phase 3 tuning).
- 240 crosstalk-spacing warnings (0.2 / 0.3 mm). The routes were laid at 0.11 mm clearance; re-routing at 0.2 mm
  (`CL=0.2`) was worse (an open net and 12 clearance errors).
- Efinix: ≥ 100 mil from the 0V85/1V1 switching nodes, and return vias at layer changes.

**Phase 3 targets must be recomputed on this board** (`kicad_delays.sh` + `ddr_timing.py --kicad`). The bytes spread
53–162 ps, against 48–100 ps on the 0.1 mm board, so tuning needs more meander room. In byte 0 every DQ/DM now runs
up to 83 ps shorter than DQS. Phase 3 is next; meanders must keep the 40 Ω widths (`widen.py` again afterwards).

## 5. LPDDR4 sign-off (your review)

`ddr_timing.py` all PASS, `grade.sh` with no DDR errors, a picture per layer, the swizzle unchanged
(`tools/lpddr4_swizzle_score.py`).

## 6. Then the rest of the board (LAYOUT_PLAN.md phases 4–6)

eMMC (length-matched to CLK) → QSPI flash → RGMII and the MDI pairs to J9 → the rest → 3V3, GND stitching, F/B GND
flood → `/review-routed-board` → Gerbers/BOM/CPL with `tools/jlc`.

## Optional

- The baseboard header insulator height (the gap is assumed ≈ 5.3 mm).
