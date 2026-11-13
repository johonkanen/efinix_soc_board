#!/usr/bin/env python3
"""Which nets' copper changed between two boards (KRT venv python): tools/ddr/copper_diff.py A.kicad_pcb B.kicad_pcb

Compares tracks (ends, width, layer) and vias (position, size, drill) per net, rounded to 1 um, and footprint
poses. Prints the changed nets grouped as LPDDR4 CA/CK, LPDDR4 bytes and the rest, then the moved footprints.
"""
import collections
import re
import sys

sys.path.insert(0, "/home/jari/dev/KiCadRoutingTools/py_router")
from kicad_parser import parse_kicad_pcb  # noqa: E402

CA = re.compile(r"ddr_(ca\d|cke0|ck_[PN]|cs\d_n)$")


def copper(f):
    pcb = parse_kicad_pcb(f)
    net = {n.net_id: n.name for n in pcb.nets.values()}
    c = collections.defaultdict(collections.Counter)
    r = lambda v: round(v, 3)  # noqa: E731
    for s in pcb.segments:
        a, b = sorted([(r(s.start_x), r(s.start_y)), (r(s.end_x), r(s.end_y))])
        c[net.get(s.net_id, "")][("t", a, b, r(s.width), s.layer)] += 1
    for v in pcb.vias:
        c[net.get(v.net_id, "")][("v", r(v.x), r(v.y), r(v.size), r(v.drill))] += 1
    fps = pcb.footprints.values() if isinstance(pcb.footprints, dict) else pcb.footprints
    poses = {fp.reference: (r(fp.x), r(fp.y), r(fp.rotation), fp.layer) for fp in fps}
    return c, poses


def group(n):
    s = n.split("/")[-1]
    if CA.search(s):
        return "CA/CK"
    return "bytes" if "ddr_" in s and "DDR_CAL" not in s else "rest"


(ca, pa), (cb, pb) = copper(sys.argv[1]), copper(sys.argv[2])
changed = collections.defaultdict(list)
for n in sorted(set(ca) | set(cb)):
    if ca.get(n) != cb.get(n):
        changed[group(n)].append(n.split("/")[-1] or "<no net>")
for g in ("CA/CK", "bytes", "rest"):
    print(f"{g}: {len(changed[g])} nets changed" + (f": {' '.join(changed[g])}" if changed[g] else ""))
moved = [k for k in sorted(set(pa) | set(pb)) if pa.get(k) != pb.get(k)]
print(f"footprints moved/added/removed: {len(moved)}" + (f": {' '.join(moved)}" if moved else ""))
