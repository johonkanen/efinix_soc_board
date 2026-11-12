#!/usr/bin/env bash
# Free one boxed-in power pad:  tools/fix_area.sh work/NAME 'RIP_REGEX X0 Y0 X1 Y1 [LAYERS]' 'POWER ROUTER ARGS' 'REROUTE ROUTER ARGS'
# Rips the named nets in the box on a fresh work copy, routes the power connection first, then the
# ripped nets again, applies and checks. Accept with work_copy.sh accept only if DRC is clean.
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"; cd "$R"; D="$1"; K=tools/p2k/bin/kipy; PY=work/venv/bin/python
tools/work_copy.sh new "$D"; rm -f "$D"/ops*.json
eval "$K tools/rip_box.py $D/b.kicad_pcb $2" | tail -1
$K tools/dump_geom.py "$D/b.kicad_pcb" "$D/geom.json" > /dev/null
eval "$PY tools/grid_router.py $D/geom.json $D/ops1.json $3" | grep "ok\|FAIL\|routed"
eval "$PY tools/grid_router.py $D/geom.json $D/ops2.json --prev $D/ops1.json $4" | grep "ok\|FAIL\|routed"
$K tools/apply_ops.py "$D/b.kicad_pcb" "$D/ops1.json" | tail -1
$K tools/apply_ops.py "$D/b.kicad_pcb" "$D/ops2.json" | tail -1
tools/work_copy.sh check "$D" | tail -6
python3 tools/drc_summary.py "$D/drc.json" -v | grep "^    " | cut -c1-200 | head -6
