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

## 1. Learn the tools on their own example first (1–2 h)

So far we have used the KiCadRoutingTools pieces one by one, with a few mistakes along the way (route_diff needs
fan-out stubs, route_bus wants F.Cu,B.Cu first in its layer list, the B.Cu template mirror). Before cleaning up our
DDR, reproduce one of the toolkit's own routing examples end to end, so we learn the intended chain on a board where
the expected result is known.

- **Board:** `kicad_files/haasoscope_pro_max_test.kicad_pcb`. It has a two-channel LPDDR4 (`DQ0_A` / `DQ0_B`, shared
  `CK_t_A`), the closest match to ours. Alternatives:
  - `orangecrab_ext_pll` / `ulx3s`: FPGA BGA fan-out;
  - `tigard`: placement, with `docs/examples/tigard.groups.json`.
- **How:**
  1. Copy the board, with its `.kicad_pro`, into `work/learn/`.
  2. Run `/plan-pcb-routing` on it and follow its chain step by step: planes → fan-out → decap pass → diff pairs →
     route with `--length-match-group auto` → finalize → `/review-routed-board`.
  3. Write down each command and its result in `work/learn/NOTES.md`.
- **Read first:** `docs/claude-skills.md`, `docs/bus-routing.md` (both bus tools, including `route.py --bus`, which
  we have not tried), `docs/length-matching.md`, `docs/differential-pairs.md`, `docs/route-plane.md`.
- **Take away:** the right order and flags for a two-BGA LPDDR4. In particular, whether to fan out with
  `bga_fanout.py` (stubs for route_diff) or with the bus step, and how length/time matching with pad-to-die is
  meant to run.

## 2. Pick the LPDDR4 base (1 h)

Compare on our board, each graded with **our** rules (the bus router writes a relaxed hole clearance into its own
project copy: always check with `kicad/ti135_card.kicad_pro` / `.kicad_dru`):

| Candidate | Where |
|---|---|
| A. draft on main (route.py, 56/56, 91 vias, 1215 mm) | `kicad/ti135_card.kicad_pcb` |
| B. bus router, **finished 2026-10-26 06:06** after 9.1 h; kept round 1: 42 lanes connected and locked, 5 open (ddr_dq1, DQS0 P/N, DQS3 P/N), 72 vias, 1095 mm on the board, bus DRC 0 by its own rules. Bytes still span 3 layers (F.Cu 29–57 % from its surface escapes) | `work/route/bus1.kicad_pcb` (its project copy relaxes hole clearance to 0.1 mm) |
| C. what step 1 teaches (e.g. `bga_fanout.py` + `route_diff.py` + `route.py --bus`) | new run |

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
