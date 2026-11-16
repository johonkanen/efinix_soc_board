#!/usr/bin/env python3
"""RGMII TX series resistors R901-R906, a fresh arrangement (user, 2026-11-16: one step at a time; not the old spots):
    tools/p2k/bin/kipy tools/rgmii_tx.py IN.kicad_pcb OUT.kicad_pcb
Six 0201 on B.Cu in the one block east of U501's corner where vias fit on every layer (x 175.2-178.9, y 71.2-73.5),
standing north-south: pad 2 (PHY side) north, pad 1 (FPGA side) south, a via in each pad. Four in a row at
y 71.57, two behind them at y 73.12 on the half pitch, so that every track leaves between two vias.
The PHY-side In5 bus comes down from the north in the order txd0, txd3, tx_ctl, txd2, txc, txd1 (west to east);
the slots keep that order, so the fan to the vias has no crossing. Of the FPGA-side nets only the escapes from
the balls are kept (west of x 173); they are routed to the new vias in a second step, with the router:
    KICAD_RIP_PREEXISTING=0 ~/dev/KiCadRoutingTools/.venv/bin/python -X utf8 ~/dev/KiCadRoutingTools/py_router/route.py \
        OUT ROUTED --nets /rgmii_txc /rgmii_tx_ctl /rgmii_txd0 /rgmii_txd1 /rgmii_txd2 /rgmii_txd3 \
        --layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --track-width 0.12 --clearance 0.11 \
        --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --no-bga-zones U501 --no-fix-drc-settings \
        --board-edge-clearance 0.5 --escalation off --layer-costs 1 -1 1 -1 -1 1 -1 1
then refill the zones. R903 has to be 0201 first (sheet 09, tools/swap_footprint.py)."""
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); MM, TOMM = pcbnew.FromMM, pcbnew.ToMM
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
#        signal   ref     x      row centre y   x of the In5 vertical it comes down on
#                                               ... and the y where it leaves that vertical: staggered, the
#        track that moves furthest from its neighbour first, so that no two diagonals run side by side
SLOTS = [("txd0", "R903", 175.6, 71.57, 174.3, 69.0), ("txd3", "R906", 176.0, 73.12, 175.9, 68.7),
         ("tx_ctl", "R902", 176.4, 71.57, 176.15, 68.2), ("txd2", "R905", 176.8, 73.12, 176.45, 67.6),
         ("txc", "R901", 177.2, 71.57, 177.95, 67.6), ("txd1", "R904", 178.0, 71.57, 178.2, 68.6)]


def seg(netname, layer, a, c, w=0.12):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetLayer(layer); t.SetWidth(MM(w))
    t.SetNet(b.FindNet(netname)); b.Add(t)


def via(netname, x, y):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(pcbnew.F_Cu, MM(0.3)); v.SetDrill(MM(0.15))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(b.FindNet(netname)); b.Add(v)


for sig, ref, x, yc, xold, FAN_Y in SLOTS:
    fnet, pnet = "/rgmii_" + sig, "/09 ethernet/phy_" + sig
    f = b.FindFootprintByReference(ref)
    if f.GetLayer() != pcbnew.B_Cu:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for rot in (90, 270):
        f.SetOrientationDegrees(rot); f.SetPosition(P(x, yc))
        p1 = f.FindPadByNumber("1").GetPosition(); p2 = f.FindPadByNumber("2").GetPosition()
        if p2.y < p1.y:
            break
    assert f.FindPadByNumber("1").GetNetname() == fnet and f.FindPadByNumber("2").GetNetname() == pnet, ref
    y1, y2 = TOMM(p1.y), TOMM(p2.y)
    via(fnet, x, y1); via(pnet, x, y2)
    # PHY side on In5: cut the run at FAN_Y on its vertical, drop what was south of it, fan to the via
    w = 0.12
    for t in list(b.GetTracks()):
        if t.Type() == pcbnew.PCB_VIA_T or t.GetNetname() != pnet or t.GetLayer() != pcbnew.In5_Cu:
            continue
        ys = sorted((TOMM(t.GetStart().y), TOMM(t.GetEnd().y)))
        if ys[0] >= FAN_Y - 0.001:
            b.Delete(t)
        elif ys[1] > FAN_Y:
            assert abs(TOMM(t.GetStart().x) - xold) < 0.01 and abs(TOMM(t.GetEnd().x) - xold) < 0.01, (sig, "not vertical at the cut")
            w = TOMM(t.GetWidth())
            (t.SetEnd if t.GetEnd().y > t.GetStart().y else t.SetStart)(P(xold, FAN_Y))
    d = abs(x - xold)
    seg(pnet, pcbnew.In5_Cu, (xold, FAN_Y), (x, FAN_Y + d), w); seg(pnet, pcbnew.In5_Cu, (x, FAN_Y + d), (x, y2), w)
    # FPGA side: only the escape from the ball stays (everything that ends east of x 173 was the old approach)
    for t in list(b.GetTracks()):
        if t.GetNetname() == fnet and t.Type() != pcbnew.PCB_VIA_T and max(TOMM(t.GetStart().x), TOMM(t.GetEnd().x)) > 173.0:
            b.Delete(t)
    print(f"{ref} {sig}: ({x}, {yc}) B.Cu, FPGA via ({x}, {y1:.2f}), PHY via ({x}, {y2:.2f})")
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(sys.argv[2])
