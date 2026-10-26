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

## CK/CA trunk-and-branch (2026-10-26, `tools/ddr/ca_trunk_branch.py`, `tools/ddr/ca_tb_chain.sh`)

Each shared CA/CKE/CK net: a trunk U501 → T via in U801's ball-free columns L/M, then two mirror-image branches in
the channels between ball rows to channel A and B (CA5 on In2, the rest on F.Cu). The trunk step routes against
temporary THT pads at the T points (the router targets pads, not bare vias), with the U801 pads parked on TMP_ nets
and the branches pre-drawn on BR_ nets so the trunks keep out of their corridors.

**Gotchas found on the way:**
- **die_delay units (correction 2026-10-26): no KiCadRoutingTools bug.** KiCad's `(die_delay X)` is in ps
  (pcbnew `pcbIUScale.IU_PER_PS` = 1e6) and the router reads it correctly. **Our `tools/pad_to_die.py` stored the
  delays 1000x too small** (it assumed fs per IU). The "x1000 workaround" in the trunk step was in fact correcting
  that, so the CK/CA matching used the right delays. Fixed: pad_to_die.py writes ps x IU_PER_PS, ddr_timing.py reads
  through IU_PER_PS, and the workaround is gone.
- **Group patterns:** in `--length-match-group` only `*` and `[..]` are wildcards; `?` is literal (`--nets`
  accepts `?`). A group that matches < 2 nets is skipped silently.
- **Multi-point nets disable a group's matching:** leftover escape fragments count as extra terminals. Rip the
  whole net so it is point to point.
- **`--no-bga-zones <BGA>`** is needed to route to anything inside a ball field.
- **pcbnew SWIG:** removing hundreds of tracks garbles later object lookups (do pads and vias first, remove last).
  Two `NETINFO_ITEM`s added back to back share a net code (give explicit codes).
- **Meanders:** amplitude 1.0 fits best here (1.5 and 0.6 left more nets unmatched); some nets still have no straight
  run long enough.

**Result (on main):** all connected, every net's two channels equal; CA/CKE/CS − CK −8.6 … +36.8 ps (C: −57 …
+123, 85 ps between channels). Within the ±100 ps timing budget, not yet the ±5.3 ps length rule (CA4 +37, CA1 +21,
CS0 +16). CK P/N skew 9 ps.

## LPDDR4 at 40 Ω (2026-10-26, `tools/ddr/ddr40_chain.sh`, `tools/ddr/widen.py`)

- **Route at width; don't widen afterwards.** Buses routed at 0.1 mm / 0.11 mm clearance sit on a 0.21 mm pitch, and
  widening in place reached only 23 % of the length.
- **`--impedance 40`** on route.py computes a width per layer from the stack-up: 0.171 mm inner, 0.272 mm F/B. The
  microstrip model has no solder mask (JLC: 0.25 mm), so clamp F/B afterwards (narrowing always clears). Where it
  finds no room it necks a net down to the floor for up to ~30 mm, and reports it under `design_rules.narrowed` in
  the JSON summary.
- **route_diff `--impedance 80`** gives 0.149 / 0.224 mm at a 0.15 gap, and coupled fewer pairs than
  `--track-width 0.14`. Use the explicit width.
- **The fan-out pair stub gap must be ≥ route_diff's `--clearance`.** At a 0.1 gap and 0.11 clearance it skips every
  pair, then crashes in `order_nets_mps` (`'list' object has no attribute 'num_rounds'`: an empty MPS result
  returns a list). Possible upstream bug; not reported.
- **Not deterministic:** the same inputs gave CK P/N skews of 0.6–103 ps across runs, and an open DQ in two of five
  byte runs. Run a few variants in parallel and grade them all.
- **`--layer-costs` in `DQS_EXTRA` had no effect** (the later `$COMMON` value wins: argparse takes the last).
- **KiCad DRC stops at 199 reports per violation type.** Measure progress some other way.
- **A net KRT necked can often be re-routed at width with `--escalation off`** once the rest is placed
  (`tools/ddr/reroute_nets.sh`). For dm0/dm1 it only worked with `--rip-existing-nets` on their byte's other nets;
  without that it fails with "no rippable blockers".
- **Re-fitting a fitted board** must not split segments again at a courtyard edge: zero-length tracks result, and
  KiCad reports them as `tracks_crossing`. `widen.py` now splits only from strictly inside and drops zero-length
  tracks.

## Delay tuning on routed copper (2026-10-26, `tools/ddr/tune_meander.py`)

- `length_matching.apply_meanders_to_route(segments, extra_mm, GridRouteConfig(...), pcb_data=..., net_id=...)` works
  on a board's existing segments, given as a path-ordered chain (parse_kicad_pcb keeps each segment's UUID, so the
  edits can be applied by UUID in pcbnew). It meanders the longest straight runs first, spills over several, and
  checks every bump against the copper around it, but not against the board edge.
- Bumps alternate sides and a blocked side is dropped. A trace inside a bundle routed at the minimum clearance gets
  no bumps at all. Matching needs room planned at routing time.
- `route.py --length-match-group` on a few re-routed nets can rip and lose unrelated nets ("RIP-RESTORE ... remains
  UNROUTED"), so check connectivity after every such step.

## Possible KiCadRoutingTools bugs (2026-10-26; not reported upstream, the user decides)

Found while driving KRT from our scripts (`~/dev/KiCadRoutingTools`, commit as of 2026-10-26). Each has a workaround in
our tools.

1. **route_diff crashes when every pair is skipped.** If all pairs are skipped (here: fan-out stub gap 0.1 below
   `--clearance 0.11`, "Skipping 4 pair(s): fanout escape stubs already pinch their own P/N"), `order_nets_mps`
   fails with `AttributeError: 'list' object has no attribute 'num_rounds'`: `compute_mps_net_ordering(...,
   return_extended_info=True)` returns a plain list when there are no units ("MPS: No units with valid routing
   endpoints found"). Expected: a clean "nothing to route" exit. Workaround: route DQS at the class clearance 0.1
   (`byte_chain.sh` `DQS_CL`).
2. **A meander bump can never start next to a close (but legal) neighbour, on either side.**
   `length_matching.get_safe_amplitude_at_point` checks the bump's first segment (the entry chamfer, which starts on
   the existing track's centreline) against `required_clearance`. That value includes a corner margin: for a 0.171 mm
   track and a 0.14 mm neighbour at 0.11 clearance it is 0.367 mm centre to centre, while the track already sits
   0.315 mm from it (0.159 mm edge gap, DRC-clean). So every amplitude on both sides is rejected, though the far side
   is empty. This is why both route.py's in-route matching and our tuner reported "No straight run with clearance
   found for meanders" for most DDR nets. Expected: the part of the bump on the existing centreline (or moving away
   from the neighbour) should not need more than the existing clearance. Workaround (`tools/ddr/tune_meander.py`):
   ask at a small clearance (0.03) as well, then verify every new segment against the real rules ourselves.
3. **route.py's default rip of small pre-existing nets can leave them open.** Without `--rip-existing-nets`, small
   pre-existing nets (≤ 30 segments, ≤ 6 vias) are still rip candidates. In a few-net re-route it ripped other
   DDR nets (dqs2_N, dqs3_P, dq19), then reported "restore skipped ... saved copper would short other-net copper;
   left ripped (#134)" and "RIP-RESTORE (#468) ... remains UNROUTED", so the step's output had new opens.
   Workaround: `KICAD_RIP_PREEXISTING=0` (`byte_seq.sh`) and a connectivity check after every step.

Not bugs, but surprising when KRT is used as a library:
- `GridRouteConfig.layers` defaults to `['F.Cu', 'B.Cu']`, and the meander clearance index expands pad layers
  against it. Pass the board's copper layers.
- `GridRouteConfig.board_edge_clearance` defaults to 0 (the edge check then uses the track clearance); set 0.5.
- `--impedance`'s microstrip model has no solder mask (F/B come out about 0.27 mm for 40 Ω where JLC says 0.25).
- Time matching always targets the group's longest member; there is no offset or window in ps (the `.kicad_dru`
  length window is in mm), so "DQ 0…66 ps longer than DQS" needs our own top-up (`tune_meander.py`).
