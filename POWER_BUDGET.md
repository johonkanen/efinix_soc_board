# Power budget and regulator choice

Written 2026-10-24. These are **estimates**. The Ti135 data sheet gives no operating currents; it refers to the
Efinix Power Estimator, a spreadsheet from the Support Center (login needed, not part of Efinity). Run it once the
FPGA design exists and replace the Ti135 rows below.

## Input limit: the baseboard 5V_ISOL rail

- The card takes **5V_ISOL** from baseboard J12 (our J6).
- On the baseboard (`~/dev/ac_psu_kicad`), 5V_ISOL comes from U8, fed from 20V_ISO_SEC. The same rail also feeds the
  three gate-driver connectors J4/J6/J8 (pin 45) and U10 (TPS73033, 3.3 V for the isolators).
- **2026-10-29 (from the ac_psu_kicad session): U8 becomes the Mornsun K7805-2000R3, 5 V / 2 A**, upright (the
  baseboard user decided there is room above it), with C93 10 µF / 50 V X7R 1210 at its input (no 22 µF / 50 V ceramic
  stocked at JLC) and C94 22 µF / 10 V 0805 at its output, both on the bottom side just south of U8's pins.
  Committed in `johonkanen/ac_psu_kicad` main 732c9b1. The card's budget is **2 A minus the gate-driver logic and U10**.
- **Open:** whether 20V_ISO_SEC can deliver the extra ~2.5 W has to be measured on a built baseboard.
- Before: U8 = RECOM VXO7805-1000 (1 A), which gave the card less than 5 W (target was ≤ 0.7 A at 5 V).
- The Ti60 card drew well below that (Ti60 + PEF7071 PHY + HyperRAM). The Agilex 5 card would not fit in it at all.
- If the budget is tight, upgrading U8 on the baseboard (it is being redrawn in KiCad anyway) is the cleanest fix.

## Ti135 reference numbers

| Source | Content |
|---|---|
| Ti135 data sheet, *Recommended Operating Conditions* | VCC/VCCA/VDD_SOC 0.95 V (I3) or 0.85 V ("L" grades); VDD_PHY/VDDPLL 0.85 V; VDDQ/VDDQX/VDDQ_CK 1.1 V (LPDDR4); VCCAUX 1.8 V |
| Data sheet, *Power Supply Ramp Rates* | every supply 0.1 × V_supply … 10 V/ms (VCC 0.95 V: ramp time 95 µs … 10 ms) |
| Data sheet, *Power Supply Current Transient* | **VCC must supply at least 1.5 A** of inrush at power-up (preliminary) |
| Efinix slides 2023 (preliminary, CERN Indico) | Ti135 at 100k LUT/200 MHz + PCIe Gen4 x4 + quad RISC-V 0.9 GHz + MIPI x4 + LPDDR4x x16 3 Gbps: **3.14 W typ, 4.0 W worst case**, 40 mW standby. The quad RISC-V at 1 GHz is about 400 mW; LPDDR4x x16 at 3 Gbps about 650 mW |

This card uses **no PCIe, no transceivers and no MIPI** (their supplies are unconnected or tied off), so it lands well below
the slide numbers. LPDDR4 at 1.1 V I/O and x32 costs more than the slide's LPDDR4x x16, but the planned data rate
is lower.

## Estimate per rail

Typ = expected in operation (RISC-V about 600–800 MHz, about 50k LUT at 100–150 MHz, LPDDR4 at about 1.6–2.1 Gbps,
GbE linked). High = margin case (warm junction, heavier DDR traffic).

| Rail | Loads | Typ (A) | High (A) | Power typ / high (W) |
|---|---|---|---|---|
| VCORE 0.95 V | VCC, VCCA, VDD_SOC (fabric, hard RISC-V, DDR controller) | 0.6 | 1.0 (inrush ≥ 1.5 A) | 0.57 / 0.95 |
| 0V85 | VDD_PHY_DDR, VDDPLL_MCB | 0.25 | 0.45 | 0.21 / 0.38 |
| 1V1 | FPGA VDDQ/VDDQX/VDDQ_CK + LPDDR4 VDD2/VDDQ | 0.4 | 0.7 | 0.44 / 0.77 |
| 1V8 | VCCAUX, HSIO VCCIO, LPDDR4 VDD1, eMMC VCCQ, flash, oscillator, translator A sides | 0.3 | 0.5 | 0.54 / 0.90 |
| 3V3 | HVIO, eMMC VCC, translator B sides + J3 pull-downs, LCD module + backlight; RTL8211FDI (all of it: its 1.0 V core and 1.8 V RGMII pads come from internal LDOs, estimate about 0.18 / 0.22 A, no current table in data sheet Rev 1.7) | 0.48 | 0.67 | 1.58 / 2.21 |
| 3V3_analog | ADC block (LDO from 5V0) | 0.01 | 0.02 | 0.05 / 0.1 (LDO loss included) |
| **Sum of outputs** | | | | **3.4 / 5.3** |
| **At 5 V input, about 85 % efficiency** | | **0.80 A** | **1.25 A** | 4.0 / 6.2 |

2026-10-25: KSZ9031 + 1V2 buck replaced by the RTL8211FDI-CG (stock). Its linear core LDO costs about 0.3 W more than the
KSZ9031's external 1V2 buck.

**Result: with the old 1 A U8 the typical case used most of the rail and the high case exceeded it. With the 2 A K7805-2000R3 (2026-10-29) both fit, if the gate-driver logic and U10 stay below about 0.75 A and 20V_ISO_SEC delivers the power.** Ways to cut power, in
order of effect:

1. **LCD backlight and module** (about 0.3 W): leave them out of the budget, or power them from another source.
2. **Ethernet at 100 Mbit/s** instead of 1000 (a gigabit PHY roughly halves its power at 100 Mbit/s). The control card needs no GbE.
3. **LPDDR4 data rate** at the low end (1.6 Gbps or below) and **RISC-V clock** about 500–600 MHz.
4. **Ti135 "L" grade (I3L)**: VCC/VCCA/VDD_SOC at 0.85 V. That gives about 20–25 % less core power (slides: LP worst case
   3.0 W vs 4.0 W) and lets **VCORE and 0V85 merge into one rail**, one regulator fewer. Lower speed grade; check
   availability (the Ti135 is not stocked at JLC in any grade).
5. Raise the baseboard U8 to a 1.5–2 A part (VXO7805-1500 / R-78K5.0-1.5 class) in the KiCad redraw.

Decision needed before layout: see §Open below.

## Regulator choice

The Agilex card uses AP61202Z6 (2 A, SOT-563) for the rails and a TDA38812 for VCORE. For this card:

| | AP61202Z6-7 (Agilex) | **TLV62585PDRLR** (chosen) |
|---|---|---|
| Current | 2 A | **3 A** (4 A switch limit), covers the 1.5 A VCC inrush with margin |
| JLC stock (2026-10-24) | **72** (C5188956), too few for 6 rails × boards | **19,486** (C485118), about $0.24 |
| Package | SOT-563 | SOT-563 (PDRL: 1 GND, 2 SW, 3 VIN, 4 EN, 5 FB, 6 PG) |
| V_FB | 0.6 V | 0.6 V ±1 % (0–85 °C), ±2 % (−40…125 °C) |
| Soft start | about 1 ms | 900 µs → VCORE ramps at about 1 V/ms (inside 0.095…10 V/ms) |
| PG | yes | yes (open drain, 95 % rising) |
| Disable | – | 10 Ω output discharge when EN is low |

The TDA38812 (VCORE on the Agilex card) is not needed: the Ti135 core is about 1 A, not 10+ A.

**One TLV62585PDRLR per rail**, the same part five times: VCORE 0.95 V, 0V85, 1V1, 1V8, 3V3 (the 1V2 rail went with the KSZ9031). Each with:

- Cin 10 µF 0805
- L 1 µH, 4 × 4 mm: **Sunlord WPN4020H1R0MT** (C98359, 26 mΩ, Isat 5.8 A, above the 4 A switch limit; 11,421 orderable)
- Cout 22 µF 0805 (2 × 22 µF on VCORE)
- R2 = 100 kΩ (data sheet maximum), R1 = R2 × (Vout/0.6 − 1), optional feed-forward C3

| Rail | Vout | R1 (top) | R2 (bottom) | Vout with E96 values |
|---|---|---|---|---|
| VCORE | 0.95 V | 58.3 k → **59.0 k** | 100 k | 0.954 V |
| 0V85 | 0.85 V | 41.7 k → **41.2 k** | 100 k | 0.847 V |
| 1V1 | 1.1 V | 83.3 k → **82.5 k** | 100 k | 1.095 V |
| 1V8 | 1.8 V | **200 k** | 100 k | 1.800 V |
| 3V3 | 3.3 V | 450 k → **453 k** | 100 k | 3.318 V |

VCC tolerance is 0.92…0.98 V (±3.2 %). FB ±2 % plus 1 % resistors fits; use 0.5 % resistors on VCORE for margin.
3V3_analog: NCP163ASN330T1G LDO from 5V0, as on the Agilex card.

## Open

- [ ] Run the Efinix Power Estimator with the real design and replace the Ti135 rows.
- [x] **Decided 2026-10-24: upgrade the baseboard U8 to a 1.5–2 A part.** Requested from the ac_psu_kicad session; 2026-10-29: K7805-2000R3 (2 A) chosen there. The card keeps the Ti135N484**I3**, GbE and the on-card LCD supply. The other cuts stay available as fallbacks.
- [ ] Measure the Ti60 card's 5V_ISOL current on the baseboard as a reference.
- [ ] Measure on a built baseboard that 20V_ISO_SEC can deliver the extra ~2.5 W for the 2 A U8.
- [ ] Get the gate-driver logic and U10 5V_ISOL currents, to fix the card's share of the 2 A.
