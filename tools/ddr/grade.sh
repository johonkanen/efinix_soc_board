#!/usr/bin/env bash
# Grade a routed board the same way every time (KRT_LEARNING.md): our .kicad_pro/.kicad_dru, planes refilled, KiCad DRC,
# DDR connectivity, per-byte layer use.   tools/ddr/grade.sh NAME BOARD.kicad_pcb
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; N=$1; B=$2; W="$R/work/grade/$N"; mkdir -p "$W"
cp "$B" "$W/b.kicad_pcb"; cp "$R/kicad/ti135_card.kicad_pro" "$W/b.kicad_pro"; cp "$R/kicad/ti135_card.kicad_dru" "$W/b.kicad_dru"
cat > "$W/refill.py" <<'PY'
import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1]); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(sys.argv[1], b)
PY
"$R/tools/p2k/bin/kipy" "$W/refill.py" "$W/b.kicad_pcb" 2>&1 | grep -v "Debug\|memory leak" || true
"$R/tools/p2k/bin/kicad-cli" pcb drc -o "$W/drc.rpt" "$W/b.kicad_pcb" > /dev/null 2>&1 || true
python3 - "$W/drc.rpt" "$N" <<'PY'
import re, sys, collections
s = open(sys.argv[1]).read(); c = collections.Counter(); open_ddr = set(); other_err = 0
for it in re.split(r'\n(?=\[)', s):
    m = re.match(r'\[(\w+)\]', it)
    if not m: continue
    k = m.group(1)
    if k == 'unconnected_items':
        for n in re.findall(r'\[([^\]]*ddr_[^\]]*)\]', it): open_ddr.add(n)
        continue
    if k in ('silk_overlap', 'silk_over_copper', 'silk_edge_clearance', 'lib_footprint_issues', 'lib_footprint_mismatch', 'via_dangling'): continue
    sev = 'warning' if '; warning' in it else 'error'
    if 'ddr_' not in it: other_err += sev == 'error'; continue
    c[(k, sev)] += 1
print(f"== {sys.argv[2]}: DDR nets with open pads {len(open_ddr)}  non-DDR DRC errors {other_err}")
for (k, sev), v in sorted(c.items(), key=lambda x: -x[1]): print(f"   {v:4} {k} ({sev})")
PY
~/dev/KiCadRoutingTools/.venv/bin/python "$R/tools/ddr/route_stats.py" "$W/b.kicad_pcb" | tail -6
