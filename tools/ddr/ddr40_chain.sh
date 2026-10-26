#!/usr/bin/env bash
# LPDDR4 at 40 ohm (NEXT_SESSION.md phase 4): re-route the data bytes and CK/CA at the impedance widths, then fit the
# widths to the JLC rules (tools/ddr/widen.py), re-apply the U501 package delays, grade and time.
#   tools/ddr/ddr40_chain.sh IN.kicad_pcb WORKDIR   -> WORKDIR/out.kicad_pcb, graded under work/grade/<WORKDIR name>
# KRT --impedance 40 gives 0.171 mm inner / 0.272 mm F/B (no solder mask in its microstrip model); widen.py clamps F/B
# to 0.25. DQS at 0.14 mm (the inner pair rule). Env: AMP (CA meander amplitude, 1.0), DQ_EXTRA (route.py options
# for DQ/DM, --ordering inside_out), TOL (byte time-match tolerance, 3 ps), BYTES (a routed bytes board: skip that step).
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; IN=$(realpath "$1"); W=$(realpath -m "$2"); mkdir -p "$W"; KP="$R/tools/p2k/bin/kipy"
pro(){ for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" "$1.$e"; done; }
if [ -z "${BYTES:-}" ]; then
  echo "-- bytes"; DQ_EXTRA="${DQ_EXTRA:---ordering inside_out}" WOPT="--impedance 40" DQS_WOPT="--track-width 0.14" \
    "$R/tools/ddr/byte_chain.sh" "$IN" "$W/bytes" 2>&1 | grep -E "^  (f|dqs|dq|fanned)|Moved" || true
  BYTES="$W/bytes/out.kicad_pcb"
fi
echo "-- CK/CA"; AMP=${AMP:-1.0} WOPT="--impedance 40" "$R/tools/ddr/ca_tb_chain.sh" "$(realpath "$BYTES")" "$W/ca" 2>&1 | grep -E "^(trunks|movers)" || true
cd "$W"; cp ca/out.kicad_pcb fit_in.kicad_pcb; pro fit_in
$KP "$R/tools/ddr/widen.py" fit_in.kicad_pcb out.kicad_pcb 2>&1 | grep -v "memory leak"
$KP "$R/tools/pad_to_die.py" out.kicad_pcb 2>&1 | grep pad_to_die; pro out
"$R/tools/ddr/grade.sh" "$(basename "$W")" out.kicad_pcb 2>&1 | grep -v "memory leak" | head -14
$KP "$R/tools/ddr/ddr_timing.py" "$R/work/grade/$(basename "$W")/b.kicad_pcb" 2>&1 | grep -v "Debug\|memory leak"
