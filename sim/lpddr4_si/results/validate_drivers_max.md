| driver model | fixture | edge | V start / end, IBIS (mV) | V start / end, KiCad (mV) | t20-80, IBIS (ps) | t20-80, KiCad (ps) |
|---|---|---|---|---|---|---|
| lpddr4_ocd_40p_40n | 20.0 ohm to GND | rising | 0 / 397 | 1 / 397 | 67.0 | 70.0 |
| lpddr4_ocd_40p_40n | 20.0 ohm to GND | falling | 397 / 0 | 397 / 1 | 56.0 | 57.0 |
| lpddr4_ocd_48p_48n | 24.0 ohm to GND | rising | 0 / 399 | 1 / 399 | 76.0 | 83.0 |
| lpddr4_ocd_48p_48n | 24.0 ohm to GND | falling | 399 / 0 | 399 / 1 | 62.0 | 65.0 |
| PD40_ODT40_VOH30 | 50.0 ohm to GND | rising | 0 / 439 | -1 / 438 | 29.0 | 27.0 |
| PD40_ODT40_VOH30 | 50.0 ohm to GND | falling | 439 / -0 | 438 / -1 | 23.0 | 17.0 |
| PD48_ODT40_VOH30 | 50.0 ohm to GND | rising | 0 / 439 | -2 / 437 | 32.0 | 27.0 |
| PD48_ODT40_VOH30 | 50.0 ohm to GND | falling | 439 / -0 | 437 / -2 | 30.0 | 18.0 |

| driver model | load | DC high, V-I tables (mV) | DC high, KiCad (mV) | diff (mV) |
|---|---|---|---|---|
| PD40_ODT40_VOH30 | 40 ohm to GND | 402 | 397 | -4 |
| PD48_ODT40_VOH30 | 40 ohm to GND | 402 | 397 | -5 |
| lpddr4_ocd_40p_40n | 60 ohm to GND | 736 | 782 | +46 |
| lpddr4_ocd_48p_48n | 60 ohm to GND | 687 | 724 | +37 |
| lpddr4_ocd_40p_40n | open | 1170 | 1299 | +129 |
| lpddr4_ocd_48p_48n | open | 1170 | 1298 | +128 |
| PD40_ODT40_VOH30 | open | 1073 | 2057 | +984 |
| PD48_ODT40_VOH30 | open | 1072 | 2055 | +983 |
