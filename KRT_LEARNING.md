# KiCadRoutingTools learning run: haasoscope_pro_max_test (2026-10-26)

Board: `kicad_files/haasoscope_pro_max_test.kicad_pcb`. Efinix **Ti90G529** (U3, Titanium) ↔ Micron 200-ball **LPDDR4
x32** (U1), 10 layers. The same pairing as our card (Ti135N484 ↔ H9HCNNN8KUMLHR, 200-ball). Reference chain:
`tests/test_fanout_and_route.py` (`--ram`); its DDR part is reproduced in `chain.sh`, with per-step logs and
`chain.log`.

## The intended chain for a FPGA ↔ LPDDR4 bus

1. **Fan out both BGAs with `bga_fanout.py`, pairs first:**
   - FPGA: `--nets DQS* CK* --diff-pairs DQS* CK* --primary-escape horizontal`, then the rest of the DDR nets with
     `--check-for-previous`.
   - DRAM: the same, plus `--no-inner-top-layer`, then channel A, then channel B, each `--check-for-previous`.
   - The fan-out produces the **escape stubs** that `route_diff.py` needs to start a coupled pair. That was our
     failure: bare via-in-pad balls have no stubs.
2. **`route_diff.py`** for DQS/CK: `--length-match-group DQS* CK* --time-matching --diff-pair-intra-match
   --mps-layer-swap --heuristic-weight 1.5` + `--bga-proximity-radius 1 --stub-proximity-radius 1
   --proximity-heuristic-factor 0.02`.
3. **`route.py`** for everything else on the DRAM: `--length-match-group auto --time-matching --no-bga-zones U1`, the
   same proximity knobs, and `--swappable-nets DQ*` (target swap; **for us only within a byte, and it must go back
   through Efinity**, so leave it off or constrain it).
4. Checks: `check_drc.py`, `check_connected.py`. Planes: in the old test they come last; the skill now says pour first.

## Results (40 s for the whole chain)

| Step | Result |
|---|---|
| Fan-outs | U3 11 pairs + 45, U1 11 + 36 + 14: all escaped. "via_segment grazes" 22 + 53 + 34 reported |
| route_diff | 4 DQS pairs coupled; CK fell back to single-ended. DQS group: one pair 114 ps short (a split escape can't be meandered) |
| route.py | 49/49 singles; 5 auto groups (4 byte lanes + CA) time-matched "within tolerance" |
| check_connected | all connected |
| check_drc | 58 via–segment contacts, the fan-out's own grazes |

## Lessons for our board

- Fan out with `bga_fanout.py` (stubs) when pairs are to be coupled. Via-in-pad on signal balls prevents
  `route_diff.py` from starting.
- Even the reference spreads each byte over 4–5 layers. One layer per byte is not something the defaults do. It
  needs per-step `--layers` (route each byte on its own layer) or a different tool.
- `--length-match-group auto` builds byte lanes **without** DQS when DQS was routed earlier as a pair. Efinix's
  DQ-vs-DQS rule (DQ 0…375 mil longer than DQS) is not enforced, so check it ourselves.
- Expect fan-out grazes: grade with check_drc and fix (smaller via, or re-run with more clearance) before
  routing.
- Whole chain about 1 minute against 9 hours for the bus router. Iterate with this chain.

## The same recipe on our board (`tools/ddr/recipe_chain.sh`, 1 min)

Start: tag `pre-ddr-routing` with the DDR signal vias stripped (`tools/ddr/strip_ddr_vias.py`); plane vias stay in
their pads. Signal layers F/In2/In5/B via `--layer-costs` (planes forbidden). Clearance 0.1, via 0.30/0.15 (U501),
0.25/0.15 (U801).

| | Recipe | Draft on main (route.py from via-in-pad) | Bus router |
|---|---|---|---|
| Connected | 56/56 | 56/56 | 42/47 |
| Coupled pairs | DQS0, DQS3, CK (DQS1/2 single-ended) | none | – |
| Vias / length | 127 / 1789 mm (with time-matching meanders) | 91 / 1215 mm | 72 / 1095 mm |
| Byte layers | 4 (F.Cu 37–54 %) | 3–4 | 3 |
| Copper clearance (our rules, **after refill**) | **0** | not re-checked after refill | not checked |
| Hole clearance | 103 (0.15–0.17 mm vs 0.175) | 195 | – |

**Two lessons that change how we grade:**
1. **Refill the zones before KiCad DRC.** The routers do not refill; vias then sit in stale plane copper and every
   one reads as a 0.000 mm clearance error. Use `work/route/refill.py`, or the PCB build, which refills. The first
   grade of the recipe showed 379 such false errors.
2. **Hole clearance:** 0.1 mm copper clearance + the 0.075 mm ring of a 0.30/0.15 via equals our 0.175 mm drill
   rule exactly, and grid rounding falls just short. Route at `--clearance 0.11` (or 0.105), or use a 0.15 drill
   with a 0.35 pad.

**Still open with any tool:** one layer per byte (needs per-byte `--layers` steps), widening to 40 Ω outside the
BGAs, DQ-vs-DQS matching (auto groups leave DQS out when it was routed as a pair).

## Recipe at 0.11 mm and the three candidates graded alike (2026-10-26, `tools/ddr/grade.sh`)

Recipe fixes for 0.11 mm: the fan-out's pair stubs need `--diff-pair-gap $CL`, otherwise route_diff skips every pair
as "stubs pinched below clearance". The `--mps-layer-swap` crash (`'list' object has no attribute 'num_rounds'`) was
the same no-routable-pairs case. Routed pair gap 0.15 mm (80 Ω inner).

| (our rules, planes refilled) | A draft (main) | B bus router | C recipe @ 0.11 |
|---|---|---|---|
| DDR nets with open pads | 0 | **14** | 0 |
| DRC errors outside the DDR | 0 | **8** (its joint fan-out touched other nets) | 0 |
| Copper clearance errors | 0 (the 76 earlier were stale fill) | 0 | 0 |
| Hole clearance | 119 | 30 | **23** (13 GND + 8 1V1 fan-out vias, CK and DQ tracks) |
| Width (no 40 Ω widening yet) | 88 | 199 | 199 |
| Pair gap / uncoupled | 28 / 5 | 9 / 1 | 8 / 3 |
| Coupled pairs | none | – | DQS0, DQS3, CK |
| Time matching | none | none | byte lanes within tolerance; DQS 5–19 ps shorter than its DQ (allowed: DQ 0…375 mil longer); **CK 117 ps short of the CA group** |
| Vias / length | 91 / 1215 mm | 87 / 1153 mm | 118 / 1782 mm |
| Bytes on layers | 3–4 | 3 | 4 |

Not yet known: whether KiCadRoutingTools' time matching includes the U501 pad-to-die delays (check with KiCad's own
length/time report).
