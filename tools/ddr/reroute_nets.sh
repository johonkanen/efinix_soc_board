#!/usr/bin/env bash
# Re-route a few LPDDR4 nets at the 40 ohm width without necking (NEXT_SESSION.md phase 4):
#   tools/ddr/reroute_nets.sh IN.kicad_pcb WORKDIR NET...   (NET = the name after ddr_, e.g. dm0 dq18 rst_n)
# rip the nets -> bga_fanout them on U501 and U801 (around the copper already there) -> route.py --impedance 40
# --escalation off (a net that cannot complete at width fails instead of necking down) -> widen.py fit -> grade.
# A net that fails keeps its old copper: the output is the input with only the nets that routed replaced.
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN=$(realpath "$1"); W="$2"; shift 2; mkdir -p "$W"; cd "$W"
K=~/dev/KiCadRoutingTools; P="$K/.venv/bin/python -X utf8"; KP="$R/tools/p2k/bin/kipy"; CL=${CL:-0.11}
pro(){ for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" "$1.$e"; done; }
RE="ddr_($(IFS='|'; echo "$*"))\$"; PAT=""; for n in "$@"; do PAT="$PAT '*ddr_$n'"; done
cp "$IN" in.kicad_pcb; pro in
$KP "$R/tools/ddr/rip_nets.py" in.kicad_pcb rip.kicad_pcb "$RE" 2>&1 | grep rip_nets; pro rip
L="--layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --layer-costs 1 -1 1 -1 -1 1 -1 1"
FO="--escape-method auto --plane-drop off --no-fix-drc-settings --track-width 0.1 --clearance $CL --check-for-previous"
eval "$P $K/py_router/bga_fanout.py rip.kicad_pcb --component U501 --output f1.kicad_pcb --nets $PAT --primary-escape vertical $L $FO --via-size 0.3 --via-drill 0.15" > f1.log 2>&1 || true; pro f1
eval "$P $K/py_router/bga_fanout.py f1.kicad_pcb --component U801 --output fanned.kicad_pcb --nets $PAT --no-inner-top-layer $L $FO --via-size 0.25 --via-drill 0.15" > f2.log 2>&1 || true; pro fanned
eval "$P $K/py_router/route.py fanned.kicad_pcb routed.kicad_pcb --nets $PAT --impedance 40 --escalation off --no-bga-zones U501 U801 $L --clearance $CL --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --bga-proximity-radius 1 --stub-proximity-radius 1 --proximity-heuristic-factor 0.02 --max-iterations 1000000 ${EXTRA:-} --json-out routed.json" > routed.log 2>&1 || true
pro routed; echo "  route: $(grep 'Single-ended:' routed.log | tail -1)"
$KP "$R/tools/ddr/widen.py" routed.kicad_pcb out.kicad_pcb 2>&1 | grep -v "memory leak"
$KP "$R/tools/pad_to_die.py" out.kicad_pcb 2>&1 | grep pad_to_die; pro out
"$R/tools/ddr/grade.sh" "$(basename "$W")" out.kicad_pcb 2>&1 | grep -v "memory leak" | head -9
