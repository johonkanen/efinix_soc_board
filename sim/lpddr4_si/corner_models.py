#!/usr/bin/env python3
"""Corner model files: models/min/ and models/max/ (git-ignored, like models/), the same IBIS files as models/ with
the min or max column copied into the typ column, so the min/max corners can be simulated as typ.
  python3 corner_models.py

Why: KiCad 10.0.7's IBIS converter is exact at typ for any load, but at vcc=MIN/MAX the Efinix driver's high level
is right only into the 20 ohm fixture of its V-t tables. Into 60 ohm (DRAM ODT) it is -21 / +46 mV off, into an open
line (CKE) -72 / +129 mV (run_si.py --validate min|max). Simulating a corner file at typ avoids KiCad's corner path.

Inside each [Model] and [Package]: every line of a key plus exactly three values (V-I and V-t table rows, C_comp,
[Voltage Range], [Pullup Reference] etc., [Ramp] dV/dt, R_pkg/L_pkg/C_pkg) gets value 1 := value of the corner
(kept when the corner is NA); V_fixture := V_fixture_<corner>. [Pin], [Model Selector] and [Diff Pin] are not touched.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, 'models')
FILES = ('ti135_lpddr4.ibs', 'ti135_lpddr4_full.ibs', 'w66_lpddr4.ibs', 'w66_lpddr4_full.ibs')
ROW = re.compile(r'^(\s*(?:\[[^\]]+\]|[^\s\[|][^\s=]*)\s+)(\S+)(\s+)(\S+)(\s+)(\S+)(\s*(?:\|.*)?)$')


def corner_text(text, corner):
    col = {'min': 3, 'max': 5}[corner]
    out, section = [], None
    for line in text.splitlines():
        kw = re.match(r'^\s*\[([^\]]+)\]', line)
        if kw:
            name = kw.group(1).strip().lower()
            if name in ('model', 'package'):
                section = name
            elif name in ('pin', 'model selector', 'diff pin', 'component', 'define package model', 'end'):
                section = None
        m = ROW.match(line) if section else None
        if m and not re.match(r'^\s*\[(Model|Package|Pin)\]', line, re.I):
            g = list(m.groups())
            if g[col].upper() != 'NA':
                g[1] = g[col].ljust(len(g[1]))
            line = ''.join(g)
        out.append(line)
    return '\n'.join(out) + '\n'


def fix_vfixture(text, corner):
    """V_fixture := V_fixture_<corner> in every waveform header (the lines may come in any order)."""
    def sub(block):
        c = re.search(rf'^V_fixture_{corner}\s*=\s*(\S+)', block, re.M)
        return re.sub(r'^(V_fixture\s*=\s*)\S+', rf'\g<1>{c.group(1)}', block, flags=re.M) if c else block
    return re.sub(r'(\[(?:Rising|Falling) Waveform\].*?)(?=\n\[)', lambda m: sub(m.group(1)), text, flags=re.S)


def main():
    for corner in ('min', 'max'):
        os.makedirs(os.path.join(MODELS, corner), exist_ok=True)
        for f in FILES:
            src = os.path.join(MODELS, f)
            if not os.path.exists(src):
                continue
            t = fix_vfixture(corner_text(open(src).read(), corner), corner)
            open(os.path.join(MODELS, corner, f), 'w').write(t)
            print(f'models/{corner}/{f}')


if __name__ == '__main__':
    main()
