#!/usr/bin/env bash
# Move the fifteen 4.7 u 0402 caps under U501 outside the BGA (user request 2026-11-12):  tools/bulk47.sh work/NAME [SET "REFS"]   (default: set bulk47; the 1 u caps: set bulk1u)
# B.Cu tracks ending on their old pads are lifted (vias stay: they may also serve a ball), the caps are moved
# (tools/place_fix.py set bulk47) and the rails are tied again; any ball that lost its tie is routed with them.
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"; cd "$R"; D="$1"; SET="${2:-bulk47}"; REFS="${3:-C562 C5056 C5055 C5027 C5029 C513 C5030 C512 C511 C514 C5048 C5049 C553 C5054 C5028}"; K=tools/p2k/bin/kipy; PY=work/venv/bin/python
NETS="'^GND\$' '^1V8\$' '^VCORE\$' '^1V1\$' '^3V3\$'"
tools/work_copy.sh new "$D"; rm -f "$D"/ops*.json
$K work/p1/geom.py "$D/b.kicad_pcb" "$D/fp.json" > /dev/null 2>&1
python3 - "$D" "$REFS" <<'PYE' > "$D/boxes.txt"
import json, sys
C = sys.argv[2].split()
for f in json.load(open(sys.argv[1] + "/fp.json"))["fps"]:
    if f["ref"] in C:
        for p in f["pads"]:
            print(p["x"] - 0.36, p["y"] - 0.36, p["x"] + 0.36, p["y"] + 0.36)
PYE
tot=0
while read b; do m=$($K tools/rip_box.py "$D/b.kicad_pcb" '^(GND|1V8|VCORE|1V1|3V3)$' $b B.Cu | tail -1 | awk '{print $2}'); tot=$((tot+m)); done < "$D/boxes.txt"
echo "lifted $tot B.Cu tracks at the old pads"
$K tools/place_fix.py "$D/b.kicad_pcb" "$SET" 2>&1 | grep relocate
$K tools/dump_geom.py "$D/b.kicad_pcb" "$D/geom.json" | tail -1
eval "$PY tools/grid_router.py $D/geom.json $D/ops1.json --plane-vias --nets $NETS --width 0.3 --max-len 4 --keep-pours '^5V0\$'" > "$D/r1.log"; grep "FAIL\|routed" "$D/r1.log" || true
eval "$PY tools/grid_router.py $D/geom.json $D/ops2.json --prev $D/ops1.json --plane-vias --nets $NETS --width 0.2 --max-len 8 --keep-pours '^5V0\$'" > "$D/r2.log"; grep "FAIL\|routed" "$D/r2.log" || true
$K tools/apply_ops.py "$D/b.kicad_pcb" "$D/ops1.json" | tail -1; $K tools/apply_ops.py "$D/b.kicad_pcb" "$D/ops2.json" | tail -1
$K tools/rail_vias.py "$D/b.kicad_pcb" --log "$D/rv.json" | grep "new vias\|LEFT" || true
tools/work_copy.sh check "$D" | tail -7
python3 tools/drc_summary.py "$D/drc.json" -v | grep "^    " | cut -c1-220 | head -30
