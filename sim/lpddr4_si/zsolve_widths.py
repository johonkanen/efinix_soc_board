"""Width -> Z0 and ps/mm for the LPDDR4 width sweep, with this repo's 2D field solver (tools/zsolve.py, the geometry of
tools/zsolve_cases.py: JLC08161H-3313, TI135_PCB_NOTES.md §6.5).

  python3 zsolve_widths.py            -> results/zsolve.csv (layer, kind, w, gap, Z, eps_eff, ps/mm)

Inner = In2 (0.1 mm core to In1 GND, 0.357 mm prepreg to In3); In5 is its mirror image (In6 / In4). Outer = F.Cu/B.Cu
microstrip over In1/In6 with 0.03 mm mask (er 3.8). Diff = odd-mode (differential) impedance; the even-mode figure is
not needed for the SI model, which uses the coupled-line matrices of xtalk.py for pairs.
"""
import csv, os, sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'tools'))
from zsolve import z_se, z_diff, C as C0     # noqa: E402
import numpy as np                            # noqa: E402

H = 0.0025
TC_OUT, TC_IN = 0.035, 0.0152


def tr(ws, g, y0, y1):
    if g is None:
        return [(-ws / 2, ws / 2, y0, y1, 1.0)]
    c = g / 2 + ws / 2
    return [(-c - ws / 2, -c + ws / 2, y0, y1, 1.0), (c - ws / 2, c + ws / 2, y0, y1, -1.0)]


def outer(w, g=None):
    hp = 0.0994; y0, y1 = hp, hp + TC_OUT
    t = tr(w, g, y0, y1)
    st = [(0, hp, 4.1), (hp, hp + 0.03, 3.8)] + [(hp, y1 + 0.03, 3.8, x0 - 0.03, x1 + 0.03) for x0, x1, *_ in t]
    return dict(stack=st, planes=[0], traces=t, top_open=True, width=3.0, h=H)


def inner(w, g=None):
    t = tr(w, g, 0.1, 0.1 + TC_IN)
    return dict(stack=[(0, 0.1, 4.6), (0.1, 0.4568, 4.16)], planes=[0, 0.4568], traces=t, top_open=False, width=3.0, h=H)


SE = {'inner': (0.18, 0.15, 0.12, 0.10, 0.09), 'outer': (0.25, 0.20, 0.15, 0.12, 0.10, 0.09)}
DIFF = {'inner': ((0.14, 0.15), (0.12, 0.12), (0.10, 0.10), (0.10, 0.13), (0.10, 0.15), (0.10, 0.20), (0.09, 0.15),
                  (0.09, 0.20), (0.11, 0.11), (0.12, 0.20)),
        'outer': ((0.20, 0.20), (0.15, 0.12), (0.12, 0.10), (0.12, 0.15), (0.10, 0.10), (0.10, 0.15), (0.10, 0.20),
                  (0.15, 0.20), (0.09, 0.15))}


def cl_matrix(layer, w, gap, n=3):
    """Per-metre L, C (Maxwell) matrices of n equal coupled lines (width w, edge gap gap) and the DC resistance of one,
    for the ngspice CPL line of the crosstalk case. C from the field energy with conductor patterns e_i and e_i+e_j
    (W = V'CV/2); L = inv(C_air) / c^2."""
    from zsolve import solve
    pitch = w + gap
    xs = [(i - (n - 1) / 2) * pitch for i in range(n)]
    geo = inner if layer == 'inner' else outer
    base = geo(w)
    y0, y1 = base['traces'][0][2], base['traces'][0][3]

    def energy(V):
        g = dict(base); tr = [(x - w / 2, x + w / 2, y0, y1, v) for x, v in zip(xs, V)]
        g['traces'] = tr
        if layer == 'outer':
            g['stack'] = [s for s in base['stack'] if len(s) == 3] + \
                [(y0, y1 + 0.03, 3.8, x0 - 0.03, x1 + 0.03) for x0, x1, *_ in tr]
        g['width'] = max(3.0, pitch * n + 2.0)
        r = solve(**g)
        return np.array([r['diel'], r['air']])
    import numpy as np
    E = {}
    for i in range(n):
        E[(i,)] = energy([1.0 if k == i else 0.0 for k in range(n)])
    for i in range(n):
        for j in range(i + 1, n):
            E[(i, j)] = energy([1.0 if k in (i, j) else 0.0 for k in range(n)])
    Cd, Ca = np.zeros((n, n)), np.zeros((n, n))
    for i in range(n):
        Cd[i, i], Ca[i, i] = 2 * E[(i,)]
    for i in range(n):
        for j in range(i + 1, n):
            d = E[(i, j)] - E[(i,)] - E[(j,)]        # = C_ij (Maxwell, negative)
            Cd[i, j] = Cd[j, i] = d[0]; Ca[i, j] = Ca[j, i] = d[1]
    L = np.linalg.inv(Ca) / C0 ** 2
    t = TC_IN if layer == 'inner' else TC_OUT
    rdc = 1.72e-8 / (w * 1e-3 * t * 1e-3)
    return L.tolist(), Cd.tolist(), rdc


def one(job):
    layer, w, g = job
    z, ee = (z_se if g is None else z_diff)(**(inner if layer == 'inner' else outer)(w, g))
    return dict(layer=layer, kind='SE' if g is None else 'DIFF', w=w, gap=g or '', Z=round(float(z), 2), eps_eff=round(float(ee), 4),
                ps_mm=round(float(ee) ** 0.5 / C0 * 1e9, 3))


if __name__ == '__main__':
    jobs = [(l, w, None) for l, ws in SE.items() for w in ws] + [(l, w, g) for l, ps in DIFF.items() for w, g in ps]
    with ProcessPoolExecutor(int(os.environ.get('JOBS', 12))) as ex:
        rows = list(ex.map(one, jobs))
    os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
    with open(os.path.join(HERE, 'results', 'zsolve.csv'), 'w', newline='') as f:
        wr = csv.DictWriter(f, list(rows[0])); wr.writeheader(); wr.writerows(rows)
    for r in rows: print(r)
