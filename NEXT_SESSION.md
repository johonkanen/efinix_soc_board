# Next session plan

Written 2026-10-26 at the end of the session. Background:
- `STATUS.md`: the overall state;
- `LAYOUT_PLAN.md`: the phases;
- `KRT_LEARNING.md`: how to drive KiCadRoutingTools, and every gotcha found so far.

Tools: `~/dev/KiCadRoutingTools` (venv `.venv`, with `ortools`); the skills are linked into `.claude/skills/`.

## Where we are

- **Main** holds the LPDDR4 routed with the haasoscope recipe, with CK/CA re-routed as trunk-and-branch
  (`tools/ddr/ca_tb_chain.sh`). Every DDR net is connected, with no shorts or crossings, and the rest of the board is
  DRC-clean.
- **Measure timing** with `tools/p2k/bin/kipy tools/ddr/ddr_timing.py`: die to die, along each path, U501
  pad-to-die included.
- **Grade** with `tools/ddr/grade.sh NAME BOARD`: our rules, planes refilled, KiCad DRC.

| Check (Efinix §6.3) | Rule | Now |
|---|---|---|
| CA/CKE/CS − CK | ±5.3 ps (30 mil); budget ±100 ps | −8.6 … +36.8 ps (CA4 +37, CA1 +21, CS0 +16); channels A/B equal |
| CK P/N | ≤ 0.9 ps | 9 ps (CK_P found no room for meanders) |
| DQS P/N | ≤ 1.8 ps | 39 / ~5 / 35 / 3.4 ps (bytes 0–3) |
| DQ/DM − DQS | 0 … 66 ps | fails in all four bytes (DQ shorter than DQS in 0, 2, 3) |
| DRC (DDR) | – | 199 width (no 40 Ω widening yet), 16 pair gap, 4 uncoupled, 14 hole clearance |

## 1. KiCad time-domain tuning setup (30–60 min)

1. In `tools/board_setup.py`, add two tuning profiles to `kicad/ti135_card.kicad_pro`, copied in form from the
   Agilex card's (`tuning_profiles.tuning_profiles_impedance_geometric`):
   - `LPDDR4 SE 40R JLC08161H-3313`: F/B 0.25 mm at 6.11 ps/mm, In2/In5 0.18 mm at 7.01 ps/mm.
   - `LPDDR4 DIFF 80R`: F/B 0.20/0.20 mm, In2/In5 0.14/0.15 mm.
   - Both: via 7.2 ps/mm, time-domain tuning on.

   Then set `tuning_profile` on the net classes `lpddr_dq` / `lpddr_ca` (SE) and `lpddr_diff` (DIFF).
2. Teach `tools/ddr/ddr_timing.py` to print **per-net targets in KiCad's own terms**. KiCad sums a net's whole copper,
   so a shared CA/CK net reads path + one branch. Then each net can be dialled to its number with the pcbnew tuner.
3. Check one net: KiCad's delay readout (net inspector or tuner) against `ddr_timing.py` (path + branch).

## 2. Data bytes: clean re-route (2–3 h)

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

## 4. LPDDR4 DRC clean-up (1–2 h)

- 40 Ω widening outside the BGA courtyards (0.18 mm In2/In5, 0.25 mm F/B; 0.1 mm stays inside, `lpddr_bga_neckdown`):
  a script that widens DDR segments where clearance allows, then DRC.
- The 14 hole-clearance hits (fan-out vias 0.15–0.17 mm against 0.175 mm), the pair-gap and uncoupled-length rules.
- Efinix: ≥ 100 mil from the 0V85/1V1 switching nodes, return vias at layer changes.

## 5. LPDDR4 sign-off (your review)

`ddr_timing.py` all PASS, `grade.sh` with no DDR errors, a picture per layer, the swizzle unchanged
(`tools/lpddr4_swizzle_score.py`).

## 6. Then the rest of the board (LAYOUT_PLAN.md phases 4–6)

eMMC (length-matched to CLK) → QSPI flash → RGMII and the MDI pairs to J9 → the rest → 3V3, GND stitching, F/B GND
flood → `/review-routed-board` → Gerbers/BOM/CPL with `tools/jlc`.

## Optional

- The baseboard header insulator height (the gap is assumed ≈ 5.3 mm).
