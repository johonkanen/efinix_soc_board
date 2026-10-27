#!/usr/bin/env bash
# Quick routing sketch of every remaining net (not LPDDR4, not the plane nets): tools/io_sketch.sh IN.kicad_pcb WORKDIR
# -> WORKDIR/r.kicad_pcb, graded as work/grade/<WORKDIR name>, picture WORKDIR/io_sketch.png.
# The Ethernet MDI pairs with route_diff (100 ohm), then one route.py --quick pass over the rest on F/In2/In5/B,
# 3V3 / 3V3_analog at 0.3 mm. --no-bga-zones (else KRT keeps every route off the BGA balls), clearance 0.11 (keeps the
# 0.175 mm via-hole rule), KICAD_RIP_PREEXISTING=0 (the LPDDR4 is not touched). A sketch: hole clearance and
# dangling stubs are not cleaned up.
set -u
R="$(cd "$(dirname "$0")/.." && pwd)"; IN=$(realpath "$1"); W="$2"; mkdir -p "$W"; cd "$W"
export KICAD_RIP_PREEXISTING=0
K=~/dev/KiCadRoutingTools; P="$K/.venv/bin/python -X utf8"
cp "$IN" in.kicad_pcb; for s in in d r; do for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" $s.$e; done; done
L="--layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --layer-costs 1 -1 1.2 -1 -1 1.2 -1 1.5"
C="--no-bga-zones --clearance 0.11 --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --board-edge-clearance 0.5"
$P $K/py_router/route_diff.py in.kicad_pcb d.kicad_pcb --nets "*eth_mdi_*" --impedance 100 --diff-pair-gap 0.15 --track-width 0.1 $L $C > d.log 2>&1
echo "diff: $(grep 'Diff pairs:' d.log | tail -1)"
$P $K/py_router/route.py d.kicad_pcb r.kicad_pcb --nets '*' '!*ddr_*' '!*eth_mdi_*' --track-width 0.1 \
  --power-nets '3V3' '3V3_analog' --power-nets-widths 0.3 0.3 --quick $L $C --max-iterations 1000000 --json-out r.json > r.log 2>&1
echo "single: $(grep 'Single-ended:' r.log | tail -1)"
for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" r.$e; done   # KRT relaxes floors in its copy; grade with ours
"$R/tools/ddr/grade.sh" "$(basename "$W")" r.kicad_pcb 2>&1 | grep -E "open pads"
grep -E "^\[" "$R/work/grade/$(basename "$W")/drc.rpt" | sed 's/:.*//' | sort | uniq -c | sort -rn
$P "$R/tools/render_board.py" r.kicad_pcb io_sketch.png 11
