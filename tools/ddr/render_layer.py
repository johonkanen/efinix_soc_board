import sys, re
sys.path.insert(0, "/home/jari/dev/KiCadRoutingTools/py_router")
from kicad_parser import parse_kicad_pcb
from PIL import Image, ImageDraw
pcb = parse_kicad_pcb(sys.argv[1]); layer = sys.argv[3]; X0, Y0, X1, Y1 = map(float, sys.argv[4].split(",")); S = float(sys.argv[5]) if len(sys.argv) > 5 else 30
net = {n.net_id: n.name for n in pcb.nets.values()}
im = Image.new("RGB", (int((X1 - X0) * S), int((Y1 - Y0) * S)), (255, 255, 255)); d = ImageDraw.Draw(im)
T = lambda x, y: ((x - X0) * S, (y - Y0) * S)
def col(n):
    m = re.search(r'ddr_(dq|dm|dqs)(\d+)', n)
    if m:
        i = int(m.group(2)); b = i // 8 if m.group(1) == 'dq' else i
        return [(220, 40, 40), (40, 140, 40), (40, 80, 220), (200, 130, 0)][b]
    if 'ddr_' in n: return (160, 0, 160)
    return (150, 150, 150)
for ref in ("U501", "U801"):
    for p in pcb.footprints[ref].pads:
        x, y = T(p.global_x, p.global_y); r = p.size_x / 2 * S
        d.ellipse([x - r, y - r, x + r, y + r], outline=(200, 200, 200))
for v in pcb.vias:
    x, y = T(v.x, v.y); r = v.size / 2 * S
    d.ellipse([x - r, y - r, x + r, y + r], fill=col(net.get(v.net_id, '')) if 'ddr_' in net.get(v.net_id, '') else (210, 210, 210))
for s in pcb.segments:
    if s.layer == layer:
        d.line([T(s.start_x, s.start_y), T(s.end_x, s.end_y)], fill=col(net.get(s.net_id, '')), width=max(1, int(s.width * S)))
im.save(sys.argv[2]); print("wrote", sys.argv[2])
