#!/usr/bin/env python3
"""Replace the board's plane zones with placement/planes.json (tools/plane_regions.py) and fill them
(tools/p2k/bin/kipy tools/apply_planes.py [BOARD]). Zones: solid pad connection, 0.1 mm clearance and minimum width."""
import json
import os
import sys

import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb")
regions = json.load(open(os.path.join(ROOT, "placement", "planes.json")))
b = pcbnew.LoadBoard(PCB)
nets = {(r["net"], r["layer"]) for r in regions}
for z in list(b.Zones()):
    if (z.GetNetname(), b.GetLayerName(z.GetLayer())) in nets or z.GetZoneName().startswith("plane:"):
        b.Remove(z)
for r in regions:
    z = pcbnew.ZONE(b)
    z.SetLayer(b.GetLayerID(r["layer"]))
    z.SetNet(b.FindNet(r["net"]))
    z.SetZoneName(f"plane:{r['net']}")
    z.SetAssignedPriority(r["priority"])
    z.SetLocalClearance(pcbnew.FromMM(0.1))
    z.SetMinThickness(pcbnew.FromMM(0.1))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline(); o.NewOutline()
    for x, y in r["outline"][:-1]:
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
print(f"apply_planes: {len(regions)} zones on {os.path.relpath(PCB, ROOT)}")
