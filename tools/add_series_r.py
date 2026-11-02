#!/usr/bin/env python3
"""33 ohm series resistors on the QSPI flash and eMMC lines (IBIS check, sim/flash_emmc_si): python3 tools/add_series_r.py

Edits the hand-maintained sheets in place, as text (KiCad formatting kept):
  10_emmc: R1001 (CLK) 10R -> 33R; new 33R on CMD, DAT0-7, DS. The label at U1001's pin becomes <net>_r, the
           resistor sits between <net> (FPGA side, with the pull-ups) and <net>_r.
  06_fpga_config: new 33R on SCK, CS#, IO0-3. The wire from U601's pin to the hierarchical label is replaced by a
           <net>_r label on the pin; the resistor joins <net> (hierarchical label, pull-ups) and <net>_r.
The resistors are copies of R1001's symbol, switched to 0201 (LCSC C320843), in a free column with labels on both pins.
"""
import os, re, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEETS = os.path.join(ROOT, 'kicad')
R33 = ('33R', 'C320843')          # 0201 (Resistor_SMD:R_0201_0603Metric)


def u(): return str(uuid.uuid4())


def block(text, start_re):
    """(start, end) of the top-level block (one tab deep) whose first line matches start_re and contains ..."""
    m = re.search(start_re, text, re.M)
    if not m: raise SystemExit(f'not found: {start_re}')
    s = text.rfind('\n\t(', 0, m.start() + 1) + 1
    e = text.index('\n\t)\n', m.start()) + 4
    return s, e


def symbol_block(text, ref):
    m = re.search(rf'^\t\t\(property "Reference" "{ref}"$', text, re.M)
    s = text.rfind('\n\t(symbol\n', 0, m.start()) + 1
    e = text.index('\n\t)\n', m.start()) + 4
    return s, e


def resistor(template, ref, x, y, path):
    b = re.sub(r'\(path "[^"]+"', f'(path "{path}"', template)
    b = re.sub(r'^(\t\t\(at )[\d.]+ [\d.]+ 90\)', rf'\g<1>{x:g} {y:g} 90)', b, count=1, flags=re.M)
    b = re.sub(r'^\t\t\(uuid "[^"]+"\)', f'\t\t(uuid "{u()}")', b, count=1, flags=re.M)
    b = b.replace('"Reference" "R1001"', f'"Reference" "{ref}"').replace('(reference "R1001")', f'(reference "{ref}")')
    b = re.sub(r'"Value" "[^"]*"', f'"Value" "{R33[0]}"', b).replace('"LCSC" "C25077"', f'"LCSC" "{R33[1]}"')
    b = b.replace('Resistor_SMD:R_0402_1005Metric', 'Resistor_SMD:R_0201_0603Metric')
    # property positions: same offsets from the symbol as on R1001 (at 50.8 63.5)
    def prop_at(m):
        px, py = float(m.group(2)), float(m.group(3))
        return f'{m.group(1)}{x + px - 50.8:g} {y + py - 63.5:g} {m.group(4)})'
    b = re.sub(r'^(\t\t\t\(at )([\d.]+) ([\d.]+) (\d+)\)', prop_at, b, flags=re.M)
    b = re.sub(r'(\(pin "\d"\n\t\t\t\(uuid ")[^"]+', lambda m: m.group(1) + u(), b)
    return b


def label(name, x, y, rot):
    just = 'left' if rot == 0 else 'right'
    return (f'\t(label "{name}"\n\t\t(at {x:g} {y:g} {rot})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t)\n\t\t\t(justify {just} bottom)\n\t\t)\n\t\t(uuid "{u()}")\n\t)\n')


def add_column(text, template, items, x0, y0):
    path = re.search(r'\(path "([^"]+)"', text).group(1)     # this sheet's instance path
    """items: [(ref, net)]; resistor at (x0, y0 + 5.08 k), pin 1 (left, x0 - 3.81) = net, pin 2 = net_r."""
    new = ''
    for k, (ref, net) in enumerate(items):
        y = round(y0 + 5.08 * k, 2)
        new += resistor(template, ref, x0, y, path) + label(net, round(x0 - 3.81, 2), y, 180) + label(net + '_r', round(x0 + 3.81, 2), y, 0)
    i = text.rindex('\n\t(embedded_fonts') + 1 if '\n\t(embedded_fonts' in text else text.rindex('\n)') + 1
    return text[:i] + new + text[i:]


def main():
    p10 = os.path.join(SHEETS, '10_emmc.kicad_sch'); t = open(p10).read()
    s, e = symbol_block(t, 'R1001'); tmpl = t[s:e]
    r1001 = re.sub(r'"Value" "10R"', '"Value" "33R"', tmpl).replace('"LCSC" "C25077"', f'"LCSC" "{R33[1]}"') \
        .replace('Resistor_SMD:R_0402_1005Metric', 'Resistor_SMD:R_0201_0603Metric')
    t = t[:s] + r1001 + t[e:]
    emmc = [('R1002', 'emmc_cmd')] + [(f'R100{3 + i}', f'emmc_dat{i}') for i in range(7)] + \
           [('R1021', 'emmc_dat7'), ('R1022', 'emmc_ds')]
    for _, net in emmc:     # the label at U1001's pin (x 172.72) -> net_r
        t, n = re.subn(rf'(\t\(label "){net}("\n\t\t\(at 172\.72 [\d.]+ 180\))', rf'\g<1>{net}_r\2', t)
        if n != 1: raise SystemExit(f'{net}: {n} labels at U1001')
    t = add_column(t, tmpl, emmc, 101.6, 66.04)
    open(p10, 'w').write(t)

    p06 = os.path.join(SHEETS, '06_fpga_config.kicad_sch'); f = open(p06).read()
    flash = [('R623', 'flash_sck', 276.86, 73.66, 264.16), ('R624', 'flash_cs_n', 276.86, 71.12, 264.16),
             ('R625', 'flash_io0', 307.34, 71.12, 320.04), ('R626', 'flash_io1', 307.34, 73.66, 320.04),
             ('R627', 'flash_io2', 307.34, 76.2, 320.04), ('R628', 'flash_io3', 307.34, 78.74, 320.04)]
    for ref, net, px, py, hx in flash:
        pat = rf'\(xy {px:g} {py:g}\) \(xy {hx:g} {py:g}\)|\(xy {hx:g} {py:g}\) \(xy {px:g} {py:g}\)'
        m = re.search(pat, f)
        if not m: raise SystemExit(f'{net}: wire to U601 not found')
        s = f.rfind('\n\t(wire\n', 0, m.start()) + 1; e = f.index('\n\t)\n', m.start()) + 4
        sx = hx + 2.54 if hx < px else hx - 2.54      # stub from the hierarchical label, with a <net> label on its end
        stub = f[s:e].replace(m.group(0), f'(xy {hx:g} {py:g}) (xy {sx:g} {py:g})')
        stub = re.sub(r'\(uuid "[^"]+"\)', f'(uuid "{u()}")', stub)
        f = f[:s] + label(net + '_r', px, py, 180 if px < 290 else 0) + stub + label(net, sx, py, 0 if sx > hx else 180) + f[e:]
    f = add_column(f, tmpl, [(r, n) for r, n, *_ in flash], 241.3, 66.04)
    open(p06, 'w').write(f)
    print('sheet 10: R1001 33R, + ' + ', '.join(r for r, _ in emmc) + '; sheet 06: + ' + ', '.join(r for r, *_ in flash))


if __name__ == '__main__':
    main()
