#!/usr/bin/env bash
# The haasoscope recipe on our board: U501 (Ti135) <-> U801 (LPDDR4); signal layers F/In2/In5/B, planes forbidden
set -u
K=~/dev/KiCadRoutingTools; P="$K/.venv/bin/python -X utf8"; cd "$(dirname "$0")"
L="--layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --layer-costs 1 -1 1 -1 -1 1 -1 1"
G="--track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.15"
step(){ n=$1; shift; echo "=== $n: $*" >> chain.log; s=$(date +%s); "$@" > $n.log 2>&1; echo "    exit $? in $(( $(date +%s)-s )) s" >> chain.log; grep -E "JSON_SUMMARY|Single-ended:|Diff pairs:|Under-pad escape|Plane drops" $n.log | grep -v "^  \[" | tail -4 | cut -c1-260 >> chain.log; for e in kicad_pro kicad_dru; do cp base.$e ${OUT}.$e 2>/dev/null; done; }
: > chain.log
OUT=f1 step f1 $P $K/py_router/bga_fanout.py base.kicad_pcb --component U501 --output f1.kicad_pcb --nets "*ddr_dqs*" "*ddr_ck_*" --diff-pairs "*ddr_dqs*" "*ddr_ck_*" --primary-escape vertical $L $G --plane-drop off --no-fix-drc-settings
OUT=f2 step f2 $P $K/py_router/bga_fanout.py f1.kicad_pcb --component U501 --output f2.kicad_pcb --nets "*ddr_dq*" "*ddr_dm*" "*ddr_ca*" "*ddr_cke*" "*ddr_cs*" "*ddr_rst*" --check-for-previous --primary-escape vertical $L $G --plane-drop off --no-fix-drc-settings
OUT=f3 step f3 $P $K/py_router/bga_fanout.py f2.kicad_pcb --component U801 --output f3.kicad_pcb --nets "*ddr_dqs*" "*ddr_ck_*" --diff-pairs "*ddr_dqs*" "*ddr_ck_*" --no-inner-top-layer $L --track-width 0.1 --clearance 0.1 --via-size 0.25 --via-drill 0.15 --plane-drop off --no-fix-drc-settings
OUT=fanned step f4 $P $K/py_router/bga_fanout.py f3.kicad_pcb --component U801 --output fanned.kicad_pcb --nets "*ddr_*" --check-for-previous --no-inner-top-layer $L --track-width 0.1 --clearance 0.1 --via-size 0.25 --via-drill 0.15 --plane-drop off --no-fix-drc-settings
RAM="--bga-proximity-radius 1 --stub-proximity-radius 1 --proximity-heuristic-factor 0.02 $G $L"
OUT=ramdiff step d1 $P $K/py_router/route_diff.py fanned.kicad_pcb ramdiff.kicad_pcb --nets "*ddr_dqs*" "*ddr_ck_*" --length-match-group "*ddr_dqs*" "*ddr_ck_*" --time-matching --mps-layer-swap --diff-pair-intra-match --heuristic-weight 1.5 $RAM
OUT=ram step r1 $P $K/py_router/route.py ramdiff.kicad_pcb ram.kicad_pcb --nets "*ddr_*" --length-match-group auto --time-matching --max-iterations 1000000 --no-bga-zones U801 $RAM
step c1 $P $K/py_router/check_drc.py ram.kicad_pcb --clearance 0.1 --nets "*ddr_*"
step c2 $P $K/py_router/check_connected.py ram.kicad_pcb --nets "*ddr_*"
echo "=== done" >> chain.log
