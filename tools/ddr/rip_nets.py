#!/usr/bin/env python3
"""Remove all tracks and vias of the nets whose short name matches a regex (kipy; IN OUT REGEX).
Collects first, removes last (removing many items through the SWIG bindings garbles later lookups)."""
import re
import sys

import pcbnew

src, dst, pat = sys.argv[1:4]
rx = re.compile(pat)
b = pcbnew.LoadBoard(src)
doomed = [t for t in b.GetTracks() if rx.fullmatch(t.GetNetname().split("/")[-1])]
for t in doomed:
    b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
print(f"rip_nets: {len(doomed)} tracks/vias of nets matching {pat}")
