# LPDDR4 swizzle: U501 (Ti135N484I3) → U801 (H9HCNNN8KUMLHR-NME)

Written 2026-10-25. **Within-byte DQ swizzle** chosen from the real pad positions of the placed, locked parts:
- U501 at (164, 81), rotated 180°;
- U801 at (173.3, 58.1), rotated −90°.

The byte, channel, DM, DQS and CA mapping stays as in TI135_PCB_NOTES.md §6.1. One file drives everything:
`efinity/pinplan/lpddr4_swizzle.json`.
- `tools/sheets/08_lpddr4.py` wires the schematic from it.
- `efinity/pinplan/pinplan.py` sets Interface Designer's `PIN_SWIZZLE_*` from it and reads the values back.
- `tools/lpddr4_swizzle_score.py` (run with kipy) scores the board as built (`--search` brute-forces all orders).

## 1. Rules and sources

| Swap | Verdict | Source |
|---|---|---|
| DQ bits within the same byte, **DQ0 included** | **Allowed, used** | (a) Efinity Interface Designer *Pin Swizzling* tab: "drag and drop pins in the DRAM column to swap DQ/DM pins", one group per byte (Titanium DDR DRAM Block UG v2.9 Table 22; help page `pt/doc/topics/titanium-ddr-id-1.html`; Python API UG Table 31 `PIN_SWIZZLE_DQM0..3`). (b) Efinix's own Ti375C529 dev kit swizzles every byte, including DQ[0]→DQ[3] (`ipm/ip/efx_hard_soc/fpga/Ti375C529_devkit/Ti375C529_devkit.peri.xml`, `<efxpt:pin_swap>`) |
| DQ to another byte | **Not allowed** | `DDRPinSwap.get_group_options()` (`pt/bin/tx180_device/ddr/ddr_design_adv.py`): group n only offers DQ[8n..8n+7] and DM[n]. Tested: `set_property` rejects it ("Unable to translate PIN_SWIZZLE_DQM0") |
| Whole byte lanes (byte 0↔1 in a channel, channel A↔B) | **Not allowed** | Not expressible, for the same reason (tested: rejected). LPDDR4 MRR data and CA-training feedback come back on byte 0 of each channel, and the controller can't be told about a moved byte |
| DM ↔ DQ inside a byte | Tool accepts it; **not used** | DM[n] is in group n's option list, and the test accepts it. But no Efinix board does it, DMI carries DM/DBI and training, and here it would gain only 1–5 crossing points per byte (§4). Staying conservative |
| DQS_t ↔ DQS_c, DQS to another byte | **No** | No such setting; the DQS pair is fixed to its byte |
| CA[5:0] among themselves | Tool supports one permutation (`PIN_SWIZZLE_CA`); **not used** | Python API UG Table 31. No Efinix board uses it, and it doesn't help here (§3.3) |
| CK, CKE, CS_N, RESET_N | **No** | No setting exists. CS_N[0]→channel A, CS_N[2]→channel B (DDR DRAM Block UG v2.9, "Single-Rank, x32 Interface") |

**Semantics** (from `design/package_pin.py` and confirmed in the generated pinout):
- Position k of `PIN_SWIZZLE_DQMn` is FPGA ball `DDR_DQ[8n+k]`, and position 8 is `DDR_DM[n]`.
- The value is the DRAM-side signal wired to that ball, numbered across the x32 bus:
  - channel A byte 0/1 = DQ[0:7] / DQ[8:15];
  - channel B byte 0/1 = DQ[16:23] / DQ[24:31].
- After the swizzle, `build/outflow/ti135_pinplan.pinout.csv` labels each ball with that DRAM-side name. For
  example, ball U1 (pad DDR_DQ[2]) is listed as `ddr.DQ[0]`.
- KiCad keeps the physical pad names (`reference/ti135n484_pinout.csv`).

**What the design check enforces** (tested 2026-10-25 in a throw-away project):
- `set_property` rejects cross-byte values, whole-byte swaps and duplicates without raising in `check_design()`, and
  the old value silently stays. That is why `pinplan.py` reads the swizzle back and stops on a mismatch.
- The 2026-10-24 note that such swaps were "accepted" was this silent no-op.
- A hand-edited peri.xml is caught by `ddr_rule_pin_swap` (help page `dc-ti-ddr-1.html`).

**Not found in any document:**
- an explicit Efinix statement about DQ0 / CBT bit constraints (the dev kit's DQ0 swap is the evidence used here);
- a statement on DM↔DQ beyond the tool's option list.

The *Titanium DDR DRAM PCB Design UG* v1.2 says nothing about swapping. It only says to keep each byte group on one
layer and route CK/A/CKE/CS on one layer.

## 2. Chosen mapping

| Byte | FPGA signal | FPGA ball | Net | DRAM signal | DRAM ball |
|---|---|---|---|---|---|
| 0 (ch A byte 0) | DDR_DQ[0] | U3 | ddr_dq0 | DQ6_A | C4 |
| 0 (ch A byte 0) | DDR_DQ[1] | U2 | ddr_dq1 | DQ7_A | B4 |
| 0 (ch A byte 0) | DDR_DQ[2] | U1 | ddr_dq2 | DQ0_A | B2 |
| 0 (ch A byte 0) | DDR_DQ[3] | V3 | ddr_dq3 | DQ4_A | F4 |
| 0 (ch A byte 0) | DDR_DQ[4] | Y2 | ddr_dq4 | DQ5_A | E4 |
| 0 (ch A byte 0) | DDR_DQ[5] | AA1 | ddr_dq5 | DQ1_A | C2 |
| 0 (ch A byte 0) | DDR_DQ[6] | AB2 | ddr_dq6 | DQ3_A | F2 |
| 0 (ch A byte 0) | DDR_DQ[7] | AA2 | ddr_dq7 | DQ2_A | E2 |
| 0 (ch A byte 0) | DDR_DM[0] | W3 | ddr_dm0 | DMI0_A | C3 |
| 0 (ch A byte 0) | DDR_DQS[0] | W2 | ddr_dqs0_P | DQS0_T_A | D3 |
| 0 (ch A byte 0) | DDR_DQS_N[0] | W1 | ddr_dqs0_N | DQS0_C_A | E3 |
| 1 (ch A byte 1) | DDR_DQ[8] | U4 | ddr_dq8 | DQ8_A | B11 |
| 1 (ch A byte 1) | DDR_DQ[9] | V5 | ddr_dq9 | DQ9_A | C11 |
| 1 (ch A byte 1) | DDR_DQ[10] | W5 | ddr_dq10 | DQ14_A | C9 |
| 1 (ch A byte 1) | DDR_DQ[11] | W4 | ddr_dq11 | DQ15_A | B9 |
| 1 (ch A byte 1) | DDR_DQ[12] | AA5 | ddr_dq12 | DQ10_A | E11 |
| 1 (ch A byte 1) | DDR_DQ[13] | AB5 | ddr_dq13 | DQ11_A | F11 |
| 1 (ch A byte 1) | DDR_DQ[14] | AA6 | ddr_dq14 | DQ13_A | E9 |
| 1 (ch A byte 1) | DDR_DQ[15] | AB7 | ddr_dq15 | DQ12_A | F9 |
| 1 (ch A byte 1) | DDR_DM[1] | AA3 | ddr_dm1 | DMI1_A | C10 |
| 1 (ch A byte 1) | DDR_DQS[1] | Y4 | ddr_dqs1_P | DQS1_T_A | D10 |
| 1 (ch A byte 1) | DDR_DQS_N[1] | AA4 | ddr_dqs1_N | DQS1_C_A | E10 |
| 2 (ch B byte 0) | DDR_DQ[16] | AA16 | ddr_dq16 | DQ6_B | Y4 |
| 2 (ch B byte 0) | DDR_DQ[17] | Y16 | ddr_dq17 | DQ3_B | U2 |
| 2 (ch B byte 0) | DDR_DQ[18] | AA17 | ddr_dq18 | DQ7_B | AA4 |
| 2 (ch B byte 0) | DDR_DQ[19] | AB17 | ddr_dq19 | DQ0_B | AA2 |
| 2 (ch B byte 0) | DDR_DQ[20] | V18 | ddr_dq20 | DQ1_B | Y2 |
| 2 (ch B byte 0) | DDR_DQ[21] | V17 | ddr_dq21 | DQ2_B | V2 |
| 2 (ch B byte 0) | DDR_DQ[22] | V16 | ddr_dq22 | DQ4_B | U4 |
| 2 (ch B byte 0) | DDR_DQ[23] | W16 | ddr_dq23 | DQ5_B | V4 |
| 2 (ch B byte 0) | DDR_DM[2] | W18 | ddr_dm2 | DMI0_B | Y3 |
| 2 (ch B byte 0) | DDR_DQS[2] | Y18 | ddr_dqs2_P | DQS0_T_B | W3 |
| 2 (ch B byte 0) | DDR_DQS_N[2] | AA18 | ddr_dqs2_N | DQS0_C_B | V3 |
| 3 (ch B byte 1) | DDR_DQ[24] | AB19 | ddr_dq24 | DQ13_B | V9 |
| 3 (ch B byte 1) | DDR_DQ[25] | AB21 | ddr_dq25 | DQ15_B | AA9 |
| 3 (ch B byte 1) | DDR_DQ[26] | AA20 | ddr_dq26 | DQ14_B | Y9 |
| 3 (ch B byte 1) | DDR_DQ[27] | AA19 | ddr_dq27 | DQ12_B | U9 |
| 3 (ch B byte 1) | DDR_DQ[28] | W22 | ddr_dq28 | DQ8_B | AA11 |
| 3 (ch B byte 1) | DDR_DQ[29] | W21 | ddr_dq29 | DQ9_B | Y11 |
| 3 (ch B byte 1) | DDR_DQ[30] | W19 | ddr_dq30 | DQ11_B | U11 |
| 3 (ch B byte 1) | DDR_DQ[31] | W20 | ddr_dq31 | DQ10_B | V11 |
| 3 (ch B byte 1) | DDR_DM[3] | Y20 | ddr_dm3 | DMI1_B | Y10 |
| 3 (ch B byte 1) | DDR_DQS[3] | AA21 | ddr_dqs3_P | DQS1_T_B | W10 |
| 3 (ch B byte 1) | DDR_DQS_N[3] | AA22 | ddr_dqs3_N | DQS1_C_B | V10 |

CA, CK, CKE0, CS_N[0]/[2] and RESET_N are unchanged (§6.1 of the notes). The Interface Designer strings are:

```
PIN_SWIZZLE_EN   = 1
PIN_SWIZZLE_DQM0 = DQ[6],DQ[7],DQ[0],DQ[4],DQ[5],DQ[1],DQ[3],DQ[2],DM[0]
PIN_SWIZZLE_DQM1 = DQ[8],DQ[9],DQ[14],DQ[15],DQ[10],DQ[11],DQ[13],DQ[12],DM[1]
PIN_SWIZZLE_DQM2 = DQ[22],DQ[19],DQ[23],DQ[16],DQ[17],DQ[18],DQ[20],DQ[21],DM[2]
PIN_SWIZZLE_DQM3 = DQ[29],DQ[31],DQ[30],DQ[28],DQ[24],DQ[25],DQ[27],DQ[26],DM[3]
PIN_SWIZZLE_CA   = CA[0],CA[1],CA[2],CA[3],CA[4],CA[5]
```

## 3. Geometry and layer assignment

### 3.1 Where things are

**U501, DDR balls along its north edge** (rows AB…U, y 72.6–76.6), west → east:
- byte 3, x 155.6–158.0;
- byte 2, x 158.8–160.4;
- CA / CK / CKE / CS / RST, x 161.2–166.8;
- byte 1, x 167.6–170.8;
- byte 0, x 170.8–172.4 (the NE corner).

**U801, 10 mm north** (ball rows 2–4 at y 54.5–56.1 and 9–11 at y 60.1–61.7):
- Channel B is on the west side (x 167.1–169.7) and channel A on the east side (x 176.9–179.5).
- In each channel, DRAM byte 0 is the **far** byte (north rows 2–4) and byte 1 the **near** byte (rows 9–11).
- The CA balls sit in the middle columns (P/R for channel B, H/J for channel A) at both ends of the package.
- A ball-free column, 1.95 mm wide (x 172.3–174.3), runs through the package centre. The ball-free gap between
  rows 5 and 8 (y 56.9–59.3) crosses it.

### 3.2 Byte-lane topology (which bundles cross)

- A far byte can't be reached through its near byte's ball field.
  - Channel A byte 0 wraps U801's **east** side and enters from the east.
  - Channel B byte 0 wraps the **west** side.
  - The near bytes enter from the south. CA goes up the centre column.
- Order seen from U501, west → east:
  - at U801: B0 (west side), B1 (south), CA (centre), A1 (south), A0 (east side);
  - at U501: byte 3, byte 2, CA, byte 1, byte 0.
- The only forced crossing is **byte 2 ↔ byte 3**:
  - FPGA byte 2 must reach the far channel B byte, round the outside.
  - FPGA byte 3 is further outside on the FPGA.
  - A channel B byte swap would remove the crossing, but Efinity can't express it (§1).
- Every other pair of bundles is planar, so byte 2 and byte 3 just go on different layers.

### 3.3 CA

Every CA net splits at U801 to a channel B ball and the mirrored channel A ball, so each one has to reach both sides of
the centre column. Permuting DDR_A only changes which FPGA ball feeds the north group (CA0/CA1, CS, CKE in rows 2–4)
and which feeds the south group (CA2–5, CK, RST in rows 8–11). It doesn't remove the per-net T branch, and all CA
are matched to CK (±30 mil) anyway. No gain, so no CA swizzle (as on the Efinix kit).

### 3.4 Layers

LPDDR4 may use **In2** (In1 GND reference, 0.1 mm) and **In5** (In6 GND reference, 0.1 mm), plus F.Cu / B.Cu for short
escapes. In3 and In6 are planes (TI135_PCB_NOTES.md §6.5).

| Layer | Groups | Why |
|---|---|---|
| **In2.Cu** | byte 3 (→ ch B near), byte 1 (→ ch A near), byte 0 (→ ch A far, round U801's east side) | Mutually non-crossing (§3.2). Byte 3 is far west and bytes 1/0 far east, so they barely meet |
| **In5.Cu** | byte 2 (→ ch B far, round U801's west side), CA/CK/CKE/CS/RST (up the U801 centre column, branching to P/R and H/J) | Byte 2 crosses byte 3 only, which is on In2. CA crosses no byte. CK/CA/CKE/CS on one layer as the PCB UG requires |
| F.Cu | none planned | Rows AB/AA of U501 could escape on top, but every U801 DQ ball needs a dog-bone via anyway, so staying on one inner layer costs no extra via |
| B.Cu | none | Decoupling capacitors under both BGAs |

- Each net gets one dog-bone via at U501 and one at U801, and no other layer change.
- Each DQS pair goes on its byte's layer with the same via count, so DQ–DQS skew sees the same layer and via
  delay.

Byte 0 (A0) and byte 2 (B0) are the long lanes, at about 23.5 / 21 mm per net (estimated) against about 16–17 mm for the near bytes. Check
DQS < CK (§6.3) once CK's length is known.

## 4. Metrics (before = identity wiring, after = this mapping)

Measured with `tools/lpddr4_swizzle_score.py` on the real pad positions:
- **cross**: straight-line crossings among the 11 lines of a byte (8 DQ, DM, DQS_P/N), the Agilex card's method.
  3 of them per byte (bytes 0, 2, 3) are DQS/DM-only crossings that no swizzle can remove.
- **inv**: river-route order inversions, comparing:
  - the FPGA escape order (north, west → east);
  - the DRAM entry order (near bytes from the south, far bytes from the outer side).
- **len**: estimated length (straight, or via the U801 corner for far bytes) and the DQ/DM length minus the DQS length.

| Byte → DRAM | cross before → after | inv before → after | DQ/DM − DQS before | after |
|---|---|---|---|---|
| 0 → A0 (far) | 35 → **14** | 19 → **4** | −2.66…+2.49 mm | −1.06…+1.40 mm |
| 1 → A1 (near) | 19 → **3** | 21 → **7** | −0.25…+2.56 mm | −1.77…+2.64 mm |
| 2 → B0 (far) | 35 → **14** | 18 → **10** | −0.94…+1.44 mm | −2.23…+2.23 mm |
| 3 → B1 (near) | 36 → **14** | 27 → **7** | −3.65…+2.67 mm | −1.39…−0.03 mm |
| **Total** | **125 → 45** | **85 → 28** | | |

- Total estimated length is unchanged: 211 / 144 / 191 / 156 mm per byte (sum of its 9 DQ/DM nets).
- All intra-byte spreads are under 5 mm, well inside the 375 mil (9.5 mm) DQ/DM–DQS window.
- Every chosen order is the brute-force optimum of cross + inv over all 8! orders, with DM/DQS fixed.
- Allowing DM↔DQ as well would lower cross + inv by only 4 / 3 / 5 / 1 points for bytes 0–3.
- Byte-lane crossings in plan view: 1 forced (byte 2 × byte 3, solved by putting them on different layers). All
  others are 0.

The metrics are proxies. The final within-byte order should follow the real dog-bone escape. Any new order inside a
byte is legal: edit `lpddr4_swizzle.json`, then run `pinplan.py`, `tools/build_schematic.sh` and update the PCB from
the schematic.

## 5. What must be set in Efinity / software

- **Interface Designer**: in the real FPGA design, set *Enable Package Pin Swapping* = on and the five strings of §2
  (Python API: `PIN_SWIZZLE_EN`, `PIN_SWIZZLE_DQM0..3`, `PIN_SWIZZLE_CA`). Copy them from
  `efinity/pinplan/build/ti135_pinplan.peri.xml` (`<efxpt:pin_swap>`), or set them with the same code as `pinplan.py`.
  - Without them, the controller's CA training, MRR (DRAM ID/density readout) and write/read training see scrambled
    bits.
  - Plain data would still work (a fixed bit permutation within a byte is transparent), but training would fail.
- **Training / DBI**: the DDR controller and PHY apply the swizzle themselves, as on the Ti375C529 kit. No U-Boot,
  OpenSBI or Linux change is needed. DBI works per byte, so a within-byte swap doesn't affect it.
- **Pin reports**: after the swizzle, Efinity's `*.pinout.csv` / `.rpt` name the balls by their DRAM-side signal.
  Use `reference/ti135n484_pinout.csv` (physical pads) for the PCB.

## 6. Verification (2026-10-25)

- `pinplan.py`: design check **passed** (only the existing info note about core-generated DDR clocks). The swizzle read
  back matches, and `outflow/ti135_pinplan.pt.rpt` "Pin Swizzling" shows the strings of §2.
- `tools/build_schematic.sh`: ERC still shows only the 2 known notes (U401 ~MR `pin_not_driven`, U1301 X0 `pin_to_pin`).
- `tools/build_pcb.sh --rebuild`: schematic parity 0, 499 unconnected (unrouted, as before), no courtyard, clearance
  or short errors. All 293 footprints are on their previous pose and layer.
- Netlist check (pcbnew): all 56 `ddr_*` nets connect exactly the intended U501 ball to the intended U801 ball(s),
  and nothing else. 0 mismatches.
