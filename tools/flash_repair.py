#!/usr/bin/env python3
"""Phase 4 step 1: undo the flash wiring that predates the series resistors R623-R628.

    tools/p2k/bin/kipy tools/flash_repair.py BOARD

The six /flash_* nets ran on In2 from the FPGA straight into vias in U601's pads; the pads have been on
the *_r nets since the 33R resistors were added, so each via shorted its pad (and two eMMC resistor vias
sit on the old flash_sck / flash_io1 tracks). This removes every track of the six FPGA-side nets and
hands the via in each U601 pad to that pad's *_r net. The FPGA ball vias stay. Routing follows with
tools/grid_router.py. Nothing locked or protected is touched."""
import sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
NETS = ["/flash_sck", "/flash_cs_n", "/flash_io0", "/flash_io1", "/flash_io2", "/flash_io3"]
u601 = next(f for f in b.GetFootprints() if f.GetReference() == "U601")
pads = [p for p in u601.Pads() if p.GetNetname().endswith("_r")]
removed = renet = 0
for t in list(b.GetTracks()):
    if t.GetNetname() not in NETS:
        continue
    if t.IsLocked():
        sys.exit("locked item on a flash net")
    if t.Type() == pcbnew.PCB_VIA_T:
        for p in pads:
            if (p.GetPosition() - t.GetPosition()).EuclideanNorm() < pcbnew.FromMM(0.05):
                assert p.GetNetname().split("/")[-1] == t.GetNetname().split("/")[-1] + "_r", (p.GetNetname(), t.GetNetname())
                t.SetNet(p.GetNet()); renet += 1
    else:
        b.RemoveNative(t); removed += 1
pcbnew.SaveBoard(sys.argv[1], b)
print(f"removed {removed} tracks, {renet} vias handed to the _r nets")
