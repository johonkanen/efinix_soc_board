#!/usr/bin/env python3
"""Whole-board picture of the four signal layers (KiCadRoutingTools venv python): BOARD OUT.png [scale px/mm].

One panel per layer (F.Cu, In2.Cu, In5.Cu, B.Cu): that layer's tracks in colour (LPDDR4 grey, power nets thick
orange, other nets blue), vias as dots, pads of every footprint as outlines. For a quick look at a routing sketch.
"""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/dev/KiCadRoutingTools/py_router"))
from kicad_parser import parse_kicad_pcb  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

pcb = parse_kicad_pcb(sys.argv[1]); S = float(sys.argv[3]) if len(sys.argv) > 3 else 12
X0, Y0, X1, Y1 = pcb.board_info.board_bounds
names = {i: n.name for i, n in pcb.nets.items()}
W, H = int((X1 - X0) * S), int((Y1 - Y0) * S) + 24
out = Image.new("RGB", (2 * W + 10, 2 * H + 10), "white")
for k, layer in enumerate(("F.Cu", "In2.Cu", "In5.Cu", "B.Cu")):
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    T = lambda x, y: ((x - X0) * S, (y - Y0) * S + 24)
    d.rectangle([T(X0, Y0), T(X1, Y1)], outline=(120, 120, 120))
    for fp in pcb.footprints.values():
        for p in fp.pads:
            if layer in p.layers or "*.Cu" in p.layers:
                hx, hy = p.size_x / 2, p.size_y / 2
                d.rectangle([T(p.global_x - hx, p.global_y - hy), T(p.global_x + hx, p.global_y + hy)], outline=(200, 200, 200))
    n_seg = 0
    for s in pcb.segments:
        if s.layer != layer:
            continue
        n = names.get(s.net_id, ""); n_seg += 1
        col = (175, 175, 175) if "ddr_" in n else (230, 130, 0) if s.width >= 0.25 and "ddr_" not in n else (30, 90, 220)
        d.line([T(s.start_x, s.start_y), T(s.end_x, s.end_y)], fill=col, width=max(1, int(s.width * S)))
    for v in pcb.vias:
        r = v.size / 2 * S; x, y = T(v.x, v.y)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(40, 40, 40))
    d.text((6, 6), f"{layer}: {n_seg} segments (blue signals, orange power, grey LPDDR4)", fill="black")
    out.paste(im, ((k % 2) * (W + 10), (k // 2) * (H + 10)))
out.save(sys.argv[2]); print("wrote", sys.argv[2])
