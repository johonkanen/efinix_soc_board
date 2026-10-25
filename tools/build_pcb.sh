#!/usr/bin/env bash
# (Re)create kicad/ti135_card.kicad_pcb from the schematic, then DRC with schematic parity.
# Rebuilds the board from scratch: use only until manual placement/routing starts (STATUS.md).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/gen_footprints.py
tools/p2k/bin/kipy tools/make_board.py
python3 tools/board_setup.py
mkdir -p reports
tools/p2k/bin/kicad-cli pcb drc --schematic-parity -o reports/drc.rpt kicad/ti135_card.kicad_pcb 2>&1 | grep -v Font | tail -3
grep -E "^\[" reports/drc.rpt | sed 's/:.*//' | sort | uniq -c | sort -rn
