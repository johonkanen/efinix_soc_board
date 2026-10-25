import sys, re, collections, math
sys.path.insert(0, "/home/jari/dev/KiCadRoutingTools/py_router")
from kicad_parser import parse_kicad_pcb
def byte(n):
    m = re.search(r'ddr_(dq|dm|dqs)(\d+)', n)
    if not m: return 'CA' if 'ddr_' in n else None
    i = int(m.group(2)); return f"B{i // 8 if m.group(1) == 'dq' else i}"
for f in sys.argv[1:]:
    pcb = parse_kicad_pcb(f); net = {n.net_id: n.name for n in pcb.nets.values()}
    L = collections.defaultdict(float); lay = collections.defaultdict(lambda: collections.defaultdict(float)); vias = collections.Counter()
    for s in pcb.segments:
        n = net.get(s.net_id, ''); b = byte(n)
        if b: d = math.hypot(s.end_x - s.start_x, s.end_y - s.start_y); L[n] += d; lay[b][s.layer] += d
    for v in pcb.vias:
        n = net.get(v.net_id, ''); b = byte(n)
        if b: vias[b] += 1
    print("==", f, "total DDR length %.0f mm" % sum(L.values()), "vias", sum(vias.values()))
    for b in sorted(lay):
        tot = sum(lay[b].values())
        print(f"  {b}: vias {vias[b]:3}  length {tot:6.0f} mm  layers " + ", ".join(f"{k} {100*v/tot:.0f}%" for k, v in sorted(lay[b].items(), key=lambda x: -x[1])))
