#!/usr/bin/env python3
"""Via-in-pad fan-out for the BGAs (tools/p2k/bin/kipy tools/via_in_pad.py IN.kicad_pcb OUT.kicad_pcb).

Every connected ball of U501 (0.8 mm, 0.32 mm pads) gets a 0.30/0.15 mm through via at its pad centre, every
connected ball of U801 (0.8 x 0.65 mm, 0.27 mm pads) a 0.25/0.15 mm one. Plane balls then reach their pour on
In1/In3/In4/In6 by fill, signal balls are routed from the via on their layer (LAYOUT_PLAN.md phase 3-4). JLC fills
and caps via-in-pad on 6+ layer boards at no cost (order option: epoxy filled & capped). Balls already carrying a via
at their centre are skipped, so the script can be re-run.
"""
import sys

import pcbnew

VIAS = {"U501": (0.30, 0.15), "U801": (0.25, 0.15)}
b = pcbnew.LoadBoard(sys.argv[1])
have = {(v.GetPosition().x, v.GetPosition().y) for v in b.GetTracks() if isinstance(v, pcbnew.PCB_VIA)}
added = {}
for ref, (dia, drill) in VIAS.items():
    for p in b.FindFootprintByReference(ref).Pads():
        name = p.GetNetname()
        if not name or name.startswith("unconnected-"):
            continue
        pos = p.GetPosition()
        if (pos.x, pos.y) in have:
            continue
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pos)
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(pcbnew.FromMM(dia))
        v.SetDrill(pcbnew.FromMM(drill))
        v.SetNet(p.GetNet())
        b.Add(v)
        added[ref] = added.get(ref, 0) + 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[2], b)
print("via_in_pad:", ", ".join(f"{r} {n}" for r, n in added.items()))
