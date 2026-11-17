#!/usr/bin/env python3
"""C508, the 100 n of the DDR PLL supply (U501 W11), on B.Cu at the ball with a clean courtyard (user, 2026-11-17):
    tools/p2k/bin/kipy tools/ddr_pll_cap.py IN.kicad_pcb OUT.kicad_pcb       (after tools/add_parts.py)
tools/pll_place.py's search: nearest position where both pads reach copper of their net by a straight track."""
import sys

_src = open(__file__.replace("ddr_pll_cap.py", "pll_place.py")).read()
__file__ = __file__.replace("ddr_pll_cap.py", "pll_place.py")
exec(_src.split("for ref in (\"C504\", \"C5064\", \"C5072\"):")[0])
assert do("C508", PLL, "GND", (164.4, 75.0), 3.5, 1.2)
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(sys.argv[2])
