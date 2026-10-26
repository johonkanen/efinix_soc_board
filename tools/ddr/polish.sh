#!/usr/bin/env bash
# One delay-tuning pass over a routed board (NEXT_SESSION.md phase 3):  tools/ddr/polish.sh IN.kicad_pcb OUT.kicad_pcb
# split at the courtyards -> pad-to-die -> ddr_timing.py --plan (DQ_LO/DQ_HI, 8/58 ps) -> tune_meander.py -> tune_apply.py
# -> widen.py (fit, clearance repair) -> pad-to-die. Env: AMP (0.8), SPACING (2), ONLY (space-separated short net names).
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN=$(realpath "$1"); OUT=$(realpath -m "$2"); W=$(dirname "$OUT")/polish_tmp
mkdir -p "$W"; KP="$R/tools/p2k/bin/kipy"; P="$HOME/dev/KiCadRoutingTools/.venv/bin/python -X utf8"
pro(){ for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" "${1%.kicad_pcb}.$e"; done; }
pro "$W/in.kicad_pcb"
$KP "$R/tools/ddr/widen.py" "$IN" "$W/in.kicad_pcb" --split-only 2>&1 | grep -q split
$KP "$R/tools/pad_to_die.py" "$W/in.kicad_pcb" 2>&1 | grep -q pad_to_die || true
$KP "$R/tools/ddr/ddr_timing.py" "$W/in.kicad_pcb" --plan "$W/plan.json" 2>&1 | grep "^plan" || true
[ -n "${ONLY:-}" ] && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); w=set(sys.argv[2].split()); json.dump({n:v for n,v in d.items() if n.split('/')[-1] in w}, open(sys.argv[1],'w'))" "$W/plan.json" "$ONLY"
$P "$R/tools/ddr/tune_meander.py" "$W/in.kicad_pcb" "$W/plan.json" "$W/ed.json" --amp ${AMP:-0.8} --spacing ${SPACING:-2} 2>&1 | grep "^tune_meander"
$KP "$R/tools/ddr/tune_apply.py" "$W/in.kicad_pcb" "$W/ed.json" "$W/tuned.kicad_pcb" 2>&1 | grep -q tune_apply; pro "$W/tuned.kicad_pcb"
$KP "$R/tools/ddr/widen.py" "$W/tuned.kicad_pcb" "$OUT" 2>&1 | grep -v "memory leak"
$KP "$R/tools/pad_to_die.py" "$OUT" 2>&1 | grep -q pad_to_die; pro "$OUT"
