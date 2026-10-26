#!/usr/bin/env bash
# KiCad's own delay per LPDDR4 net (time-domain tuning profiles + pad-to-die), via a probe DRC rule on a copy:
#   tools/ddr/kicad_delays.sh [BOARD] > delays.csv      (net,kicad_ps)
# KiCad sums a net's whole copper: a shared CA/CK net reads path + its second branch (tools/ddr/ddr_timing.py --kicad).
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; B="${1:-$R/kicad/ti135_card.kicad_pcb}"; W=$(mktemp -d)
cp "$B" "$W/p.kicad_pcb"; cp "$R/kicad/ti135_card.kicad_pro" "$W/p.kicad_pro"; cp "$R/kicad/ti135_card.kicad_dru" "$W/p.kicad_dru"
printf '\n(rule "probe_delay"\n\t(condition "A.hasNetclass(%s) || A.hasNetclass(%s) || A.hasNetclass(%s)")\n\t(constraint length (min 1ps) (max 2ps)))\n' \
    "'lpddr_ca'" "'lpddr_diff'" "'lpddr_dq'" >> "$W/p.kicad_dru"
"$R/tools/p2k/bin/kicad-cli" pcb drc --severity-all -o "$W/p.rpt" "$W/p.kicad_pcb" > /dev/null 2>&1 || true
python3 - "$W/p.rpt" <<'PY'
import re, sys
s = open(sys.argv[1]).read(); print("net,kicad_ps")
for it in re.split(r'\n(?=\[)', s):
    if it.startswith("[length_out_of_range]") and "probe_delay" in it:
        a = re.search(r"actual ([0-9.]+) ps", it); n = re.search(r"\[([^\]]*ddr_[^\]]*)\]", it)
        if a and n: print(f"{n.group(1).split('/')[-1]},{a.group(1)}")
PY
rm -rf "$W"
