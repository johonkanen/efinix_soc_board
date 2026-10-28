"""Build the two IBIS files the simulation uses, in models/ (git-ignored), from the vendor originals.

  python3 prep_models.py [EFINIX_IBS [WINBOND_IBS]]

1. models/ti135_lpddr4.ibs: the LPDDR4 models of the generic Efinix Titanium file
   (reference/efinix/ibis/titanium_ibis-v1.5/titanium_ibis.ibs, IBIS 6.1, 158 models): every [Model] whose name starts
   with lpddr4_ (not lp4x_: this card's VDDQ is 1.1 V), under a new header, [Component] Ti135N484 and a [Pin] list
   made for this simulation. The vendor [Pin] list is placeholders (pin numbers "arbitrary", RLC of the Ti180J361
   HSIO), so the pins here are named by what they carry:
     SEF / DPF DNF   single-ended / diff pair with the file's lpddr4 pin values (1.866 ohm, 1.815 nH, 0.710 pF)
     SE0 / DP0 DN0   R of the Efinix RLC sheet (3.38 ohm), ~0 L/C: the package L/C is then drawn in the schematic as
                     a 46.3 ohm line with the ball's net-length delay (gen_sch.py --pkg netlen, the default)
     SER / DPR DNR   the RLC sheet's typ values lumped (3.38 ohm, 3.12 nH, 1.45 pF; --pkg rlc)
   The model selectors (lpddr4_ocd, lpddr4_odt, lpddr4_ocd_diff, lpddr4_odt_diff) are kept; the [Diff Pin] list
   pairs DPF/DNF and DP0/DN0. CR LF line ends are converted. Nothing else of the vendor file (other I/O standards,
   [R Series], [Series Pin Mapping]) is copied.
   The driver V-t tables are trimmed (trim_waveforms); models/ti135_lpddr4_full.ibs is the untrimmed copy that
   run_si.py --validate compares against.
2. models/w66_lpddr4.ibs (trimmed the same way; w66_lpddr4_full.ibs untrimmed): Winbond W66CL2NQUAFJ (public stand-in for the SK hynix part). Its [Package] is all zero and
   the package lives in a sparse [Define Package Model] matrix that KiCad's IBIS converter does not read; the self
   R/L/C of each pin (matrix diagonal) is written into the [Pin] R_pin/L_pin/C_pin columns instead (no coupling).
   KiCad matches the [Pin] column names case-sensitively; Winbond writes R_Pin.
"""
import os, re, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MODELS = os.path.join(HERE, 'models')
EFX = os.path.join(ROOT, 'reference/efinix/ibis/titanium_ibis-v1.5/titanium_ibis.ibs')
FILE_RLC = ('1.866ohm', '1.815nH', '0.710pF')       # the vendor file's lpddr4 [Pin] values
TRIMLOG = []
ZERO_RLC = ('3.384ohm', '0.01nH', '0.01pF')   # R from the RLC sheet; L/C ~0 (not 0: ngspice's step collapses)
# Efinix "Titanium RLC" spreadsheet v1.8 (Support Center, Board Design), Ti135 N484, LPDDR4 PHY: package-wide typ/min/max
# over the balls (per pin type, not per ball). sqrt(L/C) = 46.3 ohm, sqrt(LC) = 67 ps (the net-length sheet's mean).
SHEET_RLC = ('3.3845ohm', '3.1151nH', '1.4535pF')
SHEET_MIN = ('1.3730ohm', '1.4961nH', '0.8250pF')
SHEET_MAX = ('6.4990ohm', '5.2954nH', '2.2226pF')
PINS = [('SEF', 'lpddr4_se', 'lpddr4_ocd', FILE_RLC), ('SE0', 'lpddr4_se', 'lpddr4_ocd', ZERO_RLC),
        ('SRF', 'lpddr4_in', 'lpddr4_odt', FILE_RLC), ('SR0', 'lpddr4_in', 'lpddr4_odt', ZERO_RLC),
        ('DPF', 'lpddr4_p', 'lpddr4_ocd_diff', FILE_RLC), ('DNF', 'lpddr4_n', 'lpddr4_ocd_diff', FILE_RLC),
        ('DP0', 'lpddr4_p', 'lpddr4_ocd_diff', ZERO_RLC), ('DN0', 'lpddr4_n', 'lpddr4_ocd_diff', ZERO_RLC),
        ('RPF', 'lpddr4_in_p', 'lpddr4_odt_diff', FILE_RLC), ('RNF', 'lpddr4_in_n', 'lpddr4_odt_diff', FILE_RLC),
        ('RP0', 'lpddr4_in_p', 'lpddr4_odt_diff', ZERO_RLC), ('RN0', 'lpddr4_in_n', 'lpddr4_odt_diff', ZERO_RLC),
        ('SER', 'lpddr4_se', 'lpddr4_ocd', SHEET_RLC), ('SRR', 'lpddr4_in', 'lpddr4_odt', SHEET_RLC),
        ('DPR', 'lpddr4_p', 'lpddr4_ocd_diff', SHEET_RLC), ('DNR', 'lpddr4_n', 'lpddr4_ocd_diff', SHEET_RLC),
        ('RPR', 'lpddr4_in_p', 'lpddr4_odt_diff', SHEET_RLC), ('RNR', 'lpddr4_in_n', 'lpddr4_odt_diff', SHEET_RLC)]


UNIT = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'f': 1e-15, 'k': 1e3}


def num(s):
    m = re.match(r'[-+]?[\d.]+(?:[eE][-+]?\d+)?', s)
    rest = s[m.end():]
    return float(m.group()) * (UNIT.get(rest[:1], 1) if rest[:1] in UNIT else 1)


def trim_waveforms(block, pre=20e-12, post=40e-12, tol=0.005):
    """KiCad's IBIS converter refuses a RECTDRIVER whose V-t table is longer than the on/off time ("Rising edge is
    longer than on time") and truncates PRBS edges at the next bit. The Efinix tables run 3 ns (edge 200-450 ps in),
    Winbond's 750 ps. Cut each driver model's [Rising/Falling Waveform] tables to [t0 - pre, t1 + post], where t0 is
    the first time any column of any of the model's tables leaves its start value by tol x swing and t1 the last time
    any column is away from its end value by more than that, and shift them by the same t0 - pre: the edges keep
    their shape and their timing relative to each other, the model only loses a fixed removable delay. The
    [Composite Current] tables (power-aware data KIBIS does not use) are dropped, as their time axis would no
    longer match."""
    block = re.sub(r'\[Composite Current\].*?(?=\n\[)', '', block, flags=re.S)
    wfs = list(re.finditer(r'(\[(?:Rising|Falling) Waveform\][^\n]*\n)(.*?)(?=\n\[|\Z)', block, re.S))
    if not wfs:
        return block, None
    parsed, t0s, t1s = [], [], []
    for w in wfs:
        head, data = [], []
        for line in w.group(2).split('\n'):
            f = line.split('|')[0].split()
            if len(f) >= 2 and re.match(r'[-+]?[\d.]', f[0]) and '=' not in line:
                data.append([num(x.rstrip('sSvV')) if x.upper() != 'NA' else np.nan for x in f[:4]])
            else:
                head.append(line)
        a = np.array(data); parsed.append((w, head, a))
        for c in range(1, a.shape[1]):
            v = a[:, c]
            if np.isnan(v).all():
                continue
            sw = abs(v[-1] - v[0]) or 1e-9
            away0 = np.nonzero(np.abs(v - v[0]) > tol * sw)[0]
            away1 = np.nonzero(np.abs(v - v[-1]) > tol * sw)[0]
            if len(away0): t0s.append(a[away0[0], 0])
            if len(away1): t1s.append(a[away1[-1], 0])
    t0 = max(min(t0s) - pre, 0.0); t1 = max(t1s) + post
    out, pos = [], 0
    for w, head, a in parsed:
        keep = (a[:, 0] >= t0) & (a[:, 0] <= t1)
        b = a[keep].copy(); b[:, 0] -= t0
        if b[0, 0] > 0:     # start exactly at 0 with the interpolated value
            first = [0.0] + [np.interp(t0, a[:, 0], a[:, c]) for c in range(1, a.shape[1])]
            b = np.vstack([first, b])
        rows = '\n'.join('  '.join([f'{r[0]:.6e}'] + [('NA' if np.isnan(x) else f'{x:.6e}') for x in r[1:]]) for r in b)
        out.append(block[pos:w.start()] + w.group(1) + '\n'.join(head).rstrip('\n') + '\n' + rows + '\n')
        pos = w.end()
    out.append(block[pos:])
    return ''.join(out), (t0, t1 - t0)


def trim_all(text, log):
    parts = re.split(r'(?=^\[Model\])', text, flags=re.M)
    out = []
    for p in parts:
        m = re.match(r'\[Model\]\s+(\S+)', p)
        if m and re.search(r'^\[(Rising|Falling) Waveform\]', p, re.M):
            end = re.search(r'^\[(Model Selector|End|Define Package Model)\]', p, re.M)
            body, tail = (p[:end.start()], p[end.start():]) if end else (p, '')
            body, r = trim_waveforms(body)
            log.append((m.group(1), r)); p = body + tail
        out.append(p)
    return ''.join(out)


def efinix(src):
    t = open(src, errors='replace').read().replace('\r\n', '\n').replace('\r', '\n')
    pkg = re.search(r'\[Package\]\n(.*?)\n(?=\|\n)', t, re.S).group(0)
    sels = re.findall(r'(\[Model Selector\] lpddr4_\S+\n.*?)(?=\n\|?\s*\n|\n\[)', t, re.S)
    blocks = re.findall(r'(\[Model\] lpddr4_\S+\s*\n.*?)(?=\n\|[^\n]*\n\|\*{20}|\n\[Model\]|\n\[End\])', t, re.S)
    if len(blocks) < 28: sys.exit(f'expected 28 lpddr4 models, found {len(blocks)}')
    head = ('[IBIS Ver]       6.1\n[File Name]      ti135_lpddr4.ibs\n[File Rev]       1.5-lpddr4\n'
            '[Date]           May 23, 2025\n[Source]         Efinix Inc, titanium_ibis.ibs v1.5; LPDDR4 models only, '
            'pin list rewritten by\n                 sim/lpddr4_si/prep_models.py (efinix_soc_board)\n'
            '[Notes]          Model blocks copied unchanged. Pin RLC: the vendor lpddr4 values (xxF pins) or ~0 (xx0).\n'
            '[Disclaimer]     Data is for modeling purposes only and is not guaranteed.\n'
            '[Copyright]      Copyright (C) 2022-2025 Efinix Inc. All rights reserved.\n|\n'
            '[Component]      Ti135N484\n[Manufacturer]   Efinix Inc.\n' + pkg + '\n|\n'
            '[Pin]  signal_name     model_name         R_pin      L_pin     C_pin\n')
    pins = ''.join(f'{p:6} {s:15} {m:18} {r:10} {l:9} {c}\n' for p, s, m, (r, l, c) in PINS)
    diff = ('|\n[Diff Pin]  inv_pin  vdiff  tdelay_typ  tdelay_min  tdelay_max\n'
            'DPF  DNF  NA  NA  NA  NA\nDP0  DN0  NA  NA  NA  NA\nRPF  RNF  NA  NA  NA  NA\nRP0  RN0  NA  NA  NA  NA\n'
            'DPR  DNR  NA  NA  NA  NA\nRPR  RNR  NA  NA  NA  NA\n|\n')
    head = head.replace('ti135_lpddr4.ibs', 'ti135_lpddr4_full.ibs')
    out = head + pins + diff + '\n'.join(s.rstrip() + '\n|' for s in sels) + '\n' + \
        '\n'.join(b.rstrip() + '\n|' for b in blocks) + '\n[End]\n'
    open(os.path.join(MODELS, 'ti135_lpddr4_full.ibs'), 'w').write(out)
    open(os.path.join(MODELS, 'ti135_lpddr4.ibs'), 'w').write(trim_all(out, TRIMLOG).replace(
        'ti135_lpddr4_full.ibs', 'ti135_lpddr4.ibs'))
    return len(blocks), len(sels)


def sparse_diag(text, name):
    j = text.find(f'[{name} Matrix]')
    body = text[j:]
    m = re.search(r'\n\[(?!Row\])', body[5:])
    body = body[:m.start() + 5] if m else body
    d = {}
    for r in re.split(r'\[Row\]\s+', body)[1:]:
        lines = [l.split('|')[0].split() for l in r.strip().splitlines()]
        pin = lines[0][0]
        for l in lines[1:]:
            if len(l) >= 2 and l[0] == pin: d[pin] = float(l[1])
    return d


def winbond(wibs):
    t = open(wibs).read()
    pkg = t[t.find('[Define Package Model]'):]
    L, C, R = (sparse_diag(pkg, n) for n in ('Inductance', 'Capacitance', 'Resistance'))
    out, in_pin = [], False
    for line in t.splitlines(keepends=True):
        if line.startswith('[Pin]'):
            in_pin = True
            line = '[Pin] Signal_Name   Model_Name  R_pin  L_pin C_pin\n'
        elif line.startswith('['):
            in_pin = False
        elif in_pin and line.strip() and not line.startswith('|'):
            f = line.split()
            if len(f) == 3:
                p = f[0]
                rlc = (f'{R[p]:.4f}  {L[p] * 1e9:.4f}nH  {C[p] * 1e12:.4f}pF' if p in L and p in C and p in R
                       else 'NA  NA  NA')
                line = f'{f[0]:8s}{f[1]:10s}{f[2]:12s}{rlc}\n'
        out.append(line)
    out = ''.join(out)
    open(os.path.join(MODELS, 'w66_lpddr4_full.ibs'), 'w').write(out)
    open(os.path.join(MODELS, 'w66_lpddr4.ibs'), 'w').write(trim_all(out, TRIMLOG))


if __name__ == '__main__':
    os.makedirs(MODELS, exist_ok=True)
    n, s = efinix(sys.argv[1] if len(sys.argv) > 1 else EFX)
    winbond(sys.argv[2] if len(sys.argv) > 2 else os.path.join(MODELS, 'w66cl2nquafj_a001.ibs'))
    print(f'wrote models/ti135_lpddr4.ibs ({n} models, {s} selectors) and models/w66_lpddr4.ibs; '
          f'*_full.ibs: the same without the V-t trim')
    for m, r in TRIMLOG:
        print(f'  {m:32s} V-t tables: removed delay {r[0] * 1e12:6.1f} ps, length now {r[1] * 1e12:6.1f} ps')
