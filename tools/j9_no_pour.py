#!/usr/bin/env python3
"""No zone copper under the Ethernet jack J9 (user, 2026-11-17: the jack is the card's galvanic isolation):
    tools/p2k/bin/kipy tools/j9_no_pour.py IN.kicad_pcb OUT.kicad_pcb
A rule area `j9_no_pour` over J9's courtyard inside the board (x 190.04 to the east edge, y 53.06-70.19) keeps
zone fills out on all eight copper layers: GND on In1 / In3 / In6 / B.Cu, 3V3 on In3, 1V8 on In4, 5V0 on B.Cu.
Tracks stay (the MDI pairs on F.Cu, the two LED nets). J9's three GND pins (10 CHS and the two shield tabs) lose
their plane connection and get 0.3 mm B.Cu tracks west to a GND via outside the area."""
import sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); MM = pcbnew.FromMM; TOMM = pcbnew.ToMM
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
X0, Y0, Y1 = 190.04, 53.06, 70.19
X1 = TOMM(b.GetBoardEdgesBoundingBox().GetRight()) + 0.2
if any(z.GetZoneName() == "j9_no_pour" for z in b.Zones()):
    sys.exit("j9_no_pour is already on the board")
z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName("j9_no_pour")
ls = pcbnew.LSET()
for l in b.GetEnabledLayers().CuStack():
    ls.AddLayer(l)
z.SetLayerSet(ls)
z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False)
z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
o = z.Outline(); o.NewOutline()
for x, y in ((X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)):
    o.Append(MM(x), MM(y))
b.Add(z)
gnd = b.FindNet("GND"); XV = X0 - 0.6
for p in b.FindFootprintByReference("J9").Pads():
    if p.GetNetname() == "GND":
        x, y = TOMM(p.GetPosition().x), TOMM(p.GetPosition().y)
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x, y)); t.SetEnd(P(XV, y)); t.SetLayer(pcbnew.B_Cu); t.SetWidth(MM(0.3)); t.SetNet(gnd); b.Add(t)
        v = pcbnew.PCB_VIA(b); v.SetPosition(P(XV, y)); v.SetWidth(pcbnew.F_Cu, MM(0.45)); v.SetDrill(MM(0.25))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); b.Add(v)
        print(f"   J9 pin {p.GetNumber()} ({p.GetPinFunction()}): B.Cu track from ({x:.2f}, {y:.2f}) to a GND via at ({XV:.2f}, {y:.2f})")
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.BuildConnectivity(); print("   open connections:", b.GetConnectivity().GetUnconnectedCount(False))
b.Save(sys.argv[2])
