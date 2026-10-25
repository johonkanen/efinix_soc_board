import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1]); n = 0
for v in list(b.GetTracks()):
    if isinstance(v, pcbnew.PCB_VIA) and "ddr_" in v.GetNetname() and "CAL" not in v.GetNetname():
        b.Remove(v); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(sys.argv[2], b); print("removed", n, "DDR signal vias")
