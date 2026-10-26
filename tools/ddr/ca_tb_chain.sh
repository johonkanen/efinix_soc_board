#!/usr/bin/env bash
# CK/CA trunk-and-branch re-route on a copy of the board (NEXT_SESSION.md / KRT_LEARNING.md):
#   tools/ddr/ca_tb_chain.sh IN.kicad_pcb WORKDIR   -> WORKDIR/out.kicad_pcb, graded under work/grade/<WORKDIR name>
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN=$(realpath "$1"); W="$2"; mkdir -p "$W"; cd "$W"
K=~/dev/KiCadRoutingTools; P="$K/.venv/bin/python -X utf8"; KP="$R/tools/p2k/bin/kipy"
pro(){ for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" "$1.$e"; done; }
cp "$IN" in.kicad_pcb; pro in
COMMON="--no-bga-zones U501 U801 --layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --layer-costs 1.5 -1 1.2 -1 -1 1 -1 2 --track-width 0.1 --clearance 0.11 --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --bga-proximity-radius 1 --proximity-heuristic-factor 0.02 --max-iterations 1000000"
$KP "$R/tools/ddr/ca_trunk_branch.py" prep in.kicad_pcb prep.kicad_pcb 2>&1 | grep "ca_trunk"; pro prep
N="'/08 lpddr4/ddr_ca[0-5]' '/08 lpddr4/ddr_cke0' '/08 lpddr4/ddr_ck_[PN]' '/08 lpddr4/ddr_cs[02]_n'"   # group patterns: only * and [..] are wildcards (? is literal)
eval "$P $K/py_router/route.py prep.kicad_pcb trunk.kicad_pcb --nets $N --length-match-group $N --length-match-tolerance 0.1 --time-matching --meander-amplitude ${AMP:-1.0} $COMMON --json-out trunk.json" > trunk.log 2>&1 || true
echo "trunks: $(grep 'Single-ended:' trunk.log | tail -1)"; pro trunk
$KP "$R/tools/ddr/ca_trunk_branch.py" finish trunk.kicad_pcb fin.kicad_pcb 2>&1 | grep "ca_trunk"; pro fin
M=$(sed 's#^#"/08 lpddr4/#; s#$#"#' movers.txt | tr '\n' ' ')
eval "$P $K/py_router/route.py fin.kicad_pcb movers.kicad_pcb --nets $M --length-match-group auto --time-matching $COMMON --json-out movers.json" > movers.log 2>&1 || true
echo "movers: $(grep 'Single-ended:' movers.log | tail -1)"; pro movers
$P $K/py_placer/place_fanout_clearance.py movers.kicad_pcb out.kicad_pcb --clearance 0.13 --step 0.1 --max-displacement-cap 5 2>&1 | grep -E "^Moved|Unresolved" || true
pro out
$KP "$R/tools/pad_to_die.py" out.kicad_pcb 2>&1 | grep pad_to_die   # re-apply the U501 package delays
"$R/tools/ddr/grade.sh" "$(basename "$W")" out.kicad_pcb 2>&1 | grep -v "memory leak" | head -12
$KP "$R/tools/ddr/ddr_timing.py" "$R/work/grade/$(basename "$W")/b.kicad_pcb" 2>&1 | grep -v "Debug\|memory leak"
