# LPDDR4 IBIS simulation of the routed board: plan

Written 2026-10-31, after the LPDDR4 delay tuning and crosstalk spacing passed DRC (commit eabcea1). Follow the
steps in order; each one is reported before the next starts. Tick the boxes as they are done.

Method and tools: `tools/kicad_ibis_simulation` (`CLAUDE.md`, `USER_GUIDE.md`, `DELAY_RULES.md`). Earlier
simulation work (width study, CKE): `sim/lpddr4_si/README.md`.

## Goal

Show that every LPDDR4 net as routed meets its receiver's mask and the over/undershoot limits, at the rates and
corners that matter, without running the shared machine out of RAM or for hours.

## What is simulated

| | |
|---|---|
| Nets | All LPDDR4 nets with their routed copper (about 95 netlists per rate and corner): DQ, DM and DQS in both write and read direction; CA, CS, CKE and CK, each with its T to both DRAM channels; RST |
| Rates | 2800 Mbps (the Ti135N484I3 limit) and 3200 Mbps (margin) |
| Corners | typ, min, max (min/max only after step 1 passes) |
| FPGA model | Efinix Ti135 IBIS (`sim/lpddr4_si/models/`, git-ignored, vendor copyright) |
| DRAM model | Stand-in: the SK hynix H9HCNNN8KUMLHR model is under NDA. Same JEDEC LPDDR4 type and ODT options; say so in every result |
| Checks | Eye height and width, Rx mask margins (JEDEC for the DRAM, Efinix data or a labelled proxy for the FPGA), over/undershoot peaks and areas against both data sheets |

## How RAM and runtime are kept down without losing accuracy

Earlier failures: a 44-channel netlist was OOM-killed above 9 GB; a byte of 11 nets in one netlist had not finished
after 75 min (USER_GUIDE.md). Both came from many nets in one netlist.

| Measure | Saves | Why accuracy is kept |
|---|---|---|
| One net (one driver) per netlist | RAM from GBs to about 0.3 GB per run; a byte from 75+ min to 11-20 s per net | The nets are simulated uncoupled anyway; crosstalk gets its own small coupled runs (step 6) |
| `.save` only the driver die, receiver pin and receiver die | RAM from GBs to about 0.3 GB, small output files | Those are the only nodes the eye analysis reads |
| Delete each `.dat` once its numbers are stored | `work/` from 10+ GB to about 0 | Numbers kept for every net; eye PNGs only for the worst |
| Lines < 15 ps lumped as damped L/C (`fastnet`, in use) | No "timestep too small" stops, no crawling runs | Electrically short below 15 ps; checked earlier against the full model |
| KIBIS conversion cache (in use) | Each IBIS buffer converted once | Same converted model |
| 150 PRBS7 bits (unchanged) | - | One full PRBS7 period plus the start-up bits; fewer would miss bit patterns |
| Measure one worst-case netlist first | Real numbers to set `-j` from | - |
| Memory cap per worker (`systemd-run --scope -p MemoryMax=...`) and a timeout per netlist | Protects Quartus/KiCad on the shared machine; a stuck netlist is reported, not waited on | A failed netlist is listed as failed, never left out silently |
| Results appended to the CSV as each netlist finishes; resumable | Nothing lost if the run is stopped or the PC sleeps | - |

Machine: 32 cores, 19 GB RAM (about 15 GB free), shared. Keep 2-3 GB spare. On WSL2, set Windows to "never sleep"
while a sweep runs.

**The one trade-off: corners on all nets or only the worst.**
- Full: typ, min and max on all nets at both rates, about 570 netlists. At about 20 s each and `-j 3`: about 1 h.
- Screened: typ on all nets, min/max only on the worst nets of each group plus the extremes (longest, shortest, most
  vias), about 270 netlists, about 30 min. Before trusting it, run one whole byte at all corners and check that the
  nets that are worst at typ are also worst at min and max. If not, run the full set.
- Decision: full run if step 3 measures <= 30 s per netlist, screened if slower.

## Steps

### 1. Validate the min/max drivers (done 2026-10-31)
- [x] Each driver at typ/min/max as a RECTDRIVER into its own V-t fixture (R_fixture read from the model: Efinix
      40 ohm 20, 48 ohm 24, Winbond 50 ohm), package zeroed, against the model's V-t table of that corner. Then the
      DC high level into the board's loads (Efinix: 60 ohm DRAM ODT and open; Winbond: 40 ohm FPGA ODT and open)
      against the model's own V-I tables. `python3 run_si.py --validate typ|min|max [--corner-files]`, results in
      `sim/lpddr4_si/results/validate_drivers*.md`.
- [x] Cause of the 1.24 V max-corner CKE level: **KiCad's corner switch** (`vcc=MAX rpin=MAX ...`). It is exact into
      the V-t fixture only. Into 60 ohm the Efinix driver is -21 mV (min) / +46 mV (max) off, open -72 / +129 mV.
      The tables themselves give 1.170 V open at max.
- [x] Workaround: `corner_models.py` writes `models/min/` and `models/max/` (min or max column copied into typ,
      V_fixture too) and the corner is simulated at typ (`--corner-files`). Efinix 40 and 48 ohm: levels within 3 mV
      at every load and corner, 20-80 % edges within 1-7 ps. **Use corner files for all min/max runs.**
- [x] Winbond PD40/PD48 (DRAM read driver, stand-in): into the FPGA ODT (40 ohm) within 4 mV at every corner; open
      load wrong (typ -162 mV, files at min/max -207 / -98 mV), which does not matter while the FPGA ODT is on for
      reads. Its edges come out faster than the tables: up to 12 ps at typ and 18 ps at min. Read eyes are then
      slightly optimistic in edge rate; say so in the report.
- [x] The earlier "48 ohm driver 47 mV low" (`validate_drivers.md`) was the validation circuit: it used 20 ohm, the
      model's tables use 24 ohm. Fixed.

### 2. Extract the routed copper (done 2026-10-31)
- [x] `sim/lpddr4_si/extract_routes.py` (adapted from the Agilex card's, read only there): `tools/p2k/bin/kipy
      extract_routes.py` -> `work/routes.json`. 56 nets (DQ, DM, DQS, CK, CA, CKE, CS0/CS2, RST), every pad attached.
- [x] Per net: track and arc pieces (layer, length, width: 0.10 / 0.12 mm, 0.25 mm on the CKE breakout), vias with
      the layers they join, the T and both branches of shared nets, the U501 pad-to-die delay per pad, the netclass.
      Under `_board`: stack-up depths, the tuning profiles (ps/mm per layer, via ps/mm), netclass -> profile.
- [x] `check_routes.py`: the whole-net delay rebuilt from the extracted graph alone with KiCad's model equals
      KiCad's DRC readout within 0.76 ps on every net (`results/check_routes.md`). The pad-to-pad paths per U801 ball
      are listed there too: CK reaches channel A 4-5 ps before channel B (CA - CK +2.4 / -2.2 ps, inside +-5.3); a few
      nets carry under 1 ps of stub copper (dm2, dq26, dq29).

### 3. Measure one worst-case netlist (done 2026-10-31)
- [x] `sim/lpddr4_si/routed_si.py --one NET --corner C --rate R`: one net's extracted copper (every piece with the
      Z0 and ps/mm of its layer and width, vias as hubs with L by span and C to ground, stubs and T branches as
      routed) between its IBIS buffers; min/max from the corner model files at typ; `.save` only the probed nodes;
      the `.dat` is deleted after reading. Single-ended nets so far; DQS/CK pairs follow in step 4.
- [x] Worst cases at min corner, 3200 Mbps (peak RSS summed over the whole process tree, sampled every 0.1 s):
      ddr_ca2 (T to both channels, longest copper) 11 s, 76 MB; ddr_cke0 12 s, 76 MB; ddr_dq1 8 s. ddr_ca2 at typ
      2800: 13 s, 80 MB. One-net netlists are tiny: the OOM and the hour-long runs were the many-net netlists.
- [x] `-j`: CPU-bound, not RAM-bound (6 workers ~0.5 GB). Use `-j 4` on the shared machine (up to `-j 8` when it is
      free). About 86 netlists per rate and corner (36 DQ/DM write, 32 DQ read, 9 CA/CS/CKE, 8 DQS, 1 CK), 516 for
      both rates and all corners: about 26 min at `-j 4`.
- [x] Decision: **full corners on every net** (13 s per netlist, under the 30 s threshold); no screening needed.

### 4. Typ sweep, all nets, 2800 and 3200 Mbps (done 2026-10-31)
- [x] `routed_si.py --sweep --corners typ -j 4`: 172 netlists, 7.7 min, 0 failed. DQS/CK pairs: each leg its own
      copper at the pair's odd-mode Z0 (0.10 mm / 0.20 mm gap as routed). Resumable CSV, timeout and memory cap per
      run, `.dat` deleted after reading.
- [x] **Every net passes at both rates**, no negative margin at the die or the DRAM ball, no over/undershoot limit
      or area exceeded. Tightest: DQ read timing 49 ps (3200, dq11), CA voltage margin 137 mV, CKE peak 1344 mV
      against 1400 mV. Table: `sim/lpddr4_si/results/routed_typ.md`; rows `results/routed.csv`.
- [x] Eye PNGs of the worst net per kind and rate (`--plot-worst`, `results/eyes/eye_worst_*`, git-ignored): open
      eyes, masks inside; plots agree with the numbers.

### 5. Corners (done 2026-10-31)
- [x] Full min and max on every net (no screening): `routed_si.py --sweep --corners min max -j 4`, 344 netlists,
      14 min, 0 failed. Table: `sim/lpddr4_si/results/routed_corners.md`.
- [x] No negative eye margin at any corner or rate. Worst nets mostly the same at every corner.
- [x] One limit exceeded: **CKE0, max corner, 3200 Mbps: 1486 mV peak at one DRAM die vs 1470 mV** (16 mV over,
      area 0.04 V-ns within 0.1). At 2800 Mbps (the I3's top rate) 1417 mV, 53 mV inside. Efinity has no
      CA/CK/CKE drive setting; fix: 10 ohm series resistor on B.Cu at U501 (peak 1291 mV at max/3200, eye margins
      376 mV / 208 ps; `results/routed_corners.md`).

### 6. Crosstalk (done 2026-10-31)
- [x] Coupled lengths from the board (`coupled_lengths.py`, `results/coupled_lengths.md`): besides each pair's own
      P/N, at most 2.5 mm at a 0.20-0.25 mm edge gap (dq14) and 9.2 mm at 0.30-0.40 mm (dq30/dq31). CA-to-DQ
      crossings are on different layers with planes between: not coupled lines.
- [x] Three coupled lines (both aggressors over the whole length), DQ write, typ, 2800/3200: the board's two worst
      cases and a 10 mm bound. ngspice's CPL element stopped every run ("timestep too small"); replaced by a lumped
      ladder of 0.25 mm sections from the same field-solved L/C matrices (`run_si.py` `cpl_lines`).
- [x] Crosstalk costs at most 14 mV eye height, 10 mV V margin, 8 ps t margin (10 mm bound); peak noise on a quiet
      victim 30 mV far end. Every net still passes with that taken off. `sim/lpddr4_si/results/xtalk_board.md`.

### 7. Prove the checks can fail, then report (done 2026-10-31)
- [x] `sim/lpddr4_si/bad_case.py`, 3200 Mbps: (1) DQ write with the DRAM ODT off at max: limits fail (1579 mV,
      areas over 0.1 V-ns); (2) DQ read with the FPGA ODT off at max: t margin -30 ps; (3) all traces 150 ohm and
      4x long with ODT: degraded (259 mV eye) but passes; (4) the same with the ODT off: eye closed (-450 mV, 0 ps).
      The eye plots agree with the numbers.
- [x] Report: `sim/lpddr4_si/README.md` "Routed board: result". Every net passes at 2800 and 3200 Mbps, all
      corners, except CKE0 at max/3200 (16 mV over the peak limit): **10 ohm series resistor on CKE at U501**.
- [x] R803 on the board (e4ac548): CKE extracted through it and rerun at all corners: worst peak 1299 mV (max,
      2800) vs 1470 mV, margins >= 393 mV / 210 ps (`results/routed_corners.md`).
- [x] CKE retuned (306.7 ps, -1.0 ps vs CK) and rerun: every corner passes; peak 1331 mV at max/2800 (139 mV
      margin), 1448 mV at max/3200 (22 mV margin).

## Rules while running

- IBIS sweeps share the machine: start at `-j 2`, raise it only from the measured RSS.
- Never commit vendor IBIS files, the netlength sheet, data sheets or the RLC sheet.
- If a step does not work, stop and report it. Never fill a gap with guessed numbers.
- Stop a sweep by killing its worker PIDs (`pgrep -af libngspice`), never by a broad pattern.
