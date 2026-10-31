"""Dump the routed LPDDR4 copper (U501 <-> U801) as a graph per net, for the routed-board SI (LPDDR4_IBIS_PLAN.md
step 2). Runs in KiCad's Python; adapted from the Agilex 3 card's sim/lpddr4_si/extract_routes.py:

  ../../tools/p2k/bin/kipy extract_routes.py [../../kicad/ti135_card.kicad_pcb] [work/routes.json]

Per net: track and arc pieces (layer, length, width), vias (position, the layers with copper attached), the U501 /
U801 pads with the U501 pad-to-die delay, and the net's netclass. Nodes are track end points snapped to 5 um, per
layer; a via joins the end points within its pad radius on every layer, a pad the F.Cu end points inside it and a
via in the pad. Under "_board": copper layer depths (stack-up), the tuning profiles' ps/mm per layer and via delay,
and which profile each netclass uses (from the .kicad_pro next to the board): what KiCad's own delays are made of.
"""
import json, os, re, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
board = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '../../kicad/ti135_card.kicad_pcb')
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'work', 'routes.json')
PFX = '/08 lpddr4/'
SNAP = 5000   # nm

b = pcbnew.LoadBoard(board)
ln = b.GetLayerName
key = lambda x, y, layer: f'{round(x / SNAP)},{round(y / SNAP)},{layer}'
nets = {}
for t in b.GetTracks():
    n = t.GetNetname()
    if not n.startswith(PFX + 'ddr_') or 'CAL' in n: continue
    d = nets.setdefault(n[len(PFX):], dict(segs=[], vias=[], pads=[], netclass=t.GetNetClassName()))
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition()
        d['vias'].append(dict(x=p.x, y=p.y, r=t.GetWidth(pcbnew.F_Cu) // 2, top=ln(t.TopLayer()), bot=ln(t.BottomLayer())))
    else:
        s, e = t.GetStart(), t.GetEnd()
        d['segs'].append(dict(a=key(s.x, s.y, ln(t.GetLayer())), b=key(e.x, e.y, ln(t.GetLayer())),
                              layer=ln(t.GetLayer()), mm=t.GetLength() / 1e6, w=t.GetWidth() / 1e6,
                              pa=(s.x, s.y), pb=(e.x, e.y)))
SERIES = {'ddr_cke0': ('ddr_cke0_fpga', 'R803', 15.0)}    # net: (FPGA-side net, series part, ohm); see routed_si.py
for fp in b.GetFootprints():
    if fp.GetReference() not in ('U501', 'U801') + tuple(x[1] for x in SERIES.values()): continue
    for p in fp.Pads():
        n = p.GetNetname()
        if n.startswith(PFX) and n[len(PFX):] in nets:
            nets[n[len(PFX):]]['pads'].append(dict(ref=fp.GetReference(), ball=p.GetNumber(), pad=p,
                                                   layer='B.Cu' if fp.IsFlipped() else 'F.Cu',
                                                   die_ps=p.GetPadToDieDelay() / pcbnew.pcbIUScale.IU_PER_PS))

for name, d in nets.items():
    ends = {}
    for s in d['segs']:
        ends[s['a']] = (s['pa'], s['layer']); ends[s['b']] = (s['pb'], s['layer'])
    for i, v in enumerate(d['vias']):   # via: attached layer nodes
        v['id'] = f'via{i}'
        v['att'] = sorted({(lay, k) for k, ((x, y), lay) in ends.items()
                           if (x - v['x']) ** 2 + (y - v['y']) ** 2 <= v['r'] ** 2}, key=str)
    pads = []
    for p in d['pads']:
        pad = p.pop('pad'); att = []
        for k, ((x, y), lay) in ends.items():
            if lay == p['layer'] and pad.HitTest(pcbnew.VECTOR2I(int(x), int(y))): att.append(k)
        vias = [v['id'] for v in d['vias'] if pad.HitTest(pcbnew.VECTOR2I(int(v['x']), int(v['y'])))]
        pads.append(dict(ref=p['ref'], ball=p['ball'], layer=p['layer'], die_ps=p['die_ps'], att=att, vias=vias))
    d['pads'] = pads
    for s in d['segs']: s.pop('pa'); s.pop('pb')
    for v in d['vias']: v['att'] = [list(a) for a in v['att']]

# stack-up depth of each copper layer (top of F.Cu to the top of the layer) and the tuning profiles
src = open(board).read()
st = src[src.index('(stackup'):src.index('(copper_finish')]
z, depth = 0.0, {}
for lname, body in re.findall(r'\(layer "([^"]+)"(.*?)(?=\(layer "|\Z)', st, re.S):
    if any(x in lname for x in ('Mask', 'Paste', 'SilkS')): continue
    if lname.endswith('.Cu'): depth[lname] = z
    th = re.search(r'\(thickness ([0-9.]+)', body)
    z += float(th.group(1)) if th else 0.0
pro = json.load(open(os.path.splitext(board)[0] + '.kicad_pro'))
profiles = {p['profile_name']: dict(via_ps_mm=p['via_prop_delay'] / 1e6,
                                    ps_mm={e['signal_layer']: e['delay'] / 1e6 for e in p['layer_entries']})
            for p in pro['tuning_profiles']['tuning_profiles_impedance_geometric']}
classes = {c['name']: c.get('tuning_profile', '') for c in pro['net_settings']['classes']}
nets['_board'] = dict(board=os.path.relpath(board, HERE), depth_mm=depth, profiles=profiles, netclass_profile=classes,
                      series=SERIES)

os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(nets, open(out, 'w'), indent=0)
print(f'{len(nets) - 1} nets -> {out}')
