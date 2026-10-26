# Next session plan

Written 2026-10-25 at the end of the session. The detail is in `STATUS.md` ("LPDDR4 routing: first draft"); the
overall plan is in `LAYOUT_PLAN.md`. Tools: `~/dev/KiCadRoutingTools` (venv `.venv`, skills linked into
`.claude/skills/`).

## 0. Start-up (10 min)

- Read `STATUS.md` → "Where we left off".
- The bus router **finished** (see the table in step 2). Its files:
  - log `work/route/bus1.log`: last line `WHOLE K=47 round=2 ...` / `BUS U501->U801 ...`;
  - result `work/route/bus1.kicad_pcb`, summary `work/route/bus1.json`;
  - round 1 is saved in `work/route/bus1_snapshot_round1_2026-10-25/`; see its README;
  - not finished, or the machine restarted: the tool has no resume, so re-run it in the background (about 1.5 h per
    round; `ortools` is already in the venv). Keep a WSL window open while it runs: WSL stopping kills it.
    ```
    cd work/route && K=~/dev/KiCadRoutingTools
    nohup $K/.venv/bin/python -X utf8 $K/awx/route_bus.py bus0.kicad_pcb bus1.kicad_pcb --rounds 2 --inproc \
        --bus U501:U801:joint:F.Cu,B.Cu,In2.Cu,In5.Cu --clearance-ceiling 0.1 --track-width 0.1 \
        --fanout-track-width 0.1 --via-size 0.25 --via-drill 0.15 --json-out bus1.json > bus1.log 2>&1 &
    ```
    `bus0.kicad_pcb` is the board with the DDR signal vias stripped (`tools/ddr/strip_ddr_vias.py`; copies of all
    three files are in the snapshot). The layer list must start with F.Cu,B.Cu.
- `git log --oneline -3` should show `8178627` (LPDDR4 draft). Tag `pre-ddr-routing` is the clean board before it.

## 1. ~~Learn the tools on their own example~~ (done 2026-10-26, `KRT_LEARNING.md`)

The haasoscope chain (Ti90 ↔ LPDDR4) reproduced in 40 s, and the same recipe run on our board in 1 min
(`tools/ddr/recipe_chain.sh`): 56/56 connected, 3 of 5 pairs coupled, **0 copper-clearance errors after refilling
the planes**, 103 near-miss hole clearances. Grading lesson: refill the zones before DRC, and route at `--clearance
0.11`.

## 2. Pick the LPDDR4 base (1 h)

Compare on our board, each graded with **our** rules (the bus router writes a relaxed hole clearance into its own
project copy: always check with `kicad/ti135_card.kicad_pro` / `.kicad_dru`):

| Candidate | Where |
|---|---|
| A. draft on main (route.py, 56/56, 91 vias, 1215 mm) | `kicad/ti135_card.kicad_pcb` |
| B. bus router, **finished 2026-10-26 06:06** after 9.1 h; kept round 1: 42 lanes connected and locked, 5 open (ddr_dq1, DQS0 P/N, DQS3 P/N), 72 vias, 1095 mm on the board, bus DRC 0 by its own rules. Bytes still span 3 layers (F.Cu 29–57 % from its surface escapes) | `work/route/bus1.kicad_pcb` (its project copy relaxes hole clearance to 0.1 mm) |
| C. **the haasoscope recipe** (bga_fanout both BGAs, route_diff, route.py auto-matched): 56/56, 127 vias, 1789 mm, 0 clearance errors after refill | `work/ours/ram.kicad_pcb`; rerun with `tools/ddr/recipe_chain.sh` |

Criteria, in order:
1. nets connected;
2. DRC errors (hole clearance!);
3. layers per byte (Efinix: one);
4. DQS/CK pairs coupled;
5. vias and length.

`tools/ddr/route_stats.py` gives the per-byte layer split. Keep the winner on main and note the choice in STATUS.md.

## 3. Make the LPDDR4 clean (2–4 h)

1. Hole clearance 0.175 mm: re-route at the right floor, or nudge.
2. Widths: 40 Ω outside the BGA courtyards (0.18 mm In2/In5, 0.25 mm F/B), 0.1 mm neck-down inside
   (`lpddr_bga_neckdown`). The router has no automatic DDR neck-down: a widening pass, or KiCad interactive.
3. DQS/CK as coupled 80 Ω pairs outside the BGAs (0.14/0.15 mm inner).
4. Matching to Efinix §6.3, die to die (pad-to-die is on U501):
   - DQS P/N within 10 mil, CK P/N within 5 mil;
   - DQ/DM 0…375 mil longer than their DQS;
   - CA/CKE/CS within 62.5 mil of each other and ±30 mil of CK.

   Use `route.py --length-match-group auto --time-matching`, or KiCad's tuning.
5. Efinix rules: ≥ 100 mil from switching nodes (the 0V85/1V1 cells at the corridor's east end), return vias near
   layer changes.
6. Your sign-off: DRC, a length/delay report per group, a picture per layer.

## 4. Then the rest (LAYOUT_PLAN.md phases 4–6)

eMMC (length-matched to CLK) → QSPI flash → RGMII (matched group) and MDI pairs to J9 → everything else → 3V3 routing,
GND stitching, F/B GND flood → `/review-routed-board` → Gerbers/BOM/CPL with `tools/jlc`.

## Open questions for you

- None blocking. Nice to have: the actual height of the baseboard's 1.27 mm male header insulator (the gap is
  assumed ≈ 5.3 mm).
