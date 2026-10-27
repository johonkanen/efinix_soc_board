# Efinix hardware checklist vs this card (2026-10-27)

Source: *Hardware Design Checklist and Guidelines*, generated for **Ti135 N484, SPI Active Parallel (x4)**
(`reference/efinix/ti135n484_hw_checklist.htm`, not in git). Checked against the schematic and board on main
(`kicad/`, after the 0201 decap change). ✓ meets it, ✗ does not, ~ partly or to verify.

## To act on

**2026-10-27 (phase 3, done):** items 1–4 are done in the schematic and on the board (R801 0.1 %, R622 SSU_N
pull-up, C5001–C5073, a 47u + 22p feed-forward per regulator; placement in NEXT_SESSION.md phase 3). The new caps
are placed but not yet tied to their rails by copper, except the 14 0201s sitting on via pairs: phase 5 routes them.

| # | Item | Checklist | This card | |
|---|---|---|---|---|
| 1 | DDR_CAL (Y9) | 240 Ω **±0.1 %** to GND, close to the pin | R801 240 Ω **0.1 %** (RT0402BRD07240RL, C852660) | ✓ (phase 3) |
| 2 | SSU_N (L4) | weak pull-up | R622 10 k to 1V8 (B.Cu, 4.6 mm from L4) | ✓ (phase 3; x8 chip select, unused in x4 mode) |
| 3 | Decoupling per rail | table below | the table in full: C5001–C5073 added ("Missing" column below) | ✓ (phase 3; copper in phase 5) |
| 4 | Energy storage | ≥ 1 × 47 µF at each regulator output | 47 µF per cell (C204, C304 from the table; C314, C333, C344 new) + a 22 pF feed-forward across R1 (C205/C305/C315/C334/C345: TLV62585 data sheet, > 47 µF output) | ✓ (phase 3; check loop stability at bring-up) |
| 5 | DDR byte group on one layer; CK/A/CKE/CS on one layer | required | main: bytes spread over 3–4 layers, CA over In5/In2/F. `ddr-option2`: bytes 75–81 % on one layer | ✗ (main) / ~ (option 2) |
| 6 | DDR skew (3700 Mbps) | DQ–DQS ≤ 75 ps, CK–DQS ≤ 350 ps, A/CKE/CS–CK ≤ 100 ps | main: DQ–DQS −83…+102 ✗, CK–DQS ≤ 91 ✓, CA–CK −64.5…+47 ✓. `ddr-option2`: DQ–DQS −24…+60 ✓ | ✗ (main) / ✓ (option 2) |

Item 6 matters for the phase 3 decision: the checklist generated for this exact part states the requirement as these
skew limits (the 0…66 ps window comes from the DDR user guide's length rule). By the checklist, `ddr-option2` already
meets DQ–DQS and CA–CK. DQS P/N skew is not in this table (the user guide asks ≤ 10 mil, about 1.8 ps).

## Decoupling (checklist per supply vs this card)

The card shares rails between pin groups, so the checklist rows are summed per rail. Caps counted are those on the
rail next to the FPGA (sheet 05) unless noted.

| Rail | Checklist (sum of its pin groups) | This card (05_fpga_power) | Missing |
|---|---|---|---|
| VCORE = VCC + VDD_SOC | 2×100 µ, 2×47 µ, 2×10 µ, 4.7 µ, 3×1 µ, 7×100 n, 7×10 n, 3×1 n | 2×22 µ (+2×22 µ at the regulator), 4×4.7 µ, 12×100 n | 100 µ/47 µ bulk, 10 µ, 1 µ, all 10 n and 1 n |
| VCCA ×3 (filtered from VCORE) | each 2×100 n, 2×10 n, 1 n | each 1 µ + 100 n | per VCCA: 100 n, 2×10 n, 1 n |
| 1V8 = VCCAUX + VCCIO (5 HSIO banks 2A/2B/2C/4A/4B) | VCCAUX 4.7 µ, 100 n, 10 n, 1 n; VCCIO per bank 47 µ, 10 µ, 4.7 µ, 1 µ, 100 n, 10 n, 1 n (× 5) | 10 µ, 2×4.7 µ, 8×100 n | 5×47 µ, 4×10 µ, 4×4.7 µ, 5×1 µ, all 10 n and 1 n |
| 3V3 = VCCIO33 (3 HVIO banks) | per bank 4.7 µ, 1 µ, 100 n (× 3) | 4.7 µ, 3×100 n | 2×4.7 µ, 3×1 µ |
| 0V85 = VDD_PHY | 1 µ, 100 n, 10 n | 10 µ, 4×1 µ, 6×100 n | 10 n |
| VDDPLL_MCB_TOP_PHY (filtered 0V85) | 100 n, 10 n, 1 n | 1 µ + 100 n | 10 n, 1 n |
| 1V1 = VDDQ_PHY + VDDQX + VDDQ_CK | 10 µ, 3×4.7 µ, 4×1 µ, 4×100 n, 3×10 n | 10 µ, 4×1 µ, 8×100 n | 3×4.7 µ, 3×10 n |
| VQPS | 2×1 µ, 100 n, 10 n, 1 n | tied to GND (fuses never blown) | n/a: a grounded VQPS needs no decoupling |
| MIPI, transceivers | — | unused: MIPI supplies on VCC, transceiver supplies unconnected | n/a (no decoupling for unused blocks) |

The 10 nF and 1 nF values are the main gap: the card has none. They are small (0201/0402) and can share the via-pair
scheme under U501 (`tools/place_bga_decaps.py`), which still has VCORE pairs free (about 100).

## Met

| Item | Checklist | This card |
|---|---|---|
| VCC / VDD_SOC | 0.95 V ± 30 mV (standard part) | VCORE 0.95 V |
| VCCA | 0.95 V, separate filter | 3 × ferrite bead + 1 µ + 100 n (vcca_br/tr/bl) |
| VCC18A_MIPI (E20, H19) | unused MIPI: to VCC | on VCORE |
| VCCAUX | 1.8 V | 1V8 |
| VCCIO (HSIO) | 1.2–1.8 V, no mixed voltages | all 5 banks 1V8 |
| VCCIO33 (G7, J7, M21) | 1.8–3.3 V | 3V3 |
| VDD_PHY, VDDPLL_MCB_TOP_PHY | 0.85 V | 0V85; VDDPLL through a ferrite bead |
| VDDQ_PHY, VDDQX_PHY, VDDQ_CK_PHY | 1.1 V (LPDDR4) | 1V1 |
| VQPS (F9) | stays low unless blowing fuses | GND |
| Power-up groups | group 1 (VCC, VCCA, VDD_SOC, VCCAUX, VCCIO, VCCIO33), then group 2 (DDR PHY) ≥ 10 µs later | enable chain VCORE → 1V8 → 3V3, then 0V85 / 1V1 (TI135_PCB_NOTES.md §5) |
| CRESET_N (G10) | held low by a supervisor until supplies are up; ≥ 320 ns pulse | TPS3808 (U401) on VCORE, manual reset from `pg_all`, 10 k pull-up to 1V8 |
| CDONE (H10) | external pull-up, not held low | 10 k to 1V8 |
| TEST_N (L7) | 10 k pull-up | 10 k to 1V8 |
| TCK / TDI / TDO / TMS | 10 k pull-ups | 10 k to 3V3 (JTAG at 3.3 V) |
| JTAG_VCCIO_SEL (H11) | 3.3 V JTAG: VCCIO33_BR1 at 3.3 V, pin floating | floating, BR1 on 3V3 |
| CSI (A2) | per mode | 10 k pull-up to 1V8 |
| CCK, CDI0–3, SSL_N | SPI x4 to the flash | IS25WP128 (128 Mbit ≥ 38.8 Mbit bitstream, 1.8 V like its bank), SSL_N 10 k pull-up, IO2/IO3 10 k pull-ups |
| CDI4–15 (x8/x16 only) | — | user I/O (eMMC DAT, RGMII RX): x4 configuration does not read them, so what drives them during configuration does not matter |
| CBSEL1:0 (H1, J1) | no pull resistors needed for single image | DNP pull-down footprints |
| EXT_CONFIG_CLK (K4) | only for an external configuration clock | internal oscillator; K4 is eMMC CLK after configuration |
| NSTATUS (L6) | optional LED | unconnected (optional) |
| REF_RES (G5, L16, M7, P16) | 10 k ±1 % to GND | R601–R604 10 k 1 % |
| DDR PLL reference | from I/O pads (PLL BL0/BL1/BL2 PLLIN0), not the clock tree | 25 MHz refclk_bl0/1/2 on N7 / R3 / L2 through 33 Ω |
| Package net length in matching | required | U501 pad-to-die delays on the board (`tools/pad_to_die.py`) |
| HVIO 3.3 V outputs | ≤ 6 per bank | BR0 6, BL3 6, TR1 inputs only |
| HSIO GPIO / LVDS / MIPI separation | 1 unassigned pair between GPIO and LVDS/MIPI | no LVDS/MIPI used |
| Unused HSIO/HVIO pins | float | float |

## Not covered by this checklist

- Unused transceivers (Q0/Q1): the checklist lists their pins and decoupling but has no "unused" rule. The card
  leaves the supplies, CAL_RES and REFCLK balls unconnected (TI135_PCB_NOTES.md §9); confirm with AN 063.
- Return vias within ±250 mil of DDR layer changes (DDR user guide): phase 4, still open.
