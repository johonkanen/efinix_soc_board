#!/usr/bin/env python3
"""Flash I/O finished around the user's own arrangement (2026-11-16): series resistors in a column on F.Cu at
x 183.7 with a via in pad 1 (In2 to the FPGA) and F.Cu to the flash balls, pull-ups on B.Cu under them.
    tools/p2k/bin/kipy tools/flash_io.py IN.kicad_pcb OUT.kicad_pcb
- R625 (io0, was parked): F.Cu at (186.0, 77.4) in the free lane between io2_r and io1_r, a via in pad 1,
  pad 2 on F.Cu along y 77.4 between the ball rows to U601 D3.
- Pull-ups R616 / R617 / R618: their 1V8 pads are chained on B.Cu at x 184.0 to one 1V8 via at (184.85, 77.95)
  (a via in a 1V8 pad would come up in the series resistor's pad above it).
- Dead-end stubs of the flash nets at U501 are removed.
The FPGA side of io0 (ball J4 to the via in R625 pad 1) is routed afterwards with the router (inner layers
preferred), then the zones are refilled:
    KICAD_RIP_PREEXISTING=0 ~/dev/KiCadRoutingTools/.venv/bin/python -X utf8 ~/dev/KiCadRoutingTools/py_router/route.py \
        OUT ROUTED --nets /flash_io0 --layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --track-width 0.1 \
        --clearance 0.11 --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --no-bga-zones U501 --no-fix-drc-settings \
        --board-edge-clearance 0.5 --escalation off --layer-costs 3 -1 1 -1 -1 1 -1 3"""
import sys

sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2], "none"]
exec(open(__file__.replace("flash_io.py", "pi_fixes.py")).read().split('STEPS = {"s3"')[0])   # helpers, loads the board

pp = place("R625", 186.0, 77.4, 0, "F")
if pp["1"][0] > pp["2"][0]:
    pp = place("R625", 186.0, 77.4, 180)
via(pp["1"][0], pp["1"][1], "/flash_io0")
track([pp["2"], (192.5, 77.4), (193.0, 77.9)], "F", "/06 fpga_config/flash_io0_r", 0.12)
p616, p617, p618 = pad("R616", 1), pad("R617", 1), pad("R618", 1)
track([p618, p617, p616], "B", "1V8", 0.2)
via(184.85, 77.95, "1V8")
track([p617, (184.85, 77.95)], "B", "1V8", 0.2)
strip([(175.7, 83.94), (175.68, 83.94), (174.95, 83.1), (174.95, 82.9)], {"/flash_io2"})
strip([(171.9, 88.1), (173.18, 88.1)], {"/flash_io3"}); strip([(172.75, 87.45), (174.35, 87.45)], {"/flash_cs_n"})
refill()
print("flash_io: R625 at", pp, "; open connections", opens())
b.Save(DST)
