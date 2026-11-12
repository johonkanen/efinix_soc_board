#!/usr/bin/env python3
"""Remove named rule areas, optionally refill the zones (tools/p2k/bin/kipy tools/eth_finish.py IN OUT NAME... [--fill])."""
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
names = [a for a in sys.argv[3:] if a != "--fill"]
for z in list(b.Zones()):
    if z.GetZoneName() in names:
        b.Remove(z); print("removed rule area", z.GetZoneName())
if "--fill" in sys.argv:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); print("zones refilled")
b.Save(sys.argv[2])
