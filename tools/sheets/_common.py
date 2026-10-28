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


def cap_row(sh, x, y, rail, caps, title=None, gnd="GND", pitch=None, label=False, fields=None):
    """One decoupling row: rail symbol above, GND below, caps = [(ref, value, footprint or None)].
    label=True: the rail is a local net (net label above) instead of a power symbol.
    fields: {value: {field: text}}, extra fields (e.g. LCSC) per value."""
    pitch = pitch or g(7)
    if title:
        sh.text(title, x + g(4), y - g(10))
    top, bot = None, None
    for k, (ref, val, fp) in enumerate(caps):
        cx = x + k * pitch
        _, ct, cb = vert2(sh, "C", ref, cx, y, val, text="right", fields=(fields or {}).get(val))
        t, b = up(ct, 2), down(cb, 2)
        sh.wire(ct, t); sh.wire(cb, b)
        if top:
            sh.wire(top, t); sh.wire(bot, b)
            if k < len(caps) - 1:
                sh.junction(*t); sh.junction(*b)
        else:
            if label:
                sh.label(rail, *up(t, 2), 90)
            else:
                power_at(sh, rail, up(t, 2), "up")
            sh.wire(t, up(t, 2))
            power_at(sh, gnd, down(b, 2), "down"); sh.wire(b, down(b, 2))
            if len(caps) > 1:
                sh.junction(*t); sh.junction(*b)
        top, bot = t, b
        if fp:
            set_field(sh, ref, "Footprint", fp)


def side_of(placed, num):
    """Which side of a placed symbol pin `num` sits on: 'left', 'right', 'up' or 'down' (from the pin extents)."""
    pts = list(placed.pins.values())
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    p = placed.pin(num)
    if p[0] <= min(xs) + 1e-6 and max(xs) - min(xs) > 1:
        return "left"
    if p[0] >= max(xs) - 1e-6 and max(xs) - min(xs) > 1:
        return "right"
    return "up" if p[1] <= (min(ys) + max(ys)) / 2 else "down"


_ROT = {"left": 180, "right": 0, "up": 90, "down": 270}
_MOVE = {"left": lambda p, n: left(p, n), "right": lambda p, n: right(p, n),  # noqa: F405
         "up": lambda p, n: up(p, n), "down": lambda p, n: down(p, n)}  # noqa: F405


def attach(sh, placed, num, kind, name=None, n=3, shape="passive"):
    """Connect pin `num` outward from the symbol: kind 'label' / 'hlabel' (name), 'power' (rail name) or 'nc'.
    Returns the end point of the stub."""
    if kind == "nc":
        sh.no_connect(*placed.pin(num))
        return placed.pin(num)
    d = side_of(placed, num)
    p = placed.pin(num)
    q = _MOVE[d](p, n)
    sh.wire(p, q)
    if kind == "label":
        sh.label(name, *q, _ROT[d])
    elif kind == "hlabel":
        hlabel(sh, name, *q, _ROT[d], shape)
    elif kind == "power":
        power_at(sh, name, q, d)  # noqa: F405
    return q


def series_r(sh, ref, x, y, value, left_kind, left_name, right_kind, right_name, shape="passive", fields=None):
    """Horizontal resistor with a (h)label on each end: kinds 'label' or 'hlabel'."""
    _, a, b = horiz2(sh, "R", ref, x, y, value, text="above", fields=fields)  # noqa: F405
    for (pt, kind, name, d) in ((a, left_kind, left_name, "left"), (b, right_kind, right_name, "right")):
        q = _MOVE[d](pt, 2)
        sh.wire(pt, q)
        if kind == "hlabel":
            hlabel(sh, name, *q, _ROT[d], shape)
        else:
            sh.label(name, *q, _ROT[d])


def pull_r(sh, ref, x, y, net, rail, value):
    """Vertical resistor: net label at one end, rail (power symbol) at the other (GND below, supplies above)."""
    _, t, b = vert2(sh, "R", ref, x, y, value, text="right")  # noqa: F405
    if rail == "GND":
        sh.wire(t, up(t, 2)); sh.label(net, *up(t, 2), 90)  # noqa: F405
        sh.wire(b, down(b, 2)); power_at(sh, "GND", down(b, 2), "down")  # noqa: F405
    else:
        sh.wire(t, up(t, 2)); power_at(sh, rail, up(t, 2), "up")  # noqa: F405
        sh.wire(b, down(b, 2)); sh.label(net, *down(b, 2), 270)  # noqa: F405
