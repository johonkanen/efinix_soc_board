# Routed-board SI, all corners (LPDDR4_IBIS_PLAN.md step 5, 2026-10-31)

`python3 routed_si.py --sweep --corners min max -j 4`: 344 netlists (every LPDDR4 net, both directions, 2800 and
3200 Mbps, min and max corner from the corner model files at typ), 14 min, 0 failed; typ from step 4. Rows:
`results/routed.csv`. Judged at the receiver die. Limits: VDDQ (1.10 / 1.06 / 1.17 V) + 0.3 V and -0.3 V peak,
0.1 V-ns area.

| kind | rate | corner | worst V margin (mV) | worst t margin (ps) | min eye height (mV) | Vmax / Vmin (mV) | limit fails | max OS / US area (V-ns) | worst nets V / t |
|---|---|---|---|---|---|---|---|---|---|
| CA/CS/CKE | 2800 | typ | 137 | 417 | 340 | 1307 / -172 | 0 | 0.025 / 0.019 | ca3 / ca1 |
| CA/CS/CKE | 2800 | min | 120 | 415 | 322 | 1245 / -140 | 0 | 0.021 / 0.015 | ca3 / ca1 |
| CA/CS/CKE | 2800 | max | 133 | 340 | 342 | 1417 / -211 | 0 | 0.033 / 0.024 | ca3 / cke0 |
| CA/CS/CKE | 3200 | typ | 142 | 352 | 337 | 1344 / -221 | 0 | 0.030 / 0.026 | ca1 / ca0 |
| CA/CS/CKE | 3200 | min | 126 | 256 | 319 | 1291 / -197 | 0 | 0.024 / 0.019 | ca1 / cke0 |
| CA/CS/CKE | 3200 | max | 136 | 344 | 337 | **1486** / -250 | **1** | 0.040 / 0.029 | ca1 / ca0 |
| CK | 2800 | typ / min / max | 466 / 459 / 438 | 226 / 229 / 218 | 622 | 396 / -30 | 0 | 0 / 0.003 | ck |
| CK | 3200 | typ / min / max | 498 / 455 / 484 | 161 / 162 / 158 | 608 | 398 / -28 | 0 | 0 / 0.002 | ck |
| DQ read | 2800 | typ / min / max | 140 / 138 / 158 | 61 / 60 / 69 | 295 | 520 / -71 | 0 | 0 / 0.013 | dq3 / dq1 |
| DQ read | 3200 | typ / min / max | 142 / 148 / 157 | 49 / 50 / 52 | 297 | 515 / -66 | 0 | 0 / 0.012 | dq22, dq17 / dq11, dq5 |
| DQ/DM write | 2800 | typ / min / max | 399 / 381 / 380 | 211 / 217 / 207 | 562 | 808 / -73 | 0 | 0 / 0.012 | dq3 / dq5, dq1 |
| DQ/DM write | 3200 | typ / min / max | 358 / 355 / 351 | 171 / 172 / 170 | 529 | 814 / -73 | 0 | 0 / 0.011 | dq3 / dq10, dq26, dq5 |
| DQS read | 2800 | typ / min / max | 542 / 537 / 587 | 88 / 87 / 97 | 697 | 487 / -46 | 0 | 0 / 0.012 | dqs0, dqs2 / dqs0 |
| DQS read | 3200 | typ / min / max | 523 / 537 / 557 | 61 / 62 / 62 | 693 | 497 / -53 | 0 | 0 / 0.010 | dqs2 / dqs1 |
| DQS write | 2800 | typ / min / max | 1074 / 1018 / 1086 | 233 / 237 / 232 | 1233 | 792 / -60 | 0 | 0 / 0.009 | dqs2 / dqs0 |
| DQS write | 3200 | typ / min / max | 1013 / 997 / 982 | 177 / 179 / 177 | 1234 | 788 / -60 | 0 | 0 / 0.008 | dqs0 / dqs1 |

**No negative eye margin at any corner or rate.** One limit exceeded: **CKE0 at max corner, 3200 Mbps, 1486 mV
peak at one DRAM die against 1470 mV** (VDDQ max 1.17 V + 0.3 V; 16 mV over; its area 0.04 V-ns is within 0.1).
At 2800 Mbps, the Ti135N484I3's top rate, CKE peaks at 1417 mV at max (53 mV below the limit). CKE is the only
unterminated LPDDR4 input (CKE_INPUT, no ODT); the PRBS at the CA rate is a worst case for a signal that toggles
rarely in operation. With the FPGA's 48 ohm drive on CKE (Efinity setting) the max-corner peak drops to 1342 mV (2800) /
1415 mV (3200) with the eye still wide open (523 mV, 226 ps margin at 3200). The worst nets are mostly the same at every corner (ca1/ca3, dq3, dq1/dq11, dqs0/dqs1).
