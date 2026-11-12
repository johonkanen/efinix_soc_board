#!/usr/bin/env bash
# Move the 0805 bulk caps under U501 outside the BGA, to F.Cu (user request 2026-11-12):  tools/bulk_out.sh work/NAME
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"; cd "$R"; D="$1"; K=tools/p2k/bin/kipy; PY=work/venv/bin/python
tools/work_copy.sh new "$D"; rm -f "$D"/ops*.json
$K work/p1/geom.py "$D/b.kicad_pcb" "$D/fp.json" > /dev/null 2>&1
python3 - "$D" <<'PYE' > "$D/boxes.txt"
import json, sys
for f in json.load(open(sys.argv[1] + "/fp.json"))["fps"]:
    if f["ref"] in ("C5003", "C509", "C5005", "C5004", "C5021", "C5026", "C5024"):
        c = f["cy"]; print(c[0] - 0.2, c[1] - 0.2, c[2] + 0.2, c[3] + 0.2)
PYE
tot=0
while read b; do for f in reports/phase3_rail_vias_pass1_ops.json reports/phase3/rail_vias2_ops.json reports/phase3/opsA.json reports/phase3/opsB.json reports/phase9/ops*.json; do
  m=$($K tools/remove_ops.py "$D/b.kicad_pcb" "$f" '^(GND|1V8|VCORE)$' $b | tail -1 | awk '{print $2}'); tot=$((tot+m)); done; done < "$D/boxes.txt"
echo "lifted $tot tie-in items at the old pads"
$K tools/place_fix.py "$D/b.kicad_pcb" bulk_out 2>&1 | grep relocate
$K tools/dump_geom.py "$D/b.kicad_pcb" "$D/geom.json" | tail -1
$PY tools/grid_router.py "$D/geom.json" "$D/ops1.json" --plane-vias --nets '^GND$' '^1V8$' '^VCORE$' --width 0.3 --max-len 4 --keep-pours '^5V0$' | grep "FAIL\|routed"
$PY tools/grid_router.py "$D/geom.json" "$D/ops2.json" --prev "$D/ops1.json" --plane-vias --nets '^GND$' '^1V8$' '^VCORE$' --width 0.2 --max-len 8 --keep-pours '^5V0$' | grep "FAIL\|routed"
$K tools/apply_ops.py "$D/b.kicad_pcb" "$D/ops1.json" | tail -1; $K tools/apply_ops.py "$D/b.kicad_pcb" "$D/ops2.json" | tail -1
$K tools/rail_vias.py "$D/b.kicad_pcb" --log "$D/rv.json" | grep "new vias\|LEFT"
tools/work_copy.sh check "$D" | tail -7
python3 tools/drc_summary.py "$D/drc.json" -v | grep "^    " | cut -c1-220 | head
