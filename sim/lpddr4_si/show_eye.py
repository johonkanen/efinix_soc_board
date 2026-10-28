"""Open the worst eye (smallest mask timing margin, then voltage margin) in an interactive matplotlib window.

  python3 show_eye.py                  # worst over the realistic sweeps (results, zsweep; both data rates)
  python3 show_eye.py --all            # also the deliberately bad zlimit/zfail lines
  python3 show_eye.py POINT CASE RX WHERE   # a given row, e.g. r2133.33_zs70_l20_min dqr40 U4 die

Needs the work/*.dat waveforms from run_si.py. Each 1-UI trace is coloured by its bit (1 red, 0 blue).
"""
import argparse, csv, glob, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('row', nargs='*')
ap.add_argument('--all', action='store_true')
a = ap.parse_args()

rows = []
for f in glob.glob(os.path.join(HERE, 'results', 'results*.csv')):
    if not a.all and ('zlimit' in f or 'zfail' in f): continue
    rows += list(csv.DictReader(open(f)))
if a.row:
    rows = [r for r in rows if [r['point'], r['case'], r['rx'], r['where']] == a.row]
    if not rows: sys.exit('no such row')


def key(r):
    tm = float(r['t_margin_ps']); return (tm if tm == tm else -1e9, float(r['v_margin_mV']))


r = min(rows, key=key)
os.environ['SI_RATE'] = '2133.333' if r['point'].startswith('r2133') else '1600'   # before importing run_si (UI)
sys.path.insert(0, HERE)
import run_si as R
import matplotlib.pyplot as plt

tag = r['point']; meta = json.load(open(os.path.join(R.WORK, tag + '.json')))
vecs = []
for case, m in meta.items():
    vecs.append(f"x{m['drv'].lower()}.die0")
    for ref, pad in m['rx']: vecs += [pad, f"x{ref.lower()}.die0"]
d = np.loadtxt(os.path.join(R.WORK, tag + '.dat'), skiprows=1); t = d[:, 0]
w = {v: d[:, i + 1] for i, v in enumerate(vecs)}
m = meta[r['case']]
pad = dict(m['rx'])[r['rx']]
v = w[pad if r['where'] == 'ball' else f"x{r['rx'].lower()}.die0"]
phi, bits = R.driver_bits(t, w[f"x{m['drv'].lower()}.die0"])
ph, tr, lab, lag = R.fold(t, v, phi, bits)
mask = R.MASK[m['kind']]; e = R.eye_metrics(ph, tr, lab, mask)

fig, ax = plt.subplots(figsize=(10, 6))
x = np.concatenate([ph, ph + R.UI]) * 1e12
for i in range(len(tr)):
    nxt = tr[i + 1] if i + 1 < len(tr) else tr[i]
    ax.plot(x, np.concatenate([tr[i], nxt]) * 1e3, color='#d62728' if lab[i] else '#1f5fa8', lw=0.5, alpha=0.35)
shape, V, W = mask
c = ph[int(np.argmax(e['top'] - e['bot']))] * 1e12; vr = e['vref_mV']; mw = W * R.UI * 1e12; h = V * 1e3
if shape == 'rect':
    ax.add_patch(plt.Rectangle((c - mw / 2, vr - h / 2), mw, h, fill=False, ec='k', lw=1.6))
else:
    ax.add_patch(plt.Polygon([(c - mw / 2, vr), (c, vr + h / 2), (c + mw / 2, vr), (c, vr - h / 2)], fill=False,
                             ec='k', lw=1.6))
lo, hi = R.LIMIT[m['kind']]
ax.set_xlim(0, 2 * R.UI * 1e12); ax.set_xlabel('time (ps), 2 UI'); ax.set_ylabel('mV'); ax.grid(alpha=0.3)
ax.set_title(f"{r['case']} {r['rx']} {r['where']}  |  {tag}  ({R.RATE:g} MT/s, DQ {r['zdq']} ohm {r['ldq']} mm, "
             f"{r['corner']})\nEH {e['eh_mV']:.0f} mV  EW {e['ew0_ps']:.0f} ps  mask {shape} {V * 1e3:.0f} mV x "
             f"{W:.2f} UI: margin {e['v_margin_mV']:+.0f} mV / {e['t_margin_ps']:+.0f} ps  "
             f"(swing {float(r['vmin_mV']):.0f}..{float(r['vmax_mV']):.0f} mV, limits {lo * 1e3:.0f}..{hi * 1e3:.0f})",
             fontsize=9)
fig.tight_layout(); plt.show()
