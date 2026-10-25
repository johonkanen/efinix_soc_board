#!/usr/bin/env python3
"""Create kicad/ti135_card.kicad_pcb from the schematic (run under KiCad's python: tools/p2k/bin/kipy tools/make_board.py).

Re-runnable start-of-layout tool. It rebuilds the board from scratch, so only use it until placement starts:
after that, update the board from the schematic in pcbnew instead.
- one footprint per symbol, with nets, pin functions/types and symbol links (DRC schematic parity);
- the outline (76.000 x 65.127 mm) and the aux/grid origin at KiCad (100, 100) = the Ti60 Gerber origin
  (MECHANICAL.md);
- the fixed parts J3, J6 (bottom-side sockets to the baseboard) and J9 (HR911130A magjack). Each is placed by
  trying the orientations and keeping the one that puts its pads/pegs on the MECHANICAL.md coordinates
  (it fails if none does);
- U501 rotated 180 deg (DDR edge north), U801 north of it, J5 at the Ti60/Agilex position, J1/J2 west below J3;
- every other footprint staged by sheet in a grid to the right of the board;
- 8 copper layers. The stack-up, net classes and DRC rules are added afterwards by tools/board_setup.py.
"""
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
os.environ.setdefault("P2K_BOARD", ROOT)
os.environ.setdefault("P2K_PCB", os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb"))
os.environ.setdefault("P2K_SCHEMATIC", os.path.join(ROOT, "kicad", "ti135_card.kicad_sch"))
os.environ.setdefault("P2K_REPORTS", os.path.join(ROOT, "reports"))

import subprocess  # noqa: E402
import tempfile  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

import pcbnew  # noqa: E402

from p2k import board as p2k_board  # noqa: E402
from p2k import pcb  # noqa: E402
from p2k.build_pcb import load_fp  # noqa: E402


def mm(v):
    return pcbnew.FromMM(v)


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


OUTLINE = (131.531, 51.694, 207.531, 116.821)          # x0, y0, x1, y1 (KiCad frame, MECHANICAL.md)
ORIGIN = (100.0, 100.0)                                # Ti60 Gerber origin

# fixed parts: reference -> (side, {pad number: (x, y)} the pads must land on, anchor position)
J3_PADS = {"1": (135.102, 75.445), "2": (133.832, 75.445), "37": (135.102, 52.585), "38": (133.832, 52.585)}
J6_PADS = {"1": (203.072, 113.754), "2": (203.072, 115.024), "3": (201.802, 113.754), "6": (200.532, 115.024)}
J9_ORIGIN = (200.992, 61.655)                          # peg midpoint: front face at Ti60 X 111.912, centre Y 38.345
J9_PADS = {"1": (192.102, 67.37), "10": (194.642, 55.94), "11": (205.892, 68.28), "14": (205.892, 55.03)}
FIXED = {
    "J3": ("bottom", J3_PADS, J3_PADS["1"]),
    "J6": ("bottom", J6_PADS, J6_PADS["1"]),
    "J9": ("top", J9_PADS, J9_ORIGIN),
}
# soft positions: reference -> (x, y, orientation, side)
SOFT = {
    "U501": (164.0, 81.0, 180.0, "top"),    # Agilex U7 position; 180 deg: DDR rows (U..AB) face north
    "U801": (173.3, 58.1, -90.0, "top"),    # Agilex U12 position
    "J5": (152.912, 114.454, 90.0, "top"),  # LCD header, Ti60 J4 / Agilex J5 position
    # JTAG / UART headers in line with J3's pin column, south of it: the baseboard has no top-side parts under
    # x 131.5..136.5, y 77..116 except REF1 (y 92..96), so the pin tails are clear (MECHANICAL.md)
    "J1": (133.5, 79.5, 0.0, "top"),
    "J2": (133.5, 107.0, 0.0, "top"),
}


def pin_info():
    """{(ref, pin): (pin function, pin type)} from the schematic netlist. p2k's export_netlist drops them; pcbnew's
    "Update from schematic" sets them, and the placement tools read them (power pins, an oscillator's OUT)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "netlist.xml")
        subprocess.run([os.path.join(p2k_board.BIN, "kicad-cli"), "sch", "export", "netlist", "--format", "kicadxml",
                        "-o", out, pcb.schematic_file()], check=True, capture_output=True)
        xml = ET.parse(out).getroot()
    return {(nd.get("ref"), nd.get("pin")): (nd.get("pinfunction") or "", nd.get("pintype") or "")
            for n in xml.iter("net") for nd in n.findall("node")}


def place(board, fp, x, y, side, orient):
    board.Add(fp)
    fp.SetPosition(V(x, y))
    if side == "bottom":
        fp.Flip(V(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(orient)


def pad_xy(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == num:
            q = p.GetPosition()
            return pcbnew.ToMM(q.x), pcbnew.ToMM(q.y)
    raise KeyError(num)


def fit_fixed(board, make, side, pads, anchor):
    """Try the four orientations (and, for a pad anchor, the matching position) until every listed pad lands on
    its target within 0.01 mm. make() returns a fresh footprint (Flip() on a re-used one would toggle its side)."""
    for orient in (0.0, 90.0, 180.0, 270.0):
        fp = make()
        place(board, fp, *anchor, side, orient)
        # the anchor may be a pad, not the footprint origin: shift so the first listed pad is on target
        first = next(iter(pads))
        if anchor == pads[first]:
            px, py = pad_xy(fp, first)
            pos = fp.GetPosition()
            fp.SetPosition(pcbnew.VECTOR2I(pos.x + mm(anchor[0] - px), pos.y + mm(anchor[1] - py)))
        err = max(max(abs(a - b) for a, b in zip(pad_xy(fp, n), xy)) for n, xy in pads.items())
        if err < 0.01:
            return orient
        board.Remove(fp)
    raise SystemExit(f"make_board: no orientation puts {fp.GetReference()} on its MECHANICAL.md pads")


def add_outline(board):
    x0, y0, x1, y1 = OUTLINE
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(V(*a))
        s.SetEnd(V(*b))
        s.SetWidth(mm(0.1))
        board.Add(s)


def main():
    pcbnew.KIID.SeedGenerator(4001)
    out = os.environ["P2K_PCB"]
    comps, nets = pcb.export_netlist()
    pin_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
    pins = pin_info()
    board = pcbnew.NewBoard(out)
    board.SetCopperLayerCount(8)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))
    ds.SetAuxOrigin(V(*ORIGIN))
    ds.SetGridOrigin(V(*ORIGIN))
    netinfo = {}
    for name in sorted(nets):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni

    staged = {}
    report = []
    for ref in sorted(comps, key=lambda r: (comps[r]["sheetfile"], r)):
        cm = comps[ref]
        if cm["excluded"]:
            continue
        def make(cm=cm, ref=ref):
            fp = load_fp(cm["footprint"])
            fp.SetReference(ref)
            fp.SetValue(cm["value"])
            for fname, val in cm["fields"].items():
                if fname in ("Reference", "Value", "Footprint"):
                    continue
                if fname == "Datasheet":
                    fp.GetField(pcbnew.FIELD_T_DATASHEET).SetText(val)
                elif fname == "Description":
                    fp.GetField(pcbnew.FIELD_T_DESCRIPTION).SetText(val)
                else:
                    fp.SetField(fname, val)
                    for f in fp.GetFields():
                        if f.GetName() == fname:
                            f.SetVisible(False)
            fp.SetPath(pcbnew.KIID_PATH(cm["sheet_tstamps"] + cm["tstamps"][0]))
            fp.SetSheetname(cm["sheetname"])
            fp.SetSheetfile(cm["sheetfile"])
            if cm["dnp"]:
                fp.SetDNP(True)
            for pad in fp.Pads():
                net = pin_net.get((ref, pad.GetNumber()))
                if net is not None:
                    pad.SetNet(netinfo[net])
                fn, typ = pins.get((ref, pad.GetNumber()), ("", ""))
                pad.SetPinFunction(fn)
                pad.SetPinType(typ)
            return fp
        if ref in FIXED:
            side, pads, anchor = FIXED[ref]
            orient = fit_fixed(board, make, side, pads, anchor)
            report.append(f"{ref}: {side}, orientation {orient:g}, pads on MECHANICAL.md positions")
        elif ref in SOFT:
            x, y, o, side = SOFT[ref]
            place(board, make(), x, y, side, o)
        else:
            staged.setdefault(cm["sheetfile"] or "root", []).append(make)
    # stage the rest by sheet: shelf packing on their real courtyard/bounding boxes, right of the board
    y = 45.0
    for sheet in sorted(staged):
        x, row_h = 215.0, 0.0
        for make in staged[sheet]:
            fp = make()
            place(board, fp, 0.0, 0.0, "top", 0.0)
            bb = fp.GetBoundingBox(False, False)
            w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
            if x + w > 215.0 + 160.0:
                x, y, row_h = 215.0, y + row_h + 1.5, 0.0
            dx, dy = x - pcbnew.ToMM(bb.GetX()), y - pcbnew.ToMM(bb.GetY())
            fp.SetPosition(V(dx, dy))
            x += w + 1.5
            row_h = max(row_h, h)
        y += row_h + 6.0
    add_outline(board)
    pcbnew.SaveBoard(out, board)
    for r in report:
        print("make_board: " + r)
    print(f"make_board: {len(comps)} footprints, {len(nets)} nets -> {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
