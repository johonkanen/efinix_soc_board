# Pre-order checklist for the Ti135 card PCB

Written 2026-11-13 at commit 559549e, for an agent that starts with no knowledge of this project. The layout is
finished in the sense that every net is connected and DRC is clean. It has **not** had an independent review, and
several checks below have never been run on the final board. Your job is that review: find what would make a
manufactured, assembled board fail, before it is ordered from JLCPCB (8 layers, assembly on both sides).

Do not trust this file or STATUS.md where you can measure the board instead. A check passes only on evidence you
produced in this session (a command's output, a measured distance, a data-sheet page). If you cannot run a check,
report it as "not checked" with the reason; do not mark it passed.

## Rules

- **Read-only.** Do not modify anything under `kicad/`, `lib/` or `tools/`, do not commit, do not push. Work on
  copies in a scratch directory. Copy `kicad/ti135_card.kicad_pro`, `.kicad_dru`, `fp-lib-table` and `lib/` next to
  a scratch board (keep the `kicad/` + `lib/` layout), or zone fills and DRC use the wrong rules.
- Do not place an order, upload files to JLCPCB, or open issues anywhere. Looking up public part numbers and data
  sheets is fine; do not send project files, net names or the owner's details to outside services.
- Do not fix findings. Report them. The owner decides.
- The items under "Accepted, do not report" are decisions already made.

## Setup

```sh
git submodule update --init
source tools/p2k/bin/kicad_env.sh        # KiCad 10 AppImage: kicad-cli, $KICAD_MOUNT
tools/p2k/bin/kipy SCRIPT.py             # python with pcbnew
```

Read first, in this order: `STATUS.md` (top, "What this repository is", the newest "Where we left off", "Decisions
made", "Open items"), `HW_CHECKLIST_REVIEW.md`, `TI135_PCB_NOTES.md` §2, §4, §5, §6.3, §6.5, §6.7, §8, §9,
`MECHANICAL.md`, `POWER_BUDGET.md`. Efinix's own documents are in `reference/efinix/` (local only, not in git).

pcbnew gotchas that have bitten before: `GetSize` / `GetShape` need a layer argument; the 0201 footprints have
paste-only pads (skip with `IsOnCopperLayer()`); arcs are `PCB_ARC` (start/mid/end); ball pads are circles.

Board facts: U501 = Ti135N484I3, 0.8 mm BGA, centre (164.0, 81.0) mm, via-in-pad 0.3 / 0.15 mm. Layers: In1 and
In6 GND; In3 VCORE / 1V1 / 3V3 regions; In4 1V8 / 0V85; signals on F, In2, In5, B. Stack-up JLC08161H-3313.

## Accepted, do not report

- 11 `courtyards_overlap` items. Five are under U501 (0201 capacitors and resistors packed at 0.2 mm
  pad to pad). Six are elsewhere, in three places, and still to be judged: U101 / C105, C1004 / C1005, R1009 / R1022 / R1023 at
  U501's edge (reports/order_check/inline_checks.md, finding 3). Any other overlap **is** a finding.
- No reference silkscreen; ignore silk DRC.
- R801 (DDR_CAL 240 Ω) is 0.5 %, the Efinix checklist asks 0.1 %.
- Rail monitors removed for now: R1301–R1305 are DNP, so U1301 inputs X1, X2, X3, X5 float.
- `pg_all` removed: the supervisor U401 watches VCORE only.
- Clearances: copper 0.1 mm, hole to copper 0.175 mm, hole to hole 0.2 mm (see A4 for the open question there).

## A. Rule checks

- **A1 DRC.** `kicad-cli pcb drc --format json --severity-all --schematic-parity -o OUT.json
  kicad/ti135_card.kicad_pcb`. Pass: 0 unconnected, 0 parity items, and no violation other than the 11 accepted
  courtyard overlaps. Refill the zones on a scratch copy first and confirm the result is the same (a stale fill
  hides shorts and opens).
- **A2 ERC.** `kicad-cli sch erc --format json --severity-all -o OUT.json kicad/ti135_card.kicad_sch`. Pass: only
  the one known `pin_to_pin` warning on the ADC sheet. Explain what that warning is and whether it is harmless.
- **A3 Rules are the intended ones.** Read `kicad/ti135_card.kicad_dru` and the board constraints in
  `ti135_card.kicad_pro`. Check nothing was loosened to make DRC pass (minimum clearance, track, annular ring,
  hole sizes, severities set to "ignore"). List every ignored or downgraded check.
- **A4 JLCPCB capability.** Compare the constraints actually used on the board (smallest track, gap, via pad and
  drill, hole to hole, hole to copper, copper to edge, smallest annular ring, plated slot sizes) with JLCPCB's
  current multilayer capabilities page. The `.kicad_dru` header notes that "via hole to track 0.2 mm" is ambiguous
  and the board uses 0.175 mm from the drill: count how many places are under 0.2 mm and say what the capability
  page says today. Confirm via-in-pad needs "epoxy filled and capped" and that the order notes say so.
- **A5 Leftover copper.** No track or via on a net that reaches fewer than two pads; no zone island that is
  unconnected; no copper on `unconnected-(...)` nets beyond the pad. No track segment narrower than its net
  class minimum.

## B. Power

- **B1 Every supply pin is fed at low impedance.** For every power and ground pad of U501, U801 (LPDDR4), U901
  (PHY), U601 (flash), the eMMC, the translators and the regulators: it reaches its plane or pour through a via or
  a filled-zone connection, not through a long thin track. List pads whose only path is a track longer than 3 mm
  or narrower than 0.15 mm. Known and to be judged: FB501 and FB504 feeds (about 19 mm and 15 mm), and the 5V0
  feeder finger to C311 necking to 0.74 mm.
- **B2 Plane integrity.** For each plane region (In3, In4) and the B.Cu 5V0 feeder: one connected fill per net, no
  slivers narrower than 0.3 mm carrying a rail, and no rail whose only route crosses a slot cut by via
  antipads under the BGA. Estimate the narrowest cross-section between each regulator output and U501 and compare
  it with the rail current in `POWER_BUDGET.md`.
- **B3 Decoupling against Efinix.** Compare the capacitors per supply group on the board with
  `HW_CHECKLIST_REVIEW.md` "Decoupling" and the Efinix checklist (`reference/efinix/ti135n484_hw_checklist.htm`).
  Every capacitor has both pads connected, and the ones under the BGA sit within one ball pitch of a ball of
  their rail.
- **B4 Regulators.** For each TLV62585 cell (U201, U301, U311, U331, U341) and the NCP163 LDO: input capacitor at
  the VIN pin with a short loop to GND, feedback divider values give the intended voltage, FB trace away from the
  switch node, EN connected, inductor on the new footprint `ti135_card:L_2520_FTC252012S` with both pads in copper.
  Check the sequencing against `TI135_PCB_NOTES.md` §5.
- **B5 Filtered supplies.** VCCA / PLL rails after their ferrites: ferrite, capacitor and ball are connected in
  that order, and no unfiltered copper of the source rail touches the filtered net.

## C. FPGA configuration and boot

- **C1** Every dedicated and dual-purpose configuration pin of U501 matches `TI135_PCB_NOTES.md` §4 and §8 and
  the Efinix checklist: pull-ups and pull-downs present, right value, right rail (CDONE and CRESET_N pulled to
  1V8 is an assumption: verify it against the Efinix document). Boot-mode straps select SPI active x4.
- **C2** QSPI flash U601: each of the six signals passes through exactly one series resistor, and no via ties an
  FPGA-side net to a flash-side net (four such shorts were removed on 2026-11-13; confirm none is left by tracing
  copper, not by net name).
- **C3** JTAG header J1 pinout against the Efinix cable; `jtag_tms` and `j3_oe_n` were trimmed by a script on
  2026-11-13: confirm both are continuous from ball to destination.
- **C4** Unused FPGA resources (transceiver pins, unused banks, reference pins) are tied as §9 and the Efinix
  "Unused Resources" rules require.

## D. LPDDR4

- **D1 Timing.** `tools/p2k/bin/kipy tools/ddr/ddr_timing.py kicad/ti135_card.kicad_pcb`. Pass: the limits in
  `NEXT_SESSION.md` "Decisions taken" (DQ/DM to DQS ≤ 75 ps, CK to DQS ≤ 350 ps, address/CKE/CS to CK ≤ 100 ps,
  die to die). Report DQS and CK P/N skew. The DDR copper was last tuned before many later edits around U501:
  compare the DDR nets' copper with the tuned state (`tools/ddr/copper_diff.py`, git history) and report any DDR
  net that changed afterwards.
- **D2 Pin mapping.** Every LPDDR4 net goes from the right U501 ball to the right U801 ball, with the byte and bit
  swaps allowed by `TI135_PCB_NOTES.md` §6.2 and recorded in `LPDDR4_SWIZZLE.md`, and they agree with the Efinity
  pin plan in `efinity/pinplan/`.
- **D3 Reference planes and return vias.** DDR tracks on In2 / In5 run over unbroken GND on In1 / In6 for their
  whole length (no plane splits, no long antipad slots). The DDR user guide asks for a GND return via within
  250 mil of each DDR layer change; this was never done systematically. Count the layer changes without one.
- **D4** Widths and gaps match the 40 Ω / 80 Ω targets of §6.5 and §6.10 outside the BGA neck-down areas.
  ZQ, ODT, RESET_n, CKE terminations and VREF/VDDQ decoupling of U801 against its data sheet.

## E. Ethernet, eMMC, clocks

- **E1 PHY U901 (RTL8211FDI).** Supply pins against the data sheet (pin 29 was the last pad connected, through a
  via 0.11 mm from its neighbours: check it for a short and for annular ring). `phy_rx_ctl` was re-routed by the
  autorouter near pins 28–30: check clearance and that it is one continuous net. RGMII group skew, strap
  resistors (PHY address 1, RGMII at 1.8 V), RSET, crystal load capacitors, magnetics pinout of J9 and the
  centre-tap decoupling.
- **E2 eMMC.** Pin mapping against the data sheet, CLK to data skew (never checked), series resistors placed at
  the driver, pull-ups on CMD and DAT.
- **E3 Clocks.** Oscillator supply and enable, `refclk_bl0..2` each a single point-to-point net into a
  clock-capable ball (§7), skew between them (never checked), no clock track over a plane split.

## F. I/O to the baseboard

- **F1 Connector pinouts.** J3 and J6 are bottom-side sockets numbered like the baseboard: compare pin by pin
  with `reference/baseboard_j11_pinout.csv` and `MECHANICAL.md`. A mirrored connector is the classic fatal error
  here: verify with pad coordinates, viewed from the correct side.
- **F2 Level shifters U1201–U1204.** Direction pins, OE gating and the 10 k pull-downs as described in
  STATUS.md "Decisions made"; A side on the 1.8 V bank, B side on 3.3 V; unused channels terminated.
- **F3 ADC and analog.** ADS7056 and the op-amp: supply, reference, input ranges, and the mux inputs left
  floating by the DNP monitors cannot disturb the channels that are used.
- **F4 Bank voltages.** Every signal on an FPGA ball is at the voltage of that ball's bank (§3).

## G. Mechanical and assembly

- **G1** Outline, mounting holes, J3 / J6 / J9 / J5 / J1 / J2 positions against `MECHANICAL.md`; RJ45 front face
  and centreline; parts taller than the allowed card-to-baseboard gap on the bottom side (the gap measurement is
  an open item: say which parts are at risk for which gap).
- **G2 Footprints against data sheets** for every non-generic part: pad pattern, pin 1, and pin numbering
  (U501, U801, eMMC, U601, U901, TLV62585, NCP163, ADS7056, the oscillator, RJ45, the translators). The inductor
  was checked on 2026-11-13; re-measure it anyway.
- **G3 Pin 1 and polarity** are unambiguous without silkscreen (assembly uses the CPL rotation): run
  `KICAD_ROOT=$KICAD_MOUNT tools/jlc/fab_outputs.sh kicad/ti135_card.kicad_pcb SCRATCH/fab` and check the CPL
  rotation of every polarised or multi-pin part against JLCPCB's convention, bottom side included.
- **G4** Fiducials, paste openings on the BGA and 0201 parts, solder mask between 0.8 mm pitch balls with
  via-in-pad, no exposed via next to a pad without mask between them, board-edge copper clearance.
- **G5 Fabrication files.** From the same `fab_outputs.sh` run: Gerbers for all 8 copper layers plus mask, paste
  and edge; drill files; the layer order and stack-up note; inner-layer zone fills present in the plots.

## H. Parts

- **H1 BOM completeness.** Every populated part has an MPN and an LCSC number; values, tolerances, voltage ratings
  and packages agree between schematic, footprint and the LCSC part. Capacitor voltage ratings against their rail
  with DC-bias derating for the bulk capacitors.
- **H2 Stock.** `python3 -I tools/jlc/stock_check.py SCRATCH/fab/bom_jlcpcb.csv --boards N` (ask the owner for N;
  use 5 if unknown). Judge by the orderable ("free") quantity. Known thin: ADS7056IRUGR, QSPI flash, LPDDR4, eMMC.
  The Ti135N484I3 is not stocked at JLCPCB and needs global sourcing or consignment.
- **H3 DNP parts** are excluded from BOM and CPL, and nothing that must be fitted is marked DNP.

## Report

One table: ID, result (pass / fail / not checked), evidence in one line, and for a fail what would go wrong on
the built board. Then a short list ordered by severity: must fix before ordering, should fix, note for bring-up.
State plainly at the top whether you would order this board as it is.
