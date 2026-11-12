#!/usr/bin/env bash
# Work-copy helper: every board edit runs on a copy, is checked, and only then goes into kicad/.
#   tools/work_copy.sh new DIR          copy the board, project and rules to DIR/b.kicad_*
#   tools/work_copy.sh check DIR        verify_protected + zone refill + DRC on DIR/b.kicad_pcb (the refilled board is
#                                       saved), summary vs the previous DRC. DIR must be work/NAME: the footprint
#                                       library is found through the work/lib link.
#   tools/work_copy.sh accept DIR       copy DIR/b.kicad_pcb back to kicad/ (refuses if verify_protected fails
#                                       or KiCad holds a lock)
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"; cd "$R"; D="$2"; K=tools/p2k/bin
case "$1" in
new) mkdir -p "$D"; for e in pcb pro dru; do cp kicad/ti135_card.kicad_$e "$D/b.kicad_$e"; done; cp kicad/*.kicad_sch kicad/fp-lib-table kicad/sym-lib-table "$D/" 2>/dev/null; cp "$D/ti135_card.kicad_sch" "$D/b.kicad_sch";;
check)
  $K/kipy verify_protected.py check "$D/b.kicad_pcb" 2>&1 | grep -v Font | tail -5
  $K/kicad-cli pcb drc --refill-zones --save-board --schematic-parity --severity-all --format json -o "$D/drc.json" "$D/b.kicad_pcb" > /dev/null 2>&1 || true
  python3 tools/drc_summary.py "$D/drc.json" "${3:-reports/drc_last.json}";;
accept)
  ls kicad/*.lck > /dev/null 2>&1 && { echo "KiCad lock file present: not copying"; exit 1; }
  $K/kipy verify_protected.py check "$D/b.kicad_pcb" 2>&1 | tail -1 | grep -q OK || { echo "verify_protected failed: not copying"; exit 1; }
  cp "$D/b.kicad_pcb" kicad/ti135_card.kicad_pcb; mkdir -p reports; cp "$D/drc.json" reports/drc_last.json; echo accepted;;
esac
