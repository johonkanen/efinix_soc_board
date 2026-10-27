#!/usr/bin/env python3
"""Bring a routed board up to date with the schematic without rebuilding it (kipy):
    tools/p2k/bin/kipy tools/add_parts.py IN OUT

The routing-safe part of pcbnew's "Update PCB from Schematic":
- every schematic part missing on the board is added as tools/make_board.py builds it (library footprint, fields,
  schematic link, pad nets, pin functions/types) and staged right of the board outline, one shelf per sheet;
- parts already on the board keep their position and copper; their value and fields follow the schematic;
- a pad whose net differs from the schematic is moved to the schematic net (new nets are created);
- parts on the board that are no longer in the schematic are only reported.
Nothing is deleted and no track or via is touched. Placement of the added parts is a separate step.
"""
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import make_board  # noqa: E402  (sets the P2K_* environment, no side effects on import)
from make_board import V, load_fp, pcb, pcbnew, pin_info  # noqa: E402


def main():
    src, out = sys.argv[1], sys.argv[2]
    comps, nets = pcb.export_netlist()
    pin_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
    pins = pin_info()
    board = pcbnew.LoadBoard(src)
    netinfo = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()}
    next_code = max(n.GetNetCode() for n in netinfo.values()) + 1
    new_nets = []

    def net(name):
        nonlocal next_code
        if name not in netinfo:
            ni = pcbnew.NETINFO_ITEM(board, name, next_code)  # explicit code (KRT_LEARNING.md: SWIG gotcha)
            next_code += 1
            board.Add(ni)
            netinfo[name] = ni
            new_nets.append(name)
        return netinfo[name]

    def set_fields(fp, cm):
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

    on_board = {fp.GetReference(): fp for fp in board.GetFootprints()}
    changed, renetted, added = [], [], []
    for ref, cm in sorted(comps.items()):
        if cm["excluded"]:
            continue
        fp = on_board.get(ref)
        if fp is None:
            continue
        if fp.GetValue() != cm["value"]:
            changed.append(f"{ref} value {fp.GetValue()} -> {cm['value']}")
            fp.SetValue(cm["value"])
        old = {f.GetName(): f.GetText() for f in fp.GetFields()}
        new = {k: v for k, v in cm["fields"].items() if k not in ("Reference", "Value", "Footprint")}
        diff = [k for k, v in new.items() if old.get(k, "") != v]
        if diff:
            changed.append(f"{ref} fields {', '.join(diff)}")
            set_fields(fp, cm)
        for pad in fp.Pads():
            want = pin_net.get((ref, pad.GetNumber()))
            if want is not None and not pcb.is_unconnected_net(want) and pad.GetNetname() != want:
                renetted.append(f"{ref}.{pad.GetNumber()} {pad.GetNetname() or '-'} -> {want}")
                pad.SetNet(net(want))

    shelves = {}
    for ref in sorted(comps, key=lambda r: (comps[r]["sheetfile"], r)):
        cm = comps[ref]
        if cm["excluded"] or ref in on_board:
            continue
        fp = load_fp(cm["footprint"])
        fp.SetReference(ref)
        fp.SetValue(cm["value"])
        set_fields(fp, cm)
        fp.SetPath(pcbnew.KIID_PATH(cm["sheet_tstamps"] + cm["tstamps"][0]))
        fp.SetSheetname(cm["sheetname"])
        fp.SetSheetfile(cm["sheetfile"])
        if cm["dnp"]:
            fp.SetDNP(True)
        for pad in fp.Pads():
            n = pin_net.get((ref, pad.GetNumber()))
            if n is not None:
                pad.SetNet(net(n))
            fn, typ = pins.get((ref, pad.GetNumber()), ("", ""))
            pad.SetPinFunction(fn)
            pad.SetPinType(typ)
        shelves.setdefault(cm["sheetfile"] or "root", []).append(fp)
        added.append(ref)
    # stage right of the outline (x > 215), below anything already staged there
    y = 45.0
    for fp in board.GetFootprints():
        if pcbnew.ToMM(fp.GetPosition().x) > 212:
            y = max(y, pcbnew.ToMM(fp.GetBoundingBox(False, False).GetBottom()) + 3)
    for sheet in sorted(shelves):
        x, row_h = 215.0, 0.0
        for fp in shelves[sheet]:
            board.Add(fp)
            fp.SetPosition(V(0, 0))
            bb = fp.GetBoundingBox(False, False)
            w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
            if x + w > 215.0 + 60.0:
                x, y, row_h = 215.0, y + row_h + 1.0, 0.0
            fp.SetPosition(V(x - pcbnew.ToMM(bb.GetX()), y - pcbnew.ToMM(bb.GetY())))
            x += w + 1.0
            row_h = max(row_h, h)
        y += row_h + 4.0
    gone = sorted(r for r in on_board if r not in comps and not r.startswith(("#", "REF**")))
    pcbnew.SaveBoard(out, board)
    print(f"add_parts: {len(added)} parts added: {' '.join(added) or 'none'}")
    print(f"add_parts: new nets: {new_nets or 'none'}")
    print(f"add_parts: value/field changes: {changed or 'none'}")
    print(f"add_parts: pad nets changed: {renetted or 'none'}")
    print(f"add_parts: on the board but not in the schematic (left alone): {gone or 'none'}")


if __name__ == "__main__":
    main()
