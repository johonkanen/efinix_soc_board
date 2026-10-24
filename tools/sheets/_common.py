"""Board helpers for the sheet scripts (tools/sheets/NN_name.py). Generic helpers are p2k.sheetkit.

Conventions (MIGRATION_PLAN.md, from the Agilex SCHEMATIC_REORG_PLAN §3): no global labels; signals between
sheets go through hierarchical labels (hlabel) and the root sheet (tools/sync_root.py adds the sheet pins);
rails only through power symbols; signal nets lower snake_case, active low `_n`, diff pairs `_P`/`_N`.
Reference designators: sheet number x 100 (R1201.. on sheet 12).
Coordinates: schematic mm, Y down, 1.27 mm grid. Rotations CCW like eeschema.
"""
import csv
import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from p2k.sch_builder import U, Sheet, _eff  # noqa: E402,F401
from p2k.sexpr import Sym  # noqa: E402
from p2k.sheetkit import *  # noqa: E402,F401,F403
from p2k.sheetkit import _two_pin_rot  # noqa: E402,F401


def hlabel(sh, name, x, y, rot=0, shape="passive"):
    """Hierarchical label; rot 0 = text to the right of (x, y), 180 = to the left."""
    just = {0: "left", 90: "left", 180: "right", 270: "right"}[rot % 360]
    sh._add([Sym("hierarchical_label"), name, [Sym("shape"), Sym(shape)], [Sym("at"), x, y, rot],
             _eff(just), [Sym("uuid"), U()]])


def hlabel_left(sh, name, p, n=2, shape="passive"):
    q = left(p, n)  # noqa: F405
    sh.wire(p, q)
    hlabel(sh, name, *q, 180, shape)
    return q


def hlabel_right(sh, name, p, n=2, shape="passive"):
    q = right(p, n)  # noqa: F405
    sh.wire(p, q)
    hlabel(sh, name, *q, 0, shape)
    return q


def pinplan():
    """FPGA pin plan: {signal: row} from efinity/pinplan/ti135_pinplan.csv."""
    with open(os.path.join(ROOT, "efinity", "pinplan", "ti135_pinplan.csv")) as f:
        return {r["signal"]: r for r in csv.DictReader(f)}


def baseboard_j11():
    """{baseboard pin (int): row} from reference/baseboard_j11_pinout.csv."""
    with open(os.path.join(ROOT, "reference", "baseboard_j11_pinout.csv")) as f:
        return {int(r["baseboard_pin"]): r for r in csv.DictReader(f)}


def place_unit(sh, name, ref, x, y, unit, **kw):
    """Place a unit of a multi-unit symbol and move its Reference/Value fields just above the unit's pins
    (the library field position is shared by all units, which looks wrong on the small ones)."""
    from p2k.sexpr import find, find_all
    u = sh.place(name, ref, x, y, unit=unit, **kw)
    top = min(p[1] for p in u.pins.values()) - 2 * 2.54
    node = next(c for c in reversed(sh.tree) if isinstance(c, list) and c[0] == "symbol"
                and find(c, "unit") and find(c, "unit")[1] == unit
                and any(p[1] == "Reference" and p[2] == ref for p in find_all(c, "property")))
    for p in find_all(node, "property"):
        if p[1] == "Reference":
            find(p, "at")[1:3] = [x, round(top - 1.27, 4)]
        elif p[1] == "Value":
            find(p, "at")[1:3] = [x, round(top + 1.27, 4)]
    return u


def set_field(sh, ref, key, value):
    """Change a field (e.g. Footprint) of every placed unit of `ref` on this sheet."""
    from p2k.sexpr import find_all
    for c in sh.tree:
        if isinstance(c, list) and c[0] == "symbol":
            props = find_all(c, "property")
            if any(p[1] == "Reference" and p[2] == ref for p in props):
                for p in props:
                    if p[1] == key:
                        p[2] = value


C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"


C0201 = "Capacitor_SMD:C_0201_0603Metric"


def cap_row(sh, x, y, rail, caps, title=None, gnd="GND", pitch=None):
    """One decoupling row: rail symbol above, GND below, caps = [(ref, value, footprint or None)]."""
    pitch = pitch or g(7)
    if title:
        sh.text(title, x + g(4), y - g(10))
    top, bot = None, None
    for k, (ref, val, fp) in enumerate(caps):
        cx = x + k * pitch
        _, ct, cb = vert2(sh, "C", ref, cx, y, val, text="right")
        t, b = up(ct, 2), down(cb, 2)
        sh.wire(ct, t); sh.wire(cb, b)
        if top:
            sh.wire(top, t); sh.wire(bot, b)
            if k < len(caps) - 1:
                sh.junction(*t); sh.junction(*b)
        else:
            power_at(sh, rail, up(t, 2), "up"); sh.wire(t, up(t, 2))
            power_at(sh, gnd, down(b, 2), "down"); sh.wire(b, down(b, 2))
            if len(caps) > 1:
                sh.junction(*t); sh.junction(*b)
        top, bot = t, b
        if fp:
            set_field(sh, ref, "Footprint", fp)
