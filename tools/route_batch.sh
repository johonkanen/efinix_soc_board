#!/usr/bin/env bash
# One routing batch on a fresh work copy:  tools/route_batch.sh work/NAME 'ROUTER ARGS' ['ROUTER ARGS' ...]
# Each argument string is one grid_router.py run (run in order, each seeing the earlier ones); then all
# are applied and the copy is checked (verify_protected, zone refill, DRC). Accept with work_copy.sh accept.
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"; cd "$R"; D="$1"; shift; K=tools/p2k/bin/kipy; PY=work/venv/bin/python
tools/work_copy.sh new "$D"; rm -f "$D"/ops*.json
$K tools/dump_geom.py "$D/b.kicad_pcb" "$D/geom.json" | tail -1
i=0; prev=""
for args in "$@"; do
  i=$((i+1))
  eval "$PY tools/grid_router.py $D/geom.json $D/ops$i.json ${prev:+--prev $prev} $args" | grep "FAIL\|routed" || true
  prev="$prev $D/ops$i.json"
done
[ -n "$DROP" ] && python3 - "$D" "$DROP" <<'PYE'
import json, sys, glob, re
for f in glob.glob(sys.argv[1] + "/ops*.json"):
    d = json.load(open(f))
    for k in ("tracks", "vias"):
        d[k] = [x for x in d[k] if not re.search(sys.argv[2], x["net"])]
    json.dump(d, open(f, "w"))
PYE
for f in $prev; do $K tools/apply_ops.py "$D/b.kicad_pcb" "$f" | tail -1; done
tools/work_copy.sh check "$D"
python3 tools/drc_summary.py "$D/drc.json" -v | grep "^    " | cut -c1-240 | head -20
