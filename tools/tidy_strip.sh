#!/usr/bin/env bash
# Tidy the B.Cu strip north-east of U501 (user request 2026-11-12):  tools/tidy_strip.sh work/NAME
# 1. lifts the copper this project's scripts added there (rail stubs/vias, supply feeds, vcca_bl and the
#    DDR PLL supply), 2. moves the east-side bulk caps and C542 to F.Cu, 3. routes everything again at
#    45 degrees in a fixed order, 4. checks. Nothing that was on the board before phase 3 is removed.
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"; cd "$R"; D="$1"; K=tools/p2k/bin/kipy; PY=work/venv/bin/python
BOX="160 66 181.5 84"
tools/work_copy.sh new "$D"; rm -f "$D"/ops*.json
$K tools/rip_box.py "$D/b.kicad_pcb" 'vcca_bl|vddpll_mcb' 130 50 210 120 | tail -1
n=0
for f in reports/phase3_rail_vias_pass1_ops.json reports/phase3/rail_vias2_ops.json reports/phase3/opsA.json reports/phase3/opsB.json reports/phase6/ops*.json; do
  m=$($K tools/remove_ops.py "$D/b.kicad_pcb" "$f" '^(GND|1V1|1V8|VCORE|0V85|3V3)$' $BOX | tail -1 | awk '{print $2}'); n=$((n+m))
done
echo "lifted $n rail items in the strip"
$K tools/place_fix.py "$D/b.kicad_pcb" bulk_top 2>&1 | grep relocate
$K tools/dump_geom.py "$D/b.kicad_pcb" "$D/geom.json" | tail -1
C="--ddr-extra 0 --keep-pours '^5V0$'"; P=""; i=0
run(){ i=$((i+1)); eval "$PY tools/grid_router.py $D/geom.json $D/ops$i.json ${P:+--prev $P} $*" > "$D/log$i.txt"; echo "run $i: $(grep -c '^ok' $D/log$i.txt) ok, $(grep -c FAIL $D/log$i.txt) failed"; P="$P $D/ops$i.json"; }
SK="--skip-refs C5062,C5063,C5060,C502"
run "--nets 'vcca_bl' $SK --width 0.2 --max-len 8 $C"
run "--nets 'vcca_bl' $SK --width 0.12 --max-len 14 $C"
run "--plane-vias --nets '^VCORE$' '^0V85$' --width 0.2 --max-len 8 $C"
run "--plane-vias --nets '^VCORE$' '^0V85$' --width 0.12 --max-len 15 $C"
run "--nets 'vddpll_mcb' --width 0.12 --max-len 25 $C"
run "--plane-vias --nets '^GND$' '^1V1$' '^1V8$' '^3V3$' --width 0.2 --max-len 5 --keep-pours '^5V0$'"
run "--plane-vias --nets '^GND$' '^1V1$' '^1V8$' '^3V3$' --width 0.12 --max-len 20 $C"
run "--nets 'vcca_bl' --width 0.12 --max-len 14 $C"
for f in $P; do $K tools/apply_ops.py "$D/b.kicad_pcb" "$f" > /dev/null; done
# last resort for rail pads the router could not tie: a straight stub or a via beside the pad
$K tools/rail_vias.py "$D/b.kicad_pcb" --log "$D/rail_vias_last.json" | grep "new vias\|LEFT"
grep -h FAIL "$D"/log*.txt | sort | uniq -c | sort -rn | head -30
tools/work_copy.sh check "$D" | tail -7
python3 tools/drc_summary.py "$D/drc.json" -v | grep "^    " | cut -c1-220 | head
