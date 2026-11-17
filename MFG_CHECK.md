# Manufacturability check before ordering from JLCPCB

Written 2026-11-17 for the board at commit faac053, for three reviewers who start with no knowledge of this project. Each
reviewer takes one part (A, B or C below) and works alone. The parts overlap on purpose at the edges; report what
you find even if it belongs to another part.

## What this is

The board is `kicad/ti135_card.kicad_pcb`: a control card with an Efinix Ti135N484I3 FPGA (U501, 0.8 mm BGA),
LPDDR4, eMMC, QSPI flash, a Gigabit PHY and five buck regulators. It will be ordered from JLCPCB as an 8-layer
board, 1.6 mm, stack-up JLC08161H-3313, with assembly on both sides.

DRC with schematic parity is clean (no violations, 0 unconnected). That is the starting point, not the result:
your job is to find what DRC does not see and what would make JLCPCB reject the order, build it wrong, or
deliver boards that do not work. In the last days about a third of the area around the FPGA was re-placed and
re-routed, largely by scripts. Treat everything there as unreviewed.

A check passes only on evidence you produced in this session: a command's output, a measured distance, a data
sheet or a JLCPCB page you opened. Do not take `STATUS.md` or this file as proof where you can measure. If you
cannot run a check, report it as "not checked" with the reason.

## Rules for all three

- **Read-only.** Change nothing under `kicad/`, `lib/`, `tools/`, `efinity/`; no commit, no push, no stash.
  Work on copies in your own scratch directory. A scratch board needs `kicad/ti135_card.kicad_pro`,
  `.kicad_dru`, `fp-lib-table`, `sym-lib-table`, the `.kicad_sch` files and `lib/` beside it in the same
  `kicad/` + `lib/` layout, or zone fills and DRC use the wrong rules.
- Do not place an order, upload anything to JLCPCB, or contact anyone. Opening JLCPCB's public capability pages,
  public data sheets and the public part search is fine. Do not send project files, net names or the owner's
  details to any outside service.
- Do not fix findings and do not start other agents. Report; the owner decides.
- Do not read `reports/order_check/*` or older review reports before you have formed your own view.

## Setup

```sh
source tools/p2k/bin/kicad_env.sh          # KiCad 10 AppImage: kicad-cli, $KICAD_MOUNT
tools/p2k/bin/kipy SCRIPT.py ARGS          # Python 3.11 with pcbnew; stderr is noisy, filter it
kicad-cli pcb drc --format json --severity-all --schematic-parity -o OUT.json BOARD
kicad-cli sch erc --format json --severity-all -o OUT.json kicad/ti135_card.kicad_sch
KICAD_ROOT=$KICAD_MOUNT tools/jlc/fab_outputs.sh kicad/ti135_card.kicad_pcb SCRATCH/fab --skip U1303
python3 -I tools/jlc/stock_check.py SCRATCH/fab/bom_jlcpcb.csv --boards 5
python3 -I tools/jlc/jlc_search.py <LCSC number or part name> -n 3
```

`fab_outputs.sh` writes the Gerbers (zip), the drill files, `bom_jlcpcb.csv`, `cpl_jlcpcb.csv` and a DRC
report; it does not change the board. Renders: `kicad-cli pcb export pdf --layers B.Cu,Edge.Cuts -o x.pdf BOARD`,
then `pdftoppm -r 600 -png -x .. -y .. -W .. -H ..`, and look at the picture.

pcbnew notes: `GetSize` / `GetShape` / `GetWidth` of pads and vias need a layer argument; the 0201 footprints
have unnumbered paste-only pads (skip with `IsOnCopperLayer()`); arcs are `PCB_ARC` with start / mid / end;
a pad's bounding box is much larger than the pad when the part is rotated 45 degrees; zones on disk are filled,
refill only on a copy (`zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)`).

Read first: `STATUS.md` (the top, "What this repository is", and the long entry "Where we left off
(2026-11-12)" from "Work in progress since the evening of 2026-11-16" to its end), `MECHANICAL.md`,
`TI135_PCB_NOTES.md` §6.5 (stack-up) and §9, `tools/jlc/README.md`.

## Facts and decisions (do not report these as findings)

- Stack-up: F.Cu signal, In1 GND, In2 signal, In3 power (1V1, VCORE, 3V3, GND fill), In4 power (1V8, 0V85,
  three small 3V3 pours), In5 signal, In6 GND, B.Cu signal with pours. Design rules in `kicad/ti135_card.kicad_dru`:
  track and clearance 0.10 mm, via 0.30 / 0.15 mm (0.45 / 0.25 at the regulators), hole to copper 0.175 mm,
  hole to hole 0.20 mm, copper to edge 0.5 mm. Vias in pads are meant to be filled and capped by the fab.
- No reference-designator silkscreen; only a few custom markings. Ignore silkscreen DRC.
- No courtyard overlap is accepted. A `courtyards_overlap` item is a finding.
- U1303 (ADS7056) is soldered by the owner: it is left out of the BOM and placement file (`--skip U1303`).
- U501 has no LCSC number: it is sourced separately (global sourcing or consigned).
- The owner already holds stock at JLCPCB of AP61202Z6-7 (C5188956), AP61203Z6-7 (C5244557) and the LPDDR4
  H9HCNNN8KUMLHR-NMO (C51891855); the stock check lists the regulators as short, which is expected.
- R801 (DDR_CAL) is 0.5 %; the supervisor watches VCORE only. 25 symbols are marked DNP in the schematic
  (sheets 05, 08, 13; among them the rail-monitor resistors R1301–R1305) and most have no footprint on the board.
- ERC: one `pin_to_pin` warning on the ADC sheet is known. `led0_n` / `led1_n` have only their FPGA end since the
  LEDs were removed; ERC reports them (8 items). The owner knows.
- The 3.3 V FPGA pins were re-assigned on 2026-11-17 and J5 (LCD header) was turned 180 degrees; the pin plan
  is `efinity/pinplan/ti135_pinplan.csv`.

## Part A: bare board (fabrication)

Question: will JLCPCB build this board as drawn, at the price class the owner expects, and will the copper that
comes back be what the design assumes?

1. Open JLCPCB's current PCB capability page yourself and write down the limits that apply to an 8-layer, 1.6 mm,
   1 oz outer / 0.5 oz inner board with filled and capped vias: track and space, via hole and pad, annular ring,
   via hole to track, pad to track at BGAs, hole to hole, copper to edge, solder-mask bridge and opening, plugged
   via rules, minimum slot / non-plated hole, impedance control. Quote the page; do not rely on the numbers above.
2. Measure the board against each limit with your own script, not only with KiCad's DRC. For every limit give the
   board's worst value, where it is (coordinates, layer, net) and how many places are at or under the limit.
   Known open question: via hole to track is 0.175 mm in the rules against 0.2 mm on JLCPCB's page. Count the
   places, say on which layers and nets, and say what you would ask JLCPCB.
3. Vias: every size in use and how many; vias in SMD pads (which pads, both sides: a through via in a pad on one
   side also comes out on the other side: is there a pad of another part there, and is that intended?);
   via-to-via spacing under U501; any via that is not tented or filled where it should be.
4. Solder mask: openings at the 0.8 mm BGA and at the 0201 / SOT-563 parts; mask slivers between pads; mask
   opening to neighbouring track; mask over vias.
5. Planes and pours: isolated copper, slivers and acid traps in fills, thermal reliefs on through-hole pins
   (J3, J5, J6, J9 and the other headers), copper balance between In3 and In4, copper to board edge.
6. Stack-up and impedance: `TI135_PCB_NOTES.md` §6.5 against JLCPCB's published JLC08161H-3313 stack-up; the
   track widths actually used for LPDDR4, RGMII, eMMC and the MDI pairs against the impedance they are meant to
   have. Say what to enter in the order form (impedance control yes / no, which stack-up).
7. Generate the fab files and inspect them: all eight copper layers, mask, paste, outline and both drill files
   present; drill sizes and counts agree with the board; the outline is one closed shape; nothing lies outside
   it (parts were parked right of the outline during the rework: confirm none are left).
8. Board outline and mechanics against `MECHANICAL.md`: outline size, the connector positions it calls hard
   requirements, J5's new orientation.

## Part B: assembly

Question: will JLCPCB's assembly line place the right part, the right way round, on every footprint, and can
each joint be soldered?

1. Generate the BOM and placement file. For every BOM line open the LCSC part (`jlc_search.py`) and compare
   package, value, tolerance and voltage with the schematic value and the footprint on the board. Flag parts
   that are out of stock, extended-library only, or have a minimum purchase far above what is needed.
2. Footprint against part: for every distinct footprint / part pair, compare the land pattern with the part's
   data sheet (pad size, pitch, body size, pin 1). Spend the most time on the ones that are not plain
   chip parts: U501, U801, U1001, U601, U901, the SOT-563 regulators, the 2520 inductors, Y701, Y901, the
   translators, connectors. Check that parts changed in the last days have the footprint their new part needs:
   ferrites FB501–FB504 (now 0201, MPZ0603S121HT000), the PLL filter capacitors (0201), R602–R604, R901–R906.
3. Rotation and polarity: for every polarised or multi-pin part compare the placement file's rotation with the
   footprint's pin 1 and JLCPCB's convention for that package (`tools/jlc/README.md` explains what the tool
   does). Bottom-side parts are the usual place for a 180 degree error. Many 0201 parts under U501 now stand
   at 45 degrees: confirm the placement file carries those angles.
4. Parts too close for placement or soldering: body to body on each side (the rule here is no courtyard
   overlap, but check real bodies too), parts at the edge of U501, tall parts next to small ones, parts under
   connectors, anything within 3 mm of the board edge or a mounting hole.
5. Pads that share copper: several capacitors sit with one pad on a BGA ball via, some with a pad only 0.08 mm
   off the via centre, some linked to a neighbouring via by a 0.2 mm track. List every SMD pad that has a via
   in it or touching it, and judge solder loss and tombstoning assuming filled and capped vias, and again
   assuming they are only tented. Look at the paste layer for these pads.
6. Both sides: which side carries the heavy parts, whether anything on the first-reflowed side could drop,
   fiducials on both sides (three each), tooling holes or edge rails if JLCPCB needs them for this size.
7. Not fitted and special parts: every DNP part is absent from the BOM and placement file and its absence is
   harmless; U1303 is absent; U501 is present in the placement file and marked for separate sourcing; hand-fit
   parts (headers, U1303) can be reached after assembly.
8. Count check: parts in the schematic that are on the board, in the BOM and in the placement file; the three
   counts must be explained to the last part.

## Part C: does the built board match the design (cross-checks after the rework)

Question: if JLCPCB builds exactly these files, is it the circuit in the schematic, and did the re-routing leave
anything that would stop a board from working at power-up?

1. Net-by-net: export the netlist from the schematic and from the board and compare every pad's net yourself
   (do not rely on the parity check alone). List footprints without a symbol and symbols without a footprint.
2. Pin plan: `efinity/pinplan/ti135_pinplan.csv`, the labels on sheet 11 and the nets on U501's balls on the
   board must agree for every signal. Check each signal's bank voltage against what it drives (1.8 V banks 2A,
   2B, 2C, 4A, 4B; 3.3 V banks BL3, BR0, TR1), and that clock inputs sit on clock-capable or PLL-input pins.
   Check the fixed-function pins (configuration, JTAG, flash, reference clocks) against `TI135_PCB_NOTES.md`.
   J5: the order west to east is in `MECHANICAL.md`; say whether MOSI / MISO match the common 14-pin ILI9341
   touch module (the owner has been told they look swapped; confirm or refute with a data sheet).
3. Power at every supply pin: each supply ball of U501 and each supply pin of the other ICs reaches its rail's
   plane; which capacitor is nearest to it and how far by copper; rails where the nearest capacitor moved to the
   regulator output during the rework (1V8 and 3V3 in particular) and whether that is acceptable. The four PLL
   supplies (balls R8, W11, J16, G8): ferrite, capacitor and the track between them. Regulator outputs: number
   of plane vias per rail against the load in `POWER_BUDGET.md`; the VCORE and 1V8 output pours are in two
   pieces each, by a known cause: say whether it matters.
4. Things the rework is known to have broken once: a via in a pad coming out in another part's pad on the far
   side (two such shorts were found and removed); vias that changed net because a pad was moved over them;
   stubs of old routes left on a net (three clock nets had 12–19 mm stubs); plane vias lost when parts moved.
   Search for more of each kind with your own scripts: track ends that touch nothing, vias with copper on one
   layer only, vias whose net differs from the plane they sit in, tracks that end inside a pad of another net's
   part on the far side, any net with a branch that leads nowhere.
5. Fast interfaces after the rework: rerun `tools/p2k/bin/kipy tools/ddr/ddr_timing.py BOARD` and
   `python3 tools/emmc_delay_rules.py` (it rewrites `kicad/ti135_card.kicad_dru`: run it on a copy of the
   repository or restore the file afterwards); RGMII lengths per signal; reference planes under the fast nets
   where In3 was reshaped east of U501; series resistors and pull-ups present on every net that needs them
   (flash, eMMC, RGMII, straps), each on the right side of its resistor.
6. Power-up essentials: reset, supervisor sense, configuration straps, JTAG, the 25 MHz references, flash chip
   select pull-up, PHY reset and straps. For each, trace the copper from end to end on the board.

## Report

Write your report to `reports/mfg_check/<A_fabrication | B_assembly | C_design_match>.md` (the directory is
git-ignored; create it) and return a short summary. Structure:

1. **Must fix before ordering**, **should fix**, **note for bring-up**: findings in that order, most severe
   first. For each: what and where (reference designators, coordinates in mm, layer, net), the measured numbers,
   why it matters, and a concrete fix.
2. **What to enter or ask in the JLCPCB order** (parts A and B).
3. **Checked and found fine**, one line each, with the evidence.
4. **Not checked**, with the reason.

Separate what you measured from what you inferred. If you are unsure whether something is a fault, say so
instead of leaving it out or overstating it. Put your scripts in your scratch directory and name it in the report.
