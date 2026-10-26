#!/usr/bin/env bash
# LPDDR4 data bytes re-route (NEXT_SESSION.md phase 2) on a copy:  tools/ddr/byte_chain.sh IN.kicad_pcb WORKDIR
# rip DQ/DM/DQS -> bga_fanout pairs then singles (U501, U801) -> route_diff DQS -> route.py DQ/DM, one time-matched
# group per byte incl. its DQS -> cap pass -> grade + timing.   Env: CL (clearance, 0.11), LAYERS_<n> optional;
# WOPT / DQS_WOPT: DQ/DM and DQS width options (default --track-width 0.1; e.g. --impedance 40 / --impedance 80).
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN=$(realpath "$1"); W="$2"; mkdir -p "$W"; cd "$W"
K=~/dev/KiCadRoutingTools; P="$K/.venv/bin/python -X utf8"; KP="$R/tools/p2k/bin/kipy"; CL=${CL:-0.11}
pro(){ for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" "$1.$e"; done; }
cp "$IN" in.kicad_pcb; pro in
$KP "$R/tools/ddr/rip_nets.py" in.kicad_pcb rip.kicad_pcb 'ddr_(dq[0-9]+|dm[0-3]|dqs[0-3]_[PN])' 2>&1 | grep rip_nets; pro rip
L="--layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --layer-costs 1 -1 1 -1 -1 1 -1 1"
FO="--escape-method auto --plane-drop off --no-fix-drc-settings --track-width 0.1 --clearance $CL --diff-pair-gap $CL"
fan(){ out=$1; shift; $P $K/py_router/bga_fanout.py "$@" > $out.log 2>&1 || true; pro $out; grep -oE '"requested": [0-9]+, "escaped": [0-9]+, "failed": [0-9]+' $out.log | tail -1 | sed "s/^/  $out: /"; }
fan f1 rip.kicad_pcb --component U501 --output f1.kicad_pcb --nets "*ddr_dqs*" --diff-pairs "*ddr_dqs*" --primary-escape ${DQS_ESC:-vertical} $L $FO --via-size 0.3 --via-drill 0.15
fan f2 f1.kicad_pcb --component U501 --output f2.kicad_pcb --nets "*ddr_dq[0-9]*" "*ddr_dm*" --check-for-previous --primary-escape vertical $L $FO --via-size 0.3 --via-drill 0.15
# U801: pair gap 0.1 centres the pair in the 0.8 mm channel: 0.175 mm to both via holes (0.11 gives 0.170). route_diff
# skips pairs whose stub gap is below its clearance, so DQS route at the class clearance 0.1 (DQS_CL).
fan f3 f2.kicad_pcb --component U801 --output f3.kicad_pcb --nets "*ddr_dqs*" --diff-pairs "*ddr_dqs*" --no-inner-top-layer $L $FO --diff-pair-gap 0.1 --via-size 0.25 --via-drill 0.15
fan fanned f3.kicad_pcb --component U801 --output fanned.kicad_pcb --nets "*ddr_dq[0-9]*" "*ddr_dm*" --check-for-previous --no-inner-top-layer $L $FO --via-size 0.25 --via-drill 0.15
COMMON="--no-bga-zones U501 U801 $L --clearance $CL --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --bga-proximity-radius 1 --stub-proximity-radius 1 --proximity-heuristic-factor 0.02"
if [ "${DQS_MODE:-pair}" = single ]; then   # DQS halves as single nets inside the byte groups (P/N matched by the group)
  cp fanned.kicad_pcb dqs.kicad_pcb; echo "Diff pairs: skipped (DQS_MODE=single)" > dqs.log; DQS_NETS="'*ddr_dqs*'"
else DQS_NETS=""
$P $K/py_router/route_diff.py fanned.kicad_pcb dqs.kicad_pcb --nets "*ddr_dqs*" ${DQS_EXTRA:-} --diff-pair-intra-match --diff-pair-gap 0.15 --heuristic-weight 1.5 --mps-layer-swap ${DQS_WOPT:---track-width 0.1} $COMMON --clearance ${DQS_CL:-0.1} > dqs.log 2>&1 || true
fi
pro dqs; echo "  dqs: $(grep -E 'Diff pairs:' dqs.log | tail -1) $(grep -oE '"single_ended_diff_pairs": \[[^]]*\]' dqs.log | tail -1)"
G=""; for k in 0 1 2 3; do NETS=""; for i in 0 1 2 3 4 5 6 7; do NETS="$NETS '/08 lpddr4/ddr_dq$((8*k+i))'"; done; G="$G --length-match-group $NETS '/08 lpddr4/ddr_dm$k' '/08 lpddr4/ddr_dqs${k}_[PN]'"; done
eval "$P $K/py_router/route.py dqs.kicad_pcb dq.kicad_pcb --nets '*ddr_dq[0-9]*' '*ddr_dm*' ${DQS_NETS:-} $G --time-matching --time-match-tolerance ${TOL:-3} --max-iterations 1000000 ${DQ_EXTRA:-} ${WOPT:---track-width 0.1} $COMMON --json-out dq.json" > dq.log 2>&1 || true
pro dq; echo "  dq: $(grep 'Single-ended:' dq.log | tail -1)"
$P $K/py_placer/place_fanout_clearance.py dq.kicad_pcb out.kicad_pcb --clearance 0.13 --step 0.1 --max-displacement-cap 5 2>&1 | grep -E "^Moved|Unresolved" || true
pro out
"$R/tools/ddr/grade.sh" "$(basename "$W")" out.kicad_pcb 2>&1 | grep -v "memory leak" | head -12
$KP "$R/tools/ddr/ddr_timing.py" "$R/work/grade/$(basename "$W")/b.kicad_pcb" 2>&1 | grep -v "Debug\|memory leak" | head -8
