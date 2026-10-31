| driver model | fixture | edge | V start / end, IBIS (mV) | V start / end, KiCad (mV) | t20-80, IBIS (ps) | t20-80, KiCad (ps) |
|---|---|---|---|---|---|---|
| lpddr4_ocd_40p_40n | 20.0 ohm to GND | rising | 0 / 358 | 1 / 358 | 52.0 | 51.0 |
| lpddr4_ocd_40p_40n | 20.0 ohm to GND | falling | 358 / 0 | 358 / 0 | 43.0 | 44.0 |
| lpddr4_ocd_48p_48n | 24.0 ohm to GND | rising | 0 / 361 | 1 / 361 | 56.0 | 57.0 |
| lpddr4_ocd_48p_48n | 24.0 ohm to GND | falling | 361 / 0 | 361 / 1 | 50.0 | 53.0 |
| PD40_ODT40_VOH30 | 50.0 ohm to GND | rising | 0 / 384 | 0 / 383 | 46.0 | 28.0 |
| PD40_ODT40_VOH30 | 50.0 ohm to GND | falling | 385 / 0 | 383 / -0 | 38.0 | 38.0 |
| PD48_ODT40_VOH30 | 50.0 ohm to GND | rising | 0 / 384 | -1 / 380 | 44.0 | 35.0 |
| PD48_ODT40_VOH30 | 50.0 ohm to GND | falling | 385 / 1 | 380 / -1 | 32.0 | 32.0 |

| driver model | load | DC high, V-I tables (mV) | DC high, KiCad (mV) | diff (mV) |
|---|---|---|---|---|
| PD40_ODT40_VOH30 | 40 ohm to GND | 353 | 353 | -0 |
| PD48_ODT40_VOH30 | 40 ohm to GND | 353 | 351 | -2 |
| lpddr4_ocd_40p_40n | 60 ohm to GND | 646 | 626 | -21 |
| lpddr4_ocd_48p_48n | 60 ohm to GND | 602 | 586 | -16 |
| lpddr4_ocd_40p_40n | open | 1060 | 988 | -72 |
| lpddr4_ocd_48p_48n | open | 1060 | 989 | -72 |
| PD40_ODT40_VOH30 | open | 1027 | 681 | -346 |
| PD48_ODT40_VOH30 | open | 1027 | 673 | -354 |
