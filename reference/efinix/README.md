# Efinix vendor files (not in git: Efinix copyright)

Download from the Efinix Support Center (login) and place here:

| File | Content | Used by |
|---|---|---|
| `Ti135_netlength-v0.5.xlsx` | package net length / delay per ball, all Ti135 packages (v0.5, 2026-04-23) | `ti135n484_netlength.csv` (the N484 sheet) |
| `ti135n484_netlength.csv` | N484 sheet as CSV: pin name, ball, length (mm), delay (ps) | `tools/pad_to_die.py` (U501 pad-to-die delays) |
| `Ti135N484-v1.0.bsd` | BSDL (JTAG boundary scan), v1.0 | board test / bring-up |
| `3Dmodel-3-N484-v1.1.step` | package 3D model, v1.1 | optional U501 3D model |
| `ti135n484_hw_checklist.htm` | *Hardware Design Checklist and Guidelines* generated for Ti135 N484, SPI active x4: power pins, per-rail decoupling table, power-up groups, configuration pins | design review before ordering (TI135_PCB_NOTES.md) |
| `pcb-guidelines-ddr-ti-ug-v1.2.pdf` | *Titanium DDR DRAM PCB Design User Guide* UG-PCB-DDR-TI v1.2 (Dec 2022) | TI135_PCB_NOTES.md §6.3 |
| `devboards/*.kicad_pcb` | Efinix dev-board layouts (Allegro `.brd` from the Support Center), imported with `kicad-cli pcb import` (KiCad 10 reads Allegro binary): Ti375 C529 (12 layers, 0.8 mm FPGA, one x32 LPDDR4 MT53E256M32D2), Ti180 M484 (14 layers; the Tz170 J484 `.brd` has the same part, track, via and zone counts, likely the same board), Ti375 N1156 (14 layers, two LPDDR4) | reference for the LPDDR4 routing and BGA decoupling |
