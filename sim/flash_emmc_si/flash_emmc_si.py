"""Do the QSPI flash (U601 IS25WP128) and eMMC (U1001 THGAMVG7T13BAIL) lines need series resistors?

    source ../../tools/p2k/bin/kicad_env.sh && export KICAD_MOUNT
    python3 flash_emmc_si.py prep          # models/ti135_lvcmos18.ibs (+ _fast, _slow corners) from the Efinix file
    python3 flash_emmc_si.py sweep [-j 3]  # results/sweep.csv + summary on stdout

FPGA side: the Efinix Titanium IBIS v1.5 lvcmos_1p8v_{4,8,12,16}ma_{fast,slow} models (bank 4A HSIO at 1.8 V,
Model_type I/O, so the same model is the receiver on reads), vendor pin RLC 1.035 ohm / 1.84 nH / 0.845 pF.
Memory side: no vendor IBIS (ISSI and KIOXIA give them on request only), so from the data sheets:
  receivers   lumped C behind 1 nH: flash CE#/SCK 7 pF, flash IO 12 pF (CIN / CIN/OUT max, 9.5), eMMC 6 pF (CDEVICE)
  drivers     a 0..1.8 V ramp behind a resistor: eMMC Driver Type-0 50 ohm (default; Type-1 33 ohm also run);
              flash: ISSI gives no impedance for its ODS settings (default 50 % strength), 35 and 70 ohm bracket it
Line: 0.1 mm on In2 = 53.8 ohm, 7.0 ps/mm (zsolve), lossless; a via (0.4 nH, 0.3 pF) at each end.
Pass criteria at the receiver: no ringback through the input thresholds after a crossing (flash VIL/VIH 0.3/0.7 VCC,
eMMC 0.35/0.625 VCCQ, Efinix 0.63/1.17 V), peak within -0.5 V .. VCC + 0.5 V (both memories' absolute maximum).
"""
import argparse, csv, itertools, os, re, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools/kicad_ibis_simulation')); sys.path.insert(0, os.path.join(ROOT, 'sim/lpddr4_si'))
_M = os.environ.get('KICAD_MOUNT', '')
for _k, _v in (('KICAD_CLI', f'{_M}/bin/kicad-cli'), ('NGSPICE_LIB', f'{_M}/shared/lib/libngspice.so.0'),
               ('NGSPICE_CM', f'{_M}/shared/lib/ngspice'), ('KICAD_SYMBOLS', f'{_M}/share/kicad/symbols')):
    os.environ.setdefault(_k, _v)
from kicad_ibis import fastnet, spice, ibisfix   # noqa: E402

MODELS, WORK, RES = (os.path.join(HERE, d) for d in ('models', 'work', 'results'))
EFX = os.path.join(ROOT, 'reference/efinix/ibis/titanium_ibis-v1.5/titanium_ibis.ibs')
DRV = [f'lvcmos_1p8v_{m}ma_{s}' for m in (4, 8, 12, 16) for s in ('fast', 'slow')]
PIN_RLC = ('1.035ohm', '1.840nH', '0.845pF')
Z0, PS_MM, VIA = 53.8, 7.0, (0.4e-9, 0.3e-12)
VCC = 1.8
OPTS = '.options method=gear maxord=2 reltol=1e-4'


def prep():
    os.makedirs(MODELS, exist_ok=True)
    from prep_models import trim_all
    blocks = ibisfix.extract_models(EFX, set(DRV))
    if len(blocks) != len(DRV): sys.exit(f'found {sorted(blocks)}')
    t = open(EFX, errors='replace').read().replace('\r\n', '\n')
    pkg = re.search(r'\[Package\]\n(.*?)\n(?=\|\n)', t, re.S).group(0)
    head = ('[IBIS Ver]       6.1\n[File Name]      ti135_lvcmos18.ibs\n[File Rev]       1.5-lvcmos18\n'
            '[Date]           May 23, 2025\n[Source]         Efinix Inc, titanium_ibis.ibs v1.5; lvcmos_1p8v models only\n'
            '[Disclaimer]     Data is for modeling purposes only and is not guaranteed.\n'
            '[Copyright]      Copyright (C) 2022-2025 Efinix Inc. All rights reserved.\n|\n'
            '[Component]      Ti135N484\n[Manufacturer]   Efinix Inc.\n' + pkg + '\n|\n'
            '[Pin]  signal_name     model_name              R_pin      L_pin     C_pin\n')
    pins = ''.join(f'P{i:<4} {m:22} {m:23} {PIN_RLC[0]:10} {PIN_RLC[1]:9} {PIN_RLC[2]}\n' for i, m in enumerate(DRV))
    body = '\n'.join(blocks[m].rstrip() for m in DRV).replace('\t', '  ')   # KiCad's parser does not take tabs
    txt = trim_all(head + pins + '|\n' + body + '\n|\n[End]\n', [])
    for name, corner in (('ti135_lvcmos18.ibs', None), ('ti135_lvcmos18_fast.ibs', 'max'), ('ti135_lvcmos18_slow.ibs', 'min')):
        out = txt if corner is None else ibisfix.corner_as_typ(txt, corner)
        open(os.path.join(MODELS, name), 'w').write(out.replace('ti135_lvcmos18.ibs', name))
        print('wrote', name)


# ---------------------------------------------------------------------------------------------------------- cases
# (link, direction, receiver C, VIL, VIH, length mm)
LINKS = {
    'flash_sck':   dict(c=7e-12,  vil=0.3 * VCC, vih=0.7 * VCC, rate=266e6),   # 133 MHz clock -> 266 Mtransitions/s
    'flash_cs':    dict(c=7e-12,  vil=0.3 * VCC, vih=0.7 * VCC, rate=133e6),
    'flash_io_w':  dict(c=12e-12, vil=0.3 * VCC, vih=0.7 * VCC, rate=133e6),
    'emmc_clk':    dict(c=6e-12,  vil=0.35 * VCC, vih=0.625 * VCC, rate=400e6),  # HS200 200 MHz clock
    'emmc_dat_w':  dict(c=6e-12,  vil=0.35 * VCC, vih=0.625 * VCC, rate=200e6),
}
READ = {   # memory drives, the FPGA receives (Efinix thresholds)
    'flash_io_r': dict(rout=(35, 70), cout=12e-12, tr=0.5e-9, rate=133e6),
    'emmc_dat_r': dict(rout=(33, 50), cout=6e-12, tr=0.4e-9, rate=200e6),
}
EFX_VIL, EFX_VIH = 0.63, 1.17


def bits(n, seed=7):
    """PRBS7-ish pattern with runs of 1..3 plus a clock-like 1010 stretch."""
    rng = np.random.default_rng(seed); b = list(rng.integers(0, 2, n - 16)) + [0, 1] * 8
    return np.array(b)


def build_write(link, drv, corner, rs, length, nb=48):
    p = LINKS[link]; f = {'typ': 'ti135_lvcmos18.ibs', 'fast': 'ti135_lvcmos18_fast.ibs', 'slow': 'ti135_lvcmos18_slow.ibs'}[corner]
    n = fastnet.Netlist(f'{link} {drv} {corner} Rs={rs} L={length}')
    n.ibis('U1', 'drv', os.path.join(MODELS, f), 'Ti135N484', f'P{DRV.index(drv)}', drv, ['tx'], f'f0={p["rate"]:.6g} n={nb}')
    a = 'tx'
    if rs: n.r('tx', 'txr', rs); a = 'txr'
    n.via(a, 'l0', *VIA); n.tl('l0', 'l1', Z0, length * PS_MM * 1e-12); n.via('l1', 'pin', *VIA)
    n.r('pin', 'pinr', 0.5); n.l('pinr', 'rx', 1e-9); n.c('rx', '0', p['c'])   # package: 0.5 ohm, 1 nH
    n.directive(f'.tran 2p {nb / p["rate"] * 1e9 + 3:.3f}n'); n.directive(OPTS)
    return n, p['rate'], nb


def build_read(link, rout, corner, rs, length, nb=48):
    p = READ[link]; f = {'typ': 'ti135_lvcmos18.ibs', 'fast': 'ti135_lvcmos18_fast.ibs', 'slow': 'ti135_lvcmos18_slow.ibs'}[corner]
    n = fastnet.Netlist(f'{link} Rout={rout} {corner} Rs={rs} L={length}')
    ui = 1 / p['rate']; b = bits(nb); pts = [(0, 0.0)]
    for k, v in enumerate(b):
        t0 = 1e-9 + k * ui; prev = pts[-1][1]
        if v * VCC != prev: pts += [(t0, prev), (t0 + p['tr'] / 0.6, v * VCC)]   # 20-80 % = tr
    n.lines.append('Vsrc src 0 PWL(' + ' '.join(f'{t:.4e} {v:.3f}' for t, v in pts) + ')')
    n.r('src', 'drv', rout); n.c('drv', '0', p['cout'] / 2); n.r('drv', 'drvr', 0.5); n.l('drvr', 'dpin', 1e-9); n.c('dpin', '0', p['cout'] / 2)
    a = 'dpin'
    if rs: n.r('dpin', 'dr', rs); a = 'dr'       # series R at the memory (source) end for reads
    n.via(a, 'l0', *VIA); n.tl('l0', 'l1', Z0, length * PS_MM * 1e-12); n.via('l1', 'rx', *VIA)
    n.ibis('U2', 'rx', os.path.join(MODELS, f), 'Ti135N484', f'P{DRV.index("lvcmos_1p8v_8ma_fast")}', 'lvcmos_1p8v_8ma_fast', ['rx'])
    n.directive(f'.tran 2p {nb * ui * 1e9 + 4:.3f}n'); n.directive(OPTS)
    return n, p['rate'], b


def check(t, v, vil, vih, ui):
    """At the receiver: the signal state changes only when it leaves the threshold band [VIL, VIH] on the other side.
    ringback: it enters the band from one side and leaves it on the same side again (depth = how far in, mV);
    glitch: two state changes less than half a UI apart (a ringing edge counted twice: a double clock on a clock).
    Returns (vmax, vmin, worst ringback depth mV (0 = none), glitches, worst settle time after a crossing in ps:
    from the first threshold crossing to the last time the signal is inside the band before it stays out)."""
    m = t > 2e-9; t, v = t[m], v[m]
    st, depth, worst, flips, last_flip, glitch = None, 0.0, 0.0, [], None, 0
    for tt, x in zip(t, v):
        side = 'H' if x > vih else 'L' if x < vil else None
        if st is None:
            st = side; continue
        if side is None:
            depth = max(depth, (vih - x) if st == 'H' else (x - vil)); continue
        if side == st:
            if depth > 0: worst = max(worst, depth)
        else:
            if last_flip is not None and tt - last_flip < ui / 2: glitch += 1
            last_flip = tt; st = side
        depth = 0.0
    return float(v.max()), float(v.min()), worst * 1e3, glitch


def run(case):
    kind, link, x, corner, rs, length = case
    tag = re.sub(r'[^\w.]+', '_', f'{kind}_{link}_{x}_{corner}_{rs}_{length}')
    if kind == 'w':
        n, rate, nb = build_write(link, x, corner, rs, length); vil, vih = LINKS[link]['vil'], LINKS[link]['vih']
    else:
        n, rate, b = build_read(link, x, corner, rs, length); vil, vih = EFX_VIL, EFX_VIH
    cache = fastnet.KibisCache(os.path.join(WORK, 'kibis'))
    cir = n.write(os.path.join(WORK, tag + '.cir'), cache)
    node = 'rx' if kind == 'w' else 'xu2.die0'
    t, w = spice.ngspice(cir, [node], os.path.join(WORK, tag + '.dat'))
    vmax, vmin, rb, gl = check(t, w[node], vil, vih, 1 / rate)
    return dict(kind=kind, link=link, drv=x, corner=corner, rs=rs, len_mm=length, vmax=round(vmax, 3),
                vmin=round(vmin, 3), ringback_mV=round(rb, 1), glitches=gl,
                os_ok=bool(vmax <= VCC + 0.5 and vmin >= -0.5), rb_ok=bool(rb == 0 and gl == 0))


def sweep(j):
    os.makedirs(WORK, exist_ok=True); os.makedirs(RES, exist_ok=True)
    cases = [('w', l, d, c, rs, L) for l in LINKS for d in DRV if d.endswith('fast') or d in ('lvcmos_1p8v_8ma_slow',)
             for c in ('typ', 'fast') for rs in (0, 22, 33) for L in (25, 35, 45)]
    cases += [('r', l, ro, c, rs, L) for l in READ for ro in READ[l]['rout'] for c in ('typ',) for rs in (0, 22, 33)
              for L in (25, 35, 45)]
    # convert every IBIS element once, up front (kicad-cli), then run ngspice in parallel
    cache = fastnet.KibisCache(os.path.join(WORK, 'kibis')); ents = []
    for c in cases:
        n = build_write(*c[1:])[0] if c[0] == 'w' else build_read(*c[1:])[0]; ents += n.ib
    cache.resolve(ents, jobs=min(j, 3))
    with ProcessPoolExecutor(j) as ex: rows = list(ex.map(run, cases))
    with open(os.path.join(RES, 'sweep.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('what', choices=('prep', 'sweep')); ap.add_argument('-j', type=int, default=3)
    a = ap.parse_args()
    if a.what == 'prep': prep()
    else:
        rows = sweep(a.j)
        print(f'{len(rows)} runs -> results/sweep.csv')
