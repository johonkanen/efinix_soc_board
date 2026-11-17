#!/usr/bin/env python3
"""Decoupling at U501's three 3V3 balls (user, 2026-11-17): the 100 n C565, C563 and C564 come back from the 3V3
regulator output to balls M21, G7 and J7, on B.Cu, courtyards clear.
    tools/p2k/bin/kipy tools/caps_3v3.py IN.kicad_pcb OUT.kicad_pcb
Each goes to the position nearest its ball where the 3V3 pad touches the ball's via (or reaches 3V3 copper by a
short track) and the GND pad reaches a GND via; if nothing is free, one or two ordinary rail capacitors beside
the ball move to their regulator output instead (tools/pll_place.py's search). The vias the three capacitors
had in their pads at the regulator are removed."""
import sys

_src = open(__file__.replace("caps_3v3.py", "pll_place.py")).read()
__file__ = __file__.replace("caps_3v3.py", "pll_place.py")
exec(_src.split("for ref in (\"C504\", \"C5064\", \"C5072\"):")[0])
JOBS3 = [("C565", (156.4, 80.6)), ("C563", (167.6, 84.6)), ("C564", (167.6, 83.0))]
KEEP = {"C565", "C563", "C564", "C501", "C503", "C505", "C506", "C507", "C5068"}
for ref, ball in JOBS3:
    f = b.FindFootprintByReference(ref)
    for p in f.Pads():
        if p.GetNumber():
            for t in list(b.GetTracks()):
                if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == p.GetNetCode() and p.HitTest(t.GetPosition()):
                    b.Delete(t)
    strip_part(f); f.SetPosition(P(236, 44))
geo = Geo()
for ref, ball in JOBS3:
    if do(ref, "3V3", "GND", ball, 1.5, 0.9) or do_evict(ref, "3V3", "GND", ball, 1.5, 0.9):
        continue
    # J7 has no room of its own (it hangs on G7 by 1.6 mm of In4 track): a second capacitor at G7 or M21, else back
    # to the regulator output
    if not (do(ref, "3V3", "GND", (167.6, 84.6), 3.0, 1.2) or do(ref, "3V3", "GND", (156.4, 80.6), 3.0, 1.2)):
        f = b.FindFootprintByReference(ref); geo = Geo()
        print(f"   {ref}: no place at a 3V3 ball;", "back at the regulator" if at_switcher(f, "3V3", "0201") else "NOT PLACED")
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(sys.argv[2])
