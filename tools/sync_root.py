#!/usr/bin/env python3
"""Rebuild the root sheet's sheet blocks from the sub-sheets' hierarchical labels.

For every sheet block of kicad/<PROJECT>.kicad_sch: one sheet pin per hierarchical label of its sub-sheet
(inputs/bidirectional on the left, outputs/passive on the right, sorted by name), the block resized to fit,
and a local label on each pin's end so pins of the same name on different blocks connect. The blocks are laid
out in columns. Run after any sheet script that adds or removes hierarchical labels.
"""
import os
import sys
import uuid

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
os.environ.setdefault("P2K_BOARD", ROOT)
from p2k import board  # noqa: E402
from p2k.sexpr import Sym, find, find_all, load, save  # noqa: E402

G = 2.54
PROJECT = board.config().PROJECT
KDIR = board.path("kicad")
NS = uuid.uuid5(uuid.NAMESPACE_URL, PROJECT + "/root")


def U(key):
    return str(uuid.uuid5(NS, key))


def eff(just):
    return [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("justify"), Sym(just)]]


def labels_of(fname):
    tree = load(os.path.join(KDIR, fname))
    out = {}
    for h in find_all(tree, "hierarchical_label"):
        out[h[1]] = str(find(h, "shape")[1])
    return out


def main():
    path = os.path.join(KDIR, f"{PROJECT}.kicad_sch")
    root = load(path)
    # the root sheet is only the block diagram: drop the labels and wires this tool placed before
    root[:] = [c for c in root if not (isinstance(c, list) and c[0] in ("label", "wire"))]
    sheets = find_all(root, "sheet")
    col_x = [25.4, 160.02, 294.64, 429.26]
    col_y = [30.48] * len(col_x)
    w = 63.5
    for i, s in enumerate(sheets):
        fname = next(p[2] for p in find_all(s, "property") if p[1] == "Sheetfile")
        sname = next(p[2] for p in find_all(s, "property") if p[1] == "Sheetname")
        labs = labels_of(fname)
        left = sorted(n for n, sh in labs.items() if sh in ("input", "bidirectional", "tri_state"))
        right = sorted(n for n in labs if n not in left)
        rows = max(len(left), len(right), 2)
        h = (rows + 1) * G
        c = min(range(len(col_x)), key=lambda k: col_y[k])
        x, y = col_x[c], col_y[c]
        col_y[c] = y + h + 12.7
        find(s, "at")[1:3] = [x, y]
        find(s, "size")[1:3] = [w, h]
        for p in find_all(s, "property"):
            if p[1] == "Sheetname":
                find(p, "at")[1:4] = [x, round(y - 0.7, 4), 0]
            elif p[1] == "Sheetfile":
                find(p, "at")[1:4] = [x, round(y + h + 0.6, 4), 0]
        s[:] = [c for c in s if not (isinstance(c, list) and c[0] == "pin")]
        for side, names in (("left", left), ("right", right)):
            for k, n in enumerate(names):
                py = round(y + (k + 1) * G, 4)
                px = x if side == "left" else round(x + w, 4)
                rot = 180 if side == "left" else 0
                s.append([Sym("pin"), n, Sym(labs[n]), [Sym("at"), px, py, rot],
                          [Sym("uuid"), U(f"{sname}:{n}")], eff(side)])
                lx = round(px - 2 * G, 4) if side == "left" else round(px + 2 * G, 4)
                i_ins = next(k2 for k2, c2 in enumerate(root) if isinstance(c2, list) and c2[0] == "sheet")
                root.insert(i_ins, [Sym("wire"), [Sym("pts"), [Sym("xy"), px, py], [Sym("xy"), lx, py]],
                                    [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                                    [Sym("uuid"), U(f"w:{sname}:{n}")]])
                root.insert(i_ins, [Sym("label"), n, [Sym("at"), lx, py, rot],
                                    eff("right" if side == "left" else "left"),
                                    [Sym("uuid"), U(f"l:{sname}:{n}")]])
        print(f"{sname:14s} {len(left):3d} left {len(right):3d} right")
    paper = find(root, "paper")
    paper[1] = "A1" if max(col_y) > 270 else "A2"
    save(path, root)


if __name__ == "__main__":
    main()
