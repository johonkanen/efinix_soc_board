#!/usr/bin/env bash
# Phase 3b on a work copy: PLL ferrites to their balls, rail tie-ins for the moved parts, then the rail
# pads that have no fill of their rail under them, by trace.   tools/phase3.sh work/NAME
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"; cd "$R"; D="$1"; K=tools/p2k/bin/kipy; PY=work/venv/bin/python
tools/work_copy.sh new "$D"
$K tools/place_fix.py "$D/b.kicad_pcb" pll 2>&1 | grep relocate
# the GND vias phase 3a put in the pads of C508 and C501 at their old spots
$K tools/remove_items.py "$D/b.kicad_pcb" "GND 179.7059 63.9822 0.25" "GND 177.894 57.99 0.1" | tail -1
$K tools/rail_vias.py "$D/b.kicad_pcb" --log "$D/rail_vias2.json" | grep "new vias"
$K tools/dump_geom.py "$D/b.kicad_pcb" "$D/geom.json" | tail -1
N='--nets ^5V0$ ^VCORE$ ^0V85$ ^1V1$ ^3V3$ ^1V8$ ^GND$'
$PY tools/grid_router.py "$D/geom.json" "$D/opsA.json" --plane-vias $N --width 0.2 --max-len 5 | tail -1
$PY tools/grid_router.py "$D/geom.json" "$D/opsB.json" --prev "$D/opsA.json" --plane-vias $N --width 0.12 --max-len 40 | grep "FAIL\|routed"
$K tools/apply_ops.py "$D/b.kicad_pcb" "$D/opsA.json" | tail -1
$K tools/apply_ops.py "$D/b.kicad_pcb" "$D/opsB.json" | tail -1
tools/work_copy.sh check "$D"
