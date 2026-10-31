"""SI of the routed LPDDR4 nets (LPDDR4_IBIS_PLAN.md steps 3-5): each net's real copper (extract_routes.py ->
work/routes.json) between the IBIS buffers of its ends, one net per netlist.

  source ../../tools/p2k/bin/kicad_env.sh
  ../../tools/p2k/bin/kipy extract_routes.py               # board -> work/routes.json
  python3 routed_si.py --one ddr_ca1 --corner min --rate 3200   # one netlist (step 3: time it alone)

Per net the extracted graph becomes the netlist: every track / arc piece a lossless line with Z0 and ps/mm of its
layer and width (results/zsolve.csv, field solve), every via a hub with VIA_C to ground and an L by span (gen_sch.py's
via model) to each layer it joins, 200 ohm across each L (damps the 10+ GHz tank). Stubs and T branches as routed.
Uncoupled: no crosstalk, no meander self-coupling (step 6). Buffers, drive/ODT settings, package line, masks and
limits as gen_sch.py / run_si.py. min/max use the corner model files (corner_models.py) simulated at typ:
KiCad's own vcc=MIN/MAX is wrong away from the V-t fixture (step 1). Only the probed nodes are saved (.save).
"""
import argparse, json, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv_saved = sys.argv; sys.argv = [sys.argv[0]]          # run_si / gen_sch parse no arguments at import
import gen_sch as G                                         # noqa: E402
import run_si as S                                          # noqa: E402
sys.argv = sys.argv_saved
from kicad_ibis import fastnet                              # noqa: E402  (path set by run_si)

WORK = S.WORK
NBITS, CA_BITS = 150, 140


def lname(layer):
    return G.lyr(layer)


def build(R, net, kind, corner, rate, st=None):
    """One netlist for one single-ended net. kind: dq_write, dq_read (DQ/DM), ca (CA, CS, CKE).
    Returns (Netlist, meta) in run_si.run_point's form."""
    st = dict(G.BASE, **(st or {}))
    ui = 1e-6 / rate
    s = G.FastSch('models')
    if corner != 'typ':
        s.models = os.path.join(HERE, 'models', corner)    # corner files, simulated at typ
    r = R[net]; tag = 'c'
    node = lambda k: f'{tag}_{k.replace(",", "_").replace(".", "")}'
    for seg in r['segs']:
        z, ps = G.zline(seg['layer'], seg['w'])
        s.tl(node(seg['a']), node(seg['b']), round(z, 2), max(seg['mm'], 1e-4) * ps * 1e-12)
    u501 = [p for p in r['pads'] if p['ref'] == 'U501'][0]
    u801 = [p for p in r['pads'] if p['ref'] == 'U801']
    ball = {(p['ref'], p['ball']): f'{tag}_{p["ref"].lower()}_{p["ball"].lower()}' for p in r['pads']}
    pad_of_via = {v: p for p in r['pads'] for v in p['vias']}
    depth = R['_board']['depth_mm']
    for v in r['vias']:
        att = [(lay, node(k)) for lay, k in v['att']]
        if v['id'] in pad_of_via:
            p = pad_of_via[v['id']]; att.append(('F.Cu', ball[(p['ref'], p['ball'])]))
        C = G.VIA_C_U501 if v['id'] in u501['vias'] else G.VIA_C_U801 if any(v['id'] in p['vias'] for p in u801) \
            else G.VIA_C_MID
        cnt = {}
        for lay, _ in att: cnt[lay] = cnt.get(lay, 0) + 1
        hub_layer = max(cnt, key=lambda l: (cnt[l], depth[l])); hub = f'{tag}_{v["id"]}'
        s.net.c(hub, '0', C)
        for lay, nd in att:
            span = abs(depth[lay] - depth[hub_layer])
            if span > 1e-6:
                s.net.l(nd, hub, G.VIA_L(span)); s.net.r(nd, hub, 200.0)
            else:
                s.net.r(nd, hub, 1e-3)
    for p in r['pads']:
        for k in p['att']: s.net.r(ball[(p['ref'], p['ball'])], node(k), 1e-3)

    a = argparse.Namespace(pkg='netlen')
    fb = ball[('U501', u501['ball'])]
    prbs_dq = f'f0={G.eng(1 / ui)} n={NBITS}'
    if kind == 'dq_write':
        die, fpin = G.fpga_pkg(s, a, tag, fb, u501['die_ps'], 'SE')
        d = s.ibis('drv', G.EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n', die, prbs_dq)
        p = u801[0]; m = ball[('U801', p['ball'])]
        rx = [(s.ibis('rx', G.MEM, p['ball'], f'ODT_{st["modt"]}', m), m)]
        meta = dict(kind='dq_write', net=net, ui=ui, drv=d, rx=rx, **st); t_end = NBITS * ui
    elif kind == 'dq_read':
        p = u801[0]; m = ball[('U801', p['ball'])]
        d = s.ibis('drv', G.MEM, p['ball'], f'PD{st["pdds"]}_ODT40_VOH30', m, prbs_dq)
        die, fpin = G.fpga_pkg(s, a, tag, fb, u501['die_ps'], 'SR')
        rx = [(s.ibis('rx', G.EFX, fpin, f'lpddr4_odt_{st["fodt"]}', die), fb)]
        meta = dict(kind='dq_read', net=net, ui=ui, drv=d, rx=rx, **st); t_end = NBITS * ui
    else:
        die, fpin = G.fpga_pkg(s, a, tag, fb, u501['die_ps'], 'SE')
        d = s.ibis('drv', G.EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n', die,
                   f'f0={G.eng(1 / (2 * ui))} n={CA_BITS}')       # CA/CS/CKE: one bit per tCK = 2 UI
        model = 'CKE_INPUT' if 'cke' in net else f'CS_ODT_{st["caodt"]}' if 'cs' in net else f'CA_ODT_{st["caodt"]}'
        rx = [(s.ibis('rx', G.MEM, p['ball'], model, ball[('U801', p['ball'])]), ball[('U801', p['ball'])])
              for p in u801]
        meta = dict(kind='ca', net=net, ui=2 * ui, drv=d, rx=rx, **st); t_end = CA_BITS * 2 * ui
    probes = [S.die(d)] + [x for ref, pin in rx for x in (pin, S.die(ref))]
    s.net.directive('.save ' + ' '.join(f'v({v})' for v in dict.fromkeys(probes)))
    s.net.directive(f'.tran 1p {(t_end + 2e-9) * 1e9:.1f}n')
    s.net.directive('.options method=gear maxord=2 reltol=1e-4')
    return s.net, {'case': meta}


def run_one(R, net, kind, corner, rate, tag):
    """Build, write and simulate one netlist; rows from run_si.run_point; the waveform file is deleted after."""
    n, meta = build(R, net, kind, corner, rate)
    n.title = tag
    cache = fastnet.KibisCache(S.KCACHE); cache.resolve(n.ib)
    cir = n.write(os.path.join(WORK, tag + '.cir'), cache)
    rows = S.run_point((tag, ['--rate', str(rate), '--corner', corner], meta, False))
    dat = os.path.join(WORK, tag + '.dat')
    if os.path.exists(dat): os.remove(dat)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--one', help='one net (e.g. ddr_ca1): build and run it alone, print the rows')
    ap.add_argument('--kind', choices=['dq_write', 'dq_read', 'ca'], help='default: ca for CA/CS/CKE, else dq_write')
    ap.add_argument('--corner', default='typ', choices=['typ', 'min', 'max'])
    ap.add_argument('--rate', type=float, default=2800.0)
    a = ap.parse_args()
    if not os.path.exists(S.LIBNG): sys.exit('source ../../tools/p2k/bin/kicad_env.sh first (KICAD_MOUNT)')
    os.makedirs(WORK, exist_ok=True)
    R = json.load(open(os.path.join(WORK, 'routes.json')))
    if a.one:
        kind = a.kind or ('ca' if re.match(r'ddr_(ca|cs|cke)', a.one) else 'dq_write')
        tag = f'one_{a.one}_{kind}_{a.corner}_{a.rate:g}'
        for r in run_one(R, a.one, kind, a.corner, a.rate, tag):
            print({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()
                   if k in ('net', 'rx', 'where', 'eh_mV', 'v_margin_mV', 't_margin_ps', 'vmax_mV', 'vmin_mV',
                            'limits_ok', 'os_area_Vns', 'us_area_Vns')})


if __name__ == '__main__':
    main()
