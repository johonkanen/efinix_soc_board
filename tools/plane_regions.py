#!/usr/bin/env python3
"""Plane regions for kicad/ti135_card.kicad_pcb (TI135_PCB_NOTES.md §6.6) -> placement/planes.json.

Run with a python that has shapely (~/dev/KiCadRoutingTools/.venv/bin/python); tools/apply_planes.py (kipy) turns
the JSON into zones. Inside U501 each split layer is divided between that layer's supply balls (nearest ball per grid cell), so
every ball's via-in-pad lands in its own net's copper; outside the BGA the regions are drawn here.
  In1, In6  GND, whole board
  In3       1V1: U501 cells + north block (U801, DDR corridor) + east band to L341
            VCORE: U501 cells + east corridor to L201 (B.Cu cell)
            GND: the rest (priority 0)
  In4       0V85: U501 cells + corridor to L331;  1V8: the rest
  B.Cu      5V0: J6 and the five TLV62585 inputs (all on B.Cu, reached by fill, no vias)
3V3 is not a plane: routed as a power net, then poured on the outer layers after routing.
"""
import json
import os
import sys

from shapely.geometry import box
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~/dev/KiCadRoutingTools/py_router"))
from kicad_parser import parse_kicad_pcb  # noqa: E402

OUTLINE = box(131.531, 51.694, 207.531, 116.821)
pcb = parse_kicad_pcb(os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb"))
net = {n.net_id: n.name for n in pcb.nets.values()}
balls = [(p.global_x, p.global_y, net.get(p.net_id, "")) for p in pcb.footprints["U501"].pads]
xs = [b[0] for b in balls]; ys = [b[1] for b in balls]
BGA = box(min(xs) - 0.4, min(ys) - 0.4, max(xs) + 0.4, max(ys) + 0.4)


def cells(nets):
    """The U501 ball field split between `nets`: each 0.8 mm grid cell (one per ball site) goes to the net of the
    nearest ball on `nets` (ties to the earlier net), unioned per net. A grid of squares stays exact where a Voronoi
    diagram of the regular ball grid degenerates."""
    gx = sorted({round(x, 3) for x, _, _ in balls}); gy = sorted({round(y, 3) for _, y, _ in balls})
    sites = [(x, y, n) for x, y, n in balls if n in nets]
    out = {n: [] for n in nets}
    for x in gx:
        for y in gy:
            n = min(sites, key=lambda s: ((s[0] - x) ** 2 + (s[1] - y) ** 2, nets.index(s[2])))[2]
            out[n].append(box(x - 0.4, y - 0.4, x + 0.4, y + 0.4))
    return {n: unary_union(v) for n, v in out.items()}


in3 = cells(["1V1", "VCORE"])
in4 = cells(["1V8", "0V85"])
regions = [
    # (net, layer, priority, polygon)
    ("GND", "In1.Cu", 0, OUTLINE),
    ("GND", "In6.Cu", 0, OUTLINE),
    ("GND", "In3.Cu", 0, OUTLINE),
    ("1V1", "In3.Cu", 1, unary_union([in3["1V1"], box(152.0, 52.5, 190.0, BGA.bounds[1]),
                                      box(BGA.bounds[2], 71.0, 199.2, 81.6)])),
    ("VCORE", "In3.Cu", 2, unary_union([in3["VCORE"], box(BGA.bounds[2], 82.6, 205.8, 92.8)])),
    ("1V8", "In4.Cu", 0, OUTLINE),
    ("0V85", "In4.Cu", 1, unary_union([in4["0V85"], box(168.8, 75.5, 189.2, 77.0)])),
    ("5V0", "B.Cu", 1, unary_union([box(196.5, 74.0, 207.0, 116.5), box(184.5, 74.0, 207.0, 81.6),
                                    box(188.5, 99.5, 207.0, 106.2)])),
]
out = []
for n, layer, prio, poly in regions:
    poly = poly.intersection(OUTLINE).buffer(0)
    geoms = getattr(poly, "geoms", [poly])
    for g in geoms:
        if g.area > 0.5:
            out.append({"net": n, "layer": layer, "priority": prio,
                        "outline": [list(map(lambda v: round(v, 4), c)) for c in g.exterior.coords]})
json.dump(out, open(os.path.join(ROOT, "placement", "planes.json"), "w"), indent=0)
print("plane_regions:", ", ".join(f"{r['net']}@{r['layer']}" for r in out))
