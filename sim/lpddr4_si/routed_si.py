"""SI of the routed LPDDR4 nets (LPDDR4_IBIS_PLAN.md steps 3-5): each net's real copper (extract_routes.py ->
work/routes.json) between the IBIS buffers of its ends, one net (or one pair) per netlist.

  source ../../tools/p2k/bin/kicad_env.sh
  ../../tools/p2k/bin/kipy extract_routes.py                     # board -> work/routes.json
  python3 routed_si.py --one ddr_ca1 --corner min --rate 3200     # one netlist alone (step 3)
  python3 routed_si.py --sweep [-j 4] [--corners typ] [--rates 2800 3200]   # steps 4-5: results/routed.csv

Per net the extracted graph becomes the netlist: every track / arc piece a lossless line with Z0 and ps/mm of its
layer and width (results/zsolve.csv, field solve), every via a hub with VIA_C to ground and an L by span (gen_sch.py's
via model) to each layer it joins, 200 ohm across each L (damps the 10+ GHz tank). Stubs and T branches as routed.
Pairs (DQS, CK): each leg its own extracted copper, as a single line at the pair's odd-mode Z0 and ps/mm (0.10 mm /
0.20 mm gap, as routed): P/N skew as routed is in, coupling to other nets and mode conversion are not.
Uncoupled: no crosstalk, no meander self-coupling (step 6). Buffers, drive/ODT settings, package line, masks and
limits as gen_sch.py / run_si.py. min/max use the corner model files (corner_models.py) simulated at typ: KiCad's own
vcc=MIN/MAX is wrong away from the V-t fixture (step 1). Only the probed nodes are saved (.save); each .dat is deleted
after reading. Each ngspice run has a timeout and an address-space cap; a failed netlist becomes an error row.
Results are appended to the CSV as each netlist finishes; a rerun skips what is done (resume).
"""
import argparse, csv, json, os, re, resource, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv_saved = sys.argv; sys.argv = [sys.argv[0]]          # run_si / gen_sch parse no arguments at import
import gen_sch as G                                         # noqa: E402
import run_si as S                                          # noqa: E402
sys.argv = sys.argv_saved
from kicad_ibis import fastnet                              # noqa: E402  (path set by run_si)

WORK, RES = S.WORK, S.RES
NBITS, CA_BITS = 150, 140
PAIR_GAP = 0.20             # mm, DQS/CK as routed (0.10 mm traces); DQS2 has short 0.15-0.18 mm stretches
TIMEOUT_S = 300             # per ngspice run (a netlist takes 8-15 s)
MEM_CAP = 4 << 30           # bytes of address space per ngspice process


def ngspice_limited(cir, vecs, out):
    """run_si.ngspice with a timeout and an address-space cap (a stuck or runaway run fails instead of hanging)."""
    script = f'''
import ctypes, glob, os
ng = ctypes.CDLL({S.LIBNG!r})
log = []
PF = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
EX = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
pf = PF(lambda s, i, u: log.append(s.decode(errors='replace')) or 0); ex = EX(lambda *a: 0)
ng.ngSpice_Init(pf, pf, ex, None, None, None, None)
c = lambda s: ng.ngSpice_Command(s.encode())
for cm in glob.glob(os.path.join(os.path.dirname({S.LIBNG!r}), 'ngspice', '*.cm')): c('codemodel ' + cm)
c('set wr_singlescale'); c('set wr_vecnames'); c('source {cir}'); c('run')
c('wrdata {out} ' + {' '.join(f'v({v})' for v in vecs)!r})
open({out + '.log'!r}, 'w').write('\\n'.join(log))
'''
    lim = lambda: (resource.setrlimit(resource.RLIMIT_AS, (MEM_CAP, MEM_CAP)), os.nice(5))
    try:
        r = subprocess.run([sys.executable, '-I', '-c', script], capture_output=True, text=True, timeout=TIMEOUT_S,
                           preexec_fn=lim)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'ngspice timeout ({TIMEOUT_S} s) on {os.path.basename(cir)}')
    if r.returncode or not os.path.exists(out):
        raise RuntimeError(f'ngspice failed on {os.path.basename(cir)}: {r.stderr[-500:]}')
    d = np.loadtxt(out, skiprows=1)
    return d[:, 0], {v: d[:, i + 1] for i, v in enumerate(vecs)}


S.ngspice = ngspice_limited     # run_si.ngspice_checked (early-stop retry with method=trap) calls this


def channel(s, R, net, tag, pair=False):
    """The extracted copper of one net (leg) into s. Returns {(ref, ball): node} of its pads."""
    r = R[net]
    node = lambda k: f'{tag}_{k.replace(",", "_").replace(".", "")}'
    for seg in r['segs']:
        if pair and abs(seg['w'] - 0.10) < 0.005:
            zd, ps = G.ZDIFF[(G.lyr(seg['layer']), 0.1, PAIR_GAP)]; z = zd / 2
        else:
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
    return ball, u501, u801


def build(R, net, kind, corner, rate, st=None):
    """One netlist. kind: dq_write, dq_read (DQ/DM), ca (CA, CS, CKE), dqs_write, dqs_read (net = ddr_dqsN), ck
    (net = ddr_ck). Returns (Netlist, meta) in run_si.run_point's form."""
    st = dict(G.BASE, **(st or {}))
    ui = 1e-6 / rate
    s = G.FastSch('models')
    if corner != 'typ':
        s.models = os.path.join(HERE, 'models', corner)    # corner files, simulated at typ
    a = argparse.Namespace(pkg='netlen')
    prbs_dq = f'f0={G.eng(1 / ui)} n={NBITS}'
    t_end = NBITS * ui
    if kind in ('dq_write', 'dq_read', 'ca'):
        ball, u501, u801 = channel(s, R, net, 'c')
        fb = ball[('U501', u501['ball'])]
        if kind == 'dq_write':
            die, fpin = G.fpga_pkg(s, a, 'c', fb, u501['die_ps'], 'SE')
            d = s.ibis('drv', G.EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n', die, prbs_dq)
            p = u801[0]; m = ball[('U801', p['ball'])]
            rx = [(s.ibis('rx', G.MEM, p['ball'], f'ODT_{st["modt"]}', m), m)]
        elif kind == 'dq_read':
            p = u801[0]; m = ball[('U801', p['ball'])]
            d = s.ibis('drv', G.MEM, p['ball'], f'PD{st["pdds"]}_ODT40_VOH30', m, prbs_dq)
            die, fpin = G.fpga_pkg(s, a, 'c', fb, u501['die_ps'], 'SR')
            rx = [(s.ibis('rx', G.EFX, fpin, f'lpddr4_odt_{st["fodt"]}', die), fb)]
        else:
            die, fpin = G.fpga_pkg(s, a, 'c', fb, u501['die_ps'], 'SE')
            d = s.ibis('drv', G.EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n', die,
                       f'f0={G.eng(1 / (2 * ui))} n={CA_BITS}')       # CA/CS/CKE: one bit per tCK = 2 UI
            model = 'CKE_INPUT' if 'cke' in net else f'CS_ODT_{st["caodt"]}' if 'cs' in net else f'CA_ODT_{st["caodt"]}'
            rx = [(s.ibis('rx', G.MEM, p['ball'], model, ball[('U801', p['ball'])]), ball[('U801', p['ball'])])
                  for p in u801]
            t_end = CA_BITS * 2 * ui
        meta = dict(kind=kind, net=net, ui=2 * ui if kind == 'ca' else ui, drv=d, rx=rx, **st)
        probes = [S.die(d)] + [x for ref, pin in rx for x in (pin, S.die(ref))]
    else:                                                   # pairs: P and N legs, N driven with the complement
        legs, drv = {}, {}
        for leg in 'PN':
            legs[leg] = channel(s, R, f'{net}_{leg}', f'c{leg.lower()}', pair=True)
        if kind in ('dqs_write', 'ck'):
            for leg in 'PN':
                ball, u501, _ = legs[leg]
                die, fpin = G.fpga_pkg(s, a, f'c{leg.lower()}', ball[('U501', u501['ball'])], u501['die_ps'],
                                       'D' + leg)
                drv[leg] = s.ibis('drv', G.EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n_diff', die, prbs_dq)
            om = f'CLK_ODT_{st["caodt"]}' if kind == 'ck' else f'ODT_{st["modt"]}'
            rx = []
            for (bp, _, up), (bn, _, un) in [(legs['P'], legs['N'])]:
                for pp, pn in zip(sorted(up, key=lambda p: p['ball']), sorted(un, key=lambda p: p['ball'])):
                    mp, mn = bp[('U801', pp['ball'])], bn[('U801', pn['ball'])]
                    rx.append(([s.ibis('rx', G.MEM, pp['ball'], om, mp), s.ibis('rx', G.MEM, pn['ball'], om, mn)],
                               [mp, mn]))
        else:                                               # dqs_read
            for leg in 'PN':
                ball, _, u801 = legs[leg]
                drv[leg] = s.ibis('drv', G.MEM, u801[0]['ball'], f'PD{st["pdds"]}_ODT40_VOH30',
                                  ball[('U801', u801[0]['ball'])], prbs_dq)
            refs, pins = [], []
            for leg in 'PN':
                ball, u501, _ = legs[leg]
                fb = ball[('U501', u501['ball'])]
                die, fpin = G.fpga_pkg(s, a, f'c{leg.lower()}', fb, u501['die_ps'], 'R' + leg)
                refs.append(s.ibis('rx', G.EFX, fpin, f'lpddr4_odt_{st["fodt"]}_diff', die)); pins.append(fb)
            rx = [(refs, pins)]
        next(e for e in s.net.ib if e['ref'] == drv['N'])['pattern'] = ('inv', drv['P'])
        meta = dict(kind=kind, net=net, ui=ui, drv=drv['P'], inv=drv['N'], rx=rx, **st)
        probes = [S.die(drv['P']), S.die(drv['N'])] + [x for refs, pins in rx for x in pins + [S.die(r) for r in refs]]
    s.net.directive('.save ' + ' '.join(f'v({v})' for v in dict.fromkeys(probes)))
    s.net.directive(f'.tran 1p {(t_end + 2e-9) * 1e9:.1f}n')
    s.net.directive('.options method=gear maxord=2 reltol=1e-4')
    return s.net, {'case': meta}


def run_job(job):
    """Simulate one written netlist; rows (or one error row). Deletes the waveform file."""
    tag, net, kind, corner, rate, meta, plot = job
    dat = os.path.join(WORK, tag + '.dat'); t0 = time.time()
    try:
        rows = S.run_point((tag, ['--rate', str(rate), '--corner', corner], meta, plot))
    except BaseException as e:      # run_si exits on a run that stops early even with method=trap
        rows = [dict(point=tag, error=f'{type(e).__name__}: {e}'[:300])]
    for f in (dat, dat + '.log'):
        if os.path.exists(f): os.remove(f)
    for r in rows:
        r.update(tag=tag, net=net, kind=kind, corner=corner, rate=rate, sim_s=round(time.time() - t0, 1))
    return rows


def sweep_jobs(R, rates, corners):
    dq = [f'ddr_dq{i}' for i in range(32)]; dm = [f'ddr_dm{i}' for i in range(4)]
    ca = [f'ddr_ca{i}' for i in range(6)] + ['ddr_cke0', 'ddr_cs0_n', 'ddr_cs2_n']
    jobs = []
    for rate in rates:
        for c in corners:
            for n in dq + dm: jobs.append((n, 'dq_write', c, rate))
            for n in dq: jobs.append((n, 'dq_read', c, rate))
            for n in ca: jobs.append((n, 'ca', c, rate))
            for b in range(4):
                jobs.append((f'ddr_dqs{b}', 'dqs_write', c, rate)); jobs.append((f'ddr_dqs{b}', 'dqs_read', c, rate))
            jobs.append(('ddr_ck', 'ck', c, rate))
    missing = sorted({n for n, *_ in jobs} - set(R) - {'ddr_ck'} - {f'ddr_dqs{b}' for b in range(4)})
    if missing: sys.exit(f'not in routes.json: {missing}')
    return jobs


KEYS = ['tag', 'net', 'kind', 'corner', 'rate', 'rx', 'where', 'eh_mV', 'ew0_ps', 'v_margin_mV', 't_margin_ps',
        'vmax_mV', 'vmin_mV', 'lim_lo_mV', 'lim_hi_mV', 'limits_ok', 'os_area_Vns', 'us_area_Vns', 'delay_ps',
        'fdrv', 'fodt', 'modt', 'pdds', 'caodt', 'sim_s', 'error']


def sweep(R, a):
    out = os.path.join(RES, a.out + '.csv')
    done = set()
    if os.path.exists(out):                                  # resume: skip netlists already in the CSV
        done = {r['tag'] for r in csv.DictReader(open(out)) if not r.get('error')}
    todo = []
    for net, kind, c, rate in sweep_jobs(R, a.rates, a.corners):
        tag = f'routed_{net}_{kind}_{c}_{rate:g}'
        if tag not in done: todo.append((tag, net, kind, c, rate))
    print(f'{len(todo)} netlists to run ({len(done)} already in {os.path.relpath(out, HERE)})', flush=True)
    if not todo: return
    built = []
    for tag, net, kind, c, rate in todo:
        n, meta = build(R, net, kind, c, rate); n.title = tag
        built.append((tag, net, kind, c, rate, n, meta))
    cache = fastnet.KibisCache(S.KCACHE)
    t0 = time.time()
    conv = cache.resolve([e for *_, n, _ in built for e in n.ib], jobs=min(a.j, 4))
    print(f'KIBIS: {conv} conversions in {time.time() - t0:.0f} s', flush=True)
    jobs = []
    for tag, net, kind, c, rate, n, meta in built:
        n.write(os.path.join(WORK, tag + '.cir'), cache)
        jobs.append((tag, net, kind, c, rate, meta, False))
    new = not os.path.exists(out)
    f = open(out, 'a', newline=''); wr = csv.DictWriter(f, KEYS, extrasaction='ignore')
    if new: wr.writeheader()
    t0 = time.time(); nerr = 0
    with ProcessPoolExecutor(a.j) as ex:
        futs = [ex.submit(run_job, j) for j in jobs]
        for i, fu in enumerate(as_completed(futs), 1):
            rows = fu.result()
            nerr += any('error' in r for r in rows)
            for r in rows: wr.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
            f.flush()
            if i % 10 == 0 or i == len(jobs):
                el = time.time() - t0
                print(f'{i}/{len(jobs)} done, {el / 60:.1f} min, about {el / i * (len(jobs) - i) / 60:.0f} min left, '
                      f'{nerr} failed', flush=True)
    f.close()


def plot_worst(R, a):
    """Eye PNG of the worst net (smallest V margin at the die) of each kind, rate and corner: rerun with plot."""
    rows = [r for r in csv.DictReader(open(os.path.join(RES, a.out + '.csv'))) if not r.get('error')
            and r['where'] == 'die']
    worst = {}
    for r in rows:
        k = (r['kind'], r['rate'], r['corner'])
        if k not in worst or float(r['v_margin_mV']) < float(worst[k]['v_margin_mV']): worst[k] = r
    cache = fastnet.KibisCache(S.KCACHE)
    for (kind, rate, c), r in sorted(worst.items()):
        tag = f'worst_{kind}_{c}_{float(rate):g}'
        n, meta = build(R, r['net'], kind, c, float(rate)); n.title = tag
        cache.resolve(n.ib); n.write(os.path.join(WORK, tag + '.cir'), cache)
        run_job((tag, r['net'], kind, c, float(rate), meta, True))
        print(f'{tag}: {r["net"]} ({r["rx"]}) margin {float(r["v_margin_mV"]):.0f} mV', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--one', help='one net (e.g. ddr_ca1, ddr_dqs0, ddr_ck): build and run it alone, print the rows')
    ap.add_argument('--kind', choices=['dq_write', 'dq_read', 'ca', 'dqs_write', 'dqs_read', 'ck'])
    ap.add_argument('--corner', default='typ', choices=['typ', 'min', 'max'])
    ap.add_argument('--rate', type=float, default=2800.0)
    ap.add_argument('--sweep', action='store_true', help='every net, both directions (results/<out>.csv, resumable)')
    ap.add_argument('--corners', nargs='*', default=['typ', 'min', 'max'])
    ap.add_argument('--rates', nargs='*', type=float, default=[2800.0, 3200.0])
    ap.add_argument('--out', default='routed')
    ap.add_argument('--plot-worst', action='store_true', help='eye PNGs of the worst net per kind/rate/corner')
    ap.add_argument('-j', type=int, default=4, help='parallel ngspice runs (CPU-bound, ~80 MB each)')
    a = ap.parse_args()
    if not os.path.exists(S.LIBNG): sys.exit('source ../../tools/p2k/bin/kicad_env.sh first (KICAD_MOUNT)')
    os.makedirs(WORK, exist_ok=True); os.makedirs(os.path.join(RES, 'eyes'), exist_ok=True)
    R = json.load(open(os.path.join(WORK, 'routes.json')))
    if a.one:
        kind = a.kind or ('ca' if re.match(r'ddr_(ca|cs|cke)', a.one) else 'ck' if a.one == 'ddr_ck'
                          else 'dqs_write' if a.one.startswith('ddr_dqs') else 'dq_write')
        tag = f'one_{a.one}_{kind}_{a.corner}_{a.rate:g}'
        n, meta = build(R, a.one, kind, a.corner, a.rate); n.title = tag
        cache = fastnet.KibisCache(S.KCACHE); cache.resolve(n.ib); n.write(os.path.join(WORK, tag + '.cir'), cache)
        for r in run_job((tag, a.one, kind, a.corner, a.rate, meta, False)):
            print({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()
                   if k in ('net', 'rx', 'where', 'eh_mV', 'v_margin_mV', 't_margin_ps', 'vmax_mV', 'vmin_mV',
                            'limits_ok', 'os_area_Vns', 'us_area_Vns', 'error', 'sim_s')})
    if a.sweep: sweep(R, a)
    if a.plot_worst: plot_worst(R, a)


if __name__ == '__main__':
    main()
