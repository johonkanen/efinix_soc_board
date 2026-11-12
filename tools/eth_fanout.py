#!/usr/bin/env python3
"""Ethernet PHY: MDI pairs and the north-side fan-out (tools/p2k/bin/kipy tools/eth_fanout.py IN.kicad_pcb OUT.kicad_pcb).

1. MDI pairs U901 -> J9: copied from the Agilex card (~/dev/agilex3_soc_control_card, read only), which has the same
   RTL8211FDI-CG, the same HR911130A jack and the same PHY-to-jack offset (0.05 mm apart). Its txrx{a..d}_{P,N}
   tracks (F.Cu, 0.12 mm, no vias, P/N matched) are translated by the PHY-centre offset and put on eth_mdi_*.
2. U901 pins 12-20 (PHYRSTB, MDC, MDIO, TXD3..0, TX_CTL, TXC) face north, away from the FPGA: a short F.Cu stub and
   a via each, in two staggered rows that clear R912/R920 (rxd3 series/strap), R929 (MDIO pull-up) and C920.
   MDIO's via also reaches R929.2 on B.Cu. The inner-layer runs from these vias are routed by tools/eth_route.sh.
3. R931 (RSET) moves 3.0 mm south: it sat east of pins 1/2, in the path of pair A.
Run it once on a board without this copper (it removes nothing).
"""
import os
import sys

import pcbnew

AGILEX = os.path.expanduser("~/dev/agilex3_soc_control_card/agilex_3_soc.kicad_pcb")
mm, T = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
F, B = b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")


def pad(board, ref, num):
    for p in board.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            return p
    raise KeyError((ref, num))


def track(a, c, w, layer, net):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
    t.SetWidth(mm(w)); t.SetLayer(layer); t.SetNet(net); b.Add(t)


def via(x, y, net):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(F, mm(0.3))
    v.SetDrill(mm(0.15)); v.SetLayerPair(F, B); v.SetNet(net); b.Add(v)


# ---- 1. MDI pairs from the Agilex card
a = pcbnew.LoadBoard(AGILEX)
src, dst = a.FindFootprintByReference("U10").GetPosition(), b.FindFootprintByReference("U901").GetPosition()
off = pcbnew.VECTOR2I(dst.x - src.x, dst.y - src.y)
n = 0
for t in a.GetTracks():
    name = t.GetNetname().split("/")[-1]
    if not name.startswith("txrx"):
        continue
    net = b.FindNet("/09 ethernet/eth_mdi_" + name[4:]) or next(
        x for x in b.GetNetsByName().values() if str(x.GetNetname()).endswith("eth_mdi_" + name[4:]))
    assert t.GetClass() in ("PCB_TRACK", "PCB_ARC") and a.GetLayerName(t.GetLayer()) == "F.Cu", (name, t.GetClass())
    if t.GetClass() == "PCB_ARC":
        c = pcbnew.PCB_ARC(b); c.SetMid(pcbnew.Cast_to_PCB_ARC(t).GetMid() + off)
    else:
        c = pcbnew.PCB_TRACK(b)
    c.SetStart(t.GetStart() + off); c.SetEnd(t.GetEnd() + off)
    c.SetWidth(t.GetWidth()); c.SetLayer(F); c.SetNet(net); b.Add(c); n += 1
print(f"MDI: {n} segments copied, offset {T(off.x):.3f}, {T(off.y):.3f} mm")
# ---- 2. north-side fan-out: pin -> (via x, via y)
ROW_A, ROW_B = 58.47, 57.90
FAN = {"20": ROW_A, "19": 57.30, "18": ROW_A, "17": ROW_B, "16": ROW_A, "15": ROW_B, "14": ROW_A, "13": ROW_B,
       "12": ROW_A}
for num, vy in FAN.items():
    p = pad(b, "U901", num); q = p.GetPosition(); x, y = T(q.x), T(q.y)
    track((x, y), (x, vy), 0.1, F, p.GetNet()); via(x, vy, p.GetNet())
p14, r = pad(b, "U901", "14"), pad(b, "R929", "2")
assert p14.GetNetname() == r.GetNetname()
x14, rq = T(p14.GetPosition().x), r.GetPosition()
track((x14, ROW_A), (x14, T(rq.y)), 0.1, B, r.GetNet())
if abs(T(rq.x) - x14) > 0.01:
    track((x14, T(rq.y)), (T(rq.x), T(rq.y)), 0.1, B, r.GetNet())
print(f"fan-out: {len(FAN)} stubs and vias")

# ---- 3. R931 out of pair A's path
r931 = b.FindFootprintByReference("R931"); q = r931.GetPosition()
r931.SetPosition(pcbnew.VECTOR2I(q.x, q.y + mm(3.0)))
b.Save(sys.argv[2])
