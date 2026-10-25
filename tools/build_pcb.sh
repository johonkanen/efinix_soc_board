#!/usr/bin/env bash
# PCB build: footprints, stack-up / net classes / DRC rules, DRC with schematic parity.
#   tools/build_pcb.sh                     keep the board as it is (placement done in it)
#   tools/build_pcb.sh --rebuild [PLACED]  recreate the board from the schematic (tools/make_board.py), then copy the
#                                          footprint poses back from PLACED (default: the board as it was before the
#                                          rebuild) with tools/apply_placement.py. Only until routing starts: it drops
#                                          everything else on the board. After that, use pcbnew's "Update PCB from
#                                          Schematic".
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/gen_footprints.py
if [[ "${1:-}" == "--rebuild" ]]; then
    mkdir -p reports
    placed="${2:-reports/placed_before_rebuild.kicad_pcb}"
    [[ -n "${2:-}" ]] || cp kicad/ti135_card.kicad_pcb "$placed"
    tools/p2k/bin/kipy tools/make_board.py
    tools/p2k/bin/kipy tools/apply_placement.py "$placed" 2>&1 | grep -v "Debug: Adding duplicate"
fi
python3 tools/board_setup.py
tools/p2k/bin/kipy tools/pad_to_die.py 2>&1 | grep -v "Debug: Adding duplicate"
mkdir -p reports
tools/p2k/bin/kicad-cli pcb drc --schematic-parity -o reports/drc.rpt kicad/ti135_card.kicad_pcb 2>&1 | grep -v Font | tail -3
grep -E "^\[" reports/drc.rpt | sed 's/:.*//' | sort | uniq -c | sort -rn
