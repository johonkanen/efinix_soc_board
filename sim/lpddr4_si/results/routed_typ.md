# Routed-board SI, typ corner (LPDDR4_IBIS_PLAN.md step 4, 2026-10-31)

`python3 routed_si.py --sweep --corners typ -j 4`: 172 netlists (every LPDDR4 net, both directions, 2800 and
3200 Mbps), 7.7 min, 0 failed. Rows: `results/routed.csv`. Judged at the receiver die (DRAM die for writes/CA/CK,
FPGA die for reads). DRAM = Winbond W66 stand-in. Masks: run_si.py `masks()` (JEDEC DQ/CA; TI SoC-pad diamond as
the FPGA read proxy). Limits: VDDQ + 0.3 V / -0.3 V peak, 0.1 V-ns area.

| kind | rate | receivers | worst V margin (mV) | worst t margin (ps) | min eye height (mV) | Vmax / Vmin worst (mV) | limit fails | max OS / US area (V-ns) | worst net (V) |
|---|---|---|---|---|---|---|---|---|---|
| CA/CS/CKE | 2800 | 16 | 137 | 417 (ca1) | 340 | 1307 / -172 | 0 | 0.025 / 0.019 | ca3 |
| CA/CS/CKE | 3200 | 16 | 142 | 352 (ca0) | 337 | 1344 / -221 | 0 | 0.030 / 0.026 | ca1 |
| CK | 2800 | 2 | 466 | 226 | 665 | 387 / -30 | 0 | 0 / 0.003 | ck (ch B) |
| CK | 3200 | 2 | 498 | 161 | 652 | 390 / -27 | 0 | 0 / 0.002 | ck (ch A) |
| DQ read | 2800 | 32 | 140 | 61 (dq1) | 295 | 468 / -54 | 0 | 0 / 0.009 | dq3 |
| DQ read | 3200 | 32 | 142 | 49 (dq11) | 301 | 463 / -51 | 0 | 0 / 0.008 | dq22 |
| DQ/DM write | 2800 | 36 | 399 | 211 (dq5) | 588 | 800 / -73 | 0 | 0 / 0.012 | dq3 |
| DQ/DM write | 3200 | 36 | 358 | 171 (dq10) | 543 | 809 / -73 | 0 | 0 / 0.011 | dq3 |
| DQS read | 2800 | 4 | 542 | 88 (dqs0) | 708 | 444 / -33 | 0 | 0 / 0.006 | dqs0 |
| DQS read | 3200 | 4 | 523 | 61 (dqs1) | 693 | 451 / -42 | 0 | 0 / 0.006 | dqs2 |
| DQS write | 2800 | 4 | 1074 | 233 (dqs0) | 1297 | 787 / -60 | 0 | 0 / 0.009 | dqs2 |
| DQS write | 3200 | 4 | 1013 | 177 (dqs1) | 1276 | 780 / -60 | 0 | 0 / 0.008 | dqs0 |

No negative margin anywhere, at the die or at the DRAM ball. Tightest: DQ read timing (49 ps at 3200, dq11) and the
CA voltage margin (137 mV); CKE (unterminated, CKE_INPUT) peaks at 1344 mV against the 1400 mV limit at 3200.
Not modelled: crosstalk (step 6), meander self-coupling, pair mode conversion; the DRAM is a stand-in whose edges
run up to 12 ps faster than its tables (step 1).
