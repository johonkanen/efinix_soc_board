"""LPDDR4 SI sweep: gen_sch.py -> kicad-cli (KiCad's IBIS converter) -> ngspice (libngspice of the KiCad 10.0.7 AppImage)
-> eyes, mask margins, over/undershoot -> results/.

  source ../../tools/p2k/bin/kicad_env.sh     # mounts the AppImage, sets KICAD_MOUNT
  python3 run_si.py --validate                # converted drivers vs the IBIS V-t tables
  python3 run_si.py [--sweep] [-j 12]         # width sweep: results/results.csv
  python3 run_si.py --xtalk                   # three coupled lines: results/results_xtalk.csv

Netlists and waveforms go to work/ (git-ignored). SI_REUSE=1 reuses waveforms already in work/.
"""
import argparse, ctypes, csv, glob, json, os, re, shutil, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np

_M = os.environ.get('KICAD_MOUNT', '')      # tools/p2k/bin/kicad_env.sh mounts the AppImage here
for _k, _v in (('KICAD_CLI', f'{_M}/bin/kicad-cli'), ('NGSPICE_LIB', f'{_M}/shared/lib/libngspice.so.0'),
               ('NGSPICE_CM', f'{_M}/shared/lib/ngspice'), ('KICAD_SYMBOLS', f'{_M}/share/kicad/symbols')):
    os.environ.setdefault(_k, _v)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                'tools', 'kicad_ibis_simulation'))
from kicad_ibis import eye as keye      # noqa: E402  (shared eye analysis, submodule)
from kicad_ibis import fastnet           # noqa: E402  (direct netlists, KIBIS conversion cache)

HERE = os.path.dirname(os.path.abspath(__file__))
WORK, RES = os.path.join(HERE, 'work'), os.path.join(HERE, 'results')
KCACHE = os.path.join(WORK, 'kibis')      # KIBIS subcircuits by element key (kicad_ibis.fastnet)
MOUNT = os.environ.get('KICAD_MOUNT', '')
KCLI = os.path.join(MOUNT, 'bin', 'kicad-cli')
LIBNG = os.path.join(MOUNT, 'shared/lib/libngspice.so.0')
# kicad-cli writes the KIBIS subcircuits to $XDG_CACHE_HOME/kicad/10.0/ibis: a private dir per point (other sessions
# clear ~/.cache/kicad/10.0/ibis, and per-point dirs let the exports, ~7 min each, run in parallel)
def ibis_cache(tag): return os.path.join(WORK, 'xdg', tag, 'kicad', '10.0', 'ibis')
UI = 1e-6 / 2800          # set per case (run_point): the eye functions below use this global
SKIP = 12                 # start-up bits not used in the eye
VDDQ = {'typ': 1.10, 'min': 1.06, 'max': 1.17}


def masks(rate):
    """Rx masks: (shape, height V, width in UI of the case). JEDEC JESD209-4 LPDDR4 values as reproduced in TI SPRAD66B
    Table 3-3 and the Kingston D1621PM4 LPDDR4 data sheet (DQ Tx voltage and timings / CA input parameters).
    No column for 2800: the larger (conservative) of the neighbouring columns is used.
      DQ write (DRAM): rect VdIVW 140 mV x TdIVW 0.25 UI (3200/3733 column; 1600-2400: 0.22 UI)
      CA (DRAM): rect VcIVW 155 mV (3200) / 175 mV (1600-1867, used for 2800) x TcIVW 0.30 tCK (CA UI = tCK)
      DQ read (FPGA): TI's SoC-pad diamond 140 mV x 0.61 UI (SPRAD66B, 3200 column), a proxy: Efinix publishes no Rx
        mask. Used at 2800 too (it is 0.42 UI at 1600; the larger UI fraction is the conservative one).
      DQS / CK: no JEDEC Rx mask for the strobe/clock; the DQ write mask is applied to the differential signal as a proxy.
    """
    ca_v = 155e-3 if rate >= 3200 else 175e-3
    return {'dq_write': ('rect', 140e-3, 0.25), 'ca': ('rect', ca_v, 0.30), 'dq_read': ('diamond', 140e-3, 0.61),
            'dqs_write': ('rect', 140e-3, 0.25), 'dqs_read': ('diamond', 140e-3, 0.61), 'ck': ('rect', 140e-3, 0.25)}


def limits(kind, corner):
    """Over/undershoot at the receiver pin, single-ended. DRAM: JEDEC LPDDR4 AC overshoot/undershoot, peak 0.3 V above
    VDDQ (actual) / below VSS, area <= 0.1 V-ns (Kingston D1621PM4 §1.2.4, CXMT Table 5-30); DC abs max -0.4 ... 1.5 V.
    FPGA: the Ti135 data sheet (DSTi135 v1.9, Table 82) has no VIN row for the DDR pins and no overshoot table; VDDQ_PHY
    abs max is 1.21 V. The JEDEC LPDDR4 0.3 V figure is used as the proxy there too."""
    v = VDDQ[corner]
    return (-0.3, v + 0.3)


# ---------------------------------------------------------------------------------------------------------- netlists
def simplify(t, v, tol):
    """Douglas-Peucker on a PWL (iterative)."""
    keep = np.zeros(len(t), bool); keep[[0, -1]] = True
    stack = [(0, len(t) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2: continue
        tt, vv = t[a + 1:b], v[a + 1:b]
        lin = v[a] + (v[b] - v[a]) * (tt - t[a]) / (t[b] - t[a])
        i = int(np.argmax(np.abs(vv - lin)))
        if abs(vv[i] - lin[i]) > tol:
            m = a + 1 + i; keep[m] = True; stack += [(a, m), (m, b)]
    return t[keep], v[keep]


def clean_cache(text, dt=0.5e-12, tol=1e-3):
    """KIBIS writes the switching coefficients Ku/Kd as PWL sources with ~1e5 points per driver (0.8 ps steps, every
    IBIS waveform sample), which makes ngspice crawl, and with narrow solver spikes (to -0.9 / +1.3 for a few ps where
    the two-waveform system is ill-conditioned). Resample to 0.5 ps, median-filter over 2.5 ps, simplify to 1e-3."""
    def fix(m):
        a = np.array(m.group(2).split(), float).reshape(-1, 2)
        t, v = a[:, 0], a[:, 1]
        t, idx = np.unique(t[::-1], return_index=True); v = v[::-1][idx]       # last value wins at repeated times
        tu = np.arange(0, t[-1] + dt / 2, dt); vu = np.interp(tu, t, v)
        w = np.lib.stride_tricks.sliding_window_view(np.pad(vu, 2, mode='edge'), 5)
        ts, vs = simplify(tu, np.median(w, axis=1), tol)
        return m.group(1) + ' '.join(f'{x:.6e} {y:.6e}' for x, y in zip(ts, vs)) + ' )'
    return re.sub(r'^(Vk[ud] K[UD] GND pwl \()(.*?)\)', fix, text, flags=re.M)


def pwl_of(text, which):
    m = re.search(rf'^Vk{which} K{which.upper()} GND pwl \((.*?)\)', text, re.M | re.S)
    a = np.array(m.group(1).split(), float).reshape(-1, 2)
    t, idx = np.unique(a[::-1, 0], return_index=True)
    return t, a[::-1, 1][idx]


def synth_kukd(text, f0, new_bits):
    """Rewrite a KIBIS PRBS driver's Ku/Kd for another bit pattern (KiCad 10's differential IBIS drivers come out with
    empty Ku/Kd, its PRBS has no delay/seed/inversion, and RECTDRIVER rejects V-t tables longer than a bit). One
    rising and one falling edge segment (3 bits long, from the bit boundary) are cut from KIBIS' own coefficients for
    the PRBS it generated, and laid at every transition of new_bits; a segment is cut off at the next transition, as
    KIBIS does. Used for the N leg of the pairs (complement) and the crosstalk aggressors (shifted / constant)."""
    ui = 1 / f0
    tu, ku = pwl_of(text, 'u'); td_, kd = pwl_of(text, 'd')
    dt = 0.5e-12
    n_src = int(round(tu[-1] / ui))
    src = (np.interp((np.arange(n_src) + 0.98) * ui, tu, ku) > 0.5).astype(int)
    seg_n = int(round(3 * ui / dt)); tt = np.arange(seg_n) * dt
    segs = {}
    for k in range(1, n_src - 3):
        e = 'r' if src[k - 1] == 0 and src[k] == 1 else 'f' if src[k - 1] == 1 and src[k] == 0 else None
        if e and e not in segs and src[k] == src[k + 1] == src[k + 2]:
            segs[e] = (np.interp(k * ui + tt, tu, ku), np.interp(k * ui + tt, td_, kd))
    if len(segs) < 2: raise RuntimeError('no 3-bit runs in the KIBIS pattern')
    n = len(new_bits); T = np.arange(int(round(n * ui / dt)) + 1) * dt
    U = np.empty_like(T); D = np.empty_like(T)
    lvl = {1: (segs['r'][0][-1], segs['r'][1][-1]), 0: (segs['f'][0][-1], segs['f'][1][-1])}
    U[:], D[:] = lvl[int(new_bits[0])]
    k = 0
    while k < n:
        j = k + 1
        while j < n and new_bits[j] == new_bits[k]: j += 1
        if k > 0:
            su, sd = segs['r' if new_bits[k] else 'f']
            i0, i1 = int(round(k * ui / dt)), min(int(round(j * ui / dt)), len(T))
            L = i1 - i0; m = min(L, seg_n)
            U[i0:i0 + m], D[i0:i0 + m] = su[:m], sd[:m]
            if L > m: U[i0 + m:i1], D[i0 + m:i1] = su[-1], sd[-1]
        k = j
    if T[-1] < tu[-1]:
        T = np.append(T, tu[-1]); U = np.append(U, U[-1]); D = np.append(D, D[-1])
    fmt = lambda t, v: ' '.join(f'{x:.6e} {y:.6e}' for x, y in zip(t, v))
    text = re.sub(r'^(Vku KU GND pwl \().*?\)', lambda mm: mm.group(1) + fmt(T, U) + ' )', text, flags=re.M | re.S)
    text = re.sub(r'^(Vkd KD GND pwl \().*?\)', lambda mm: mm.group(1) + fmt(T, D) + ' )', text, flags=re.M | re.S)
    return text


def post_cache(job):
    """One KIBIS subcircuit: new bit pattern if asked (synth_kukd), then the Ku/Kd clean-up (clean_cache)."""
    path, p, ui = job
    s = open(path).read()
    if p and 'Vku KU' in s:
        f0 = 1 / ui
        tu, ku = pwl_of(s, 'u')
        n = int(round(tu[-1] * f0))
        src = (np.interp((np.arange(n) + 0.98) / f0, tu, ku) > 0.5).astype(int)
        new = 1 - src if p[0] == 'inv' else np.roll(src, p[1]) if p[0] == 'shift' else np.full(n, p[1])
        s = synth_kukd(s, f0, new)
    open(path, 'w').write(s if os.environ.get('SI_RAW_KUKD') else clean_cache(s))


def export(tag, gen_args, patterns=None):
    """gen_sch.py -> work/tag.kicad_sch -> kicad-cli spice netlist with the IBIS subcircuits copied next to it.
    patterns: {case: ('shift', k) | ('const', 0|1)} rewrites the Ku/Kd of that case's driver (synth_kukd); the N legs of
    the pairs get ('inv',)."""
    sch = os.path.join(WORK, tag + '.kicad_sch')
    subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gen_sch.py'), sch, '--models', '../models'] + gen_args,
                   check=True, env=dict(os.environ))
    meta = json.load(open(os.path.join(WORK, tag + '.json')))
    IBIS_CACHE = ibis_cache(tag); shutil.rmtree(IBIS_CACHE, ignore_errors=True)
    r = subprocess.run([KCLI, 'sch', 'export', 'netlist', '--format', 'spice', '-o', tag + '.cir', tag + '.kicad_sch'],
                       cwd=WORK, capture_output=True, text=True, env=dict(os.environ, XDG_CACHE_HOME=os.path.join(WORK, 'xdg', tag)))
    msgs = sorted(set(l for l in (r.stdout + r.stderr).splitlines() if l.strip()))
    if r.returncode or any('rror' in m or 'Invalid' in m for m in msgs):
        sys.exit(f'{tag}: kicad-cli failed:\n' + '\n'.join(msgs))
    idir = os.path.join(WORK, tag + '_ibis'); shutil.rmtree(idir, ignore_errors=True); os.makedirs(idir)
    cir = open(os.path.join(WORK, tag + '.cir')).read()
    pat, ui_of = {}, {}
    for case, m in meta.items():
        if case.startswith('_'): continue
        ui_of[m['drv']] = m.get('ui')
        if m.get('inv'): pat[m['inv']] = ('inv',); ui_of[m['inv']] = m['ui']   # N leg: complement of the P leg
        if case in (patterns or {}): pat[m['drv']] = patterns[case]
    jobs = []
    for f in glob.glob(os.path.join(IBIS_CACHE, '*.cache')):   # copy at once: the cache dir is KiCad's, shared
        dst = os.path.join(idir, os.path.basename(f)); shutil.copy(f, dst); cir = cir.replace(f, dst)
        ref = os.path.basename(f).split('.')[0]
        jobs.append((dst, pat.get(ref), ui_of.get(ref)))
    for j in jobs: post_cache(j)
    cir = re.sub(r'(?<=\s)/(\w+)', r'\1', cir)            # KiCad net names '/x' -> 'x' (ngspice reads '/' as divide)
    if '_cpl' in meta:                                     # crosstalk: the coupled line between the _f and _m nets
        c = meta['_cpl']
        cir = cir.replace('\n.end', '\n' + cpl_lines(c) + '\n.end')
    open(os.path.join(WORK, tag + '.cir'), 'w').write(cir)
    return [m for m in msgs if m], meta


def cpl_lines(c):
    sys.path.insert(0, HERE)
    from zsolve_widths import cl_matrix
    key = os.path.join(WORK, f"clm_{c['layer']}_{c['w']:.3f}_{c['gap']:.3f}.json")   # ~35 s per solve: cached
    if not os.path.exists(key): json.dump(cl_matrix(c['layer'], c['w'], c['gap'], 3), open(key, 'w'))
    Lm, Cm, Rdc = json.load(open(key))
    tri = lambda M: ' '.join(f'{M[i][j]:.6e}' for i in range(3) for j in range(i, 3))
    R = [[Rdc if i == j else 0 for j in range(3)] for i in range(3)]
    G = [[0] * 3 for _ in range(3)]
    return (f"P1 {' '.join(c['nodes_in'])} 0 {' '.join(c['nodes_out'])} 0 PXT\n"
            f".model PXT CPL length={c['len'] * 1e-3:.6e}\n+R={tri(R)}\n+L={tri(Lm)}\n+G={tri(G)}\n+C={tri(Cm)}")


def ngspice_checked(cir, vecs, out):
    """ngspice, and if the run stopped early ("timestep too small", seen on a few netlists with method=gear), once
    more with method=trap. Exit if it still ends before the .tran stop time."""
    text = open(cir).read()
    t_stop = float(re.search(r'^\.tran \S+ ([\d.]+)n', text, re.M).group(1)) * 1e-9
    try:
        t, w = ngspice(cir, vecs, out)
        if t[-1] > 0.99 * t_stop: return t, w
    except SystemExit:
        pass
    alt = cir.replace('.cir', '_trap.cir')
    open(alt, 'w').write(re.sub(r'^\.options .*$', '.options method=trap reltol=1e-4', text, flags=re.M))
    t, w = ngspice(alt, vecs, out)
    if t[-1] < 0.99 * t_stop: sys.exit(f'{cir}: ngspice stopped at {t[-1] * 1e9:.1f} ns of {t_stop * 1e9:.1f} ns')
    return t, w


def ngspice(cir, vecs, out):
    """Run one netlist in a fresh process through libngspice (ctypes); write the vectors to out (wrdata)."""
    code = f'''
import ctypes, glob, os
ng = ctypes.CDLL({LIBNG!r})
log = []
PF = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
EX = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
pf = PF(lambda s, i, u: log.append(s.decode(errors='replace')) or 0); ex = EX(lambda *a: 0)
ng.ngSpice_Init(pf, pf, ex, None, None, None, None)
c = lambda s: ng.ngSpice_Command(s.encode())
for cm in glob.glob(os.path.join(os.path.dirname({LIBNG!r}), 'ngspice', '*.cm')): c('codemodel ' + cm)
c('set wr_singlescale'); c('set wr_vecnames'); c('source {cir}'); c('run')
c('wrdata {out} ' + {' '.join(f'v({v})' for v in vecs)!r})
open({out + '.log'!r}, 'w').write('\\n'.join(log))
'''
    r = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True)
    if r.returncode or not os.path.exists(out): sys.exit(f'ngspice failed on {cir}: {r.stderr[-2000:]}')
    d = np.loadtxt(out, skiprows=1)
    return d[:, 0], {v: d[:, i + 1] for i, v in enumerate(vecs)}


# -------------------------------------------------------------------------------------------------------------- eyes
def driver_bits(t, vd):
    """Bit grid and bit values from the driver's own die waveform: edges sit on phi + k*UI (phi from the mid-level
    crossings), bit k is the level at phi + (k + 0.5)*UI. Avoids depending on KIBIS' PRBS seed and polarity."""
    lo, hi = np.percentile(vd, [2, 98]); mid = (lo + hi) / 2
    s = np.sign(vd - mid); i = np.nonzero(s[1:] != s[:-1])[0]
    tc = t[i] + (mid - vd[i]) * (t[i + 1] - t[i]) / (vd[i + 1] - vd[i])
    phi = np.angle(np.mean(np.exp(2j * np.pi * tc / UI))) / (2 * np.pi) * UI % UI
    n = int((t[-1] - 2e-9 - phi) / UI)        # the stimulus ends 2 ns before the end of .tran (gen_sch.py)
    bits = (np.interp(phi + (np.arange(n) + 0.5) * UI, t, vd) > mid).astype(int)
    # on a badly mismatched line the reflection back to the driver die can flip isolated bits: replace the samples
    # by the PRBS7 (KIBIS: x^7+x^6+1) rotation/polarity that matches them best
    best = max(((np.mean(c == bits), c) for c in prbs7_candidates(n)), key=lambda x: x[0])
    if best[0] >= 0.9: bits = best[1]
    return phi, bits


def prbs7_candidates(n):
    seqs = []
    for taps in ((7, 6), (7, 1)):            # the polynomial and its reciprocal (bit order of the generator)
        r = [1] * 7; out = []
        for _ in range(127):
            b = r[taps[0] - 1] ^ r[taps[1] - 1]; out.append(r[-1]); r = [b] + r[:-1]
        seqs.append(np.array(out))
    for q in seqs:
        qq = np.tile(q, n // 127 + 2)
        for k in range(127):
            for pol in (0, 1): yield qq[k:k + n] ^ pol


def fold(t, v, phi, bits, dt=1e-12):
    """Align the receiver waveform to the driver bits (cross-correlation over 0-4 ns), return per-bit traces."""
    spb = int(round(UI / dt)); n = len(bits)
    tt = phi + np.arange(0, n * spb) * dt; vv = np.interp(tt, t, v)
    ideal = np.repeat(bits * 2 - 1.0, spb)
    s0 = SKIP * spb; L = int(4e-9 / dt)
    a = vv[s0:] - vv[s0:].mean(); b = ideal[s0:]
    nf = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    xc = np.fft.irfft(np.fft.rfft(a, nf) * np.conj(np.fft.rfft(b, nf)), nf)[:L]   # xc[lag] = sum a[i+lag] b[i]
    ph = np.arange(spb) * dt

    def cut(lag):
        traces, labels = [], []
        for k in range(SKIP, n):
            t0 = phi + lag + k * UI
            if t0 + UI > t[-1]: break
            traces.append(np.interp(t0 + ph, t, v)); labels.append(bits[k])
        return np.array(traces), np.array(labels)
    # a slow, mismatched line broadens the correlation peak and can put it one bit off: keep the whole-UI shift of
    # the peak lag that gives the largest eye opening
    best = None
    for m in range(-2, 3):
        lag = int(np.argmax(xc)) * dt + m * UI
        if lag < 0: continue
        tr, lab = cut(lag); op = (tr[lab == 1].min(0) - tr[lab == 0].max(0)).max()
        if best is None or op > best[0]: best = (op, lag, tr, lab)
    return ph, best[2], best[3], best[1]


def eye_metrics(ph, tr, lab, mask):
    shape, V, W = mask; dt = ph[1] - ph[0]; w = int(round(W * UI / dt))
    top, bot = tr[lab == 1].min(0), tr[lab == 0].max(0)
    op = top - bot
    eh = op.max(); tc = int(op.argmax())
    vref = (top[tc] + bot[tc]) / 2
    # widest Vref: eye width at zero height, and at the mask height, scanning Vref
    def widths(vrs, h):   # longest run of 'open' phases for each Vref (vectorised)
        ok = (top[None, :] >= vrs[:, None] + h / 2) & (bot[None, :] <= vrs[:, None] - h / 2)
        d = np.diff(np.pad(ok.astype(np.int8), ((0, 0), (1, 1))), axis=1)
        out = np.zeros(len(vrs))
        for i in range(len(vrs)):
            s, e = np.nonzero(d[i] == 1)[0], np.nonzero(d[i] == -1)[0]
            if len(s): out[i] = (e - s).max()
        return out * dt
    vr_scan = np.linspace(bot.min(), top.max(), 400)
    ew0 = widths(vr_scan, 0).max()
    wm = widths(vr_scan, V); ewm, vr_m = wm.max(), vr_scan[int(wm.argmax())]
    # voltage margin of the mask at its best position (opening minus mask height, rect or diamond)
    vm = -1e9
    for s in range(0, len(ph) - w):
        if shape == 'rect':
            o = top[s:s + w].min() - bot[s:s + w].max() - V
        else:
            x = np.abs(np.arange(w) - (w - 1) / 2) / ((w - 1) / 2)
            h = V / 2 * (1 - x)
            o = (top[s:s + w] - h).min() - (bot[s:s + w] + h).max()
        vm = max(vm, o)
    return dict(eh_mV=eh * 1e3, ew0_ps=ew0 * 1e12, vref_mV=vr_m * 1e3, ew_mask_ps=ewm * 1e12,
                t_margin_ps=(ewm - W * UI) * 1e12 if ewm > 0 else float('nan'), v_margin_mV=vm * 1e3,
                top=top, bot=bot)


def plot_eye(png, title, ph, tr, lab, m, mask, extra=None):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=110)
    x = np.concatenate([ph, ph + UI]) * 1e12
    for i in range(len(tr)):
        nxt = tr[i + 1] if i + 1 < len(tr) else tr[i]
        ax.plot(x, np.concatenate([tr[i], nxt]) * 1e3, color='#1f5fa8', lw=0.4, alpha=0.25)
    shape, V, W = mask
    # mask drawn at the best voltage-margin position for display: centre on the widest point at its Vref
    c = (ph[int(np.argmax(m['top'] - m['bot']))]) * 1e12; vr = m['vref_mV']; w = W * UI * 1e12; h = V * 1e3
    if shape == 'rect':
        ax.add_patch(plt.Rectangle((c - w / 2, vr - h / 2), w, h, fill=False, ec='#d62728', lw=1.4))
    else:
        ax.add_patch(plt.Polygon([(c - w / 2, vr), (c, vr + h / 2), (c + w / 2, vr), (c, vr - h / 2)], fill=False,
                                 ec='#d62728', lw=1.4))
    ax.set_xlim(0, 2 * UI * 1e12); ax.set_xlabel('time (ps), 2 UI'); ax.set_ylabel('mV')
    ax.set_title(title, fontsize=9)
    ax.text(0.01, 0.02, f"EH {m['eh_mV']:.0f} mV  EW {m['ew0_ps']:.0f} ps  mask margin {m['v_margin_mV']:+.0f} mV / "
            f"{m['t_margin_ps']:+.0f} ps" + (extra or ''), transform=ax.transAxes, fontsize=7.5)
    ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(png); plt.close(fig)


# -------------------------------------------------------------------------------------------------------------- sweep
def die(ref): return f'x{ref.lower()}.die0'


def max_area(t, x):
    """Largest single excursion area of x above 0 (V*s), for the JEDEC overshoot-area limit (0.1 V-ns)."""
    pos = np.clip(x, 0, None)
    if not pos.any(): return 0.0
    edges = np.diff(np.concatenate([[0], (pos > 0).astype(np.int8), [0]]))
    st, en = np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]
    return max(np.trapezoid(pos[a:b + 1], t[a:b + 1]) if b > a else 0.0 for a, b in zip(st, en))


def run_point(job):
    global UI
    tag, args, meta, plot = job
    p = point_params(args)
    cir = os.path.join(WORK, tag + '.cir')
    vecs = []
    cases = {k: m for k, m in meta.items() if not k.startswith('_')}
    for case, m in cases.items():
        vecs.append(die(m['drv']))
        for ref, pad in m['rx']:
            refs, pads = (ref, pad) if isinstance(ref, list) else ([ref], [pad])
            vecs += list(pads) + [die(r) for r in refs]
        if m.get('ne'): vecs.append(m['ne'])
    vecs = list(dict.fromkeys(vecs))
    dat = os.path.join(WORK, tag + '.dat')
    if os.environ.get('SI_REUSE') and os.path.exists(dat) and os.path.getmtime(dat) > os.path.getmtime(cir):
        d = np.loadtxt(dat, skiprows=1); t, w = d[:, 0], {v: d[:, i + 1] for i, v in enumerate(vecs)}
    else:
        t, w = ngspice_checked(cir, vecs, dat)
    rows = []
    MASK = masks(p['rate'])
    for case, m in cases.items():
        UI = m['ui']
        if m.get('victim') is False: continue       # crosstalk aggressors: only the victim is analysed
        vd = w[die(m['drv'])]
        if np.ptp(vd[t > SKIP * UI]) < 0.05:        # quiet victim (crosstalk noise run): coupled noise peaks only
            sel = t > SKIP * UI
            for ref, pad in m['rx']:
                for node, where in ((pad, 'ball'), (die(ref), 'die')):
                    v = w[node][sel] - np.median(w[node][sel])
                    ne = w[m['ne']][sel] - np.median(w[m['ne']][sel]) if m.get('ne') else np.zeros(1)
                    rows.append(dict(point=tag, case=case, kind='noise', net=m['net'], rx=ref, where=where,
                                     vmax_mV=np.abs(v).max() * 1e3, vmin_mV=v.min() * 1e3,
                                     ne_peak_mV=np.abs(ne).max() * 1e3, **p))
            continue
        phi, bits = keye.stimulus_bits(t, vd, UI)       # labels: KIBIS' PRBS7, aligned on the driver die
        mask = MASK[m['kind']]; lo, hi = limits(m['kind'], p['corner'])
        for ref, pad in m['rx']:
            diff = isinstance(ref, list)
            nodes = ((pad, 'ball'), (ref, 'die')) if diff else ((pad, 'ball'), (die(ref), 'die'))
            for node, where in nodes:
                if diff:
                    a_, b_ = (node if where == 'ball' else (die(node[0]), die(node[1])))
                    v = w[a_] - w[b_]; se = (w[a_], w[b_])
                else:
                    v = w[node]; se = (v,)
                ph, tr, lab, lag = keye.fold(t, v, phi, bits, UI, SKIP)
                e = keye.metrics(ph, tr, lab, mask, UI)
                sel = t > SKIP * UI
                vmax = max(x[sel].max() for x in se); vmin = min(x[sel].min() for x in se)
                vq = hi - 0.3
                osa = max(max_area(t[sel], x[sel] - vq) for x in se); usa = max(max_area(t[sel], -x[sel]) for x in se)
                row = dict(point=tag, case=case, kind=m['kind'], net=m['net'], rx=ref if not diff else '/'.join(ref),
                           where=where, delay_ps=lag * 1e12, vmax_mV=vmax * 1e3, vmin_mV=vmin * 1e3,
                           lim_lo_mV=lo * 1e3, lim_hi_mV=hi * 1e3, limits_ok=bool(lo <= vmin and vmax <= hi),
                           os_area_Vns=osa * 1e9, us_area_Vns=usa * 1e9,
                           **{k: v_ for k, v_ in e.items() if k not in ('top', 'bot')},
                           **{k: m.get(k) for k in ('fdrv', 'fodt', 'modt', 'pdds', 'caodt')}, **p)
                rows.append(row)
                if plot and where == 'die' and (plot is True or case in plot):
                    keye.save(os.path.join(RES, 'eyes', f'eye_{tag}_{case}_{row["rx"].replace("/", "-")}.png'),
                              ph, tr, lab, e, mask, UI, title=f'{case} ({m["net"]}) {row["rx"]} die, {tag}')
    return rows


def point_params(args):
    d = dict(zip(args[::2], args[1::2]))
    return dict(rate=float(d.get('--rate', 2800)), w_in=float(d.get('--w-in', 0.18)), w_out=float(d.get('--w-out', 0.25)),
                diff_in=d.get('--diff-in', '0.14/0.15'), diff_out=d.get('--diff-out', '0.20/0.20'),
                corner=d.get('--corner', 'typ'), pkg=d.get('--pkg', 'netlen'),
                xt_layer=d.get('--xtalk', ''), xt_w=d.get('--w', ''), xt_gap=d.get('--gap', ''))


def ibis_wf(path, model, edge, vfix=0.0):
    """[Rising|Falling Waveform] typ column of a model, for the table with V_fixture == vfix."""
    t = open(path).read()
    i = re.search(rf'^\[Model\]\s+{re.escape(model)}\s*$', t, re.M).start()
    j = t.find('[Model]', i + 8); blk = t[i:j if j > 0 else len(t)]
    unit = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'f': 1e-15}
    num = lambda s: float(re.match(r'[-+.\deE]+', s).group()) * unit.get(re.sub(r'[-+.\deE]+', '', s)[:1].lower(), 1)
    for w in re.finditer(rf'\[{edge} Waveform\](.*?)(?=\n\[)', blk, re.S):
        body = w.group(1)
        vf = re.search(r'^V_fixture\s*=\s*(\S+)', body, re.M)
        if not vf or abs(num(vf.group(1).rstrip('Vv')) - vfix) > 1e-6: continue
        rows = [l.split() for l in body.splitlines() if l.strip() and not l.strip().startswith('|') and '=' not in l]
        return np.array([num(r[0].rstrip('sS')) for r in rows]), np.array([num(r[1].rstrip('Vv')) for r in rows])
    raise KeyError(f'{model} {edge} V_fixture={vfix}')


def validate():
    """Converted driver (package removed, trimmed V-t tables) into its IBIS fixture to GND (Efinix 20 ohm, Winbond
    50 ohm) vs the untrimmed IBIS V-t table (V_fixture 0): levels and 20-80 % edge times."""
    msgs, meta = export('validate', ['--validate'])
    idir = os.path.join(WORK, 'validate_ibis')
    for f in glob.glob(os.path.join(idir, '*.cache')):     # the V-t tables are at the die, without package
        s = open(f).read()
        s = re.sub(r'^(RPIN \S+ \S+) \S+', r'\1 1e-6', s, flags=re.M)
        s = re.sub(r'^(LPIN \S+ \S+) \S+', r'\1 1e-15', s, flags=re.M)
        s = re.sub(r'^(CPIN \S+ \S+) \S+', r'\1 1e-18', s, flags=re.M)
        open(f, 'w').write(s)
    t, w = ngspice(os.path.join(WORK, 'validate.cir'), [f'{k}_o' for k in meta], os.path.join(WORK, 'validate.dat'))
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, len(meta), figsize=(4.2 * len(meta), 3.4), dpi=110)
    lines = ['| driver model | fixture | edge | V start / end, IBIS (mV) | V start / end, KiCad (mV) | t20-80, IBIS (ps) '
             '| t20-80, KiCad (ps) |', '|---|---|---|---|---|---|---|']

    def t2080(tt, vv):
        a, b = vv[0], vv[-1]; lo, hi = a + 0.2 * (b - a), a + 0.8 * (b - a)
        x = (vv - lo) / (hi - lo) if b > a else (lo - vv) / (lo - hi)
        i1 = np.argmax(x >= 0); i2 = np.argmax(x >= 1)
        return tt[i1], tt[i2] - tt[i1]
    for ax, (k, m) in zip(axs, meta.items()):
        v = w[f'{k}_o']; lib = os.path.join(HERE, 'models', m['lib'].replace('.ibs', '_full.ibs'))
        for edge, sel in (('Rising', t < 4.0e-9), ('Falling', t >= 4.0e-9)):
            ti, vi = ibis_wf(lib, m['model'], edge)
            tk, vk = t[sel], v[sel]
            mid = (vi[0] + vi[-1]) / 2
            ic = np.argmax(vk > mid) if edge == 'Rising' else np.argmax(vk < mid)
            _, d_ic = t2080(ti, vi)
            tsim = tk[ic] - (ti[np.argmax(vi > mid) if edge == 'Rising' else np.argmax(vi < mid)])
            ts = tsim + ti; vs = np.interp(ts, tk, vk)
            _, d_k = t2080(ts, vs)
            lines.append(f"| {m['model']} | {m['rf']} ohm to GND | {edge.lower()} | {vi[0]*1e3:.0f} / {vi[-1]*1e3:.0f} | "
                         f"{vs[0]*1e3:.0f} / {vk[-1]*1e3:.0f} | {d_ic*1e12:.1f} | {d_k*1e12:.1f} |")
            ax.plot(ti * 1e12, vi * 1e3, 'k', lw=1.2, label=f'IBIS {edge.lower()}')
            ax.plot(ti * 1e12, vs * 1e3, '--', lw=1.2, label=f'KiCad {edge.lower()}')
        ax.set_title(f"{m['model']} into {m['rf']} ohm to GND", fontsize=8); ax.set_xlabel('ps'); ax.set_ylabel('mV')
        ax.grid(alpha=.3); ax.legend(fontsize=7); ax.set_xlim(0, 800)
    fig.tight_layout(); fig.savefig(os.path.join(RES, 'validate_drivers.png')); plt.close(fig)
    open(os.path.join(RES, 'validate_drivers.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


# width points: (inner, outer). Today 0.18 / 0.25 (40 ohm); each layer swept with the other at today's width, then both
W_IN = (0.15, 0.12, 0.10, 0.09)
W_OUT = (0.20, 0.15, 0.12, 0.10, 0.09)
WIDTHS = [(0.18, 0.25)] + [(w, 0.25) for w in W_IN] + [(0.18, w) for w in W_OUT] + [(0.10, 0.10), (0.09, 0.09)]
KEY_WIDTHS = [(0.18, 0.25), (0.12, 0.15), (0.10, 0.10), (0.09, 0.09)]     # also at the min/max corners
# pair geometry (w/gap) near 80, 90, 100 ohm (results/zsolve.csv): inner, outer
DIFFS = [('0.14/0.15', '0.20/0.20'), ('0.10/0.10', '0.12/0.10'), ('0.10/0.13', '0.10/0.10'), ('0.09/0.20', '0.10/0.15')]
# a point is run as several small netlists (one with all channels needs > 9 GB in ngspice: about 0.3 GB per IBIS
# driver at 150 bits); a part never mixes CA (SDR, 2 UI per bit) with data channels
PARTS_BASE = {'wa': r'w_(dq4|dq6|dq1|dq11)', 'wb': r'w_(dq10|dq23|dq27|dm3)', 'ra': r'r_(dq4|dq6|dq1|dq11)',
              'rb': r'r_(dq10|dq23|dq27|dm3)', 'sw': r'w_dqs\d', 'sr': r'r_dqs\d', 'ck': r'ck_40',
              'ca': r'(ca1|ca2|ca4)_40', 'cs': r'(cs2_n|cs0_n)_40', 'ke': r'cke0_40'}
# (CS and CKE in one netlist stop ngspice ("timestep too small", gear and trap); each alone runs)
PARTS_ALL = {'vw': r'w_dq4_d.*', 'vr': r'r_dq4_p.*', 'vk': r'ck_80', 'vc': r'(ca1_(60|80|off|40_d48)|cs2_n_off)'}
PARTS_PAIRS = {k: PARTS_BASE[k] for k in ('sw', 'sr', 'ck')}


SMALL_WIDTHS = [(0.18, 0.25), (0.12, 0.25), (0.10, 0.25), (0.18, 0.15), (0.18, 0.10), (0.12, 0.15), (0.10, 0.10),
                (0.09, 0.09)]


def small_points():
    """A few minutes with the fast path: typ, 2800 and 3200, SMALL_WIDTHS with every base channel, the pair
    geometries with DQS/CK."""
    pts = []
    for rate in (2800, 3200):
        for wi, wo in SMALL_WIDTHS:
            pts.append((f'r{rate}_typ_i{wi:.2f}_o{wo:.2f}', ['--rate', str(rate), '--w-in', str(wi), '--w-out', str(wo)],
                        PARTS_BASE, rate == 2800 and (wi, wo) in ((0.18, 0.25), (0.10, 0.10))))
        for di, do in DIFFS[1:]:
            pts.append((f'r{rate}_typ_d{di.replace("/", "-")}_{do.replace("/", "-")}',
                        ['--rate', str(rate), '--diff-in', di, '--diff-out', do], PARTS_PAIRS, False))
    return pts


def sweep_points(quick=False):
    """(point tag, gen_sch args, eye plot cases); run_si splits each into parts."""
    pts = []
    for rate in (2800, 3200):
        for corner in ('typ', 'min', 'max'):
            for wi, wo in ((WIDTHS + [w for w in KEY_WIDTHS if w not in WIDTHS]) if corner == 'typ' else KEY_WIDTHS):
                if quick and (corner != 'typ' or (wi, wo) not in KEY_WIDTHS[::2]): continue
                args = ['--rate', str(rate), '--corner', corner, '--w-in', str(wi), '--w-out', str(wo)]
                parts = dict(PARTS_BASE, **(PARTS_ALL if corner == 'typ' else {}))
                pts.append((f'r{rate}_{corner}_i{wi:.2f}_o{wo:.2f}', args, parts,
                            corner == 'typ' and (wi, wo) in KEY_WIDTHS))
        if quick: continue
        for wi, wo in KEY_WIDTHS:      # package as the vendor file's lumped pin RLC
            pts.append((f'r{rate}_typ_i{wi:.2f}_o{wo:.2f}_pkgfile',
                        ['--rate', str(rate), '--w-in', str(wi), '--w-out', str(wo), '--pkg', 'file'], PARTS_BASE, False))
        for corner in ('typ', 'min'):
            for di, do in DIFFS[1:]:
                pts.append((f'r{rate}_{corner}_d{di.replace("/", "-")}_{do.replace("/", "-")}',
                            ['--rate', str(rate), '--corner', corner, '--diff-in', di, '--diff-out', do], PARTS_PAIRS,
                            corner == 'typ'))
    return pts


# crosstalk: (layer, w, gap): today's width at the board's 0.11 mm clearance and at the 0.2 mm xtalk-spacing rule, and
# the narrow candidate at the same pitch (the freed width becomes gap)
XT = [('inner', 0.18, 0.11), ('inner', 0.10, 0.19), ('inner', 0.18, 0.20), ('inner', 0.10, 0.28),
      ('outer', 0.25, 0.11), ('outer', 0.10, 0.26), ('outer', 0.25, 0.20), ('outer', 0.10, 0.35)]
XT_LEN = {'inner': 25.0, 'outer': 25.0}


def xtalk_points():
    pts = []
    for rate in (2800, 3200):
        for layer, wv, g in XT:
            base = f'xt_r{rate}_{layer}_w{wv:.2f}_g{g:.2f}'
            args = ['--xtalk', layer, '--w', str(wv), '--gap', str(g), '--len', str(XT_LEN[layer]), '--rate', str(rate)]
            # 1 victim PRBS, aggressors uncorrelated PRBS; 2 aggressors quiet (reference); 3 victim quiet low,
            # aggressors in phase (peak coupled noise)
            for k, pat in (('rand', {'xa1': ('shift', 37), 'xa2': ('shift', 71)}),
                           ('quiet', {'xa1': ('const', 0), 'xa2': ('const', 0)}), ('noise', {'xv': ('const', 0), 'xa2': ('shift', 0)})):
                pts.append((f'{base}_{k}', args + ['--bits', '150'], {'x': None}, pat))
    return pts


def complete(dat, cir):
    """A waveform file that reaches the .tran stop time (ngspice can stop early and still write it)."""
    try:
        t_stop = float(re.search(r'^\.tran \S+ ([\d.]+)n', open(cir).read(), re.M).group(1)) * 1e-9
        last = open(dat, 'rb').read()[-400:].decode(errors='replace').strip().splitlines()[-1].split()[0]
        return float(last) > 0.99 * t_stop
    except Exception:
        return False


def fast_gen(job):
    """Phase 1 of the fast path: gen_sch.py --fast -> work/<tag>.net (fastnet netlist as JSON) + <tag>.json (meta)."""
    tag, args, extra, xt = job
    subprocess.run([sys.executable, os.path.join(HERE, 'gen_sch.py'), os.path.join(WORK, tag + '.net'), '--fast']
                   + args, check=True)
    return json.load(open(os.path.join(WORK, tag + '.net')))['ib']


def fast_point(job):
    """Phase 3: netlist with the cached KIBIS subcircuits (patterns built in Python) -> ngspice -> eyes."""
    tag, args, extra, xt = job
    try:
        d = json.load(open(os.path.join(WORK, tag + '.net')))
        meta = json.load(open(os.path.join(WORK, tag + '.json')))
        n = fastnet.Netlist(tag); n.lines, n.ib, n.directives = d['lines'], d['ib'], d['directives']
        if xt:                             # crosstalk: aggressor / victim patterns, and the coupled line
            for case, p in extra.items():
                next(e for e in n.ib if e['ref'] == meta[case]['drv'])['pattern'] = list(p)
            n.lines += cpl_lines(meta['_cpl']).splitlines()
        cir = n.write(os.path.join(WORK, tag + '.cir'), fastnet.KibisCache(KCACHE))
        dat = os.path.join(WORK, tag + '.dat')
        if os.path.exists(dat): os.remove(dat)
        rows = run_point((tag, args, meta, True if xt else extra))
    except BaseException as e:
        print(f'{tag}: FAILED {type(e).__name__}: {e}'[:400], flush=True); return []
    for r in rows: r['point'] = tag.split('__')[0]; r['part'] = tag.split('__')[1] if '__' in tag else ''
    return rows


def full_point(job):
    tag, args, extra, xt = job        # extra: eye plots (True / False) or, for crosstalk, the aggressor patterns
    try:
        dat = os.path.join(WORK, tag + '.dat')
        if os.environ.get('SI_REUSE') and os.path.exists(dat) and complete(dat, os.path.join(WORK, tag + '.cir')):
            meta = json.load(open(os.path.join(WORK, tag + '.json')))
        else:
            if os.path.exists(dat): os.remove(dat)
            for attempt in range(3):     # kicad-cli instances started at the same moment can fail silently
                try:
                    msgs, meta = export(tag, args, extra if xt else None); break
                except SystemExit:
                    if attempt == 2: raise
                    import time, random; time.sleep(5 + 10 * random.random())
            msgs = [m for m in msgs if 'Bitrate' not in m]     # KIBIS: V-t table longer than a bit (prep_models.py)
            if msgs: print(tag, 'kicad-cli:', '; '.join(msgs), flush=True)
        if not [k for k in meta if not k.startswith('_')]: return []
        rows = run_point((tag, args, meta, True if xt else extra))
    except BaseException as e:      # one failed netlist must not lose the sweep
        print(f'{tag}: FAILED {type(e).__name__}: {e}'[:400], flush=True); return []
    for r in rows: r['point'] = tag.split('__')[0]; r['part'] = tag.split('__')[1] if '__' in tag else ''
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--validate', action='store_true', help='only check the converted drivers against IBIS V-t tables')
    ap.add_argument('--quick', action='store_true', help='typ corner, today / 0.10 / 0.09 mm only')
    ap.add_argument('--xtalk', action='store_true', help='three coupled lines (CPL)')
    ap.add_argument('--small', action='store_true', help='typ, 2800/3200, 8 width points, pair geometries (minutes)')
    ap.add_argument('--first', action='store_true', help='first result in about a minute: the worst DQ (dq4) write '
                    'and read and CA1, today vs 0.10 mm, typ, 2800 MT/s (4 small netlists in parallel)')
    ap.add_argument('--routed', action='store_true', help='the hand-routed byte lanes (results/board_paths_routed.json, '
                    'all 0.10 mm, DQS 0.10/0.20): the longest DQ of each byte, DM0, DQS0/2; typ, 2800/3200')
    ap.add_argument('--cke', action='store_true', help='CKE0 as routed (results/board_paths_cke.json: In2 0.12, B.Cu '
                    '0.25 mm), and at 0.10 mm inner on the same route; typ/min/max, 2800/3200')
    ap.add_argument('--only', help='regex on the point tag')
    ap.add_argument('--legacy', action='store_true', help='kicad-cli export per netlist (the slow path, for checks)')
    ap.add_argument('-j', type=int, default=2)     # RAM: shared machine, ~1-2 GB per netlist
    a = ap.parse_args()
    if not os.path.exists(LIBNG): sys.exit('source tools/p2k/bin/kicad_env.sh first (KICAD_MOUNT)')
    os.makedirs(WORK, exist_ok=True); os.makedirs(os.path.join(RES, 'eyes'), exist_ok=True)
    if a.validate: return validate()
    if a.first:
        pts = [(f'first_i{wi:.2f}_o{wo:.2f}', ['--rate', '2800', '--w-in', str(wi), '--w-out', str(wo)],
                {'dq': r'(w|r)_dq4', 'ca': r'ca1_40'}, True) for wi, wo in ((0.18, 0.25), (0.10, 0.10))]
        out = 'results_first'
    elif a.routed:
        dq, ds = ['ddr_dq3', 'ddr_dm0', 'ddr_dq15', 'ddr_dq19', 'ddr_dq28'], ['ddr_dqs0', 'ddr_dqs2']
        parts = {'wa': r'w_(dq3|dm0|dq15)', 'wb': r'w_(dq19|dq28)', 'ra': r'r_(dq3|dm0|dq15)', 'rb': r'r_(dq19|dq28)',
                 'sw': r'w_dqs\d', 'sr': r'r_dqs\d'}
        pts = [(f'routed_r{rate}', ['--rate', str(rate), '--w-in', '0.10', '--w-out', '0.10', '--diff-in', '0.10/0.2',
                                    '--paths', 'board_paths_routed.json', '--dq-nets', *dq, '--dqs-nets', *ds],
                parts, True) for rate in (2800, 3200)]
        out = 'results_routed'
    elif a.cke:
        pts = [(f'cke_r{rate}_{corner}_i{wi:.2f}', ['--rate', str(rate), '--corner', corner, '--w-in', f'{wi:.2f}',
                                                    '--w-out', '0.25', '--ca-paths', 'board_paths_cke.json',
                                                    '--ca-neck-cap', '0'], {'ke': r'cke0_40'}, corner == 'typ')
               for rate in (2800, 3200) for corner in ('typ', 'min', 'max') for wi in (0.12, 0.10)]
        out = 'results_cke'
    elif a.small:
        pts, out = small_points(), 'results_small'
    elif a.xtalk:
        pts, out = xtalk_points(), 'results_xtalk'
    else:
        pts, out = sweep_points(a.quick), 'results' + ('_quick' if a.quick else '')
    jobs = []
    for tag, args, parts, plot in pts:
        for pk, rx in parts.items():
            sub = tag if rx is None else f'{tag}__{pk}'
            jobs.append((sub, args + ([] if rx is None else ['--keep', rx]), plot, a.xtalk))
    if a.only: jobs = [j for j in jobs if re.search(a.only, j[0])]
    print(f'{len(jobs)} netlists', flush=True)
    rows = []
    if a.legacy:
        with ProcessPoolExecutor(a.j) as ex:     # kicad-cli export + ngspice per netlist; one KIBIS cache dir each
            for r in ex.map(full_point, jobs):
                rows += r
                if r: print(f'{r[0]["point"]}: {len(r)} rows', flush=True)
    else:
        import time; t0 = time.time()
        with ProcessPoolExecutor(a.j) as ex:                   # 1: netlists
            entries = [e for ib in ex.map(fast_gen, jobs) for e in ib]
        t1 = time.time()
        conv = fastnet.KibisCache(KCACHE).resolve(entries)    # 2: KIBIS, only what is not cached yet
        t2 = time.time()
        print(f'{len(jobs)} netlists in {t1 - t0:.0f} s; {conv} IBIS elements converted in {t2 - t1:.0f} s', flush=True)
        with ProcessPoolExecutor(a.j) as ex:                   # 3: ngspice + eyes
            for r in ex.map(fast_point, jobs):
                rows += r
        print(f'simulated in {time.time() - t2:.0f} s', flush=True)
    if a.only:   # a re-run of some netlists: replace their rows in the existing CSV
        old = os.path.join(RES, out + '.csv'); tags = {j[0] for j in jobs}
        if os.path.exists(old):
            keep = [r for r in csv.DictReader(open(old))
                    if (r['point'] + ('__' + r['part'] if r.get('part') else '')) not in tags]
            rows = keep + rows
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(RES, out + '.csv'), 'w', newline='') as f:
        wr = csv.DictWriter(f, keys); wr.writeheader(); wr.writerows(rows)
    print(f"{len(rows)} rows -> results/{out}.csv")
    if a.cke:
        print('| point | where | Vmax/Vmin mV | limits ok | overshoot / undershoot area V*ns | eye height mV | margin V mV | margin t ps |')
        for r in sorted(rows, key=lambda r: (r['point'], r['rx'], r['where'])):
            print(f"| {r['point']} {r['rx']} | {r['where']} | {r['vmax_mV']:.0f}/{r['vmin_mV']:.0f} | {r['limits_ok']} | "
                  f"{r['os_area_Vns']:.4f} / {r['us_area_Vns']:.4f} | {r['eh_mV']:.0f} | {r['v_margin_mV']:+.0f} | "
                  f"{r['t_margin_ps']:+.0f} |")
    if a.first or a.routed:
        print('| width in/out | case | where | eye height mV | eye width ps | margin V mV | margin t ps | Vmax/Vmin mV |')
        for r in sorted(rows, key=lambda r: (r['case'], r['where'], -r['w_in'])):
            if r['kind'] == 'dq_read' and r['where'] == 'ball': continue
            print(f"| {r['w_in']:.2f}/{r['w_out']:.2f} | {r['case']} {r['rx']} | {r['where']} | {r['eh_mV']:.0f} | "
                  f"{r['ew0_ps']:.0f} | {r['v_margin_mV']:+.0f} | {r['t_margin_ps']:+.0f} | {r['vmax_mV']:.0f}/{r['vmin_mV']:.0f} |")


if __name__ == '__main__':
    main()
