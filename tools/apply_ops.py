#!/usr/bin/env python3
"""Add the tracks and vias of a grid_router ops file to a board:  tools/p2k/bin/kipy tools/apply_ops.py BOARD OPS.json
Only adds copper; nothing existing is changed."""
import sys, json
import pcbnew

MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); ops = json.load(open(sys.argv[2]))
lid = {b.GetLayerName(l): l for l in pcbnew.LSET.AllCuMask(b.GetCopperLayerCount()).Seq()}
for t in ops["tracks"]:
    s = pcbnew.PCB_TRACK(b)
    s.SetStart(pcbnew.VECTOR2I(MM(t["x1"]), MM(t["y1"]))); s.SetEnd(pcbnew.VECTOR2I(MM(t["x2"]), MM(t["y2"])))
    s.SetWidth(MM(t["w"])); s.SetLayer(lid[t["layer"]]); s.SetNet(b.FindNet(t["net"])); b.Add(s)
for v in ops["vias"]:
    s = pcbnew.PCB_VIA(b)
    s.SetPosition(pcbnew.VECTOR2I(MM(v["x"]), MM(v["y"]))); s.SetWidth(pcbnew.F_Cu, MM(v["d"])); s.SetDrill(MM(v["drill"]))
    s.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); s.SetNet(b.FindNet(v["net"])); b.Add(s)
pcbnew.SaveBoard(sys.argv[1], b)
print("added", len(ops["tracks"]), "tracks,", len(ops["vias"]), "vias")
