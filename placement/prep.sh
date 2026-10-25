#!/usr/bin/env bash
# Placement inputs from kicad/ti135_card.kicad_pcb (KiCadRoutingTools plan-pcb-placement): lock the fixed parts,
# unplace the rest, flip the BGA/LPDDR4 decaps and the power supplies to B.Cu, emit and fix the intent, fit the buck cell templates.
set -euo pipefail
# Inputs kept here (groups.json, the hand fixes); the boards and runs go to work/place (not in git).
H="$(cd "$(dirname "$0")" && pwd)"
R="$(dirname "$H")"; W="$R/work/place"; K=~/dev/KiCadRoutingTools; P=$K/.venv/bin/python
mkdir -p "$W"; cd "$W"; cp "$H/groups.json" .
$P -X utf8 $K/py_placer/place_pose.py $R/kicad/ti135_card.kicad_pcb locked.kicad_pcb lock J3 J6 J9 J5 J1 J2 U501 U801 | tail -2
$P -X utf8 $K/.claude/skills/plan-pcb-placement/scripts/make_unplaced.py locked.kicad_pcb fixed.kicad_pcb --keep-locked | tail -2
for b in locked fixed; do cp $R/kicad/ti135_card.kicad_pro $b.kicad_pro; cp $R/kicad/ti135_card.kicad_dru $b.kicad_dru; done
$R/tools/p2k/bin/kipy "$H/flip_bottom.py" fixed.kicad_pcb
$P -X utf8 $K/py_tools/check_floorplan.py fixed.kicad_pcb --emit-intent intent.json > /dev/null 2>&1 || true
python3 "$H/fix_intent.py" intent.json
# buck cell templates (TI TLV62585 Figure 24; B.Cu variants in placement/sketches_B)
for sk in "$H"/sketches_B/U*.json; do   # cells are on B.Cu: mirrored sketches (TI135_PCB_NOTES.md 6.8)
    $P -X utf8 $K/py_tools/fit_template.py fixed.kicad_pcb --sketch "$sk" --intent intent.json --write-intent intent.json \
        | grep -E "^  (ground return|NOTE)" | grep -v ESTIMATED || true
done
cp intent.json "$H/intent.json"
