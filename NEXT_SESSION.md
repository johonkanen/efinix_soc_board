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
  re-runs differ; main is the `work/fit_cd1.0` candidate.
- **Measure timing** with `tools/p2k/bin/kipy tools/ddr/ddr_timing.py`: die to die, along each path, U501
  pad-to-die included.
- **Grade** with `tools/ddr/grade.sh NAME BOARD`: our rules, planes refilled, KiCad DRC. KiCad caps each DRC type at
  199 reports; `widen.py` prints the real narrow length per net.

| Check (Efinix §6.3) | Rule | Now (40 Ω board) |
|---|---|---|
| CA/CKE/CS − CK | ±5.3 ps (30 mil); budget ±100 ps | −47.5 … +39.1 ps; channels A/B equal |
| CK P/N | ≤ 0.9 ps | 3.7 ps |
| DQS P/N | ≤ 1.8 ps | 8.5 / 1.9 / 12.9 / 1.9 ps (bytes 0–3; DQS1/DQS2 routed as singles) |
| DQ/DM − DQS | 0 … 66 ps | −59…56 / −35…60 / −60…103 / 5…58 ps |
| Width (DDR, outside the BGAs) | 0.17–0.19 inner, 0.23–0.27 F/B; pairs 0.13–0.15 / 0.19–0.21 | 70 mm below the minimum (115 segments): dm0 24.6, dq18 9.3, rst_n 8.4, dq21 6.1, ca5 4.7 mm … |
| Other DDR DRC | – | 7 hole clearance, 4 skew, 3 uncoupled, 1 edge (dm2), 240 xtalk-spacing warnings |

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

## 3. CK/CA final tuning (1 h)

- CK is about 20–35 ps short of the long CA nets, and CK_P/N differ by 9 ps. Lengthen CK and match its two halves.
  Then pull CA4, CA1 and CS0 in (or bring the rest up) to ±5.3 ps.
- Use the KiCad tuner with the targets from step 1, or a meander pass with room made for CK_P.

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

Left:
- **The remaining 70 mm of narrow DDR copper** (115 `track_width` errors): KRT necked dm0 (24.6 mm), dq18, dq21 and
  others where it found no room, and `rst_n` is in neither chain. Re-route these few nets at width, or move
  neighbours by hand. Five neck-down segments are 0.0898 mm against a 0.09 minimum.
- 7 hole clearance (6 are DQS stubs inside U801, 5 µm short), 1 edge clearance (dm2 at 0.481 mm), 4 skew and 3
  uncoupled (DQS/CK pairs; these go with phase 3 tuning).
- 240 crosstalk-spacing warnings (0.2 / 0.3 mm). The routes were laid at 0.11 mm clearance; re-routing at 0.2 mm
  (`CL=0.2`) was worse (an open net and 12 clearance errors).
- Efinix: ≥ 100 mil from the 0V85/1V1 switching nodes, and return vias at layer changes.

**Phase 3 targets must be recomputed on this board** (`kicad_delays.sh` + `ddr_timing.py --kicad`). The bytes spread
95–162 ps, against 48–100 ps on the 0.1 mm board, so tuning needs more meander room. Do phase 3 after the width
clean-up above.

## 5. LPDDR4 sign-off (your review)

`ddr_timing.py` all PASS, `grade.sh` with no DDR errors, a picture per layer, the swizzle unchanged
(`tools/lpddr4_swizzle_score.py`).

## 6. Then the rest of the board (LAYOUT_PLAN.md phases 4–6)

eMMC (length-matched to CLK) → QSPI flash → RGMII and the MDI pairs to J9 → the rest → 3V3, GND stitching, F/B GND
flood → `/review-routed-board` → Gerbers/BOM/CPL with `tools/jlc`.

## Optional

- The baseboard header insulator height (the gap is assumed ≈ 5.3 mm).
