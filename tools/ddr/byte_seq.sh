#!/usr/bin/env bash
# LPDDR4 data bytes routed one byte at a time, each matched before the next is routed (NEXT_SESSION.md phase 3,
# option 2):  tools/ddr/byte_seq.sh IN.kicad_pcb WORKDIR
# rip DQ/DM/DQS -> bga_fanout (as byte_chain.sh) -> for each byte in ORDER, on its primary layer LAYER_<k>:
#   route_diff its DQS pair (intra-pair matched) -> route.py its DQ/DM as one time-matched group with the DQS measured
#   from the board (KRT meanders the group right after routing it, while the corridor is still free) -> top-up with
#   tools/ddr/tune_meander.py to the byte's plan (DQ/DM 8..58 ps over DQS) -> next byte routes around those meanders
# -> widen.py -> pad_to_die -> grade + timing.  KRT may not rip nets outside a step (KICAD_RIP_PREEXISTING=0).
# Env: ORDER (bytes, "0 1 2 3"), LAYER_<k> (F.Cu / In2.Cu / In5.Cu / B.Cu; default In2 F In5 B), SIDE (cost of the other
# signal layers, 5), TOL (ps, 3), AMP (KRT meander amplitude, 0.8), CL (fan-out/route clearance, 0.11);
# NET_ORDER=far (MODE=net): farthest ball pair first. MODE=net routes each DQ/DM alone and meanders it to DQS + DQ_LO_NET (30 ps) before the next (default: one group).
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN=$(realpath "$1"); W="$2"; mkdir -p "$W"; cd "$W"
K=~/dev/KiCadRoutingTools; P="$K/.venv/bin/python -X utf8"; KP="$R/tools/p2k/bin/kipy"; CL=${CL:-0.11}
export KICAD_RIP_PREEXISTING=0
pro(){ for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" "$1.$e"; done; }
cp "$IN" in.kicad_pcb; pro in
# RIP_BYTES: redo only these bytes on a routed board (default all four); ORDER defaults to them
RB=${RIP_BYTES:-0 1 2 3}; ORDER=${ORDER:-$RB}
RX=""; FQ=""; FS=""
for k in $RB; do for i in 0 1 2 3 4 5 6 7; do RX="$RX|dq$((8*k+i))"; FS="$FS '*ddr_dq$((8*k+i))'"; done
  RX="$RX|dm$k|dqs${k}_[PN]"; FS="$FS '*ddr_dm$k'"; FQ="$FQ '*ddr_dqs${k}_*'"; done
$KP "$R/tools/ddr/rip_nets.py" in.kicad_pcb rip.kicad_pcb "ddr_(${RX#|})\$" 2>&1 | grep rip_nets; pro rip
LALL="--layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu"
L="$LALL --layer-costs 1 -1 1 -1 -1 1 -1 1"
FO="--escape-method auto --plane-drop off --no-fix-drc-settings --track-width 0.1 --clearance $CL --diff-pair-gap $CL"
fan(){ out=$1; shift; $P $K/py_router/bga_fanout.py "$@" > $out.log 2>&1 || true; pro $out; grep -oE '"requested": [0-9]+, "escaped": [0-9]+, "failed": [0-9]+' $out.log | tail -1 | sed "s/^/  $out: /"; }
eval fan f1 rip.kicad_pcb --component U501 --output f1.kicad_pcb --nets $FQ --diff-pairs $FQ --check-for-previous --primary-escape vertical $L $FO --via-size 0.3 --via-drill 0.15
eval fan f2 f1.kicad_pcb --component U501 --output f2.kicad_pcb --nets $FS --check-for-previous --primary-escape vertical $L $FO --via-size 0.3 --via-drill 0.15
# U801: pair gap 0.1 centres the pair in the 0.8 mm channel (byte_chain.sh)
eval fan f3 f2.kicad_pcb --component U801 --output f3.kicad_pcb --nets $FQ --diff-pairs $FQ --check-for-previous --no-inner-top-layer $L $FO --diff-pair-gap 0.1 --via-size 0.25 --via-drill 0.15
eval fan cur f3.kicad_pcb --component U801 --output cur.kicad_pcb --nets $FS --check-for-previous --no-inner-top-layer $L $FO --via-size 0.25 --via-drill 0.15
COMMON="--no-bga-zones U501 U801 --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --bga-proximity-radius 1 --stub-proximity-radius 1 --proximity-heuristic-factor 0.02 --board-edge-clearance 0.5"
declare -A DEF=([0]=In2.Cu [1]=F.Cu [2]=In5.Cu [3]=B.Cu)
costs(){  # layer-cost vector over F In1 In2 In3 In4 In5 In6 B: primary 1, other signal layers SIDE, planes forbidden
  local v=""; for l in F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu; do
    case $l in In1.Cu|In3.Cu|In4.Cu|In6.Cu) v="$v -1";; "$1") v="$v 1";; *) v="$v ${SIDE:-5}";; esac; done; echo $v; }
tune_to(){  # tune_to IN OUT "short net names" DQ_LO: pad-to-die, plan, meander only those nets, apply -> OUT
  $KP "$R/tools/ddr/widen.py" "$1" tp_in.kicad_pcb --split-only 2>&1 | grep -q split; pro tp_in   # whole runs outside the BGAs
  $KP "$R/tools/pad_to_die.py" tp_in.kicad_pcb 2>&1 | grep -q pad_to_die || true
  DQ_LO=$4 $KP "$R/tools/ddr/ddr_timing.py" tp_in.kicad_pcb --plan tp.full.json 2>&1 | grep -q plan || true
  python3 -c "import json,sys; d=json.load(open('tp.full.json')); w=set(sys.argv[1].split()); json.dump({n:v for n,v in d.items() if n.split('/')[-1] in w}, open('tp.json','w'))" "$3"
  $P "$R/tools/ddr/tune_meander.py" tp_in.kicad_pcb tp.json tp_ed.json --amp ${AMP:-0.8} --spacing 2 2>&1 | grep "^  ddr_" | sed 's/^/   /' || true
  $KP "$R/tools/ddr/tune_apply.py" tp_in.kicad_pcb tp_ed.json "$2" 2>&1 | grep -q tune_apply; pro "${2%.kicad_pcb}"
}
for k in $ORDER; do
  eval "LY=\${LAYER_$k:-${DEF[$k]}}"; LC="$LALL --layer-costs $(costs $LY)"
  $P $K/py_router/route_diff.py cur.kicad_pcb s$k.kicad_pcb --nets "*ddr_dqs${k}_*" --diff-pair-intra-match --diff-pair-gap 0.15 \
    --heuristic-weight 1.5 --track-width 0.14 $LC $COMMON --clearance 0.1 > dqs$k.log 2>&1 || true
  pro s$k
  NETS=""; for i in 0 1 2 3 4 5 6 7; do NETS="$NETS dq$((8*k+i))"; done; NETS="$NETS dm$k"
  if [ "${NET_ORDER:-}" = far ]; then  # farthest U501-U801 ball pair first: the long nets take the short paths
    NETS=$($P - cur.kicad_pcb $NETS <<'PY'
import sys, math
sys.path.insert(0, __import__("os").path.expanduser("~/dev/KiCadRoutingTools/py_router"))
from kicad_parser import parse_kicad_pcb
p = parse_kicad_pcb(sys.argv[1]); d = {}
for n in sys.argv[2:]:
    nid = [i for i, x in p.nets.items() if x.name.endswith("ddr_" + n)][0]
    a = [q for q in p.pads_by_net[nid] if q.component_ref == "U501"][0]; b = [q for q in p.pads_by_net[nid] if q.component_ref == "U801"][0]
    d[n] = abs(a.global_x - b.global_x) + abs(a.global_y - b.global_y)
print(" ".join(sorted(d, key=lambda n: -d[n])))
PY
)
  fi
  if [ "${MODE:-group}" = net ]; then
    # meander as you go: each DQ/DM is routed alone and meandered to its DQS + DQ_LO before the next one routes,
    # so the next routes around the meanders instead of packing against a straight neighbour
    cp s$k.kicad_pcb cur.kicad_pcb; pro cur; got=0
    for n in $NETS; do
      $P $K/py_router/route.py cur.kicad_pcb n.kicad_pcb --nets "*ddr_$n" --impedance 40 --max-iterations 1000000 \
        $LC $COMMON --clearance $CL > r_$n.log 2>&1 || true
      pro n; grep -q "1/1 routed" r_$n.log && got=$((got+1))
      tune_to n.kicad_pcb cur.kicad_pcb "ddr_$n" ${DQ_LO_NET:-30}
    done
    tune_to cur.kicad_pcb cur.kicad_pcb "ddr_dqs${k}_P ddr_dqs${k}_N" ${DQ_LO_NET:-30}   # DQS up if a DQ ran long
    echo "  byte $k on $LY: $(grep -E 'Diff pairs:' dqs$k.log | tail -1 | sed 's/  */ /g') | net by net: $got/9 routed"
    continue
  fi
  N=""; for n in $NETS; do N="$N '/08 lpddr4/ddr_$n'"; done
  eval "$P $K/py_router/route.py s$k.kicad_pcb r$k.kicad_pcb --nets $N --length-match-group $N '/08 lpddr4/ddr_dqs${k}_[PN]' \
    --time-matching --time-match-tolerance ${TOL:-3} --meander-amplitude ${AMP:-0.8} --impedance 40 --max-iterations 1000000 \
    $LC $COMMON --clearance $CL --json-out r$k.json" > r$k.log 2>&1 || true
  pro r$k
  $KP "$R/tools/pad_to_die.py" r$k.kicad_pcb 2>&1 | grep -q pad_to_die || true   # the plan needs the package delays
  $KP "$R/tools/ddr/ddr_timing.py" r$k.kicad_pcb --plan plan$k.full.json 2>&1 | grep -q plan || true
  python3 - plan$k.full.json plan$k.json $k <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1])); k = int(sys.argv[3])
mine = {f"ddr_dq{8 * k + i}" for i in range(8)} | {f"ddr_dm{k}", f"ddr_dqs{k}_P", f"ddr_dqs{k}_N"}
json.dump({n: v for n, v in d.items() if n.split("/")[-1] in mine}, open(sys.argv[2], "w"))
PY
  $P "$R/tools/ddr/tune_meander.py" r$k.kicad_pcb plan$k.json ed$k.json --amp ${AMP:-0.8} --spacing 2 2>&1 | grep "^tune_meander" | sed "s/^/  byte $k: /"
  $KP "$R/tools/ddr/tune_apply.py" r$k.kicad_pcb ed$k.json cur.kicad_pcb 2>&1 | grep -q tune_apply; pro cur
  echo "  byte $k on $LY: $(grep -E 'Diff pairs:' dqs$k.log | tail -1 | sed 's/  */ /g') | $(grep 'Single-ended:' r$k.log | tail -1 | sed 's/  */ /g')"
done
$KP "$R/tools/ddr/widen.py" cur.kicad_pcb out.kicad_pcb 2>&1 | grep -v "memory leak"
$KP "$R/tools/pad_to_die.py" out.kicad_pcb 2>&1 | grep -q pad_to_die; pro out
"$R/tools/ddr/grade.sh" "$(basename "$W")" out.kicad_pcb 2>&1 | grep -v "memory leak" | head -9
$KP "$R/tools/ddr/ddr_timing.py" "$R/work/grade/$(basename "$W")/b.kicad_pcb" --nets 2>&1 | grep -v "Debug\|memory leak\|^   ddr_" | head -10
