"""Write the LPDDR4 SI simulation schematic (KiCad 10: IBIS drivers/receivers, TLINE, via L/C), one channel per case,
each channel the real copper path of a board net (results/board_paths_*.json, board_paths.py).

  python3 gen_sch.py OUT.kicad_sch [--rate 2800] [--w-in 0.18] [--w-out 0.25] [--diff-in 0.14/0.15]
                     [--diff-out 0.20/0.20] [--corner typ|min|max] [--pkg netlen|file] [--set base|all]
  python3 gen_sch.py OUT.kicad_sch --validate          driver check circuit (run_si.py --validate)
  python3 gen_sch.py OUT.kicad_sch --xtalk inner|outer --w W --gap G   three coupled lines (run_si.py --xtalk)

run_si.py writes one schematic per sweep point into work/, exports it with kicad-cli (which runs KiCad's IBIS-to-SPICE
converter, KIBIS) and runs ngspice on it. Every element is a normal KiCad simulation symbol, so the file also opens and
simulates in Eeschema (the N legs of the pairs and the crosstalk aggressors then carry the same PRBS as the P leg /
victim: run_si.py rewrites their switching coefficients, see there).

Channel model, U501 -> U801 (reversed for reads; all uncoupled):
  FPGA die -- package -- ball -- [run: TLINE per layer run, neck part at 0.10 mm] -- via (pi C/2 L C/2) -- ... -- ball
  -- DRAM package (Winbond pin R/L/C) -- DRAM die.
  * Package U501: --pkg netlen (default): the IBIS pin xx0 (R 3.38 ohm from the Efinix RLC sheet, ~0 L/C) plus a
    TLINE of Z_PKG = 46.3 ohm (sqrt(L/C) of the RLC sheet's Ti135 N484 LPDDR4 PHY typ, 3.115 nH / 1.4535 pF) with the
    ball's delay from the Efinix N484 net-length table (pad-to-die on the board, tools/pad_to_die.py; their mean, 67 ps,
    equals the sheet's sqrt(LC)). --pkg rlc: the RLC sheet's typ values lumped (pin xxR). --pkg file: the IBIS file's
    placeholder lpddr4 pin values (1.866 ohm, 1.815 nH, 0.710 pF, Ti180J361 HSIO).
  * Lines: Z0 and ps/mm per layer and width from results/zsolve.csv (zsolve_widths.py, field solve). Every run of the
    net is at the swept width (--w-in for In2/In5, --w-out for F.Cu/B.Cu) except the part the board has narrower than
    0.125 mm (the BGA neck-downs), which stays at 0.10 mm (or the swept width if narrower), split half/half to the
    run's two ends. CA/CK/CS/CKE come from the phase-4 work board, whose widening is not done: there the neck part is
    capped at NECK_CAP_P4 mm per run.
  * Pairs (DQS, CK): two uncoupled lines at the odd-mode impedance Zdiff/2 and odd-mode delay of the pair geometry:
    exact for the differential signal, not for common mode.
  * Vias: pi model C/2-L-C/2, L by the span between the two layers it joins (VIA_L), C by pad: 0.40 pF U501 side and
    mid-route vias (0.30/0.15 mm), 0.35 pF at U801 (0.25/0.15 mm), stub and pad included. Estimates (the Agilex study's
    values, 0.15 nH / 0.40 pF short, 0.50 nH / 0.40 pF long), not field solved.
  * CA/CK/CKE: trunk to the T point, two branches (both as routed) to the channel A and B balls of U801.
"""
import argparse, csv, json, os, re, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
KSYM = os.path.join(os.environ.get('KICAD_MOUNT', ''), 'share/kicad/symbols')
EFX = ('ti135_lpddr4.ibs', 'Ti135N484')         # (file in models/, IBIS [Component])
MEM = ('w66_lpddr4.ibs', 'W66CL2NQUAFJ')        # Winbond W66CL2NQUAFJ: STAND-IN for the SK hynix H9HCNNN8KUMLHR
Z_PKG = 46.3      # sqrt(L/C) of the Efinix RLC sheet, Ti135 N484 LPDDR4 PHY typ (3.115 nH / 1.4535 pF)
NECK_W = 0.10
NECK_CAP_P4 = 6.0
Z_LAYER = {'z': {'F.Cu': 0.0, 'In2.Cu': 0.249, 'In5.Cu': 1.308, 'B.Cu': 1.538}}['z']   # mm from the top, approx.
VIA_C_U501, VIA_C_MID, VIA_C_U801 = 0.40e-12, 0.40e-12, 0.35e-12


def VIA_L(span):
    """Via inductance by span (mm): F<->In2 / In5<->B 0.15 nH, In2<->In5 0.40 nH, F<->In5 / In2<->B / F<->B 0.50 nH."""
    return 0.15e-9 if span <= 0.4 else 0.40e-9 if span <= 1.1 else 0.50e-9


INNER = ('In2.Cu', 'In5.Cu')
# settings (TI135_PCB_NOTES.md §6.11): FPGA drive / ODT from Efinity's DDR block, memory MR values from the same block
BASE = dict(fdrv=40, fodt=60, modt=60, pdds=40, caodt=40)


def load_z():
    se, df = {}, {}
    for r in csv.DictReader(open(os.path.join(HERE, 'results', 'zsolve.csv'))):
        key = (r['layer'], float(r['w']))
        if r['kind'] == 'SE': se[key] = (float(r['Z']), float(r['ps_mm']))
        else: df[(r['layer'], float(r['w']), float(r['gap']))] = (float(r['Z']), float(r['ps_mm']))
    return se, df


ZSE, ZDIFF = load_z()


def zline(layer, w):
    """(Z0, ps/mm) of a single-ended line, interpolated in width over the field-solved points."""
    pts = sorted((k[1], v) for k, v in ZSE.items() if k[0] == lyr(layer))
    ws = [p[0] for p in pts]
    if w <= ws[0]: return pts[0][1]
    if w >= ws[-1]: return pts[-1][1]
    for (w0, a), (w1, b) in zip(pts, pts[1:]):
        if w0 <= w <= w1:
            f = (w - w0) / (w1 - w0); return a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])


def lyr(L): return 'inner' if L in INNER else 'outer'


def uid(): return str(uuid.uuid4())


def eng(v):
    for e, s in ((1e9, 'G'), (1e6, 'Meg'), (1, ''), (1e-3, 'm'), (1e-6, 'u'), (1e-9, 'n'), (1e-12, 'p'), (1e-15, 'f')):
        if abs(v) >= e * 0.999: return f'{v / e:.4g}{s}'
    return f'{v:.4g}'


def lib_symbol(lib, name):
    t = open(os.path.join(KSYM, f'{lib}.kicad_symdir', f'{name}.kicad_sym')).read()
    i = t.find(f'(symbol "{name}"')
    body = t[i:t.rstrip().rfind(')')].rstrip()
    return body.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)


def pins_of(lib, name):
    t = open(os.path.join(KSYM, f'{lib}.kicad_symdir', f'{name}.kicad_sym')).read()
    return {m[2]: (float(m[0]), float(m[1])) for m in
            re.findall(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) [-\d.]+\).*?\(number "(\w+)"', t, re.S)}


class Sch:
    def __init__(self, models):
        self.models = models; self.root = uid(); self.items = []; self.libs = {}; self.n = {}; self.x = 25.4; self.y = 25.4

    def prop(self, k, v, x, y, hide=True):
        return (f'\t\t(property "{k}" "{v}"\n\t\t\t(at {x:.2f} {y:.2f} 0)\n\t\t\t(effects\n\t\t\t\t(font\n'
                f'\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n{"				(hide yes)" + chr(10) if hide else ""}\t\t\t)\n\t\t)\n')

    def sym(self, lib, name, pfx, nets, value='', props=None):
        key = f'{lib}:{name}'
        if key not in self.libs: self.libs[key] = (lib_symbol(lib, name), pins_of(lib, name))
        pins = self.libs[key][1]
        self.n[pfx] = self.n.get(pfx, 0) + 1; ref = f'{pfx}{self.n[pfx]}'
        x, y = self.x, self.y
        s = (f'\t(symbol\n\t\t(lib_id "{key}")\n\t\t(at {x:.2f} {y:.2f} 0)\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n'
             f'\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "{uid()}")\n')
        s += self.prop('Reference', ref, x, y - 6.35, False) + self.prop('Value', value or name, x, y + 7.62, False)
        s += self.prop('Footprint', '', x, y) + self.prop('Datasheet', '', x, y)
        for k, v in (props or {}).items(): s += self.prop(k, v, x, y)
        for p in pins: s += f'\t\t(pin "{p}"\n\t\t\t(uuid "{uid()}")\n\t\t)\n'
        s += (f'\t\t(instances\n\t\t\t(project "lpddr4_si"\n\t\t\t\t(path "/{self.root}"\n\t\t\t\t\t(reference "{ref}")\n'
              f'\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')
        self.items.append(s)
        for p, net in nets.items():   # a local label on each pin end (no wires needed)
            px, py = pins[p]
            self.items.append(f'\t(label "{net}"\n\t\t(at {x + px:.2f} {y - py:.2f} 0)\n\t\t(effects\n\t\t\t(font\n'
                              f'\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "{uid()}")\n\t)\n')
        self.x += 30.48
        return ref

    def text(self, s, x, y):
        s = s.replace('"', '\\"').replace('\n', '\\n')
        self.items.append(f'\t(text "{s}"\n\t\t(exclude_from_sim no)\n\t\t(at {x:.2f} {y:.2f} 0)\n\t\t(effects\n'
                          f'\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n'
                          f'\t\t(uuid "{uid()}")\n\t)\n')

    def row(self, title):
        self.y += 30.48; self.x = 25.4
        self.text(title, 25.4, self.y - 12.7)

    # elements
    def ibis(self, kind, lib, pin, model, net, params='', stype=None):
        name = 'IBIS_DRIVER' if kind == 'drv' else 'IBIS_DEVICE'
        st = stype or ('PRBSDRIVER' if kind == 'drv' else 'IBISDEVICE')
        props = {'Sim.Device': 'IBIS', 'Sim.Type': st, 'Sim.Pins': '1=GND 2=IN/OUT',
                 'Sim.Library': f'{self.models}/{lib[0]}', 'Sim.Name': lib[1], 'Sim.Ibis.Pin': pin,
                 'Sim.Ibis.Model': model}
        if params: props['Sim.Params'] = params
        return self.sym('Simulation_SPICE', name, 'U', {'1': 'GND', '2': net}, f'{model}', props)

    def tl(self, a, b, z0, td):
        return self.sym('Simulation_SPICE', 'TLINE', 'TL', {'1': a, '2': 'GND', '3': b, '4': 'GND'},
                        f'TLINE {z0:g}R {td * 1e12:.1f}ps',
                        {'Sim.Device': 'TLINE', 'Sim.Pins': '1=1+ 2=1- 3=2+ 4=2-',
                         'Sim.Params': f'z0={z0:g} td={eng(td)}'})

    def via(self, a, b, L, C):
        self.sym('Device', 'C', 'C', {'1': a, '2': 'GND'}, eng(C / 2))
        self.sym('Device', 'L', 'L', {'1': a, '2': b}, eng(L))
        self.sym('Device', 'C', 'C', {'1': b, '2': 'GND'}, eng(C / 2))





class FastSch:
    """Same calls as Sch, but into a kicad_ibis.fastnet.Netlist (SPICE text, IBIS converted once and cached): the
    fast sweep path (run_si.py). No schematic is written."""

    def __init__(self, models):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'tools', 'kicad_ibis_simulation'))
        from kicad_ibis.fastnet import Netlist
        self.models = os.path.join(HERE, 'models'); self.net = Netlist(); self.n = 0

    def text(self, s, x, y):
        for line in s.split('\n'):
            if line.startswith('.'): self.net.directive(line)

    def row(self, title): pass

    def ibis(self, kind, lib, pin, model, net, params='', stype=None):
        self.n += 1; ref = f'U{self.n}'
        self.net.ibis(ref, kind, os.path.join(self.models, lib[0]), lib[1], pin, model, [net], params, stype)
        return ref

    def tl(self, a, b, z0, td): self.net.tl(a, b, z0, td)

    def via(self, a, b, L, C): self.net.via(a, b, L, C)

    def sym(self, lib, name, pfx, nets, value='', props=None):     # only R is used outside ibis/tl/via
        assert name == 'R'; self.net.r(nets['1'], '0' if nets['2'] == 'GND' else nets['2'], float(value))

def finish(s, meta):
    if isinstance(s, FastSch):
        for m in meta.values():           # N legs of the pairs: complement of the P leg
            if isinstance(m, dict) and m.get('inv'):
                next(e for e in s.net.ib if e['ref'] == m['inv'])['pattern'] = ('inv', m['drv'])
        return meta, json.dumps(dict(lines=s.net.lines, ib=s.net.ib, directives=s.net.directives))
    libs = ''.join('\t\t' + v[0].replace('\n', '\n\t') + '\n' for v in s.libs.values())
    return meta, (f'(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n'
                  f'\t(uuid "{s.root}")\n\t(paper "A0")\n\t(lib_symbols\n{libs}\t)\n' + ''.join(s.items) +
                  '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n')


class Chain:
    """Builds the copper path of one net leg as TLINEs and via pi sections between two nets."""

    def __init__(self, s, a, tag):
        self.s, self.a, self.tag, self.k = s, a, tag, 0

    def node(self):
        self.k += 1; return f'{self.tag}_{self.k}'

    def runs(self, start, runs, end, pair=False, cap=None, first_via='U501', last_via='U801'):
        """runs: [[layer, mm, mm_neck] | 'via', ...] from the start net to the end net. Layer of the balls: F.Cu."""
        a, n, prev = self.a, start, 'F.Cu'
        items = [x for x in runs]
        for i, it in enumerate(items):
            last = i == len(items) - 1
            nxt = end if last else self.node()
            if it == 'via':
                before = prev
                after = next((x[0] for x in items[i + 1:] if x != 'via'), 'F.Cu')
                C = VIA_C_U801 if not any(x != 'via' for x in items[i + 1:]) else \
                    VIA_C_U501 if not any(x != 'via' for x in items[:i]) else VIA_C_MID
                self.s.via(n, nxt, VIA_L(abs(Z_LAYER[before] - Z_LAYER[after])), C)
            else:
                L, mm, neck = it; prev = L
                if cap is not None: neck = min(neck, cap)
                neck = min(neck, mm)
                w = a.w_in if L in INNER else a.w_out
                if pair:
                    gw, gg = a.diff_in if L in INNER else a.diff_out
                    zd, psd = ZDIFF[(lyr(L), gw, gg)]
                    zw, pw = zd / 2, psd
                    zn, pn = zline(L, NECK_W)        # neck part of a pair: uncoupled single line at 0.10 mm
                    wn = gw
                else:
                    zw, pw = zline(L, w); wn = w
                    zn, pn = zline(L, NECK_W)
                if wn < NECK_W: zn, pn = zw, pw       # a line narrower than the neck-down needs no neck-down
                main = mm - neck
                segs = [(zn, pn, neck / 2), (zw, pw, main), (zn, pn, neck / 2)]
                if neck < 0.2: segs = [(zw, pw, mm)]     # a neck piece this short is part of the line (ngspice
                if main < 0.2: segs = [(zn, pn, mm)]     # chokes on fs-long TLINEs)
                segs = [x for x in segs if x[2] > 1e-3]
                for j, (z, ps, l) in enumerate(segs):
                    m = nxt if j == len(segs) - 1 else self.node()
                    self.s.tl(n, m, round(z, 2), l * ps * 1e-12)
                    n = m
                continue
            n = nxt
        return n


def fpga_pkg(s, a, tag, ball, pad_ps, kind):
    """The U501 die-side net for an IBIS element and the pin name: netlen = pin xx0 + TLINE(pad-to-die), file = xxF."""
    if a.pkg in ('file', 'rlc'):
        return ball, kind + ('F' if a.pkg == 'file' else 'R')
    die = f'{tag}_pkg'
    s.tl(die, ball, Z_PKG, pad_ps * 1e-12)
    return die, kind + '0'


def build(a):
    rate = a.rate; ui = 1e-6 / rate
    main = json.load(open(os.path.join(HERE, 'results', 'board_paths_main.json')))
    p4 = json.load(open(os.path.join(HERE, 'results', 'board_paths_p4.json')))
    s = (FastSch if a.fast else Sch)(a.models); meta = {}
    nb_dq, nb_ca = a.bits, a.ca_bits
    c = a.corner.upper()
    corner = '' if a.corner == 'typ' else f' vcc={c} rpin={c} lpin={c} cpin={c}'
    s.text(f'LPDDR4 SI, generated by gen_sch.py: {rate:g} MT/s, inner {a.w_in} mm, outer {a.w_out} mm, pairs inner '
           f'{a.diff_in[0]}/{a.diff_in[1]}, outer {a.diff_out[0]}/{a.diff_out[1]}, corner {a.corner}, package {a.pkg}. '
           f'DRAM = Winbond W66CL2NQUAFJ stand-in.', 25.4, 10.16)
    prbs_dq = f'f0={eng(1 / ui)} n={nb_dq}'
    prbs_ca = f'f0={eng(1 / (2 * ui))} n={nb_ca}'      # CA/CS/CKE are single data rate: one bit per tCK = 2 UI

    keep = (lambda tag: re.fullmatch(a.keep, tag) is not None) if a.keep else (lambda tag: True)

    def dq(tag, net, mode, st):
        if not keep(tag): return
        e = main[net]; ch = Chain(s, a, tag); pin = e['u801_pad']
        if mode == 'w':
            s.row(f'{tag}: {net} write, FPGA {st["fdrv"]} ohm -> DRAM ODT {st["modt"]}')
            die, fpin = fpga_pkg(s, a, tag, f'{tag}_fb', e['u501_pad_to_die_ps'], 'SE')
            d = s.ibis('drv', EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n', die, prbs_dq + corner)
            ch.runs(f'{tag}_fb', e['path'], f'{tag}_mb')
            om = 'ODT_OFF' if st['modt'] == 'off' else f'ODT_{st["modt"]}'
            r = s.ibis('rx', MEM, pin, om, f'{tag}_mb', corner.strip())
            meta[tag] = dict(kind='dq_write', net=net, ui=ui, drv=d, rx=[(r, f'{tag}_mb')], **st)
        else:
            s.row(f'{tag}: {net} read, DRAM PDDS {st["pdds"]} -> FPGA ODT {st["fodt"]}')
            d = s.ibis('drv', MEM, pin, f'PD{st["pdds"]}_ODT40_VOH30', f'{tag}_mb', prbs_dq + corner)
            ch.runs(f'{tag}_fb', e['path'], f'{tag}_mb')
            die, fpin = fpga_pkg(s, a, tag, f'{tag}_fb', e['u501_pad_to_die_ps'], 'SR')
            r = s.ibis('rx', EFX, fpin, f'lpddr4_odt_{st["fodt"]}', die, corner.strip())
            meta[tag] = dict(kind='dq_read', net=net, ui=ui, drv=d, rx=[(r, f'{tag}_fb')], **st)

    def dqs(tag, base, mode, st):
        if not keep(tag): return
        P, N = main[base + '_P'], main[base + '_N']
        pp, pn = P['u801_pad'], N['u801_pad']
        legs = {}
        if mode == 'w':
            s.row(f'{tag}: {base} write (pair), FPGA {st["fdrv"]} ohm diff -> DRAM ODT {st["modt"]}')
            for leg, e, fpin_k in (('p', P, 'DP'), ('n', N, 'DN')):
                die, fpin = fpga_pkg(s, a, f'{tag}{leg}', f'{tag}{leg}_fb', e['u501_pad_to_die_ps'], fpin_k)
                legs[leg] = s.ibis('drv', EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n_diff', die, prbs_dq + corner)
                Chain(s, a, f'{tag}{leg}').runs(f'{tag}{leg}_fb', e['path'], f'{tag}{leg}_mb', pair=True)
            om = 'ODT_OFF' if st['modt'] == 'off' else f'ODT_{st["modt"]}'
            rp = s.ibis('rx', MEM, pp, om, f'{tag}p_mb', corner.strip())
            rn = s.ibis('rx', MEM, pn, om, f'{tag}n_mb', corner.strip())
            meta[tag] = dict(kind='dqs_write', net=base, ui=ui, drv=legs['p'], inv=legs['n'],
                             rx=[((rp, rn), (f'{tag}p_mb', f'{tag}n_mb'))], **st)
        else:
            s.row(f'{tag}: {base} read (pair), DRAM PDDS {st["pdds"]} -> FPGA ODT {st["fodt"]} diff')
            for leg, e, pin in (('p', P, pp), ('n', N, pn)):
                legs[leg] = s.ibis('drv', MEM, pin, f'PD{st["pdds"]}_ODT40_VOH30', f'{tag}{leg}_mb', prbs_dq + corner)
                Chain(s, a, f'{tag}{leg}').runs(f'{tag}{leg}_fb', e['path'], f'{tag}{leg}_mb', pair=True)
            rx = []
            for leg, e, k in (('p', P, 'RP'), ('n', N, 'RN')):
                die, fpin = fpga_pkg(s, a, f'{tag}{leg}', f'{tag}{leg}_fb', e['u501_pad_to_die_ps'], k)
                rx.append(s.ibis('rx', EFX, fpin, f'lpddr4_odt_{st["fodt"]}_diff', die, corner.strip()))
            meta[tag] = dict(kind='dqs_read', net=base, ui=ui, drv=legs['p'], inv=legs['n'],
                             rx=[(tuple(rx), (f'{tag}p_fb', f'{tag}n_fb'))], **st)

    def tee(tag, net, chain, start, cap, pair=False):
        e = p4[net]; trunk_end = f'{tag}_t'
        chain.runs(start, e['trunk'], trunk_end, pair=pair, cap=cap, last_via='MID')
        ends = []
        for i, (pad, br) in enumerate(e['branches'].items()):
            m = f'{tag}_m{"ab"[i]}'
            chain.runs(trunk_end, br, m, pair=pair, cap=cap)
            ends.append((pad, m))
        return ends

    def ca(tag, net, st, model_of):
        if not keep(tag): return
        e = p4[net]
        s.row(f'{tag}: {net}, FPGA {st["fdrv"]} ohm, ' + ('T to both channels' if 'trunk' in e else 'point to point') +
              f', DRAM {model_of("X")}')
        die, fpin = fpga_pkg(s, a, tag, f'{tag}_fb', e['u501_pad_to_die_ps'], 'SE')
        d = s.ibis('drv', EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n', die, prbs_ca + corner)
        ch = Chain(s, a, tag)
        if 'trunk' in e:
            ends = tee(tag, net, ch, f'{tag}_fb', NECK_CAP_P4)
        else:
            ch.runs(f'{tag}_fb', e['path'], f'{tag}_ma', cap=NECK_CAP_P4); ends = [(e['u801_pad'], f'{tag}_ma')]
        rx = [(s.ibis('rx', MEM, pad, model_of(pad), m, corner.strip()), m) for pad, m in ends]
        meta[tag] = dict(kind='ca', net=net, ui=2 * ui, drv=d, rx=rx, **st)

    def ck(tag, st):
        if not keep(tag): return
        s.row(f'{tag}: CK pair, T to both channels, FPGA {st["fdrv"]} ohm diff, DRAM CK ODT {st["caodt"]}')
        legs, ends = {}, {}
        for leg, net in (('p', 'ddr_ck_P'), ('n', 'ddr_ck_N')):
            e = p4[net]
            die, fpin = fpga_pkg(s, a, f'{tag}{leg}', f'{tag}{leg}_fb', e['u501_pad_to_die_ps'], 'D' + leg.upper())
            legs[leg] = s.ibis('drv', EFX, fpin, f'lpddr4_ocd_{st["fdrv"]}p_{st["fdrv"]}n_diff', die, prbs_dq + corner)
            ends[leg] = tee(f'{tag}{leg}', net, Chain(s, a, f'{tag}{leg}'), f'{tag}{leg}_fb', NECK_CAP_P4, pair=True)
        om = 'CLK_INPUT' if st['caodt'] == 'off' else f'CLK_ODT_{st["caodt"]}'
        rx = []
        for (pp, mp), (pn, mn) in zip(ends['p'], ends['n']):
            rx.append(((s.ibis('rx', MEM, pp, om, mp, corner.strip()), s.ibis('rx', MEM, pn, om, mn, corner.strip())),
                       (mp, mn)))
        meta[tag] = dict(kind='ck', net='ddr_ck', ui=ui, drv=legs['p'], inv=legs['n'], rx=rx, **st)

    B = dict(BASE)
    # DQ: the longest net of each byte, the longest package, most vias, most outer-layer length (results/board_paths)
    for net in a.dq_nets:
        k = net.replace('ddr_', '')
        dq(f'w_{k}', net, 'w', B)
        dq(f'r_{k}', net, 'r', B)
    for b in a.dqs_nets:
        dqs(f'w_{b.replace("ddr_", "")}', b, 'w', B)
        dqs(f'r_{b.replace("ddr_", "")}', b, 'r', B)
    if not a.no_ck: ck('ck_40', B)
    for net in a.ca_nets:
        k = net.replace('ddr_', '')
        mdl = (lambda p, o=B['caodt']: 'CKE_INPUT') if 'cke' in net else \
              (lambda p, o=B['caodt']: f'CS_ODT_{o}') if 'cs' in net else (lambda p, o=B['caodt']: f'CA_ODT_{o}')
        ca(f'{k}_{B["caodt"]}', net, B, mdl)
    if a.set == 'all':      # settings on the worst nets
        v = a.dq_nets[0].replace('ddr_', '')
        for fd, mo in ((48, 60), (40, 40), (40, 48), (48, 48), (40, 'off'), (48, 'off')):
            dq(f'w_{v}_d{fd}o{mo}', a.dq_nets[0], 'w', dict(B, fdrv=fd, modt=mo))
        for pd, fo in ((48, 60), (40, 40), (40, 48), (48, 48), (48, 40)):
            dq(f'r_{v}_p{pd}o{fo}', a.dq_nets[0], 'r', dict(B, pdds=pd, fodt=fo))
        ck('ck_80', dict(B, caodt=80))
        ca1 = a.ca_nets[0]; k = ca1.replace('ddr_', '')
        for o in (60, 80, 'off'):
            ca(f'{k}_{o}', ca1, dict(B, caodt=o), lambda p, o=o: 'CA_INPUT' if o == 'off' else f'CA_ODT_{o}')
        ca(f'{k}_{40}_d48', ca1, dict(B, fdrv=48), lambda p: 'CA_ODT_40')
        cs = next(n for n in a.ca_nets if 'cs' in n); k = cs.replace('ddr_', '')
        ca(f'{k}_off', cs, dict(B, caodt='off'), lambda p: 'CS_INPUT')
    # stimulus length of the slowest case present (CA is SDR) + 2 ns tail
    t_end = max((nb_ca if m['kind'] == 'ca' else nb_dq) * m['ui'] for m in meta.values()) + 2e-9 if meta else 10e-9
    s.text(f'.tran 1p {t_end * 1e9:.1f}n\n.options method=gear maxord=2 reltol=1e-4', 25.4, 15.24)
    return finish(s, meta)


def build_validate(a):
    """Each driver model as a RECTDRIVER into its IBIS waveform fixture to GND (Efinix 20 ohm? see run_si), to compare
    the converted model with the [Rising/Falling Waveform] tables (run_si.py --validate strips the package)."""
    s = (FastSch if a.fast else Sch)(a.models); meta = {}
    s.text('.tran 1p 8n', 25.4, 15.24)
    for tag, lib, pin, model, rf in (('efx40', EFX, 'SE0', 'lpddr4_ocd_40p_40n', 20),
                                     ('efx48', EFX, 'SE0', 'lpddr4_ocd_48p_48n', 20),
                                     ('mem_pd40', MEM, 'C11', 'PD40_ODT40_VOH30', 50),
                                     ('mem_pd48', MEM, 'C11', 'PD48_ODT40_VOH30', 50)):
        s.row(f'{tag}: {model} into {rf} ohm to GND')
        meta[tag] = dict(kind='validate', model=model, lib=lib[0], rf=rf,
                         drv=s.ibis('drv', lib, pin, model, f'{tag}_o', 'ton=3n toff=3n td=1n n=1', 'RECTDRIVER'))
        s.sym('Device', 'R', 'R', {'1': f'{tag}_o', '2': 'GND'}, str(rf))
    return finish(s, meta)


def build_xtalk(a):
    """Three coupled lines (aggressor - victim - aggressor) of length --len on one layer: drivers and receivers only;
    run_si.py adds the ngspice CPL line (L/C matrices from xtalk_matrix in zsolve_widths.py) between the _f and _m
    nets. DQ write: FPGA 40 ohm -> DRAM ODT 60, plus the FPGA package (netlen, 70 ps) and one via at each end."""
    ui = 1e-6 / a.rate
    s = (FastSch if a.fast else Sch)(a.models); meta = {}
    c = a.corner.upper()
    corner = '' if a.corner == 'typ' else f' vcc={c} rpin={c} lpin={c} cpin={c}'
    s.text(f'.tran 1p {a.bits * ui * 1e9 + 2:.1f}n\n.options method=gear maxord=2 reltol=1e-4', 25.4, 15.24)
    for line in ('a1', 'v', 'a2'):
        tag = f'x{line}'
        s.row(f'{tag}: {"victim" if line == "v" else "aggressor"} {a.xtalk} w {a.w} gap {a.gap}')
        die = f'{tag}_pkg'
        s.tl(die, f'{tag}_fb', Z_PKG, 70e-12)
        d = s.ibis('drv', EFX, 'SE0', 'lpddr4_ocd_40p_40n', die, f'f0={eng(1 / ui)} n={a.bits}' + corner)
        L = 'In2.Cu' if a.xtalk == 'inner' else 'F.Cu'
        s.via(f'{tag}_fb', f'{tag}_f', VIA_L(abs(Z_LAYER['F.Cu'] - Z_LAYER[L])) if L != 'F.Cu' else 0.05e-9, VIA_C_U501)
        s.via(f'{tag}_m', f'{tag}_mb', VIA_L(abs(Z_LAYER['F.Cu'] - Z_LAYER[L])) if L != 'F.Cu' else 0.05e-9, VIA_C_U801)
        r = s.ibis('rx', MEM, 'E4', 'ODT_60', f'{tag}_mb', corner.strip())
        meta[tag] = dict(kind='dq_write', net='xtalk', ui=ui, drv=d, rx=[(r, f'{tag}_mb')], victim=line == 'v',
                         ne=f'{tag}_fb')
    meta['_cpl'] = dict(layer=a.xtalk, w=a.w, gap=a.gap, len=a.len, nodes_in=['xa1_f', 'xv_f', 'xa2_f'],
                        nodes_out=['xa1_m', 'xv_m', 'xa2_m'])
    return finish(s, meta)


def pair(t): return tuple(float(x) for x in t.split('/'))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('out')
    p.add_argument('--rate', type=float, default=2800.0)
    p.add_argument('--w-in', type=float, default=0.18)
    p.add_argument('--w-out', type=float, default=0.25)
    p.add_argument('--diff-in', type=pair, default=(0.14, 0.15))
    p.add_argument('--diff-out', type=pair, default=(0.20, 0.20))
    p.add_argument('--corner', default='typ', choices=['typ', 'min', 'max'])
    p.add_argument('--pkg', default='netlen', choices=['netlen', 'file', 'rlc'])
    p.add_argument('--set', default='base', choices=['base', 'all'])
    p.add_argument('--bits', type=int, default=150, help='data bits (PRBS7 127 + 12 start-up)')
    p.add_argument('--ca-bits', type=int, default=140, help='CA/CS/CKE bits (one per tCK)')
    p.add_argument('--dq-nets', nargs='*', default=['ddr_dq4', 'ddr_dq6', 'ddr_dq1', 'ddr_dq11', 'ddr_dq10', 'ddr_dq23',
                                                     'ddr_dq27', 'ddr_dm3'])
    p.add_argument('--dqs-nets', nargs='*', default=['ddr_dqs0', 'ddr_dqs3'])
    p.add_argument('--ca-nets', nargs='*', default=['ddr_ca1', 'ddr_ca2', 'ddr_ca4', 'ddr_cs2_n', 'ddr_cs0_n', 'ddr_cke0'])
    p.add_argument('--no-ck', action='store_true', help='leave CK out (debugging)')
    p.add_argument('--keep', help='regex (full match) on the case tags: only these channels (run_si.py splits a point '
                                  'into several small netlists; one with all 44 channels needs > 9 GB in ngspice)')
    p.add_argument('--validate', action='store_true', help='driver-into-fixture schematic instead')
    p.add_argument('--xtalk', choices=['inner', 'outer'])
    p.add_argument('--w', type=float, default=0.18)
    p.add_argument('--gap', type=float, default=0.11)
    p.add_argument('--len', type=float, default=25.0)
    p.add_argument('--fast', action='store_true', help='write OUT as a kicad_ibis.fastnet netlist (JSON), no schematic')
    p.add_argument('--models', default='models', help='models/ folder, relative to the schematic')
    a = p.parse_args()
    meta, text = (build_validate if a.validate else build_xtalk if a.xtalk else build)(a)
    open(a.out, 'w').write(text)
    json.dump(meta, open(os.path.splitext(a.out)[0] + '.json', 'w'), indent=1)   # case -> driver / receivers
