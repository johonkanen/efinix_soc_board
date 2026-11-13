#!/bin/bash
# Board side of the TLV62585 -> AP61302 / AP61102 change (2026-11-13), after `python3 tools/ap61_cells.py sch`.
#   tools/ap61_layout.sh WORKDIR      WORKDIR/kicad/ti135_card.kicad_pcb is rebuilt in place (copy the project
#                                     files and lib/ beside it first); intermediate boards a0..a4 stay there.
# Steps: pad nets and fields, strip the old cells, clear foreign copper, place the mirrored cells
# (tools/buck_cell.py), reshape the 5V0 feeder, route pg_group1 to the new PG / EN pins, reconnect loose rail
# pads, remove dangling leftovers.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
W=$1/kicad
source "$HERE/p2k/bin/kicad_env.sh"
K="$HERE/p2k/bin/kipy"
q() { grep -v -e swig -e Debug || true; }
cp $W/ti135_card.kicad_pcb $W/orig.kicad_pcb
$K $HERE/ap61_cells.py board $W/orig.kicad_pcb $W/a0.kicad_pcb 2>&1 | q
$K $HERE/buck_cell.py --strip $W/a0.kicad_pcb $W/a1.kicad_pcb 2>&1 | q
$K $HERE/ap61_cells.py prep $W/a1.kicad_pcb $W/a1p.kicad_pcb 2>&1 | q
BUCK_SHIFT_HOME=1 $K $HERE/buck_cell.py $W/a1p.kicad_pcb $W/a2.kicad_pcb 2>&1 | q
$K $HERE/shape_5v0.py $W/a2.kicad_pcb $W/a3.kicad_pcb 2>&1 | q
(cd $W && KICAD_RIP_PREEXISTING=0 ~/dev/KiCadRoutingTools/.venv/bin/python -X utf8 ~/dev/KiCadRoutingTools/py_router/route.py \
    a3.kicad_pcb a4.kicad_pcb --nets "/pg_group1" --layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu \
    --track-width 0.15 --clearance 0.11 --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --no-bga-zones U501 \
    --no-fix-drc-settings --board-edge-clearance 0.5 --escalation off --layer-costs 1 -1 1 -1 -1 1 -1 1 > a4.log 2>&1)
grep -E "Single-ended|Multi-point" $W/a4.log
B=$W/ti135_card.kicad_pcb
cp $W/a4.kicad_pcb $B
$K - <<PY 2>&1 | q
import pcbnew
b = pcbnew.LoadBoard("$B"); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard("$B", b)
PY
kicad-cli pcb drc --format json --severity-all -o $W/d.json $B > /dev/null 2>&1
$K $HERE/decap_connect.py $B $B --all $W/d.json 2>&1 | q | grep -E "loose|left open"
for r in 1 2 3 4 5 6 7 8; do
    kicad-cli pcb drc --format json --severity-all -o $W/d.json $B > /dev/null 2>&1
    n=$(python3 -c "import json;d=json.load(open('$W/d.json'));print(sum('dangling' in v['type'] for v in d['violations']), len(d['unconnected_items']))")
    echo "round $r: dangling, unconnected = $n"
    [ "${n%% *}" = 0 ] && break
    $K $HERE/drop_dangling.py $B $B $W/d.json 2>&1 | q | tail -1
done
