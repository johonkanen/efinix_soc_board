# Agent prompt: LPDDR4 IBIS simulation, how narrow the traces can be

Prompt for an agent that answers how narrow the LPDDR4 traces can be (inner In2/In5 and outer F.Cu/B.Cu) without
hurting signal integrity, with the Efinix Titanium IBIS models. Written 2026-10-27. It follows the method of the
Agilex 5 card (`~/dev/agilex3_soc_control_card/sim/lpddr4_si/`, its README and NEXT_STEPS.md "IBIS simulation
results"), which found 50–70 Ω DQ lines cost only 10–15 ps of margin at 1600 MT/s. This card runs about twice as fast
(UI 357 ps instead of 625), so that result does not carry over as is.

```text
You are doing a signal-integrity (IBIS) simulation for the LPDDR4 interface of a KiCad board. The question is how
narrow the LPDDR4 traces can be, on the inner layers (In2/In5, stripline) and the outer layers (F.Cu/B.Cu,
microstrip), without hurting signal integrity. Today they are routed at 40 ohm (0.18 mm inner, 0.25 mm outer),
which crowds the bus. Work in the repo /home/jari/dev/efinix_soc_board (KiCad 10). Read STATUS.md first, then
TI135_PCB_NOTES.md §6.3 (Efinix routing rules, timing budget), §6.5 (stack-up, layer roles, field-solve table) and
§6.10 (the 40 ohm widths, neck-downs).

THE METHOD TO REUSE (read, do not modify)
- ~/dev/agilex3_soc_control_card/sim/lpddr4_si/: README.md (method, KiCad 10 IBIS converter bugs and workarounds,
  masks, "How narrow can the data traces be"), gen_sch.py, run_si.py, report.py, prep_models.py, zsolve.py, and
  results/. That repo belongs to another session: NEVER write anything under ~/dev/agilex3_soc_control_card. Copy the
  scripts into this repo (sim/lpddr4_si/) and adapt them there.
- Tool chain proven there: gen_sch.py writes a KiCad schematic (IBIS driver/receiver, TLINE, via L/C) ->
  `kicad-cli sch export netlist --format spice` (runs KiCad's IBIS converter, KIBIS) -> ngspice (the libngspice
  inside the KiCad 10.0.7 AppImage) -> eye, mask margins, over/undershoot. Here the AppImage is mounted by
  `source tools/p2k/bin/kicad_env.sh` ($KICAD_MOUNT/bin/kicad-cli, $KICAD_MOUNT/lib for libngspice); use that, or
  extract the AppImage into the scratchpad as the Agilex README describes.

SYSTEM (this card)
- FPGA: Efinix Ti135N484I3 (U501), hard LPDDR4 controller. Memory: SK hynix H9HCNNN8KUMLHR-NME (U801), x32, 2
  channels, 1 rank. CA/CKE/CK go as a T to both channels; CS0/CS2 point to point.
- Data rate: the I3 part tops out at 2.8 Gbps (TI135_PCB_NOTES.md §6.3), UI 357 ps. Simulate at 2800 MT/s; add
  3200 MT/s as a margin check (the board is routed to Efinix's 3700 Mbps timing budget).
- Stack-up JLC08161H-3313, 1.6 mm, 8 layers (§6.5): In2 sits on a 0.1 mm core over In1 GND with In3 (split plane:
  VCORE/1V1/3V3) 0.357 mm away; In5 on a 0.1 mm core over In6 GND with In4 (1V8/0V85/5V0) above. F/B microstrip
  over In1/In6 with 0.03 mm mask. tools/zsolve.py and tools/zsolve_cases.py are this repo's 2D field solver (checked
  against Cohn's formula); use them for width -> Z0 and ps/mm per layer, single-ended and diff (pair width/gap).
- Today: 40 ohm SE = 0.18 mm inner / 0.25 mm outer; DQS/CK 80 ohm diff = 0.14 mm / 0.15 mm gap inner, 0.20/0.20
  outer; neck-down to 0.09–0.10 mm inside the BGA courtyards. Vias 0.30/0.15 mm (U501, via-in-pad) and 0.25/0.15 mm
  (U801). JLC's floor is 0.09 mm track.
- Routed board: kicad/ti135_card.kicad_pcb. DO NOT open or modify it in place. Copy it to a scratch folder to read
  lengths. Use `tools/p2k/bin/kipy tools/ddr/ddr_timing.py BOARD --nets` (die-to-die delays per net) and the KRT
  parser (~/dev/KiCadRoutingTools/py_router/kicad_parser.py) for per-layer segment lengths and via counts. Pick the
  worst real nets: the longest DQ of each byte, the one with the most vias or layer changes, DQS, the longest CA
  trunk and its T branches, and CS (point to point). Note: a phase 4 session is re-routing CK/CA right now (CA
  trunks and branches all on In5, via-in-pad at the U801 balls, branches ~1.5–2.5 mm). Model the CA T in that
  topology, and take the trunk lengths from the board at the time you start.

MODELS
- Efinix: reference/efinix/ibis/titanium_ibis-v1.5/titanium_ibis.ibs (git-ignored; the zip is beside it). Generic
  Titanium file (IBIS 6.1, 158 models). LPDDR4 ones: [Model Selector] lpddr4_ocd (single-ended driver
  lpddr4_ocd_240p_240n ... _40p_40n, _120pd_60p_40n), lpddr4_ocd_diff (DQS/CK), lpddr4_odt (receiver ODT 240 ... 40,
  off) and lpddr4_odt_diff. Use the LPDDR4 models, not lp4x (this card's VDDQ is 1.1 V, LPDDR4 not 4X).
  CAUTION: its [Package] and [Pin] R/L/C are for the Ti180J361 HSIO, and its pin numbers are placeholders. The file
  says to take the real per-pin RLC from Efinix's "Titanium RLC spreadsheet" (Support Center, Board Design tab). This
  repo has only reference/efinix/ti135n484_netlength.csv (per-ball length and delay, no RLC). If the RLC spreadsheet
  is not in reference/efinix/, ask the user for it before final numbers. Meanwhile, run with the file's
  lpddr4 pin values (1.866 ohm, 1.815 nH, 0.710 pF) and with an estimate from the netlength delay (state how), and
  say which one each result used.
- Which FPGA drive strength and ODT does the Ti135 controller use? Find out from Efinity 2026.1 (~/efinity/2026.1):
  the DDR block's properties in Interface Designer (efinity/pinplan/pinplan.py creates the block "ddr", type DDR),
  the DDR controller/PHY documentation under ~/efinity/2026.1/doc, or the Ti135 data sheet. Read only: do not change
  pinplan.py or the Efinity project. If it is configurable, simulate the default plus 40 and 48 ohm drive, and
  FPGA read ODT 40/48/60.
- Memory: the SK hynix IBIS model is not public. Use the same public stand-in as the Agilex card: Winbond W66CL2NQUAFJ
  (LPDDR4 x32, 2 ch, DDP). Copy ~/dev/agilex3_soc_control_card/sim/lpddr4_si/models/w66cl2nquafj_a001.ibs into this
  repo's git-ignored sim/lpddr4_si/models/ (copying out is fine; never write there). Apply the same fixes as its
  prep_models.py (R_Pin header case, package matrix diagonal into [Pin]). Memory DQ ODT 40/48/60, drive 40/48
  (PDDS), CA ODT 80 (and 60). Say clearly in the results that the memory is a stand-in.
- The Agilex README lists KiCad 10 IBIS converter problems (case-sensitive [Pin] columns, [R Series] rejected,
  [Define Package Model] ignored, Ku/Kd PWL too dense plus solver spikes, corner names must be upper case). Expect them
  here too, and check the Efinix file for others ([Model Selector] handling, IBIS 6.1 keywords). Validate every
  converted driver against its IBIS V-t tables (run_si.py --validate) before sweeping.

CASES (each at 2800 and 3200 MT/s, typ/min/max corners)
1. DQ write: FPGA lpddr4_ocd -> package -> via-in-pad -> neck-down -> line -> via -> DRAM package -> DRAM ODT.
2. DQ read: DRAM driver -> same channel -> FPGA lpddr4_odt.
3. DQS (and CK) as a differential pair: lpddr4_ocd_diff / lpddr4_odt_diff, pair width/gap sweep.
4. CA through the T: FPGA driver -> In5 trunk (a real length) -> T via -> two equal In5 branches -> via-in-pad -> two
   DRAM CA inputs with CA ODT. Also CS point to point.
Width sweep, with field-solved Z0 and ps/mm per point. Inner In2/In5: 0.18 (today), 0.15, 0.12, 0.10, 0.09 mm.
Outer F/B: 0.25 (today), 0.20, 0.15, 0.12, 0.10, 0.09 mm. Diff pairs: today's geometry plus 2-3 narrower width/gap
combinations near 80, 90 and 100 ohm. Model each net's real layer mix (the bytes have up to 1/3 of their length on
F/B). Vias as π L/C: state the values. The Agilex estimates were 0.15 nH / 0.40 pF short, 0.50 nH / 0.40 pF long,
with U501 0.30/0.15 and U801 0.25/0.15 here.
5. Crosstalk, if the tool chain allows (ngspice coupled lines, e.g. a CPL or multiconductor line): one victim
   between two aggressors at the board's real pitch (0.11 mm clearance today, the 0.2 mm xtalk-spacing rule), for
   today's width and the narrowest candidate at the same pitch, so that the freed space shows up as gap. The Agilex
   study did not simulate crosstalk; this card's bus is denser, so try. If it is not feasible, say so.

MEASUREMENTS
- PRBS7 at the data rate, eye at the receiver ball and die, after the first 12 bits.
- JEDEC JESD209-4 LPDDR4 Rx masks for the simulated rate (DQ: VdIVW, TdIVW; CA: VcIVW, TcIVW). State the values
  and the source. The Agilex study used TI SPRAD66B's reproduction for 1600; find the 2800/3200 columns. FPGA read
  side: Efinix publishes no Rx mask that we know of. Use the same TI SoC diamond proxy and say so.
- Over/undershoot against the DRAM and Ti135 absolute maximum ratings (Ti135 data sheet; quote the table).
- Table: case x layer x width x setting -> eye height, eye width, mask margin V / t, Vmax/Vmin. Then the answer:
  the narrowest inner and outer width (and diff geometry) for which the margins stay within a small, stated loss
  of today's 40 ohm result (e.g. <= 10 % of the time margin), and the width where they start to fall off. Also the
  delay per mm at each width: tools/ddr/ddr_timing.py uses 7.01 ps/mm inner, 6.11 outer, and a width change
  must not change those enough to break the matching.

DELIVERABLES
- sim/lpddr4_si/ in this repo: scripts adapted from the Agilex ones, a small KiCad simulation project, README (how to
  rerun, models and where they come from, converter workarounds), results/ (CSV, MD table, eye PNGs).
- A new section TI135_PCB_NOTES.md §6.11 "LPDDR4 trace width from IBIS simulation": result table, recommendation per
  layer and signal class, what is not modelled. Do not change the DRC rules or tools/board_setup.py: the user decides
  on a width change afterwards.

RULES
- The GitHub repo is PUBLIC. Never commit vendor files (Efinix IBIS, Winbond IBIS, the netlength sheet, data
  sheets). reference/efinix/ is git-ignored; add sim/lpddr4_si/models/ and sim/lpddr4_si/work/ to .gitignore.
- Never modify ~/dev/agilex3_soc_control_card (read and copy out only).
- Do not write anything under kicad/ or work/p4/ (a phase 4 routing session is using them). Never save a pcbnew
  board into the repo; read copies in the scratchpad.
- Schematics of the card only through tools/sheets/*.py (not needed here; the sim schematic in sim/lpddr4_si/ is
  generated by its own script).
- Do not commit or push (the phase session commits in this repo). Leave everything as uncommitted changes and list
  them at the end.
- If a step is impossible (no headless IBIS path, a model that will not load, no RLC data where it matters), stop
  at that point and report what you found, rather than guessing numbers. Ask the user for missing vendor files.
```
