#!/usr/bin/env python3
"""ADC front-end settling with the analog mux (sheet 13): ngspice transient of mux -> OPA365 -> 33R/680p -> ADS7056.

    source tools/p2k/bin/kicad_env.sh            # KiCad's libngspice (no ngspice binary needed)
    python3 sim/adc_mux/adc_mux_sim.py fetch     # TI OPA365 PSpice model -> sim/adc_mux/models/ (git-ignored)
    python3 sim/adc_mux/adc_mux_sim.py run [-j 2] [scenario ...]

Circuit (sheet 13 values):
  S0 GND | S1 mon_vcore (VCORE 0.85 V, R1301 100R) | S2 mon_1v8 (R1302 100R) | S3 mon_3v3 (R1303/R1305 200R/200R,
  1.65 V / 100R) | S4 isoada2 | S5 mon_1v1 (R1304 100R) | S6 isoada3 | S7 isoada1
  isoada chain: ideal source -> baseboard Rbb/Cbb -> J3 -> Rloc/Cloc (R1307-9 1k, C1307-9 1n C0G)
                -> OPA365 follower (U1304-6, optional) -> mux Sx
  mux D -> OPA365 follower U1302 -> R1306 33R -> AINP (C1302 680p) -> ADS7056 sample switch 50R + 16 pF
The mux is a behavioural model from the data sheet (Ron, CS(OFF), CD(OFF), CD(ON), charge injection, tTRAN/tBBM):
TI's TMUX1308 PSpice model stalls ngspice at every channel change and its capacitances (fitted to bandwidth,
~2-3 pF) are below the data-sheet CD(ON) 11 pF typ / 40 pF max, so it would understate the charge sharing.

Timing: 2.5 MSPS (400 ns), acquisition = the last 100 ns before each sampling instant (CS falling), the FPGA moves
the mux select 5 ns after CS falls, so each channel has ~395 ns to settle. The ADS7056 sampling capacitor keeps
the previous sample's voltage during conversion (kickback = previous channel's voltage).
Error = sampled voltage - the DC operating point with that channel selected (so static offsets cancel);
1 LSB = 3.3 V / 16384 = 201 uV.
"""
import argparse, ctypes, glob, io, os, sys, zipfile, urllib.request
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS, WORK = os.path.join(HERE, 'models'), os.path.join(HERE, 'work')
OPA_LIB = os.path.join(MODELS, 'opa365', 'OPA365-PSpiceFiles', 'SCHEMATIC1', 'TransientAnalysis', 'OPA365.lib')
OPA_URL = 'https://www.ti.com/lit/zip/SBOC133'
OPA322_LIB = os.path.join(MODELS, 'opa322', 'OPAx322.LIB')     # OPA4322 (quad) family model
OPA322_URL = 'https://www.ti.com/lit/zip/SBOM888'
LSB = 3.3 / 16384

# data-sheet switch parameters at 3.3 V (typ unless *_max); caps in F, R in ohm, Q in C, t in s
MUX = {
    'tmux1308':     dict(ron=120, cs=2e-12, cd=7e-12, con=11e-12, q=-1e-12, ton=23e-9, toff=1e-9),
    'tmux1308_max': dict(ron=330, cs=14e-12, cd=37e-12, con=40e-12, q=-1e-12, ton=51e-9, toff=50e-9),
    'nx3l4051':     dict(ron=0.5, cs=35e-12, cd=315e-12, con=350e-12, q=9e-12, ton=19e-9, toff=8e-9),
    'sn74lv4051a':  dict(ron=30, cs=5e-12, cd=18e-12, con=23e-12, q=0.0, ton=20e-9, toff=8e-9),
}
CH = [  # (name, kind, value V, source R)
    ('GND', 'rail', 0.0, 1e-3), ('mon_vcore', 'rail', 0.85, 100), ('mon_1v8', 'rail', 1.8, 100),
    ('mon_3v3', 'rail', 1.65, 100), ('isoada2', 'iso', 3.0, None), ('mon_1v1', 'rail', 1.1, 100),
    ('isoada3', 'iso', 1.5, None), ('isoada1', 'iso', 0.3, None)]
SCEN = {  # mux, followers on isoada, baseboard R/C, local R/C at J3
    'tmux1308':          dict(mux='tmux1308', fol=True, rbb=8.2e3, cbb=4.7e-9, rloc=1e3, cloc=1e-9),
    'tmux1308_max':      dict(mux='tmux1308_max', fol=True, rbb=8.2e3, cbb=4.7e-9, rloc=1e3, cloc=1e-9),
    'nx3l4051':          dict(mux='nx3l4051', fol=True, rbb=8.2e3, cbb=4.7e-9, rloc=1e3, cloc=1e-9),
    'sn74lv4051a':       dict(mux='sn74lv4051a', fol=True, rbb=8.2e3, cbb=4.7e-9, rloc=1e3, cloc=1e-9),
    'tmux1308_max_nofol':      dict(mux='tmux1308_max', fol=False, rbb=8.2e3, cbb=4.7e-9, rloc=1e3, cloc=1e-9),
    'tmux1308_max_nofol_bigc': dict(mux='tmux1308_max', fol=False, rbb=100, cbb=470e-9, rloc=1e-3, cloc=100e-9),
    # the rail monitors before 2026-11-05: 1V8/1V1 series 1k, 3V3 divider 1k/1k (500 ohm)
    'tmux1308_max_rmon1k':     dict(mux='tmux1308_max', fol=True, rbb=8.2e3, cbb=4.7e-9, rloc=1e3, cloc=1e-9,
                                    rsrc={2: 1000, 3: 500, 5: 1000}),
    # isoada followers as one OPA4322 quad (20 MHz) instead of three OPA365 (50 MHz)
    'opa4322':                 dict(mux='tmux1308', fol=True, folm='OPAx322', rbb=8.2e3, cbb=4.7e-9, rloc=1e3, cloc=1e-9),
    'opa4322_max':             dict(mux='tmux1308_max', fol=True, folm='OPAx322', rbb=8.2e3, cbb=4.7e-9, rloc=1e3, cloc=1e-9),
}
T, TACQ, TSEL, T0 = 400e-9, 100e-9, 5e-9, 2e-6


class NgSpice:
    """KiCad's libngspice through its shared-library API."""
    def __init__(self):
        m = os.environ.get('KICAD_MOUNT', '')
        c = sorted(glob.glob(os.path.join(m, 'shared/lib/libngspice.so.0*'))) if m else []
        if not c: raise SystemExit('libngspice not found: source tools/p2k/bin/kicad_env.sh first')
        self.lib = ctypes.CDLL(c[0]); self.out = []
        P = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        E = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        self._p = P(lambda s, i, u: self.out.append(s.decode(errors='replace')) or 0)
        self._e = E(lambda *a: 0)
        self.lib.ngSpice_Init(self._p, None, self._e, None, None, None, None)
        self.lib.ngSpice_Command.argtypes = [ctypes.c_char_p]
        self.lib.ngSpice_Circ.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
        # XSPICE code models: PSpice-mode TABLE/VSWITCH cards become xfer/aswitch instances that need them
        cm = os.path.join(os.path.dirname(c[0]), 'ngspice')
        for f in ('analog.cm', 'digital.cm', 'xtradev.cm', 'xtraevt.cm', 'table.cm', 'spice2poly.cm'):
            if os.path.exists(os.path.join(cm, f)): self.cmd(f'codemodel {os.path.join(cm, f)}')
    def cmd(self, c): return self.lib.ngSpice_Command(c.encode())
    def circ(self, text):
        lines = text.splitlines() + ['.end']
        self.lib.ngSpice_Circ((ctypes.c_char_p * (len(lines) + 1))(*[l.encode() for l in lines], None))


def pwl(edges, t_end):
    """edges: [(t, level)] level changes with 1 ns ramps, starting from edges[0] level at t=0."""
    pts, lv = [(0.0, edges[0][1])], edges[0][1]
    for t, v in edges[1:]:
        if v != lv: pts += [(t, lv), (t + 1e-9, v)]; lv = v
    pts.append((t_end, lv))
    return 'PWL(' + ' '.join(f'{t:.12e} {v:g}' for t, v in pts) + ')'


def netlist(sc, seq, fixed=None):
    """seq: channel index sampled at each instant k (t_k = T0 + k*T). fixed: channel held on (for .op)."""
    p, m = SCEN[sc], MUX[SCEN[sc]['mux']]
    n = len(seq); t_end = T0 + (n + 0.5) * T
    L = [f'adc mux {sc}', f'.include {OPA_LIB}'] + ([f'.include {OPA322_LIB}'] if p.get('folm') == 'OPAx322' else []) + ['VAA vaa 0 3.3',
         f'.model swm sw vt=0.5 vh=0.01 ron={m["ron"]} roff=1e9',
         '.model swa sw vt=0.5 vh=0.01 ron=50 roff=1e9']
    # sources
    for i, (name, kind, v, r) in enumerate(CH):
        if kind == 'rail':
            L += [f'V{i} src{i} 0 {v}', f'R{i} src{i} s{i} {p.get("rsrc", {}).get(i, r)}']
        else:
            L += [f'V{i} src{i} 0 {v}', f'RBB{i} src{i} bb{i} {p["rbb"]}', f'CBB{i} bb{i} 0 {p["cbb"]}',
                  f'RLOC{i} bb{i} loc{i} {p["rloc"]}', f'CLOC{i} loc{i} 0 {p["cloc"]}']
            L += [f'XF{i} loc{i} s{i} vaa 0 s{i} {p.get("folm", "OPA365")}'] if p['fol'] else [f'RW{i} loc{i} s{i} 1e-3']
    # mux: CS(OFF) on each source, CD(OFF) on D, extra ON capacitance switched onto the source side
    extra = max(m['con'] - m['cd'] - m['cs'], 0.0)
    L.append(f'CD d 0 {m["cd"]}')
    # select changes at t_k + TSEL for the next sample's channel
    changes = [(0.0, seq[0])] + [(T0 + k * T + TSEL, seq[k + 1]) for k in range(n - 1)]
    for i in range(len(CH)):
        L.append(f'CS{i} s{i} 0 {m["cs"]}')
        if fixed is not None:
            ctl = f'DC {1 if i == fixed else 0}'
        else:
            ed = [(0.0, 1 if changes[0][1] == i else 0)]
            for tc, ch in changes[1:]:
                prev = ed[-1][1]
                if ch == i and prev == 0: ed.append((tc + m['ton'], 1))
                elif ch != i and prev == 1: ed.append((tc + m['toff'], 0))
            ctl = pwl(ed, t_end)
        L += [f'VC{i} c{i} 0 {ctl}', f'SW{i} s{i} d c{i} 0 swm']
        if extra > 0: L += [f'SX{i} s{i} sx{i} c{i} 0 swm', f'CX{i} sx{i} 0 {extra}']
    if fixed is None and m['q']:   # charge injection into D at each channel turn-on (2 ns pulse)
        qi = [f'{tc + m["ton"]:.12e}' for tc, ch in changes[1:]]
        pts = ['0 0'] + [f'{float(t):.12e} 0 {float(t) + 0.2e-9:.12e} {m["q"] / 2e-9:g} {float(t) + 2e-9:.12e} {m["q"] / 2e-9:g} {float(t) + 2.2e-9:.12e} 0' for t in qi]
        L.append(f'IQ 0 d PWL({" ".join(pts)})')
    # post-mux buffer, kickback filter, ADS7056 sampler
    L += ['XB d bo vaa 0 bo OPA365', 'RK bo ainp 33', 'CK ainp 0 680p']
    if fixed is not None:
        L.append('VCA ca 0 DC 1')
    else:
        ed = [(0.0, 0)]
        for k in range(n): ed += [(T0 + k * T - TACQ, 1), (T0 + k * T, 0)]
        L.append(f'VCA ca 0 {pwl(ed, t_end)}')
    L += ['SA ainp csh ca 0 swa', 'CSH csh 0 16p']
    return '\n'.join(L), t_end


def run_scenario(sc, cycles=100):
    os.makedirs(WORK, exist_ok=True)
    nch = len(CH); seq = [k % nch for k in range(cycles * nch)]
    ref = []
    # one libngspice instance per process; free each circuit and its plots after use (the library keeps every
    # loaded circuit and all vectors in memory otherwise)
    ng = NgSpice(); ng.cmd('set ngbehavior=psa')
    for c in range(nch):                       # DC reference with each channel held on
        net, _ = netlist(sc, [c], fixed=c); ng.circ(net); ng.cmd('op'); ng.out.clear()
        ng.cmd('print v(csh)')
        v = [l for l in ng.out if 'v(csh)' in l]
        ref.append(float(v[-1].split('=')[-1]))
        ng.cmd('destroy all'); ng.cmd('remcirc')
    net, t_end = netlist(sc, seq)
    net = net.replace('CSH csh 0 16p', 'CSH csh 0 16p\n.save v(csh)')   # keep only the sampled node
    open(os.path.join(WORK, f'{sc}.cir'), 'w').write(net)
    ng.circ(net)
    ng.cmd(f'tran 0.5n {t_end:.4e} 0 1n')
    dat = os.path.join(WORK, f'{sc}.dat'); ng.cmd(f'wrdata {dat} v(csh)')
    ng.cmd('destroy all'); ng.cmd('remcirc')
    err = [l for l in ng.out if any(k in l.lower() for k in ('error', 'timestep too small', 'aborted'))]
    import numpy as np
    d = np.loadtxt(dat); t, v = d[:, 0], d[:, 1]
    tk = T0 + np.arange(len(seq)) * T - 0.3e-9
    vs = np.interp(tk, t, v)
    e = (vs - np.array([ref[c] for c in seq])) / LSB
    return sc, ref, seq, e.tolist(), err


def report(results):
    import numpy as np
    nch = len(CH)
    print(f'\nError at the sampling instant vs. the DC value with that channel held (LSB, 1 LSB = {LSB*1e6:.0f} uV)')
    print('worst |error| per channel: first round-robin cycle / last cycle\n')
    hdr = f'{"scenario":26s}' + ''.join(f'{n:>15s}' for n, *_ in CH)
    print(hdr)
    rows = []
    for sc, ref, seq, e, err in results:
        e = np.array(e); first = e[:nch]; last = e[-nch:]
        s = f'{sc:26s}' + ''.join(f'{abs(first[c]):7.1f}/{abs(last[c]):<7.1f}' for c in range(nch))
        print(s + ('   ' + '; '.join(err[:2]) if err else ''))
        rows.append((sc, first, last))
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        fig, axs = plt.subplots(len(results), 1, figsize=(11, 2.3 * len(results)), sharex=True)
        for ax, (sc, ref, seq, e, err) in zip(np.atleast_1d(axs), results):
            e = np.array(e)
            for c, (name, *_) in enumerate(CH):
                ax.plot(np.arange(c, len(e), nch), e[c::nch], '.', ms=2, label=name)
            ax.set_ylabel('LSB'); ax.set_title(sc, fontsize=9); ax.grid(alpha=.3)
        np.atleast_1d(axs)[0].legend(fontsize=7, ncol=8, loc='upper right')
        np.atleast_1d(axs)[-1].set_xlabel('sample (2.5 MSPS, round-robin over 8 channels)')
        fig.tight_layout(); png = os.path.join(WORK, 'adc_mux_error.png'); fig.savefig(png, dpi=110)
        print('\nplot:', png)
    except ImportError:
        pass


def fetch():
    os.makedirs(MODELS, exist_ok=True)
    req = urllib.request.Request(OPA_URL, headers={'User-Agent': 'Mozilla/5.0'})
    zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req).read())).extractall(os.path.join(MODELS, 'opa365'))
    req = urllib.request.Request(OPA322_URL, headers={'User-Agent': 'Mozilla/5.0'})
    zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req).read())).extractall(os.path.join(MODELS, 'opa322'))
    print('OPA365 model:', OPA_LIB, os.path.exists(OPA_LIB))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=('fetch', 'run'))
    ap.add_argument('scenarios', nargs='*', default=list(SCEN))
    ap.add_argument('-j', type=int, default=2)
    ap.add_argument('--cycles', type=int, default=100)
    a = ap.parse_intermixed_args()
    if a.cmd == 'fetch': return fetch()
    if not os.path.exists(OPA_LIB): raise SystemExit('run "fetch" first (OPA365 model)')
    with ProcessPoolExecutor(a.j) as ex:
        res = list(ex.map(run_scenario, a.scenarios, [a.cycles] * len(a.scenarios)))
    report(res)


if __name__ == '__main__':
    main()
