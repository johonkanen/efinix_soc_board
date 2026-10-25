# Layout plan: placement and routing

How the board goes from placed parts to fab outputs, and which tool does each step. The tools are KiCadRoutingTools
(`~/dev/KiCadRoutingTools`, its skills linked into `.claude/skills/`) and this repo's scripts. Decided with the user
2026-10-25.

## Ground rules

- `kicad/ti135_card.kicad_pcb` is the only real board. Tool runs work on copies in `work/` (always with the
  `.kicad_pro` / `.kicad_dru` beside them). A result is applied back only after its check passes.
- **LPDDR4, eMMC and QSPI flash are routed automatically and signed off by hand**: the router draws them, then a
  review checks lengths, delays, references and DRC. Parts the review rejects are fixed by hand in pcbnew.
- Until the first copper is committed, `tools/build_pcb.sh --rebuild` may recreate the board (placement is restored).
  After that, schematic changes go in with pcbnew's "Update PCB from Schematic".
- Gate between phases: KiCad DRC with `kicad/ti135_card.kicad_dru`, schematic parity 0, commit.

## Design inputs (fixed)

| Item | Value | Where |
|---|---|---|
| Stack-up | JLC08161H-3313, F / **In1 GND** / In2 / **In3 plane** / **In4 plane** / In5 / **In6 GND** / B | TI135_PCB_NOTES.md §6.5 |
| Signal layers | F.Cu, In2, In5, B.Cu | §6.5 |
| LPDDR4 impedance | 40 Ω SE / 80 Ω diff (Efinix DDR PCB guide): In2/In5 0.18 mm, 0.14/0.15 mm | §6.3, §6.5 |
| Other controlled nets | 50 Ω / 100 Ω: In2/In5 0.12 mm, 0.11/0.25 mm; F/B 0.15 mm, 0.13/0.25 mm | §6.5 |
| LPDDR4 data rate | Ti135N484I3 maximum 2.8 Gbps (data sheet Table 22); routed to the Efinix table (3700 Mbps budget) | §6.3 |
| LPDDR4 swizzle | DQ order within each byte fixed in Efinity (`efinity/pinplan/lpddr4_swizzle.json`); bytes 0/1/3 on In2, byte 2 + CA/CK on In5 | LPDDR4_SWIZZLE.md |
| Planes | In1 GND · In3 1V1 / VCORE / GND · In4 1V8 / 0V85 · In6 GND · B.Cu 5V0 region · F/B GND flood after routing; 3V3 routed | §6.6 |
| BGA fan-out | via-in-pad on every connected ball of U501 (0.30/0.15) and U801 (0.25/0.15) | §6.7 |
| Card-to-baseboard gap | ≈ 5.3 mm (1.27 mm socket on male header); power supplies on the underside, as on the Ti60 card | MECHANICAL.md |

## Phase 1: placement

| Step | Tool / by hand |
|---|---|
| 1. Placement inputs: fixed parts locked (J3, J6, J9, J5, J1, J2, U501, U801), BGA decaps and power cells on B.Cu, the five TLV62585 cells held to TI's Figure 24 layout | `placement/prep.sh` (`fit_template.py`) |
| 2. Place 12 seeds, quick-route the best 3–6 one at a time, keep the best | `place_simple.py`, `judge_seeds.py` |
| 3. Apply it, check courtyards / edges / template drift | `tools/apply_placement.py`, `check_assembly`, `render_placement` |
| 4. Hand touch-ups: RGMII TX resistors at the FPGA, RX resistors at the PHY; Y901 at the PHY; ZQ (R802) and DDR_CAL (R801) at their balls; the PLL ferrites at their balls | pcbnew |
| 5. Reference labels | `beautify_labels.py` |

## Phase 2: routing inputs (no copper)

| Step | Tool |
|---|---|
| 6. Net classification: LPDDR4 (DQ/DM, DQS and CK pairs, CA), RGMII, MDI pairs, eMMC, QSPI | `/find-high-speed-nets`, `/identify-diff-pairs` |
| 7. Power-net widths (buck rails, 5V0, PHY local rails) | `/analyze-power-nets` |
| 8. One parameter set for the router: per-layer widths (explicit, never `--impedance` on F/B), layer costs, length-match groups per DDR byte, eMMC and QSPI groups | `/plan-pcb-routing` steps 0–6 |

## Phase 3: planes and fan-out

| Step | Tool / by hand |
|---|---|
| 9. **Done.** Planes per §6.6; check the In3 VCORE/1V1 seam (y ≈ 78) and that the DDR corridor is all 1V1. Draw region outlines by hand if the tool's split does not follow the ball map | `route_planes.py`, pcbnew |
| 10. **Done: via-in-pad** on every connected ball (`tools/via_in_pad.py`); the escapes are part of the routing steps | §6.7 |
| 11. **Done.** Under-BGA decaps moved off foreign vias | `place_fanout_clearance.py` |
| 12. Buck cells on B.Cu: one cell drawn by hand (SW node small, GND strip between the pin rows with vias to In6, wide VIN/VOUT with vias to the planes), copied to the other four | pcbnew |

## Phase 4: memories (automatic, hand sign-off)

| Step | Tool |
|---|---|
| 13. LPDDR4 DQ bytes on their layers, DQS matched to its byte. **Target swap off** (the swizzle is fixed in Efinity). A reorder inside a byte is legal only through `lpddr4_swizzle.json` → `pinplan.py` → schematic | `route.py` / `route_diff.py` with length-match groups |
| 14. CA, CK, CKE, CS, RST on In5 up U801's centre column | same |
| 15. eMMC (CLK, CMD, DAT0–7, DS, RST): length-matched to CLK, CLK through R1001 | `route.py` with a match group |
| 16. QSPI flash (CLK, CS, IO0–3): short, matched to CLK | same |
| 17. Sign-off: lengths and delays against §6.3 (with the FPGA package net lengths once downloaded), reference planes, return vias, DRC. Swizzle re-score | `/review-routed-board`, `tools/lpddr4_swizzle_score.py`, by hand |

## Phase 5: the rest

| Step | Tool |
|---|---|
| 18. MDI pairs to J9 (100 Ω), RGMII as a matched group | `route_diff.py`, `route.py` |
| 19. Everything else on F/In2/In5/B, planes by via; iterate on the open nets | `route.py`, `/diagnose-routing-failures` |
| 20. A non-DDR FPGA pin that blocks routing: swap it in `pinplan.py` (Efinity check), rebuild the schematic, "Update PCB from Schematic" | pin-plan loop |
| 21. GND stitching, return vias at high-speed layer changes, F/B GND flood | the routing skill's plane-finalise step |

## Phase 6: sign-off and fab

| Step | Tool |
|---|---|
| 22. DRC, connectivity, orphan stubs, length groups, return vias, diff pairs | `/review-routed-board`, KiCad DRC |
| 23. Mechanical: J3/J6/J9 positions (make_board check); bottom-side part heights against the 5.3 mm gap over the baseboard parts | script + review |
| 24. Gerbers, BOM, CPL; JLC DFM; stock (Ti135 sourcing, ADS7056, LPDDR4, eMMC) | `tools/jlc` (`fab_outputs.sh`, `jlc_bom_cpl.py`, `stock_check.py`) |
