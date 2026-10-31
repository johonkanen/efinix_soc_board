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
rarely in operation. The worst nets are mostly the same at every corner (ca1/ca3, dq3, dq1/dq11, dqs0/dqs1).

**CKE fix (2026-10-31).** Efinity's DDR block has no drive setting for CA/CK/CKE, so a weaker CKE driver is not an
option. Simulated at the DRAM die, the routed CKE with a series resistor at U501 (worst corner of each):

| series R at U501 | peak, max 3200 (limit 1470 mV) | peak, max 2800 | undershoot | V margin | t margin |
|---|---|---|---|---|---|
| none | 1486 mV (fails) | 1417 mV | -250 mV | 527 mV | 256 ps |
| **10 ohm** | **1291 mV** | 1236 mV | -74 mV | 376 mV | 208 ps |
| 15 ohm | 1230 mV | 1191 mV | -48 mV | 313 mV | 183 ps |
| 22 ohm | 1217 mV | 1182 mV | -34 mV | 236 mV | 154 ps |

A lower-impedance trunk also passes (In2 0.18 mm, 39.8 ohm: 1384 mV; B.Cu 0.25 mm, 39.3 ohm: 1377 mV at max 3200)
but needs a reroute. Chosen: **10 ohm in series on B.Cu at U501**.

**CKE as built with R803 (board e4ac548, 2026-10-31).** CKE now runs U501 -> via -> R803 (10 ohm, B.Cu) -> B.Cu
0.12 mm (about 56 ohm) -> T -> U801; `extract_routes.py` / `routed_si.py` follow it through the resistor. Still
with the meander sized for the old rule (path about 67 ps long; it is retuned next). At the DRAM die:

| corner | rate | peak (mV) | limit (mV) | undershoot (mV) | V margin (mV) | t margin (ps) | OS / US area (V-ns) |
|---|---|---|---|---|---|---|---|
| typ | 2800 | 1223 | 1400 | -99 | 507 | 303 | 0.013 / 0.010 |
| typ | 3200 | 1251 | 1400 | -118 | 428 | 210 | 0.016 / 0.013 |
| min | 2800 | 1167 | 1360 | -89 | 506 | 310 | 0.010 / 0.008 |
| min | 3200 | 1221 | 1360 | -136 | 393 | 214 | 0.015 / 0.013 |
| max | 2800 | 1299 | 1470 | -105 | 558 | 312 | 0.021 / 0.012 |
| max | 3200 | 1292 | 1470 | -115 | 545 | 226 | 0.021 / 0.014 |

Every corner passes; the worst peak is 171 mV under the limit (was 16 mV over).

**CKE retuned (board saved 14:52).** CKE die to die 306.7 ps, -1.0 ps vs CK (rule +-5.3). The CKE rule is written
from R803 and shifted by the tuner's offset on this routing (-23.0 ps). At the DRAM die:

| corner | rate | peak (mV) | limit (mV) | undershoot (mV) | V margin (mV) | t margin (ps) | OS / US area (V-ns) |
|---|---|---|---|---|---|---|---|
| typ | 2800 | 1237 | 1400 | -106 | 561 | 286 | 0.012 / 0.009 |
| typ | 3200 | 1280 | 1400 | -167 | 502 | 236 | 0.019 / 0.016 |
| min | 2800 | 1154 | 1360 | -94 | 552 | 305 | 0.009 / 0.008 |
| min | 3200 | 1214 | 1360 | -120 | 449 | 228 | 0.013 / 0.009 |
| max | 2800 | 1331 | 1470 | -156 | 592 | 293 | 0.017 / 0.013 |
| max | 3200 | 1448 | 1470 | -227 | 500 | 216 | 0.030 / 0.023 |

Every corner passes. At 2800 Mbps (the I3's top rate) the peak is 139 mV under the limit; at 3200 / max only 22 mV
(the shorter route moved the reflections; before the retune it was 1292 mV). If 3200 Mbps margin matters, 15 ohm
gave about 60 mV lower peaks than 10 ohm in the resistor comparison above.

**R803 = 15 ohm (2026-10-31, final).** Same routing, the resistor raised from 10 to 15 ohm for margin at 3200 Mbps:

| corner | rate | peak (mV) | limit (mV) | undershoot (mV) | V margin (mV) | t margin (ps) | OS / US area (V-ns) |
|---|---|---|---|---|---|---|---|
| typ | 2800 | 1170 | 1400 | -45 | 467 | 265 | 0.004 / 0.004 |
| typ | 3200 | 1216 | 1400 | -103 | 422 | 218 | 0.010 / 0.008 |
| min | 2800 | 1098 | 1360 | -35 | 454 | 275 | 0.002 / 0.002 |
| min | 3200 | 1159 | 1360 | -63 | 370 | 206 | 0.006 / 0.005 |
| max | 2800 | 1262 | 1470 | -86 | 500 | 263 | 0.007 / 0.006 |
| max | 3200 | 1376 | 1470 | -157 | 443 | 208 | 0.019 / 0.014 |

Peak margin 208 mV at 2800 and 94 mV at 3200 (10 ohm: 139 / 22 mV); the eye keeps >= 370 mV / 206 ps.
