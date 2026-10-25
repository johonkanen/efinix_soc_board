# Efinix vendor files (not in git: Efinix copyright)

Download from the Efinix Support Center (login) and place here:

| File | Content | Used by |
|---|---|---|
| `Ti135_netlength-v0.5.xlsx` | package net length / delay per ball, all Ti135 packages (v0.5, 2026-04-23) | `ti135n484_netlength.csv` (the N484 sheet) |
| `ti135n484_netlength.csv` | N484 sheet as CSV: pin name, ball, length (mm), delay (ps) | `tools/pad_to_die.py` (U501 pad-to-die delays) |
| `Ti135N484-v1.0.bsd` | BSDL (JTAG boundary scan), v1.0 | board test / bring-up |
| `3Dmodel-3-N484-v1.1.step` | package 3D model, v1.1 | optional U501 3D model |
