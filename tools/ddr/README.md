# LPDDR4 routing helpers (2026-10-25 session)

| File | Use |
|---|---|
| `ddr_nets.json` | DDR net lists: `in2` / `in5` (first layer plan), `L_in2` / `L_in5` / `L_fcu` (bytes 0+1 / byte 2 + CA / byte 3) |
| `route_stats.py BOARD...` | per byte: vias, length, share of copper per layer (KiCadRoutingTools venv python) |
| `render_layer.py BOARD OUT.png LAYER x0,y0,x1,y1 [scale]` | PNG of one layer's DDR copper around U501/U801, coloured by byte |
| `dump_pads.py` (kipy) + `u801_pose_study.py` | U801 rotation/position study: straight-line crossings with the best within-byte swizzle per pose. Crude for the far bytes (they route round the package); the routing trial decided it: the current -90 deg pose won |
