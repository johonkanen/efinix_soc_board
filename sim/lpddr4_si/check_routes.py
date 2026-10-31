"""Check work/routes.json (extract_routes.py) against KiCad's own delay per net (LPDDR4_IBIS_PLAN.md step 2):

  ../../tools/ddr/kicad_delays.sh > work/kicad_delays.csv
  python3 check_routes.py [work/routes.json] [work/kicad_delays.csv]

From the extracted graph alone, with KiCad's model (the net's tuning profile: ps/mm per layer, via delay times the
stack-up height between the outermost layers a via joins, the U501 pad-to-die delay), the whole-net delay must equal
KiCad's DRC readout: proof that the extraction holds all the copper. Also prints each net's pad-to-pad paths (U501 to
every U801 pad), the delays the simulation channels will have.
"""
import csv, heapq, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'work', 'routes.json')))
kd = {r['net']: float(r['kicad_ps']) for r in
      csv.DictReader(open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'work', 'kicad_delays.csv')))}
B = R.pop('_board')
depth = B['depth_mm']


def via_layers(net, v):
    lays = {lay for lay, _ in v['att']}
    if any(v['id'] in p['vias'] for p in net['pads']): lays.add('F.Cu')
    return lays


def via_ps(prof, lays):
    zs = [depth[l] for l in lays]
    return (max(zs) - min(zs)) * prof['via_ps_mm'] if zs else 0.0


def paths(net, prof):
    """{U801 ball: delay from the U501 pad to it}, Dijkstra over track pieces, via barrels and pads."""
    adj = defaultdict(list)
    link = lambda a, b, w: (adj[a].append((b, w)), adj[b].append((a, w)))
    for s in net['segs']:
        link(s['a'], s['b'], s['mm'] * prof['ps_mm'][s['layer']])
    for v in net['vias']:
        lays = sorted(via_layers(net, v), key=lambda l: depth[l])
        for l1, l2 in zip(lays, lays[1:]): link(f'{v["id"]}:{l1}', f'{v["id"]}:{l2}', via_ps(prof, [l1, l2]))
        for lay, k in v['att']: link(f'{v["id"]}:{lay}', k, 0.0)
    for p in net['pads']:
        pn = f'pad:{p["ref"]}:{p["ball"]}'
        for k in p['att']: link(pn, k, 0.0)
        for vid in p['vias']: link(pn, f'{vid}:F.Cu', 0.0)
    src = [p for p in net['pads'] if p['ref'] == 'U501'][0]
    start = f'pad:U501:{src["ball"]}'
    dist = {start: src['die_ps']}; pq = [(src['die_ps'], start)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18): continue
        for v, w in adj[u]:
            if d + w < dist.get(v, 1e18): dist[v] = d + w; heapq.heappush(pq, (d + w, v))
    return {p['ball']: dist.get(f'pad:U801:{p["ball"]}') for p in net['pads'] if p['ref'] == 'U801'}


worst = 0.0
print('| net | KiCad whole net (ps) | extracted whole net (ps) | diff | pad-to-pad paths to U801 (ps) |')
print('|---|---|---|---|---|')
for name in sorted(R, key=lambda n: (n.rstrip('_PN0123456789'), len(n), n)):
    net = R[name]; prof = B['profiles'][B['netclass_profile'][net['netclass']]]
    whole = (sum(s['mm'] * prof['ps_mm'][s['layer']] for s in net['segs']) +
             sum(via_ps(prof, via_layers(net, v)) for v in net['vias']) +
             max(p['die_ps'] for p in net['pads'] if p['ref'] == 'U501'))
    k = kd.get(name)
    diff = whole - k if k is not None else float('nan')
    if k is not None: worst = max(worst, abs(diff))
    pp = paths(net, prof)
    print(f"| {name} | {k if k is not None else '-'} | {whole:.2f} | {diff:+.2f} | "
          + ', '.join(f'{b} {d:.1f}' if d is not None else f'{b} UNREACHED' for b, d in sorted(pp.items())) + ' |')
missing = sorted(set(kd) - set(R))
print(f'\nworst |diff| {worst:.2f} ps over {len(R)} nets; in KiCad but not extracted: {missing or "none"}')
