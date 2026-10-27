#!/usr/bin/env python3
"""Swap the footprint of some parts on the board for a library footprint (kipy):
    swap_footprint.py BOARD LIB:NAME REF [REF ...]
Keeps each part's position, orientation, side, reference, value, fields, schematic link (path, sheet), DNP and the
pad nets / pin functions by pad number, like tools/make_board.py does when it builds the board. For a footprint
change made in the sheet generators (tools/sheets/*.py) without rebuilding the board.
"""
import os
import sys

import pcbnew

board_path, fpid, refs = sys.argv[1], sys.argv[2], sys.argv[3:]
lib, name = fpid.split(":")
libdir = os.path.join(os.environ["KICAD_MOUNT"], "share", "kicad", "footprints", lib + ".pretty")
b = pcbnew.LoadBoard(board_path)
old, done = [], []
for ref in refs:
    f = b.FindFootprintByReference(ref)
    n = pcbnew.FootprintLoad(libdir, name)
    n.SetFPID(pcbnew.LIB_ID(lib, name))
    n.SetReference(ref); n.SetValue(f.GetValue())
    for fl in f.GetFields():
        if fl.GetName() in ("Reference", "Value", "Footprint"):
            continue
        n.SetField(fl.GetName(), fl.GetText())
        for g in n.GetFields():
            if g.GetName() == fl.GetName():
                g.SetVisible(fl.IsVisible())
    n.SetPath(f.GetPath()); n.SetSheetname(f.GetSheetname()); n.SetSheetfile(f.GetSheetfile())
    n.SetDNP(f.IsDNP())
    pads = {p.GetNumber(): p for p in f.Pads()}
    for p in n.Pads():
        q = pads.get(p.GetNumber())
        if q is not None:
            p.SetNet(q.GetNet()); p.SetPinFunction(q.GetPinFunction()); p.SetPinType(q.GetPinType())
    b.Add(n)
    n.SetPosition(f.GetPosition())
    if f.IsFlipped():
        n.Flip(n.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    n.SetOrientation(f.GetOrientation())
    old.append(f); done.append(ref)
for f in old:  # SWIG: remove last (KRT_LEARNING.md)
    b.Remove(f)
pcbnew.SaveBoard(board_path, b)
print(f"swap_footprint: {len(done)} parts -> {fpid}")
