#!/usr/bin/env bash
# Regenerate the symbol library and every scripted sheet, rebuild the root sheet pins, run ERC.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/gen_symbols.py
for s in tools/sheets/[0-9][0-9]_*.py; do python3 "$s"; done
python3 tools/sync_root.py >/dev/null
mkdir -p reports
tools/p2k/bin/kicad-cli sch erc -o reports/erc.rpt kicad/ti135_card.kicad_sch 2>&1 | grep -v Font | tail -1
grep -E "^\[" reports/erc.rpt | sed 's/:.*//' | sort | uniq -c | sort -rn
# ERC does not flag a reference used on two sheets (sheet 5 once ran into C6xx), and the netlist merges them:
# count (reference, unit) over the sheet files
python3 -I - kicad/[0-9][0-9]_*.kicad_sch <<'PY'
import collections, re, sys
seen = collections.defaultdict(list)
for f in sys.argv[1:]:
    for m in re.finditer(r'\(lib_id "[^"]+"\)(.*?)\(property "Reference" "([^"]*)"', open(f).read(), re.S):
        unit = re.search(r'\(unit (\d+)\)', m.group(1))
        if not m.group(2).startswith("#"):
            seen[(m.group(2), unit.group(1) if unit else "1")].append(f.split("/")[-1])
dup = sorted(f"{r}({', '.join(fs)})" for (r, u), fs in seen.items() if len(fs) > 1)
print(f"references: {len(seen)} symbol units, duplicates:", " ".join(dup) if dup else "none")
sys.exit(1 if dup else 0)
PY
