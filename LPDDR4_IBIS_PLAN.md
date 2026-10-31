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

### 2. Extract the routed copper
- [ ] Copy `extract_routes.py` and `routed_si.py` from `~/dev/agilex3_soc_control_card/sim/lpddr4_si/` (read only:
      never write there) into `sim/lpddr4_si/` and adapt them to this board (U501/U801, layer stack, nets).
- [ ] Per net: segments per layer with width and length, vias with the layers they join, the T and both branches
      of shared nets, the U501 pad-to-die delays from the board.
- [ ] Check the extraction against KiCad: delay per net from the extracted model vs `tools/ddr/kicad_delays.sh`,
      within about 1 ps (the same check as `ddr_timing.py`).

### 3. Measure one worst-case netlist
- [ ] Longest route, min corner (typ if min is not validated yet), 3200 Mbps, under `/usr/bin/time -v`: wall time
      and maximum resident set size.
- [ ] Set `-j` = min(free cores, (free RAM - 3 GB) / peak RSS), probably 3-4. Estimate the total: netlists x time / `-j`.
- [ ] Choose full or screened corners (see above).

### 4. Typ sweep, all nets, 2800 and 3200 Mbps
- [ ] Per net: eye height and width at pin and die, mask margins (V and t), Vmax/Vmin, overshoot/undershoot areas.
- [ ] Results to `sim/lpddr4_si/results/routed_*.csv`, eye PNGs of the worst net of each group.

### 5. Corners
- [ ] min (and max once step 1 allows it), full or screened.
- [ ] If screened: one whole byte at all corners first, to check the ranking holds.

### 6. Crosstalk
- [ ] Short coupled-line netlists (3-5 lines each) at the tightest spots: the 0.2 mm meanders (CA0/CA1, dq10/dq14,
      dq11/dq13, dq26/dq29, dq27/dq28) and the CA-to-DQ crossings. Victim eye with and without aggressors.

### 7. Prove the checks can fail, then report
- [ ] One deliberately bad case (no ODT, a very long line, or a much too narrow trace): margins must go negative and
      the eye plot must agree.
- [ ] Report in `sim/lpddr4_si/README.md`: what was modelled, the stand-ins, every assumption, results per group and
      corner, the worst nets and their margins, and what was not modelled.

## Rules while running

- IBIS sweeps share the machine: start at `-j 2`, raise it only from the measured RSS.
- Never commit vendor IBIS files, the netlength sheet, data sheets or the RLC sheet.
- If a step does not work, stop and report it. Never fill a gap with guessed numbers.
- Stop a sweep by killing its worker PIDs (`pgrep -af libngspice`), never by a broad pattern.
