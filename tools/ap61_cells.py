#!/usr/bin/env python3
"""Regulators TLV62585PDRLR -> Diodes AP61203Z6-7 / AP61202Z6-7 (user decision 2026-11-13: the user has 48 + 72 of
them at JLCPCB, the parts of the Agilex 5 card; first done with AP61302 / AP61102 the same day, same cell).

    python3 tools/ap61_cells.py sch              library symbol and sheets 02 / 03, in place (repeatable)
    kipy    tools/ap61_cells.py board IN OUT     pad nets and fields of the five regulators and their dividers
    kipy    tools/ap61_cells.py prep IN OUT      after buck_cell.py --strip: foreign copper in the way of a cell
    kipy    tools/ap61_cells.py parts IN OUT     fields only (a part change within the family, no layout change)

Same SOT-563 package, different pinout:   AP6120x / AP6130x: 1 FB, 2 GND, 3 VIN, 4 SW, 5 EN, 6 PG
                                          TLV62585:          1 GND, 2 SW, 3 VIN, 4 EN, 5 FB, 6 PG
The symbol keeps its drawing and only its pin numbers change, so no wire in the sheets moves. Layout: tools/buck_cell.py.

Parts (2 A, 1.3 MHz, peak limit 2.4 A min, DS: AP61200/1/2/3 September 2022):
  AP61203 (forced PWM) on VCORE, 0V85 and 1V1: fixed frequency and low ripple on the core, PLL and DDR rails;
  AP61202 (PFM at light load) on 1V8 and 3V3.
The mode is fixed by the part, so EN stays as wired (group 1 on 5V0, group 2 on pg_group1).
Feedback as in the data sheet's Table 1: R1 (top) 200 k, C3 33 pF across it, R2 (bottom) = 0.6 * R1 / (VOUT - 0.6):
VCORE 340 k (0.953 V), 0V85 475 k (0.853 V), 1V1 243 k (1.094 V), 1V8 100 k (1.800 V), 3V3 44.2 k (3.315 V).
L 1 uH (table value), CIN 10 u + 100 n, COUT 47 u + 22 u stay.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "TLV62585PDRL", "AP61x02Z6"
PINS = {"FB": "1", "GND": "2", "VIN": "3", "SW": "4", "EN": "5", "PG": "6"}
A203 = {"Value": "AP61203Z6-7", "LCSC": "C5244557",          # forced PWM, PG
        "Datasheet": "https://www.diodes.com/assets/Datasheets/AP61200_AP61201_AP61202_AP61203.pdf",
        "Description": "Diodes 2 A synchronous buck, forced PWM, 2.3-5.5 V in, 0.6 V FB, power good, SOT-563"}
A202 = {"Value": "AP61202Z6-7", "LCSC": "C5188956",          # PFM at light load, PG
        "Datasheet": "https://www.diodes.com/assets/Datasheets/AP61200_AP61201_AP61202_AP61203.pdf",
        "Description": "Diodes 2 A synchronous buck, PFM at light load, 2.3-5.5 V in, 0.6 V FB, power good, SOT-563"}
R200K = {"Value": "200k", "LCSC": "C138163"}
CFF = {"Value": "33p", "LCSC": "C277477"}                      # CC0201JRNPO9BN330, 50 V C0G
#        U: (sheet, part, R2 value, R2 LCSC, CFF ref)
CELLS = {"U201": ("02_pwr_vcore.kicad_sch", A203, "340k", "C423573", "C205"),
         "U301": ("03_pwr_rails.kicad_sch", A202, "100k", "C106224", "C305"),
         "U311": ("03_pwr_rails.kicad_sch", A202, "44.2k", "C226551", "C315"),
         "U331": ("03_pwr_rails.kicad_sch", A203, "475k", "C388079", "C334"),
         "U341": ("03_pwr_rails.kicad_sch", A203, "243k", "C423644", "C345")}


def edits(u):
    """ref -> fields for the regulator, R1 (top), R2 (bottom) and the feed-forward capacitor of one cell."""
    sheet, part, r2, r2l, cff = CELLS[u]
    b = int(u[1:])
    return {u: part, f"R{b}": R200K, f"R{b + 1}": {"Value": r2, "LCSC": r2l}, cff: CFF}


def block_end(t, a):
    d = 0
    for i in range(a, len(t)):
        d += (t[i] == "(") - (t[i] == ")")
        if d == 0:
            return i + 1


def renumber(t):
    """Rename the symbol and renumber its pins by name, in every definition of it in the text."""
    pos, n = 0, 0
    while True:
        m = re.compile(rf'\(symbol "(?:ti135_card:)?{OLD}"').search(t, pos)
        if not m:
            break
        e = block_end(t, m.start()); blk = t[m.start():e]
        blk, k = re.subn(r'(\(name "(FB|GND|VIN|SW|EN|PG)".*?\(number ")\d(")', lambda q: q.group(1) + PINS[q.group(2)] + q.group(3), blk, flags=re.S)
        assert k == 6, k
        blk = blk.replace('"Value" "TLV62585PDRLR"', '"Value" "AP61302Z6-7"')
        t = t[:m.start()] + blk + t[e:]; pos = m.start() + len(blk); n += 1
    return re.sub(rf"{OLD}(?!R)", NEW, t), n


def set_fields(t, ref, fields):
    m = re.search(rf'^\t\t\(property "Reference" "{ref}"$', t, re.M)
    a = t.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = t.index("\n\t)\n", m.start()) + 4
    blk = t[a:e]
    for k, v in fields.items():
        blk, n = re.subn(rf'(\(property "{k}" ")[^"]*(")', rf"\g<1>{v}\g<2>", blk, count=1)
        assert n == 1, (ref, k)
    return t[:a] + blk + t[e:]


def sch():
    p = os.path.join(ROOT, "lib", "ti135_card.kicad_sym"); t, n = renumber(open(p).read()); assert n in (0, 1)
    t = t.replace('"Value" "AP61302Z6-7"', '"Value" "AP61203Z6-7"')
    open(p, "w").write(t)
    for sheet in sorted({c[0] for c in CELLS.values()}):
        p = os.path.join(ROOT, "kicad", sheet); t, n = renumber(open(p).read()); assert n in (0, 1)
        for u, c in CELLS.items():
            if c[0] == sheet:
                for ref, f in edits(u).items():
                    t = set_fields(t, ref, f)
        open(p, "w").write(t)
        print(sheet, "done")


def board(src, dst, nets=True):
    import pcbnew
    b = pcbnew.LoadBoard(src)
    old = {"1": "GND", "2": "SW", "3": "VIN", "4": "EN", "5": "FB", "6": "PG"}
    for u in CELLS:
        f = b.FindFootprintByReference(u)
        net = {old[p.GetNumber()]: p.GetNet() for p in f.Pads()}
        for p in f.Pads() if nets else ():
            role = next(r for r, n in PINS.items() if n == p.GetNumber())
            p.SetNet(net[role]); p.SetPinFunction(role)
            p.SetPinType({"FB": "input", "GND": "power_in", "VIN": "power_in", "SW": "power_out", "EN": "input", "PG": "open_collector"}[role])
        for ref, fields in edits(u).items():
            g = b.FindFootprintByReference(ref)
            for k, v in fields.items():
                if k == "Value":
                    g.SetValue(v)
                elif g.HasField(k) or k == "Description":
                    g.SetField(k, v)
    pcbnew.SaveBoard(dst, b)
    print("board: pad nets and fields of", ", ".join(CELLS))


def prep(src, dst):
    """Foreign copper that the mirrored cells cannot live with. U341: the B.Cu 3V3 feed of C1204 ran round the old
    input capacitor; it is removed here and C1204 is reconnected afterwards (tools/decap_connect.py)."""
    import pcbnew
    b = pcbnew.LoadBoard(src)
    mm = pcbnew.ToMM
    kill = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayerName() == "B.Cu" and t.GetNetname() == "3V3"
            and all(146.25 < mm(q.x) < 150.5 and 57.0 < mm(q.y) < 62.2 for q in (t.GetStart(), t.GetEnd()))]   # the east chain only: the west one (x 145.7) feeds C1204
    for t in kill:
        print("  remove 3V3 B.Cu", round(mm(t.GetStart().x), 2), round(mm(t.GetStart().y), 2), "->", round(mm(t.GetEnd().x), 2), round(mm(t.GetEnd().y), 2))
    for t in kill:
        b.Remove(t)
    pcbnew.SaveBoard(dst, b)


if sys.argv[1] == "prep":
    prep(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "sch":
    sch()
else:
    board(sys.argv[2], sys.argv[3], nets=sys.argv[1] == "board")
