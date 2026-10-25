# Ti135N484I3 PCB design notes

Device-specific rules for the schematic and the layout of the Ti135 control card. Board-level decisions (which
signal goes where, part choices) are in `MIGRATION_PLAN.md`. This file covers what the Ti135 itself requires.

Written 2026-10-24. Sources are listed at the end. Most Ti135 data sheet pages are still marked *preliminary*, so
re-check the items marked **[verify]** against the current data sheet and the *Titanium Hardware Design Checklist*
(Efinix Support Center) before ordering.

Ball and pad names below are from `reference/ti135n484_pinout.csv`, which was extracted from the Efinity 2026.1 device
database. It already includes advisory ADV-2604-001: ball K8 (formerly GPIOR_125) is now **GND**.

---

## 1. Package overview

FBGA-484, 18 × 18 mm, 0.8 mm pitch, full 22 × 22 array (rows A–AB without I, O, Q, S, X, Z; columns 1–22).
Dog-bone fan-out with standard vias works at 0.8 mm; no via-in-pad is needed.

Ball map by function (top view, `.` GND, `+` supply, `d` DDR, `q` transceiver, `m` MIPI, `*` config/JTAG/REF_RES,
HSIO banks `A` 4A, `B` 4B, `a` 2A, `b` 2B, `c` 2C, HVIO banks `3` BR1_BL3, `0` BR0, `1` TR1):

```
    1234567890123456789012
  A .AA.q.q.q.q.q.q.q.q.m.
  B AA..q.q.q.q.q.q.q.q.mm
  C AA.q.q.q.q.q.q.q.q..mm
  D .A.q+q+q+q+q+q+q+q+.m.
  E AA........q.q.q.q..+mm
  F AAA33***++q+q+q+q+.mmm
  G .AAA*3++**+.q.+.q..m.m
  H AAB+03333**+.+.+..+mmm
  J A.BAA0+++.+.+.++c+cmm.
  K BBBA+00..+.+.+.cccc.mm
  L BB+ABAA0+.+.+.+*b+cc11
  M .BBBB+*0.+.+.+.+bbb1+1
  N BBB+BBB++.+.+.+aab+111
  P B+BBBB.+.+.+.+.*+abbb.
  R +BBB.B+++.+.+.+aabb.bb
  T .+.++B.+.+.+.+.aa.bbbb
  U dddd++++++++++++.++b.b
  V +.d.d.+.+.+.+.+ddd.++.
  W ddddd+++++++dd+d+ddddd
  Y .d+d.+.+d+ +.d.d.d.d.+
 AA dddddddddd ddddddddddd
 AB .d+.d.d.d.d.d.d.d.d.d.
```

The layout consequences:

- **LPDDR4 balls fill rows U–AB.** Place the LPDDR4 on that edge (south in this view).
- **HSIO 4A/4B are on the west edge (columns 1–7), 2A/2B/2C on the east edge (columns 15–22).** The SPI flash
  goes next to the north-west corner (bank 4A, config pins), Ethernet/eMMC/translators along the west and east edges.
- **The north edge (rows A–G) is transceivers and MIPI only.** They are unused, so that edge is free for decoupling
  and for routing power, not for signals.
- The HVIO balls sit in the interior (F–M, columns 4–8, and L–N, columns 19–22). They need via fan-out toward the inside.

---

## 2. Supplies

| Rail on the card | Ti135 balls | Voltage | Notes |
|---|---|---|---|
| `VCORE` 0V95 | VCC (31), VDD_SOC (3), VCCA_BL / VCCA_BR / VCCA_TR (1 each), VCC18A_MIPI1_TX / _RX (1 each) | **0.95 V** (0.92–0.98, I3 grade) | VCCA (PLL analog) through a ferrite bead + local caps. VDD_SOC is required because the hard RISC-V is used. The MIPI analog supplies of an **unused** MIPI block go **to VCC** (Unused Resources table). The Ti135 has **no core-sense balls**: take the regulator sense from a VCC via under the BGA. |
| `0V85` | VDD_PHY_DDR (15), VDDPLL_MCB_TOP_PHY_DDR (1, through a ferrite) | **0.85 V** **[verify]** | DDR PHY core and PLL. |
| `1V1` | VDDQ_PHY_DDR (15), VDDQX_PHY_DDR (8), VDDQ_CK_PHY_DDR (1) | **1.1 V** (LPDDR4; 0.6 V would be LPDDR4x) | Same rail as LPDDR4 VDD2/VDDQ. |
| `1V8` | VCCAUX (4), VCCIO2A (1), VCCIO2B (2), VCCIO2C (1), VCCIO4A (3), VCCIO4B (4) | 1.8 V | VCCAUX must be 1.8 V. All HSIO banks at 1.8 V (§3). |
| `3V3` | VCCIO33_BR1_BL3 (1), VCCIO33_BR0 (1), VCCIO33_TR1 (1) | 3.3 V | HVIO. BR1_BL3 also powers JTAG (§4.3). |
| GND | VQPS (1) | 0 V | Security-fuse supply. Keep at 0 V always (fuses are not planned). |
| unconnected | VCC_SERDES01 (2), VDDA_C_Q01 (4), VDDA_D_Q01 (8), VDDA_H_Q01 (1) | – | Transceivers unused: leave these supplies unconnected (Unused Resources table). |

Decoupling: follow the *Titanium Hardware Design Checklist and Guidelines* (Support Center) per rail. Use the Efinity
Power Estimator currents to size the regulators and the bulk capacitance (`MIGRATION_PLAN.md` §5, phase 0).

---

## 3. I/O banks

| Bank | Type | Supply ball(s) | VCCIO here | User pins | REF_RES | Use on this card |
|---|---|---|---|---|---|---|
| 4A | HSIO | VCCIO4A ×3 (H4, K5, M6) | 1.8 V | 24 | G5 | Config flash (dual-purpose config pins, §4.2), translator A side, spare |
| 4B | HSIO | VCCIO4B ×4 (L3, N4, P2, T4) | 1.8 V | 28 | M7 | RGMII to the RTL8211FDI (KSZ9031 until 2026-10-25), MDIO, 25 MHz reference clock |
| 2A | HSIO | VCCIO2A (P17) | 1.8 V | 7 | P16 | eMMC / translators |
| 2B | HSIO | VCCIO2B ×2 (L18, N19) | 1.8 V | 18 | (none on this package) | eMMC / translators |
| 2C | HSIO | VCCIO2C (J18) | 1.8 V | 8 | L16 | eMMC / translators |
| BR1_BL3 | HVIO | VCCIO33_BR1_BL3 (G7) | 3.3 V | 7 + JTAG | – | JTAG, 3.3 V header inputs / LCD outputs |
| BR0 | HVIO | VCCIO33_BR0 (J7) | 3.3 V | 6 | – | 3.3 V header inputs / LCD outputs (GPIOR_131 is PCIE_PERSTN-capable, usable as GPIO) |
| TR1 | HVIO | VCCIO33_TR1 (M21) | 3.3 V | 7 | – | 3.3 V header inputs / LCD outputs, FPGA UART |

Rules:

- **HSIO accepts at most 1.8 V** (1.2/1.35/1.5/1.8 V VCCIO). A 3.3 V signal must never reach an HSIO pin, not even
  as an input, so 3.3 V signals either go on HVIO or through a translator (`MIGRATION_PLAN.md` §3.2).
- **HVIO:** 1.8/2.5/3.0/3.3 V. Only 20 pins on this package.
- **REF_RES_xx:** each to GND through **10 kΩ ±1 %** (Ti135 *Pinout Description*). These are not optional, even for
  banks that are used only as GPIO.
- Every bank supply must be powered even if the bank is unused (Unused Resources: HSIO VCCIO 1.2–1.8 V, HVIO VCCIO33
  1.8–3.3 V).
- **Pin state while unconfigured:** every HSIO and HVIO user pin is *input, tri-state, weak pull-up* during reset
  (CRESET_N low) and during configuration, and stays that way in user mode if unused (Ti135 *Pin States*). Anything
  that must be low before user mode needs an external pull-down strong enough to override the weak pull-up, or a
  gated buffer. This is why the J3 translators have their OE pulled up and the J3 pins have 10 k pull-downs.
- Clock inputs: only pins with GCLK / PLL_CLKIN alternate functions can drive the clock network / PLLs directly
  (list in §7). Put the 25 MHz reference and the RGMII RX_CLK on such pins.

---

## 4. Configuration and JTAG

Configuration mode: **SPI active ×4** from one 1.8 V QSPI flash (ISSI IS25WP128-RHLE). Single image.
All values below are **10 kΩ** unless noted; AN 033 recommends 10 kΩ for every unspecified configuration
pull-up/pull-down. "VCCIO" means the supply of the bank the pin is in.

### 4.1 Dedicated pins

| Pin | Ball | Connection |
|---|---|---|
| CRESET_N | G10 | **Pull-up** + reset supervisor (open drain) that holds it low until all supplies are up, then releases it ≥ 10 µs later and ≥ 4.5 ms after the supplies reached 90 % (§5). A push-button to GND is optional. This pin only resets/reconfigures the FPGA; it is not a system reset. |
| CDONE | H10 | Open-drain output: **pull-up**. Optional LED/buffer. High = user mode. |
| TCK | F8 | **Pull-up** (data sheet table; note TCK and TDO are *not* internally pulled during configuration). JTAG header. |
| TMS | F7 | Pull-up. JTAG header. |
| TDI | G9 | Pull-up. JTAG header. |
| TDO | F6 | Pull-up. JTAG header. |
| JTAG_VCCIO_SEL | H11 | **Leave floating** (or pull up): JTAG at 3.3 V because VCCIO33_BR1_BL3 = 3.3 V. (1 kΩ to GND would select 1.8 V JTAG.) |

**[verify]** which supply CDONE and CRESET_N are referenced to. They sit next to the JTAG balls in the BR1_BL3
area. The pull-ups go to that bank's VCCIO (3.3 V here) only if the pinout file / checklist confirms it; otherwise
pull them to 1.8 V. AN 033 only says "pull-up to VCCIO".

### 4.2 Dual-purpose configuration pins (bank 4A, usable as GPIO after configuration)

| Function | Pad | Ball | Connection for SPI active ×4 |
|---|---|---|---|
| SSL_N | GPIOB_N_25_SSL_N | C1 | **Pull-up** (selects *active* mode at CRESET_N rising edge) → flash CS# |
| CCK | GPIOB_P_26_CCK | G4 | → flash CLK. Optional pull-up. Keep short; series resistor footprint (0 Ω/22 Ω) recommended |
| CDI0 | GPIOB_N_27_CDI0_CLK10_N | J4 | → flash IO0 (SI) |
| CDI1 | GPIOB_P_27_CDI1_CLK10_P | J5 | → flash IO1 (SO) |
| CDI2 | GPIOB_N_26_CDI2 | G3 | → flash IO2 (WP#), **pull-up** (AN 033 Figure 4) |
| CDI3 | GPIOB_P_25_CDI3_PLLIN0 | C2 | → flash IO3 (HOLD#), **pull-up** (AN 033 Figure 4) |
| CSI | GPIOB_N_28_CSI_CLK11_N | A2 | **Pull-up** (must stay high during configuration) |
| TEST_N | GPIOB_N_17_TEST_N_CLK4_N | L7 | **Pull-up** (test mode off) |
| CBSEL0 / CBSEL1 | GPIOB_N_19_CBSEL0 / GPIOB_P_19_CBSEL1 | J1 / H1 | Not used for a single image. Leave as GPIO. Fit 10 k pull-down footprints (DNP) if multi-image boot might be wanted later |
| NSTATUS | GPIOB_P_17_NSTATUS_CLK4_P | L6 | Output, low = configuration error. Optional LED, otherwise GPIO |
| CSO | GPIOB_P_28_CSO_CLK11_P | A3 | Daisy-chain only. Free GPIO |
| SSU_N | GPIOB_N_20_SSU_N_CLK6_N | L4 | ×8 mode only. Free GPIO |
| CDI4–CDI31 | various (4A/4B/2C) | – | Not used in ×4. Free GPIO |

Flash side (IS25WP128-RHLE, 24-ball BGA): VCC = 1V8, 100 nF at the pins. **RESET# (ball A4) to 1V8 through 10 k.** It
has no configuration role on the Ti135; optionally also route it to a GPIO for a software reset. 128 Mbit uses
24-bit addressing (AN 033, *SPI Flash Address Width*). The flash must hold the uncompressed bitstream,
4,371,669 bytes (measured), plus the boot loader.

The FPGA sequence in active mode: SSL_N low, release-from-power-down command, wait ≥ 30 µs, fast read from address 0
(AN 033).

### 4.3 JTAG header

Efinix Download Cable II or an FT2232H/FT4232H cable (AN 033 *Supported Download Cables*). Header signals: TCK, TMS,
TDI, TDO, GND, VCCIO reference = VCCIO33_BR1_BL3 (3.3 V). No level shifter is needed. Programming the SPI flash goes
over JTAG through the Efinity Programmer's JTAG-bridge flow. Do not use SPI passive and JTAG configuration at the
same time.

---

## 5. Power sequencing

From the Ti135 data sheet (*Power-Up Sequence*, *Power-Down Sequence*):

**Power-up:**

1. **CRESET_N low** from the start, until every supply is up.
2. **Group 1, any order:** VCC, VCCA, VDD_SOC, VCCAUX, VCCIO (HSIO), VCCIO33 (HVIO). Respect the ramp-rate limits
   (data sheet *Power-Up Sequence*, Table 3) **[verify values]**.
3. **Group 2, any order, ≥ 10 µs after all of Group 1 reached 90 %:** DDR PHY rails (VDD_PHY, VDDPLL_MCB_TOP_PHY,
   VDDQ_PHY, VDDQX_PHY, VDDQ_CK_PHY). Transceiver supplies: any order (unused here). **[verify]** which column of the
   data sheet's Table 1 the DDR rails belong to; the extracted table was ambiguous. Starting them last is safe either way.
   MIPI analog supplies are tied to VCC (unused), so they follow Group 1.
4. **LPDDR4 device:** VDD1 (1.8 V) must ramp before or together with VDD2/VDDQ (1.1 V) (JEDEC). With 1V8 in Group 1
   and 1V1 in Group 2 this holds by construction. The LPDDR4 supplies must be fully up before CRESET_N is released.
5. **Release CRESET_N ≥ 10 µs after the last supply reached 90 %.** Configuration must not start earlier than
   **4.5 ms** after the supplies reached 90 %. In SPI active mode it starts at the CRESET_N rising edge (+ t_DMIN),
   so delay CRESET_N ≥ 4.5 ms (use a supervisor with 10–20 ms delay).
6. VQPS stays at 0 V.

**Power-down:** no specific order for the FPGA. For the LPDDR4: CRESET_N goes low first (this resets the DDR
controller and tri-states CKE), then VDD2/VDDQ, then VDD1, all below 300 mV at the end, with **VDD1 and VDD2
falling slower than 0.5 V/µs**. In practice: pull CRESET_N low from the supervisor as soon as the input drops (PG
fails), and do not add active discharge that pulls 1V8 down before 1V1.

Card implementation (enable chain): `MIGRATION_PLAN.md` §4.3. VCORE → 1V8 → 3V3 form Group 1 (the 1V2 PHY rail was dropped with the KSZ9031). Then 1V1 and
0V85 (Group 2) are enabled from the 3V3 power-good. The wired-AND of all PGs drives the supervisor, which drives CRESET_N.

---

## 6. LPDDR4

Memory: SK hynix **H9HCNNN8KUMLHR-NME**, LPDDR4 (1.1 V), 8 Gb, 2 channels × 16, **single rank**. Interface Designer:
DDR_0, LPDDR4, DQ width 32, 1 physical rank, `MEMORY_DENSITY` = **4G** (the setting is per channel: 2 × 4 Gb = the 8 Gb device). This is set in `efinity/pinplan/pinplan.py`.

### 6.1 Connections (FPGA → DRAM)

The Ti135 has **one** CA bus, one CK and one RESET for a two-channel x32 device. They are shared by channel A and
channel B, in the same way as on Efinix's Ti375C529 dev kit (schematic v1.1, page 10):

| FPGA | DRAM (H9HCNNN8KUMLHR) | Notes |
|---|---|---|
| DDR_CK / DDR_CK_N | CK_t_A + CK_t_B / CK_c_A + CK_c_B | One pair, split at the DRAM to both channels' balls |
| DDR_A[5:0] | CA[5:0]_A **and** CA[5:0]_B | Shared bus, split at the DRAM |
| DDR_CKE[0] | CKE0_A + CKE0_B | |
| DDR_CKE[1] | – (rank 1 not fitted) | Leave unconnected |
| DDR_CS_N[0] | CS0_A | |
| DDR_CS_N[1] | – (CS1_A, rank 1) | Leave unconnected |
| DDR_CS_N[2] | CS0_B | |
| DDR_CS_N[3] | – (CS1_B, rank 1) | Leave unconnected |
| DDR_RST_N | RESET_n | |
| DDR_DQ[7:0], DDR_DM[0], DDR_DQS[0]/_N[0] | channel A byte 0: DQ[7:0]_A, DMI0_A, DQS0_A | DQ swizzled within the byte (below) |
| DDR_DQ[15:8], DDR_DM[1], DDR_DQS[1]/_N[1] | channel A byte 1: DQ[15:8]_A, DMI1_A, DQS1_A | DQ swizzled within the byte |
| DDR_DQ[23:16], DDR_DM[2], DDR_DQS[2]/_N[2] | channel B byte 0: DQ[7:0]_B, DMI0_B, DQS0_B | DQ swizzled within the byte |
| DDR_DQ[31:24], DDR_DM[3], DDR_DQS[3]/_N[3] | channel B byte 1: DQ[15:8]_B, DMI1_B, DQS1_B | DQ swizzled within the byte |

**DQ swizzle (2026-10-25, `LPDDR4_SWIZZLE.md`)**. Net `ddr_dq<n>` is FPGA ball DDR_DQ[n]. The DRAM bit it lands on
is listed below, and `efinity/pinplan/lpddr4_swizzle.json` holds the same map for both the sheet script and the Interface Designer project.
DM, DQS, CA, CK, CKE, CS and RESET are not swapped.

| FPGA DDR_DQ[k] (ball) | k = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| byte 0 → DQ_A | U3→**6** | U2→**7** | U1→**0** | V3→**4** | Y2→**5** | AA1→**1** | AB2→**3** | AA2→**2** |
| byte 1 → DQ_A | U4→**8** | V5→**9** | W5→**14** | W4→**15** | AA5→**10** | AB5→**11** | AA6→**13** | AB7→**12** |
| byte 2 → DQ_B | AA16→**6** | Y16→**3** | AA17→**7** | AB17→**0** | V18→**1** | V17→**2** | V16→**4** | W16→**5** |
| byte 3 → DQ_B | AB19→**13** | AB21→**15** | AA20→**14** | AA19→**12** | W22→**8** | W21→**9** | W19→**11** | W20→**10** |

(k = position within the byte: FPGA DDR_DQ[8·byte + k].)
| DDR_CAL (Y9) | – | **240 Ω 1 % to GND** |
| – | ZQ0 (A5) | **240 Ω 1 % to VDDQ (1V1)** (LPDDR4; the dev kit's LPDDR4x uses 0V6) |
| – | ODT_CA_A / ODT_CA_B | To VDD2 (1V1). The dev kit uses 240 Ω; the Agilex card ties them directly. Either enables CA ODT |
| – | VDD1 / VDD2 / VDDQ | 1V8 / 1V1 / 1V1 |

DDR_CKE[1] and DDR_CS_N[1]/[3] stay unconnected (single rank). The unconnected DQ/DQS/DM of an x16 design may float,
but they don't apply here (x32).

### 6.2 Swizzling (pin swapping) rules

Efinity has a *Pin Swizzling* tab on the DDR block: `PIN_SWIZZLE_EN`, `PIN_SWIZZLE_DQM0…3` (position k of group n =
FPGA ball DDR_DQ[8n+k], position 8 = DDR_DM[n]; the value is the DRAM-side signal wired there) and `PIN_SWIZZLE_CA`.
The swizzle must be entered there exactly as routed. Otherwise training, mode-register reads and DBI give wrong
data. `efinity/pinplan/pinplan.py` sets it from `lpddr4_swizzle.json` and reads it back. Details and sources are in `LPDDR4_SWIZZLE.md`.

**What Efinity enforces (2026.1, tested 2026-10-25).** Each group only accepts its own DQ[8n…8n+7] and DM[n]
(`DDRPinSwap.get_group_options`). `set_property` **rejects** a DQ from another byte, a whole-byte swap and duplicates
("Unable to translate PIN_SWIZZLE_DQM0"). It does not raise in the design check, and the old value silently stays,
so always read it back. A hand-edited peri.xml is caught by `ddr_rule_pin_swap`. A DM↔DQ swap inside a group is
accepted. (The 2026-10-24 note that cross-byte values were "accepted" was a silent no-op.)

| Swap | Allowed? |
|---|---|
| DQ bits **within the same byte**, DQ0 included (FPGA DQ[8n…8n+7] ↔ any DQ of the same DRAM byte) | **Yes.** Declare in PIN_SWIZZLE_DQMn. The Ti375C529 kit swaps every byte this way, DQ[0] included. **Used on this card** |
| DM ↔ DQ (same byte) | Tool accepts it, but **not used**. No Efinix board does it, DMI carries DM/DBI, and it would gain only 1–5 crossing points per byte here |
| DQ to another byte | **No.** Not expressible in Efinity (rejected) |
| Whole byte lanes (FPGA byte 0 ↔ DRAM byte 1, A ↔ B) | **No.** Not expressible in Efinity. Keep the byte mapping of §6.1 |
| DQS / DQS_N within a pair | **No** |
| CA[5:0] among themselves | Tool supports PIN_SWIZZLE_CA (one permutation; both channels share DDR_A). **Not used**: no Efinix board does it, and it does not change the CA topology (`LPDDR4_SWIZZLE.md`) |
| CK, CKE, CS, RESET | **No** (no setting exists) |

### 6.3 Routing (Efinix *Titanium DDR DRAM PCB Design User Guide* v1.2)

| Item | CK | CA (A) | CKE | CS | DM | DQ | DQS |
|---|---|---|---|---|---|---|---|
| Impedance (±10 %) | 80 Ω diff | 40 Ω | 40 Ω | 40 Ω | 40 Ω | 40 Ω | 80 Ω diff |
| Length match within group (max) | 5 mil | 62.5 mil | 62.5 mil | 62.5 mil | 375 mil | 375 mil | 10 mil |
| P/N match (max) | 5 mil | – | – | – | – | – | 10 mil |
| Relative | – | CK ± 30 mil | CK ± 30 mil | CK ± 30 mil | DQS + 0…375 mil | DQS + 0…375 mil | shorter than CK |
| Total length (max) | 2.5 in | 2.5 in | 2.5 in | 2.5 in | 2.5 in | 2.5 in | 2.5 in |
| Route order | 5 | 4 | 7 | 6 | 3 | 2 | 1 |

- Timing budget at 3700 Mbps: DQ–DQS ≤ 75 ps, CK–DQS ≤ 350 ps, CA/CKE/CS–CK ≤ 100 ps. P/N intra-pair skew < 1 ps (the
  controller cannot deskew differential pairs).
- **Include the FPGA package net length** (download *Package Net Length* for Ti135N484 from the Support Center).
- Width ≥ 5 mil. Spacing: 3H data↔CA, 5H CK↔anything. Byte group ↔ byte group ≥ 5× width. **Keep each byte group on
  one layer.** Route CK, A, CKE, CS on one layer.
- Stripline preferred. Continuous reference plane between FPGA and DRAM. Return vias within ±250 mil of layer
  changes. No routing over splits. Keep >100 mil from switching nodes.
- The shared CA/CK split to channels A and B is a short branch at the DRAM (same as the dev kit). Keep both branches
  equal and as short as possible.
- The stack-up and the LPDDR4 net classes of the Agilex card (JLC08161H-3313, `LPDDR4_DELAY_MATCHING.md` in
  `agilex3_soc_control_card`) carry over. Check its impedance classes against 40 Ω / 80 Ω.
- **Data rate:** Ti135 data sheet Table 22 (LPDDR4/4x Interface Performance) for **N484**: 3.3 Gbps (C4/I4), **2.8 Gbps
  (C3/I3, this card's Ti135N484I3)**, 2.5 Gbps (Q3). The LPDDR4 (H9HCNNN8KUMLHR) is rated 3733+. The board is routed to the
  Efinix table above (its 3700 Mbps budget is tighter than 2.8 Gbps needs), so it supports the I3 maximum; Linux
  bring-up can start lower (e.g. 2,133 Mbps) by changing only the PLL.
- **Impedance:** the table's 40 Ω SE / 80 Ω diff is used (not the Agilex card's 50 / 100 Ω): 0.18 mm and 0.14 / 0.15 mm on
  In2 / In5 (§6.5), set in `tools/board_setup.py`.

### 6.4 DDR clocking

The DDR block is clocked from a PLL whose reference must come **from an I/O pad** (not the clock tree). That PLL must
not use fractional mode, programmable duty cycle or spread spectrum, and outclk 3 = 2 × outclk 4 with 0° phase
(Efinity DDR design-check rules).

Results from the pin-plan project (`efinity/pinplan`, design check passed 2026-10-24):

| PLL | Feeds | Reference pin (25 MHz, 1.8 V) |
|---|---|---|
| PLL_BL0 | Hard RISC-V **system clock** ("Clock 0"), RGMII TX 125 MHz | GPIOB_P_00 = **N7** (bank 4B) |
| PLL_BL1 | Hard RISC-V **memory clock** ("Clock 1") | GPIOB_P_03 = **R3** (bank 4B) |
| PLL_BL2 | **DDR** (`CLKIN_SEL` = CLKIN 2) | GPIOB_P_06 = **L2** (bank 4B) |

- Only PLL_BL0/BL1/BL2 can clock the DDR block (CLKIN 0/1/2) and the hard SoC (Clock 0/1/2). The Efinity defaults
  are SoC → BL0 + BL1 and DDR → BL2.
- Each of these PLLs has exactly one 1.8 V reference pin, and all three are in bank 4B close together. The alternates
  for BL1/BL2 are GPIOL_32 / GPIOL_34, which are 3.3 V HVIO. → **Fan the 25 MHz oscillator (Y2, 1.8 V) out to N7,
  R3 and L2**, e.g. with a 1:4 LVCMOS clock buffer, or as a short star with one series resistor per branch.
- CLKOUT0 is the PLL's local feedback clock, which fixes the VCO. Pick the output frequencies with that in mind.

---

### 6.5 Stack-up, layer roles and impedance (field solve 2026-10-25)

JLC08161H-3313, 1.6 mm: F.Cu 35 µm | 3313 prepreg 0.0994 (εr 4.1) | In1 | core 0.1 (4.6) | In2 | 2116×3 prepreg
0.3568 (4.16) | In3 | core 0.3 (4.6) | In4 | prepreg 0.3568 | In5 | core 0.1 | In6 | prepreg 0.0994 | B.Cu 35 µm
(inner copper 15.2 µm, solder mask 0.03 mm εr 3.8).

**Layer roles** (set by `tools/board_setup.py`): F.Cu signal, **In1 GND**, In2 signal, **In3 plane**, **In4 plane**,
In5 signal, **In6 GND**, B.Cu signal. The thin 0.1 mm cores pair In2 with In1 and In5 with In6. That is the
arrangement JLC's impedance calculator assumes, and the only one where the widths below hold. Route LPDDR4 on In2 / In5
(plus F.Cu / B.Cu for escapes). In3 as a signal layer would be about 73 Ω SE / 123 Ω diff (no plane closer than
0.3 mm). In6 as a signal layer would take In5's reference away.

2D finite-difference solve (`tools/zsolve.py`, `tools/zsolve_cases.py`; rectangular cross-section; checked against
Cohn's exact stripline formula to 0.5 %. Real trapezoidal etching reads a few % higher; JLC tolerance ±10 %):

| Layer | Geometry | Z |
|---|---|---|
| F.Cu / B.Cu (with mask) | 0.15 mm SE | 51.0 Ω (JLC calculator: 50 Ω at 0.1509) |
| | 0.13 / 0.25 mm diff | 99.8 Ω |
| | 0.10 mm (BGA neck-down) | 60 Ω |
| In2 / In5 | 0.12 mm SE | 48.6 Ω (JLC: 50 Ω at 0.1207) |
| | 0.11 mm SE | 50.5 Ω |
| | 0.11 / 0.25 mm diff | 95.9 Ω (JLC: 100 Ω at 0.1082) |
| | 0.10 / 0.20 mm diff | 97.2 Ω |
| In2 if In3 is not a plane | 0.12 mm SE | 50.2 Ω (In1 dominates) |

**LPDDR4 uses the Efinix 40 Ω / 80 Ω targets (§6.3)**, solved the same way:

| Layer | 40 Ω SE | 80 Ω diff |
|---|---|---|
| In2 / In5 | 0.18 mm (0.17 → 41.0 Ω, 0.19 → 38.6 Ω) | 0.14 / 0.15 mm gap → 80.6 Ω |
| F.Cu / B.Cu (escapes only) | 0.25 mm → 39.3 Ω | 0.20 / 0.20 mm → 79.6 Ω |

The DRC rules (`lpddr_se_outer/inner`, `lpddr_diff_outer/inner`) use these LPDDR4 widths. The 50 Ω / 100 Ω table above
applies to the other controlled nets (RGMII, MDI pairs, eMMC/QSPI clocks).

### 6.6 Plane assignment (KiCadRoutingTools `recommend-plane-mappings`, 2026-10-25)

Supply balls under U501 (rotated 180°, DDR edge north): 1V1 in the north band (y 72.6…78.2), 0V85 inside it
(y 75.8…76.6), VCORE in the centre/south (y 77.4…86.2), 1V8 spread through both (y 76.6…83.8), and 3 × 3V3.
U801 is 1V1 (46 balls) + 1V8 (8). 0V85 and 1V8 interleave with 1V1/VCORE, so they go on the other plane layer.

**As built (2026-10-25, `tools/plane_regions.py` → `placement/planes.json` → `tools/apply_planes.py`).** The tool's
automatic split of a shared layer (route_planes Voronoi over each net's pads) cut the VCORE regulator off from the
BGA and ran 3V3 as thin strips across In3, so the regions are drawn by script instead:

| Layer | Net(s) | Region |
|---|---|---|
| In1.Cu, In6.Cu | GND | whole board |
| In3.Cu | 1V1 | U501 cells (each ball-grid cell goes to the nearest 1V1/VCORE ball) + north block (U801, DDR corridor) + east band to L341 |
| In3.Cu | VCORE | U501 cells + east corridor to L201 |
| In3.Cu | GND | the rest |
| In4.Cu | 0V85 | U501 cells (nearest 1V8/0V85 ball) + corridor to L331 |
| In4.Cu | 1V8 | the rest |
| B.Cu | 5V0 | J6 and the five regulator inputs (all on B.Cu, reached by fill) |
| F.Cu / B.Cu | GND flood | after routing |

3V3 is not a plane: it reaches about 45 pads across the whole board, so it is routed as a power net and poured on the
outer layers after routing. All 334 plane balls of U501/U801 lie inside their own net's fill.

Left to wide traces: the PHY's `phy_vdd10` / `phy_avdd33` / `phy_dvdd_rg` and the FPGA's ferrite-fed PLL rails
(`vcca_*`, `vddpll_*`), 2–10 pads each, all local.

Signal layers are F.Cu, In2.Cu, In5.Cu and B.Cu. **Do not use `--impedance 50` on F.Cu/B.Cu.** The router's IPC-2141 microstrip
model ignores the solder mask and asks for 0.188 mm, against 0.15 mm from JLC's calculator and the field solve
(§6.5). Its inner-layer result (0.119 mm, 100 Ω at 0.110/0.25) agrees with both. Pass the widths explicitly.

### 6.7 BGA fan-out: via-in-pad (2026-10-25)

Every connected ball of U501 has a 0.30/0.15 mm via at its pad centre (0.32 mm pads), and every connected ball of
U801 a 0.25/0.15 mm via (0.27 mm pads): `tools/via_in_pad.py`, 392 + 178 vias. JLC fills and caps via-in-pad free on
6+ layer boards (order option "epoxy filled & capped"). Plane balls reach their pour by fill. Signal balls escape on
their own layer between the via columns: one 0.1 mm track per 0.8 mm channel (`lpddr_bga_neckdown` rule). The
LPDDR4 bytes route directly from the via on In2 or In5, so each byte stays on one layer (§6.3), with no surface stub.
- Tried first: `bga_fanout.py --escape-method underpad`. It escaped the outer DDR rows on F.Cu and put the plane
  balls on dog-bone gap vias, against both the via-in-pad choice and the one-layer-per-byte rule.
- The decaps under both BGAs were then moved off foreign vias with `place_fanout_clearance.py --clearance 0.13
  --max-displacement-cap 5`: 69 caps moved, no vias nudged. Three caps were nudged 0.05 mm by hand for the 0.175 mm
  hole clearance.
- Test: byte 1 alone, In2 only, 0.1 mm: 9 of 11 nets routed in 1 s (DQ8/DQ9 next to the 0V85 row left open).

## 7. Clock-capable pins (from the Efinity device database)

| Bank | PLL_CLKIN | GCLK | Other |
|---|---|---|---|
| 4A | GPIOB_P_23 (E2), GPIOB_P_25 (C2, also CDI3) | P_17 (L6), P_18 (G2), P_20 (K4), P_21 (B2), P_27 (J5), P_28 (A3, RCLK) | EXTFB P_22, P_24; VREF P_23 |
| 4B | GPIOB_P_00 (N7), P_03 (R3), P_06 (L2, also CDI19) | P_13 (K1), P_14 (P5), P_15 (M4), P_16 (H3) | EXTFB P_04, P_07; VREF P_09 |
| 2A | – | GPIOT_P_00 (T16, RCLK), P_01 (T17), P_04 (R17) | |
| 2B | GPIOT_P_20 (M17) | P_22 (T19), P_23 (U22), P_24 (U20), P_25 (R21) | EXTFB P_19; VREF P_18 |
| 2C | GPIOT_P_34 (J17), P_37 (L19) | P_39 (K16) | |
| BR1_BL3 | GPIOL_32 (H9), GPIOL_34 (F5) | GPIOL_26 (F4), GPIOL_27 (H6) | |
| BR0 | GPIOR_129 (K6), GPIOR_130 (L8) | GPIOR_127 (M8, RCLK), GPIOR_128 (K7) | GPIOR_131 PCIE_PERSTN |
| TR1 | GPIOR_78 (M20) | GPIOR_80 (N21), GPIOR_81 (N22) | GPIOR_82 MIPI_CLKIN |

Which PLL (BL0–2, BR0–1, TR0–2) each PLL_CLKIN reaches, and which PLL can feed the DDR block and the hard SoC, is
resolved in Interface Designer.

---

## 8. Required resistors at a glance (boot-relevant)

| Net / pin | Resistor | To |
|---|---|---|
| CRESET_N (G10) | 10 k pull-up + supervisor | VCCIO **[verify]** |
| CDONE (H10) | 10 k pull-up | VCCIO **[verify]** |
| TCK, TMS, TDI, TDO | 10 k pull-up each | 3V3 (VCCIO33_BR1_BL3) |
| JTAG_VCCIO_SEL (H11) | none (floating) or pull-up | 3V3 |
| SSL_N (C1) | 10 k pull-up | 1V8 |
| CSI (A2) | 10 k pull-up | 1V8 |
| TEST_N (L7) | 10 k pull-up | 1V8 |
| CDI2 (G3), CDI3 (C2) = flash WP#/HOLD# | 10 k pull-up | 1V8 |
| CCK (G4) | optional pull-up; series-R footprint | 1V8 |
| CBSEL0/1 (J1/H1) | DNP pull-down footprints | GND |
| Flash RESET# (A4) | 10 k pull-up | 1V8 |
| REF_RES_2A (P16), REF_RES_2C (L16), REF_RES_4A (G5), REF_RES_4B (M7) | **10 k 1 %** | GND |
| DDR_CAL (Y9) | **240 Ω 1 %** | GND |
| LPDDR4 ZQ0 (A5) | **240 Ω 1 %** | 1V1 (VDDQ) |
| LPDDR4 ODT_CA_A/B | 0–240 Ω | 1V1 (VDD2) |
| VQPS (F9) | direct | GND |
| J3 translator OE (4 × SN74AXC8T245) | 10 k pull-up (outputs Hi-Z until the FPGA drives OE low) | 1V8 |
| J3 header signals (32) | 10 k pull-down (8 × 4D02WGJ0103TCE) | GND |
| eMMC (KIOXIA THGAMVG7T13BAIL) | CMD 4.7–100 k pull-up, DAT0–7 10–100 k pull-up, DS 10–100 k pull-down | 1V8 / GND |

---

## 9. Unused resources (Ti135 *Unused Resources and Features*)

| Resource | Connection |
|---|---|
| Transceivers Q0/Q1 | Supplies VCC_SERDES01, VDDA_C/D/H_Q01 unconnected. Q0/Q1 signal, REFCLK and CAL_RES balls unconnected **[verify in checklist]** |
| MIPI1 TX/RX | VCC18A_MIPI1_TX / _RX **to VCC**. Data/clock balls unconnected |
| Unused PLLs | VCCA stays connected to VCC (they share VCCA_BL/BR/TR) |
| Unused GPIO | Leave unconnected (weak pull-up by default; can be set to weak pull-down in Interface Designer) |
| Security fuses | VQPS to GND |
| NC balls (AA11, Y11) | Unconnected |

---

## 10. Open items **[verify]**

1. Reference supply of CDONE / CRESET_N (1.8 V or BR1_BL3 3.3 V).
2. Power-up group membership of the DDR PHY rails and the ramp-rate limits (data sheet Table 1 and Table 3).
3. VDD_PHY_DDR / VDDPLL_MCB voltage (0.85 V assumed).
4. Transceiver signal and CAL_RES balls when unused.
5. FPGA package net lengths for LPDDR4 length matching (Support Center download).
6. ~~Which PLL serves the DDR and the SoC~~: resolved in §6.4 (PLL_BL0/1/2, references N7/R3/L2).
7. Run everything through the *Titanium Interactive Hardware Design Checklist* (Support Center) before ordering.

## Sources

- Ti135 data sheet (HTML, `https://www.efinixinc.com/docs-html/dsti135/topics/`): *Pinout Description*
  (`ref_pinout_desc-ti.html`), *Configuration Pins* (`ref_pinout_desc-ti-config.html`), *DDR pins*
  (`ref_pinout_desc-ti-ddr.html`), *Pin States* (`titanium-io-pin-states.html`), *Power-Up Sequence*
  (`ref_ti_power_up-ti375.html`), *Power-Down Sequence* (`ref_ti_power_down.html`), *Unused Resources*
  (`ref_ti_unused-ti375.html`)
- AN 033 *Configuring Titanium FPGAs* v3.1 (Feb 2026): https://www.efinixinc.com/docs/an033-configuring-titanium-fpgas-v3.1.pdf
- *Titanium DDR DRAM PCB Design User Guide* v1.2: https://www.efinixinc.com/docs/pcb-guidelines-ddr-ti-ug-v1.2.pdf
- Ti375C529 dev board schematic v1.1 (LPDDR4 wiring, page 10): https://www.efinixinc.com/docs/ti375c529-dev-board-schematics-v1.1.pdf
- Efinity 2026.1: device database `pt/db/resource/Ti135N484.db`, Interface Designer API (`pt/bin/api_service`),
  DDR help pages `pt/doc/topics/titanium-ddr-id-1.html` and `dc-ti-ddr-1.html`
- Advisory ADV-2604-001: https://www.efinixinc.com/docs/ADV-2604-001-v1.0.pdf
