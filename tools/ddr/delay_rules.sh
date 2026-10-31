#!/usr/bin/env bash
# LPDDR4 delay targets as DRC length rules, so pcbnew's tuners and DRC know them:
#   tools/ddr/delay_rules.sh [DRU]      (default kicad/ti135_card.kicad_dru)
# Reads KiCad's delay per net (kicad_delays.sh), computes the targets (ddr_timing.py --kicad) and replaces the block
# between the "generated delay targets" markers at the end of the rules file. The targets are absolute (ps, die to die)
# and follow from the longest net of each group: rerun after rerouting a net.
# DRC reads the whole net, the tuner the pad-to-pad path; on the shared CA/CK nets these differ by the second branch:
# their rules have min/opt in path terms and max = path + tol + branch, so the tuner catches short and DRC long.
set -eu
R="$(cd "$(dirname "$0")/../.." && pwd)"; DRU="${1:-$R/kicad/ti135_card.kicad_dru}"; W=$(mktemp -d)
"$R/tools/ddr/kicad_delays.sh" > "$W/delays.csv"
"$R/tools/p2k/bin/kipy" "$R/tools/ddr/ddr_timing.py" --kicad "$W/delays.csv" --rules "$W/rules.txt"
python3 - "$DRU" "$W/rules.txt" <<'PY'
import sys
dru, rules = sys.argv[1], open(sys.argv[2]).read()
BEGIN = "# ---- BEGIN generated delay targets (tools/ddr/delay_rules.sh; do not edit by hand) ----"
END = "# ---- END generated delay targets ----"
s = open(dru).read()
if BEGIN in s:
    s = s[:s.index(BEGIN)].rstrip("\n") + "\n" + s[s.index(END) + len(END):].lstrip("\n")
s = s.rstrip("\n") + "\n\n" + BEGIN + "\n" + rules + END + "\n"
open(dru, "w").write(s)
PY
rm -rf "$W"
