# Crosstalk on the routed board (LPDDR4_IBIS_PLAN.md step 6, 2026-10-31)

**Coupled lengths** (`coupled_lengths.py`, full list `results/coupled_lengths.md`): parallel pieces of two different
LPDDR4 nets on one layer, edge gap <= 0.4 mm, outside the U501/U801 courtyards. Apart from each DQS/CK pair's own
P/N coupling (intended), the worst are: edge gap 0.20-0.25 mm: at most 2.5 mm (dq14 beside dq10/dq9, In5);
0.30-0.40 mm: dq30/dq31 9.2 mm (In5); CA0/CA1 0.8 mm at 0.30 mm. CA-to-DQ crossings are on different layers (In2 vs
In5) with the In3/In4 planes between them, so they are not coupled lines.

**Runs** (`python3 run_si.py --xtalk --xt inner,0.10,0.20,2.5 inner,0.10,0.30,9.2 inner,0.10,0.20,10 -j 2`, rows
`results/results_xtalk_board.csv`): three coupled 0.10 mm lines (aggressor - victim - aggressor, both aggressors over
the whole length: more than the board has), DQ write (FPGA 40 ohm -> DRAM ODT 60), typ. The coupled section is a
lumped ladder of 0.25 mm sections from the field-solved L/C matrices (ngspice's CPL element stopped every run).
Patterns: quiet aggressors (reference), uncorrelated switching aggressors, and quiet victim with the aggressors in
phase (peak coupled noise). Victim at the DRAM die:

| rate | gap (mm) | coupled length (mm) | eye height, quiet -> switching aggressors (mV) | V margin (mV) | t margin (ps) | peak noise on a quiet victim, far / near end (mV) |
|---|---|---|---|---|---|---|
| 2800 | 0.20 | 2.5 (board worst) | 692 -> 686 | 535 -> 527 | 228 -> 226 | 17 / 46 |
| 2800 | 0.30 | 9.2 (dq30/dq31) | 687 -> 682 | 512 -> 507 | 239 -> 235 | 13 / 35 |
| 2800 | 0.20 | 10 (bound) | 682 -> 668 | 502 -> 492 | 239 -> 231 | 26 / 66 |
| 3200 | 0.20 | 2.5 (board worst) | 671 -> 670 | 518 -> 515 | 181 -> 180 | 14 / 37 |
| 3200 | 0.30 | 9.2 (dq30/dq31) | 637 -> 636 | 454 -> 454 | 180 -> 178 | 13 / 31 |
| 3200 | 0.20 | 10 (bound) | 642 -> 635 | 449 -> 442 | 179 -> 175 | 30 / 51 |

Crosstalk costs at most 14 mV of eye height, 10 mV of V margin and 8 ps of t margin, in the bounding case (4x the
board's worst coupled length at its gap). Taken off the tightest margins of steps 4-5 (DQ read 138 mV / 49 ps, CA
120 mV) every net still passes. Not modelled: coupling inside the BGA escapes (excluded above; short), the read
direction and CA (same geometry, same order of magnitude expected).
