# LPDDR4 IBIS simulation: trace width study and the routed board

KiCad 10 + ngspice IBIS simulation of U501 (Efinix Ti135N484I3) ↔ U801 (SK hynix H9HCNNN8KUMLHR, simulated with the
Winbond W66CL2NQUAFJ **stand-in**) at 2800 / 3200 MT/s. The question and the full brief are in
`IBIS_SIM_AGENT_PROMPT.md` (repo root). The method comes from `~/dev/agilex3_soc_control_card/sim/lpddr4_si/` (read only, never
write there). That method is going to `johonkanen/kicad_ibis_simulation` (see "Next").

## Routed board: result (2026-10-31, LPDDR4_IBIS_PLAN.md steps 1-7)

**Every LPDDR4 net of the routed board (commit eabcea1) passes at 2800 and 3200 Mbps, typ/min/max, with one
exception: CKE0 at max corner and 3200 Mbps peaks 16 mV over the overshoot limit. Fix: a 10 ohm series resistor on B.Cu at U501's CKE via. Efinity has no drive setting for CA/CK/CKE (only DQ_PD/PU_DRV_STRENGTH), so the FPGA side cannot be weakened; with it CKE
peaks at 1291 mV there (limit 1470 mV).**

| check | result | detail |
|---|---|---|
| Drivers (step 1) | Efinix exact at every load with the corner model files; KiCad's own `vcc=MIN/MAX` is not | `results/validate_drivers*.md` |
| Extraction (step 2) | whole-net delay within 0.76 ps of KiCad on all 56 nets | `results/check_routes.md` |
| Typ sweep (step 4) | 172 netlists, all pass | `results/routed_typ.md` |
| Corners (step 5) | 344 netlists, all eyes pass; CKE0 max/3200 1486 mV vs 1470 mV (10 ohm series R: 1291 mV) | `results/routed_corners.md` |
| Crosstalk (step 6) | at most 14 mV / 8 ps lost (bounding case); every net still passes | `results/xtalk_board.md` |
| Checks can fail (step 7) | overshoot, timing and closed-eye failures all detected; plots agree | `bad_case.py`, below |

Tightest margins over all corners and both rates (at the receiver die): DQ read timing 49 ps (dq11, typ 3200) and
voltage 138 mV; CA/CS/CKE voltage 120 mV (min 2800); DQ/DM write 351 mV / 170 ps; DQS read 523 mV / 61 ps; DQS
write 982 mV / 170 ps; CK 438 mV / 158 ps. Over/undershoot areas at most 0.04 V-ns (limit 0.1).

**Step 7, the checks can fail** (`python3 bad_case.py`, eye PNGs `results/eyes/eye_bad*.png`), all at 3200 Mbps:

| case | result |
|---|---|
| 1. dq1 write, DRAM ODT off, max | peak 1579 mV vs 1470 mV, OS/US area 0.140 / 0.104 V-ns: **limits fail**; eye still open (short line) |
| 2. dq11 read, FPGA ODT off, max | t margin **-30 ps** at the FPGA die: **mask fails** |
| 3. dq1 write, all traces 150 ohm, 4x long, ODT 60 | eye 259 mV, +53 mV / +48 ps: degraded, still passes (the ODT absorbs it) |
| 4. as 3 with the DRAM ODT off | eye **closed** (-450 mV, 0 ps), peaks 1942 / -658 mV: **everything fails** |

**How it was run** (`routed_si.py`, see its docstring): every net's extracted copper (`extract_routes.py`) as one
netlist (one net or pair per netlist, `.save` only the probes, `.dat` deleted), every piece with the Z0 and ps/mm of
its layer and width; vias by span; DQS/CK legs at the pair's odd-mode Z0 (0.10 / 0.20 mm as routed); min/max from
the corner model files (`corner_models.py`); `-j 4` (CPU-bound, ~80 MB per run), 7.7 min typ + 14 min corners.

**Assumptions and what is not modelled:**
- DRAM = Winbond W66CL2NQUAFJ stand-in (the SK hynix model is under NDA); its edges run up to 12-18 ps faster than
  its own tables after KiCad's conversion; its open-load level is wrong (does not matter while the FPGA ODT is on).
- U801 has no package delays (none public); U501 package delay as a 46.3 ohm line of the pad-to-die delay.
- Settings: FPGA 40 ohm drive (DQ_PD/PU_DRV_STRENGTH 40 in efinity/pinplan/pinplan.py; the Efinity default
  34.3 ohm has no IBIS model; the CA/CK/CKE drive is fixed and assumed 40 ohm), FPGA ODT 60, DRAM ODT 60, DRAM drive PD40, CA ODT 40 (`gen_sch.py` BASE); CKE has no
  ODT (CKE_INPUT). Masks: JEDEC DQ/CA; for the FPGA read side TI's SoC-pad diamond as a proxy (Efinix publishes none).
- Lossless lines; no meander self-coupling; pair mode conversion not modelled; crosstalk only from the board's
  worst coupled lengths outside the BGAs (step 6).
- `limits_ok` checks the peaks; the areas are in the CSV (`os_area_Vns`, `us_area_Vns`) and were checked by hand.

## Status (2026-10-27, stopped by the user for the day)

**Done**
- Scripts adapted and rewritten: `prep_models.py`, `gen_sch.py`, `run_si.py`, `report.py`, plus the new `board_paths.py` and
  `zsolve_widths.py` (details below). Nothing has been simulated end to end yet: **no results table exists yet**.
- Models prepared (`models/`, git-ignored). The Efinix LPDDR4 models load in KiCad's IBIS converter (KIBIS) unchanged.
- Driver check (`run_si.py --validate`, `results/validate_drivers.md`): Efinix 40 Ω and Winbond PD40/PD48 match their V-t
  tables (levels within 1 mV, 20–80 % edges within 0–12 ps). **Efinix `lpddr4_ocd_48p_48n` is inconsistent in the vendor
  file itself:** its I-V gives 327 mV high into 20 Ω (≈ 47 Ω, as named), but its V-t tables end at 373 mV (≈ 39 Ω, the
  40 Ω level). KIBIS follows the I-V.
- Field solve (`results/zsolve.csv`). The delay per mm hardly moves with width, so the length/delay tuning stays valid:

  | layer | 0.18 / 0.25 (today) | 0.15 | 0.12 | 0.10 | 0.09 mm |
  |---|---|---|---|---|---|
  | In2/In5 | 39.8 Ω, 7.024 ps/mm | 43.7 | 48.6 | 52.6 | 54.9 Ω, 7.008 ps/mm |
  | F/B (0.25, 0.20, 0.15, 0.12, 0.10, 0.09) | 39.3 Ω, 6.195 ps/mm | 44.3 / 51.0 | 56.2 | 60.4 | 62.7 Ω, 6.085 ps/mm |

  Pairs: inner 0.14/0.15 = 80.6 Ω, 0.10/0.13 = 90.4, 0.09/0.20 = 101.3. Outer 0.20/0.20 = 79.6, 0.10/0.10 = 90.3,
  0.10/0.15 = 100.9. Note that `tools/ddr/ddr_timing.py` uses 6.11 ps/mm outer; the solve gives 6.20 at 0.25 mm and 6.13
  at 0.15 mm.
- Crosstalk L/C matrices (`zsolve_widths.cl_matrix`): inner 0.18/0.11 gap kL 0.139, kC 0.129; 0.10/0.19 (same pitch)
  kL 0.084, kC 0.079. Outer 0.25/0.11 kL 0.195, kC 0.131; 0.10/0.26 kL 0.102, kC 0.052.
- Board paths extracted to `results/board_paths_main.json` (committed board, DQ/DQS) and `results/board_paths_p4.json`
  (phase-4 work board `work/p4/x5a/fin.kicad_pcb` as of 21:20: CA trunks and branches on In5, via-in-pad at U801).
- Efinity DDR settings (`efinity/pinplan/build/ti135_pinplan.peri.xml`, as created by `pinplan.py`):
  - FPGA side: drive pull-up/pull-down 34.3 Ω, read ODT 60 Ω pull-down, pull-up Hi-Z.
  - Memory side: DQ ODT RZQ/4 (60 Ω), CA ODT RZQ/6 (40 Ω), PDDS RZQ/6 (40 Ω), ODT_CA pad obeyed.
  - The Efinity help page (`pt/doc/topics/titanium-ddr-id-1.html`) lists other defaults: 48/48 drive, ODT 60, DRAM
    ODT disabled.
  - **The IBIS file has no 34.3 Ω driver**, so 40 Ω is used as the baseline.
- Masks and limits are researched (see `run_si.masks()` / `limits()` for sources):
  - JEDEC LPDDR4, 3200 column: DQ 140 mV × 0.25 UI; CA 155 mV × 0.3 tCK (175 mV used at 2800).
  - TI SPRAD66B read diamond 140 mV × 0.61 UI, as a proxy for the FPGA side.
  - DRAM overshoot: 0.3 V peak, 0.1 V·ns area; abs max −0.4…1.5 V.
  - Ti135 DS v1.9 Table 82 has no VIN or overshoot row for the DDR pins (VDDQ_PHY abs max 1.21 V).

**2026-10-28: running.**
- The pipeline works end to end. The first ngspice failure was fs-long TLINEs (fixed).
- The full 44-channel netlist was OOM-killed (> 9 GB). A point is now split into small netlists (`run_si.PARTS_*`,
  `gen_sch.py --keep`): about 4 drivers each, about 1.3 GB and 1-2 min each, 5 in parallel.
- 150 data bits and 140 CA bits (CA is SDR, so its UI is tCK).
- Eye analysis is the submodule's `kicad_ibis.eye` (labels from KIBIS' PRBS7).
- Reads are judged at the FPGA die. The ball sits mid-package when the package is drawn as a line.
- Proven to fail: one DQ at 8000 MT/s gives negative margins.
- Quick set (`results/results_quick.csv`, typ, today vs 0.10/0.10 mm), time margin change:

  | Signal | 2800 MT/s | 3200 MT/s |
  |---|---|---|
  | DQ write | −10 % | −24 % |
  | DQ read | −4 % | −21 % |
  | CA | −49 % | −70 % |

  - The CA loss is ringing at the channel-B DRAM ball: the stand-in's 3 nH CA pins. The die eye is unchanged.
  - CKE (no ODT, T) overshoots to about 1.45 V and undershoots to −0.3 V **already at today's width**.
- **Full sweep 2026-10-28 06:10-06:56:** 564 netlists (`work/full.log`), 559 done.
  - Failures: 4 parallel kicad-cli startups (now retried), and 1 ngspice "timestep too small" (gear). Truncated runs
    are now detected and re-run with method=trap.
  - Bug fixed: 0.12/0.15 mm was not run at typ.
  - `results/results.csv` holds this run. Typ at 2800 MT/s, time margin vs today:

    | Width (inner / outer) | DQ write | DQ read | CA | CS |
    |---|---|---|---|---|
    | 0.10 / 0.10 mm | −11 % | −4 % | −49 % | 0 % |
    | 0.09 / 0.09 mm | −12 % | −3 % | −51 % | 0 % |

    The CA loss comes from the inner (trunk) width: ≤ 0.12 mm inner triggers it, outer width does not. The cause is
    ringing at the DRAM ball (stand-in package).
- **Crosstalk:** the ngspice CPL line needs method=trap (gear stops with "timestep too small"); the fallback is in.
  Aggressors are not eye-analysed.
- **07:10: the fill-in pass and the crosstalk run were stopped by Claude Code because the system ran low on memory.**
  - The fill-in pass is `SI_REUSE=1 python3 run_si.py -j 5`: it runs the missing netlists and re-analyses the rest.
  - The phase-4 routing session was running at the same time.
  - To resume (when memory allows, e.g. `-j 3`): `SI_REUSE=1 python3 run_si.py -j 3`, then
    `python3 run_si.py --xtalk -j 3`, then `python3 report.py`.

**2026-10-28, later: Efinix RLC sheet in.**
- `reference/efinix/titanium_rlc-v1.8.xlsx` (from the user). Ti135 N484, LPDDR4 PHY, package-wide (not per ball):

  | | typ | min | max |
  |---|---|---|---|
  | R | 3.38 Ω | 1.37 Ω | 6.50 Ω |
  | L | 3.12 nH | 1.50 nH | 5.30 nH |
  | C | 1.45 pF | 0.83 pF | 2.22 pF |

- The default package model is now a 46.3 Ω line (√(L/C) of the sheet) with each ball's net-length delay, plus the
  sheet's 3.38 Ω in series. √(LC) = 67 ps equals the net-length sheet's mean ball delay.
- `--pkg rlc` gives the sheet's values lumped; `--pkg file` the IBIS placeholder.
- **Every result in `results/results.csv` above was made with the old package (50.6 Ω line, no R) and must be re-run.**
- `python3 run_si.py --first` runs the worst DQ (dq4) write and read and CA1, today vs 0.10 mm, typ, 2800 MT/s: 4 small
  netlists, about 15 s.
  - With the real package R, the CA ball ringing is damped: CA1 time margin +441 → +417 ps (−5 %) instead of −49 %.
  - dq4 write and read: within 2 %.

**2026-10-28: fast path (submodule `kicad_ibis.fastnet`) and the small sweep.**
- IBIS buffers are converted once (40-bit PRBS, cached in `work/kibis/`). The 150-bit patterns are built in Python and
  the netlists written directly. `--first` takes 17 s.
- Lines < 15 ps become 1 ps L/C sections with 4·Z0 across each L. That matches the lossless lines within 2.4 mV and
  1 ps, and removes the "timestep too small" stops and the minute-long runs.
- `python3 run_si.py --small -j 2` covers typ, 2800/3200, 8 widths and the pair geometries; results in
  `results/results_small.{csv,md}`. Runtime 20 min at -j 6 before the lumping fix. **Use -j 2: the RAM is shared.**
- Not converged: CKE at 0.09/0.09 mm, both rates. CKE is the unterminated T through 5 vias, and in this lossless model
  its via resonances are barely damped. Fixing that needs a lossy model (dielectric loss), not invented damping.
- Small-sweep results, typ, time margin vs today (0.18/0.25 mm):

  | Width (inner / outer) | Rate | DQ write | DQ read |
  |---|---|---|---|
  | 0.10 / 0.10 mm | 2800 MT/s | −10 % | −7 % |
  | 0.10 / 0.10 mm | 3200 MT/s | −33 % | −14 % |

  - Outer narrowing costs more than inner. At 3200 MT/s, write: 0.18/0.10 −34 %, 0.10/0.25 −20 %.
  - CA: voltage margin 112 → 77 mV (2800) and 150 → 109 mV (3200) at inner ≤ 0.10 mm. The 2800 time margin drops
    45 % because ringing at the channel-B DRAM ball touches the 175 mV mask height. At 3200 the mask is 155 mV and the
    drop is 1 %.
  - CS and DQS: unchanged.
  - CK pairs: 80 → 100 Ω geometries change little.
  - CKE: overshoots past 1.4 V at 3200 already at 0.18/0.10.

**2026-10-28: hand-routed byte lanes (`python3 run_si.py --routed -j 2`, 71 s).**
- Paths from the committed board 2588f29 (`results/board_paths_routed.json`): DQ/DM 0.10 mm, one layer per byte
  (byte 0/2 F.Cu, 1/3 In5, DM/DQS In2), DQS 0.10/0.20 inner (97 Ω). Worst DQ of each byte (dq3, dq15, dq19, dq28),
  DM0, DQS0/2; typ only, 2800/3200 MT/s. Results in `results/results_routed.csv`.
- All DQ/DM/DQS eyes pass at both rates. Lowest margins (3200): write 101 ps / 382 mV (dq3, ball), read 51 ps /
  144 mV (dq3, die). DQS read at the ball is negative here as in every earlier run (reads are judged at the die).
- Not covered: corners, crosstalk, CA/CK/CS/CKE (CA paths still the phase-4 board).

**2026-10-30: CKE0 as routed (`python3 run_si.py --cke -j 2`, 40 s; `results/results_cke.csv`).**
- Path from the delay-tuned board (`results/board_paths_cke.json`): U501 via-in-pad, In2 30.7 mm at 0.12 mm, via,
  B.Cu 1.0 mm trunk + 2 × 1.06 mm branches at 0.25 mm, ball vias. Compared with the same route at 0.10 mm inner.
  `gen_sch.py --ca-paths/--ca-neck-cap 0` (the CA channels used to come from the phase-4 board only).
- Typ and min corners, 2800/3200: **0.12 mm is better than 0.10 mm everywhere** (lower peaks and undershoot, smaller
  areas). 3200 typ, die: 1385 / −231 mV at 0.12 (in limits), 1417 / −271 mV at 0.10 (above VDDQ + 0.3 V). Ball
  peaks 1.23–1.24 V (0.12) vs 1.25–1.27 V (0.10). All over/undershoot areas ≤ 0.048 V·ns (limit 0.1). Eye height
  ≥ 840 mV, time margin ≥ 209 ps (CKE is SDR, one bit per tCK).
- **The max corner is not usable:** the Efinix driver at `vcc=MAX` settles at 1.24 V into the unterminated line,
  70 mV above its own 1.17 V [Voltage Range] max. That is a model/conversion problem, not ringing, and it makes the
  overshoot areas (0.3–0.5 V·ns) and the die peaks meaningless. The driver validation only covered typ: validate
  the max-corner drivers before trusting any max-corner result.

**2026-10-31: driver validation at all corners (LPDDR4_IBIS_PLAN.md step 1).** KiCad's corner keywords
(`vcc=MIN/MAX ...`) are right only into the V-t fixture: the Efinix driver is up to +129 mV off into an open line
(the max-corner CKE result above) and +46 mV into 60 ohm. `corner_models.py` writes `models/min|max/` with that
column as typ; simulated at typ (`run_si.py --validate min|max --corner-files`) every Efinix level is within 3 mV at
every load and the edges within 1-7 ps. The Winbond stand-in is within 4 mV into the FPGA ODT; its edges are up to
18 ps faster than its tables. Details and tables: `results/validate_drivers*.md`, LPDDR4_IBIS_PLAN.md step 1.

## Next

1. Re-run `prep_models.py` (it has already been re-run with the new pins), then
   `python3 run_si.py --quick --only r2800_typ_i0.18 -j 1`.
   - If ngspice still stops, bisect the netlist: drop channels, look at the CPIN/LPIN values and the synthesized N-leg
     Ku/Kd.
   - Check the eye PNGs in `results/eyes/` and the DQS/CK N-leg complement before trusting anything.
2. Cost per point: KIBIS export about 7.5 min (about 90 IBIS elements, 300-bit PRBS); the ngspice time is not known yet.
   The full sweep is about 100 points (`sweep_points()`).
   - Exports now run in parallel (`-j`).
   - If it is still too slow: fewer bits (`--bits`), fewer settings channels, or split the channels over two netlists.
3. `python3 run_si.py` (full), `python3 run_si.py --xtalk`, `python3 report.py`, then write TI135_PCB_NOTES.md §6.11.
4. **Ask the user for the Efinix "Titanium RLC spreadsheet"** (Support Center, Board Design tab) before final numbers.
   Until then, every result says which package model it used: net-length line (default) or the vendor file's lumped
   values (`--pkg file`).
5. **Submodule `tools/kicad_ibis_simulation` added (2026-10-27, staged, not committed)**: the Agilex agent's common tools
   (commit 783e057: `kicad_ibis/` sch, spice, eye, ibisfix, zsolve, p2p, show_eye; README, CLAUDE.md).
   - **First thing next session:** read its README and CLAUDE.md, compare it with the scripts here, and rebase this
     study on it.
   - Contribute what it lacks: the private KIBIS cache dir per point, `synth_kukd` (diff N leg and aggressors), the V-t
     trim for RECTDRIVER, CPL crosstalk, and the T topology from board paths.
6. Rules: no commits (the phase session commits). Do not touch `kicad/` or `work/p4/` (read copies only). Never write
   under `~/dev/agilex3_soc_control_card`.

## Files

| file | what |
|---|---|
| `prep_models.py` | Builds `models/ti135_lpddr4.ibs` from the Efinix Titanium file: the LPDDR4 models, a new [Pin] list (SEF/SE0 single-ended, DPF/DNF/DP0/DN0 pairs, SRF/SR0/RPF/RNF/RP0/RN0 receivers; xxF = the vendor pin RLC 1.866 Ω / 1.815 nH / 0.710 pF, xx0 ≈ 0), and V-t tables trimmed of the flat delay and tail. Also builds `models/w66_lpddr4.ibs` (Winbond: R_pin header case, package-matrix diagonal into [Pin], same trim). `*_full.ibs` are the untrimmed copies. |
| `gen_sch.py` | One KiCad schematic per point. Each channel is a real board net's layer runs (TLINE per run, the neck-down part at 0.10 mm, via π L/C by span). Package as a 50.6 Ω line with the Efinix net-length delay, or `--pkg file`. Pairs are uncoupled odd-mode lines. CA/CK/CKE run as a T to both channels. Also `--validate` and `--xtalk` (3 lines, CPL added by `run_si.py`). |
| `run_si.py` | kicad-cli export (KIBIS) → Ku/Kd synthesis and clean-up → ngspice (libngspice in the AppImage) → eye, mask margins, over/undershoot and overshoot area. `--validate`, `--quick`, `--xtalk`, `--only REGEX`, `-j`. |
| `report.py` | `results/*.csv` → `results/results.md` (width table per group, settings, package model, pair geometry, crosstalk, field solve). |
| `board_paths.py` | Per net, the U501 → U801 copper path from a board copy: layer runs, neck length, vias, T split. Run it with `tools/p2k/bin/kipy`. |
| `zsolve_widths.py` | Width → Z0 and ps/mm (SE and pairs) with `tools/zsolve.py`; `cl_matrix` gives the coupled-line L/C matrices. |
| `show_eye.py` | Copied from the Agilex study, not adapted yet. |

## KiCad 10 IBIS converter: problems found here (plus the ones in the Agilex README)

- **Shared cache dir:** KIBIS writes its subcircuits to `~/.cache/kicad/10.0/ibis/`. A parallel session (the Agilex one)
  clears that dir, and files vanished mid-run. `run_si.py` now gives kicad-cli a private `XDG_CACHE_HOME` per point
  (`work/xdg/<tag>`).
- **Differential IBIS drivers** (IBIS_DRIVER_DIFF, PRBS and RECTDRIVER) come out with **empty Ku/Kd** (`pwl ( )`).
- The PRBS driver ignores `td`, and the model's `Polarity Inverting` is ignored.
  - Workaround (`run_si.synth_kukd`): the N leg (and the crosstalk aggressors) is a single-ended driver of the `_diff`
    model.
  - Its Ku/Kd are rebuilt from KIBIS' own rising and falling edge segments, for the complement (or a shifted or
    constant pattern).
- **RECTDRIVER rejects V-t tables longer than the on time** ("Rising edge is longer than on time"). The Efinix tables run
  3 ns, with the edge at 200–450 ps.
  - The PRBS driver only warns ("Bitrate could be too high") and cuts each edge at the next transition.
  - `prep_models.py` trims every table to the edge (same shift for all of a model's tables). It is still about 530 ps
    long at the 0.5 % tolerance.
- The vendor file loads otherwise. [Model Selector], IBIS 6.1, [ISSO_PD/PU], [Composite Current] and [C Comp Corner]
  gave no errors; [Composite Current] is dropped by the trim.

## Rerun (once it works)

```sh
source ../../tools/p2k/bin/kicad_env.sh && export KICAD_MOUNT
python3 prep_models.py
python3 zsolve_widths.py
python3 run_si.py --validate
python3 run_si.py -j 12
python3 run_si.py --xtalk -j 12
python3 report.py
```
