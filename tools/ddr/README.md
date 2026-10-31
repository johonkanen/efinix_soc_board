# LPDDR4 routing helpers (2026-10-25 session)

| File | Use |
|---|---|
| `ddr_nets.json` | DDR net lists: `in2` / `in5` (first layer plan), `L_in2` / `L_in5` / `L_fcu` (bytes 0+1 / byte 2 + CA / byte 3) |
| `route_stats.py BOARD...` | per byte: vias, length, share of copper per layer (KiCadRoutingTools venv python) |
| `render_layer.py BOARD OUT.png LAYER x0,y0,x1,y1 [scale]` | PNG of one layer's DDR copper around U501/U801, coloured by byte |
| `dump_pads.py` (kipy) + `u801_pose_study.py` | U801 rotation/position study: straight-line crossings with the best within-byte swizzle per pose. Crude for the far bytes (they route round the package); the routing trial decided it: the current -90 deg pose won |
| `strip_ddr_vias.py IN OUT` (kipy) | remove the DDR signal vias (keeps DDR_CAL and plane vias): the input the bus router wants |
| `transplant.py IN_MAIN FROM_BOARD OUT` (kipy) | replace the LPDDR4 copper (`ddr_*` tracks/arcs/vias, not DDR_CAL) of IN_MAIN with FROM_BOARD's; checks U501/U801 poses match |
| `delay_rules.sh [DRU]` | KiCad delays → `ddr_timing.py --kicad --rules` → length rules (ps, die to die) in the generated block of `kicad/ti135_card.kicad_dru`, for pcbnew's tuner and DRC. Shared CA/CK nets: min/opt in path terms (what the tuner reads and "Update all tuning patterns" aims at), max = path + tol + the net's second branch (DRC sums the whole net): the tuner flags short, DRC flags long, so good = pattern green after an update and DRC green. Where the tuner's pad-to-pad path takes in part of the other branch (read from the patterns: CA1 +11 ps, CK +3 ps), min/opt are shifted by that offset: run it right after "Update all tuning patterns" + save, then update again. DQ/DM window DQS + 5 / 10 / 15 ps (`DQ_MAX` env). Rerun after rerouting |
