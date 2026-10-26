#!/usr/bin/env python3
"""Apply tools/ddr/tune_meander.py's edits to a board (kipy): IN.kicad_pcb EDITS.json OUT.kicad_pcb.

Removes the meandered segments (by UUID) and adds the new ones on their nets. Removal comes last (pcbnew SWIG: removing
garbles later lookups, KRT_LEARNING.md).
"""
import json
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
ed = json.load(open(sys.argv[2]))
gone = set(ed["remove"])
nets = {}
for e in ed["add"]:
    if e["net"] not in nets:
        nets[e["net"]] = b.FindNet(e["net"])
    t = pcbnew.PCB_TRACK(b)
    t.SetLayer(b.GetLayerID(e["layer"])); t.SetWidth(pcbnew.FromMM(e["width"])); t.SetNet(nets[e["net"]])
    t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(e["start"][0]), pcbnew.FromMM(e["start"][1])))
    t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(e["end"][0]), pcbnew.FromMM(e["end"][1])))
    b.Add(t)
old = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.m_Uuid.AsString() in gone]
for t in old:
    b.Remove(t)
pcbnew.SaveBoard(sys.argv[3], b)
print(f"tune_apply: {len(old)} segments replaced by {len(ed['add'])}")
