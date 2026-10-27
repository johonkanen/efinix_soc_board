#!/usr/bin/env python3
"""LPDDR4 routing, one panel per copper layer that carries DDR (KiCadRoutingTools venv python):
    render_ddr.py BOARD OUT.png FPGA_REF DRAM_REF [title] [px/mm]

Frames the FPGA and DRAM; tracks coloured by byte lane (from the DQ/DM/DQS index in the net name: byte 0 red,
1 green, 2 blue, 3 orange, and 4+ for a second DRAM in darker shades), CK/CA/CS/CKE purple, other nets light grey.
Vias of DDR nets in their byte colour. For comparing a reference layout (e.g. an Efinix dev board imported with
`kicad-cli pcb import`) with ours.
"""
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.expanduser("~/dev/KiCadRoutingTools/py_router"))
from kicad_parser import parse_kicad_pcb  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

board, out, fpga, dram = sys.argv[1:5]
title = sys.argv[5] if len(sys.argv) > 5 else os.path.basename(board)
S = float(sys.argv[6]) if len(sys.argv) > 6 else 14
pcb = parse_kicad_pcb(board)
names = {i: n.name for i, n in pcb.nets.items()}
BYTE = [(220, 40, 40), (40, 150, 40), (40, 90, 220), (230, 140, 0), (150, 20, 20), (20, 100, 20), (20, 50, 150), (160, 90, 0)]


def colour(n):
    s = n.upper()
    m = re.search(r"DQS_?N?(\d+)|DQS(\d+)", s) or re.search(r"DM_?(\d+)", s)
    if m:
        k = int(next(g for g in m.groups() if g is not None))
        return BYTE[k % len(BYTE)]
    m = re.search(r"DQ_?(\d+)", s)
    if m and "DQS" not in s:
        return BYTE[(int(m.group(1)) // 8) % len(BYTE)]
    if re.search(r"(DDR|LP4|LPDDR)", s) and re.search(r"CK|CA|_A\d|CS|CKE|RST|RESET|ODT", s):
        return (150, 40, 170)
    return None


pts = [(p.global_x, p.global_y) for r in (fpga, dram) for p in pcb.footprints[r].pads]
X0, Y0 = min(x for x, y in pts) - 4, min(y for x, y in pts) - 4
X1, Y1 = max(x for x, y in pts) + 4, max(y for x, y in pts) + 4
length = Counter()
for s in pcb.segments:
    if colour(names.get(s.net_id, "")):
        length[s.layer] += math.hypot(s.end_x - s.start_x, s.end_y - s.start_y)
layers = [L for L, v in length.most_common() if v > 5]
W, H = int((X1 - X0) * S), int((Y1 - Y0) * S) + 26
cols = min(3, len(layers)); rows = math.ceil(len(layers) / cols)
img = Image.new("RGB", (cols * (W + 8), rows * (H + 8) + 30), "white")
ImageDraw.Draw(img).text((8, 8), f"{title}: LPDDR4 per layer (byte 0 red, 1 green, 2 blue, 3 orange; CA/CK purple)", fill="black")
T = lambda x, y: ((x - X0) * S, (y - Y0) * S + 26)
for k, L in enumerate(layers):
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    for r in (fpga, dram):
        for p in pcb.footprints[r].pads:
            q = 0.18 * S; x, y = T(p.global_x, p.global_y)
            d.ellipse([x - q, y - q, x + q, y + q], outline=(205, 205, 205))
    for s in pcb.segments:
        if s.layer != L:
            continue
        c = colour(names.get(s.net_id, ""))
        if c is None:
            if X0 < s.start_x < X1 and Y0 < s.start_y < Y1:
                d.line([T(s.start_x, s.start_y), T(s.end_x, s.end_y)], fill=(225, 225, 225), width=1)
            continue
        d.line([T(s.start_x, s.start_y), T(s.end_x, s.end_y)], fill=c, width=max(1, int(s.width * S)))
    for v in pcb.vias:
        c = colour(names.get(v.net_id, ""))
        if c and X0 < v.x < X1 and Y0 < v.y < Y1:
            r = v.size / 2 * S; x, y = T(v.x, v.y)
            d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    d.text((6, 6), f"{L}: {length[L]:.0f} mm DDR", fill="black")
    img.paste(im, ((k % cols) * (W + 8), (k // cols) * (H + 8) + 30))
img.save(out); print("wrote", out, "layers:", ", ".join(f"{L} {length[L]:.0f} mm" for L in layers))
