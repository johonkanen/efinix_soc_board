#!/usr/bin/env python3
"""Put the copper of some nets, and some footprints, back as they are in another copy of the board (kipy):
    tools/p2k/bin/kipy tools/restore_nets.py FROM.kicad_pcb BOARD.kicad_pcb OUT.kicad_pcb NET_REGEX [REF ...]
Every track, arc and via in BOARD whose net name matches NET_REGEX is replaced by those of FROM; the listed
footprints get FROM's position, side and rotation. Zones are refilled. Written for the eMMC routes, which are
delay-matched by hand, after the area around them was cleared for re-routing (user, 2026-11-16):
    git show HEAD:kicad/ti135_card.kicad_pcb > /tmp/head.kicad_pcb
    tools/p2k/bin/kipy tools/restore_nets.py /tmp/head.kicad_pcb kicad/ti135_card.kicad_pcb OUT 'emmc_' R1001 ...
"""
import re
import sys

import pcbnew

src, dst, out, pat, refs = sys.argv[1], sys.argv[2], sys.argv[3], re.compile(sys.argv[4]), sys.argv[5:]
h = pcbnew.LoadBoard(src); b = pcbnew.LoadBoard(dst)
n_del = 0
for t in list(b.GetTracks()):
    if pat.search(t.GetNetname()):
        b.Delete(t); n_del += 1
n_add = 0
for t in h.GetTracks():
    name = t.GetNetname()
    if not pat.search(name):
        continue
    net = b.FindNet(name)
    assert net, name
    if t.Type() == pcbnew.PCB_VIA_T:
        v = pcbnew.PCB_VIA(b); v.SetPosition(t.GetPosition()); v.SetViaType(t.GetViaType())
        v.SetLayerPair(t.TopLayer(), t.BottomLayer()); v.SetWidth(pcbnew.F_Cu, t.GetWidth(pcbnew.F_Cu)); v.SetDrill(t.GetDrillValue())
        n = v
    elif t.Type() == pcbnew.PCB_ARC_T:
        a = pcbnew.Cast_to_PCB_ARC(t) if hasattr(pcbnew, "Cast_to_PCB_ARC") else t
        n = pcbnew.PCB_ARC(b); n.SetStart(a.GetStart()); n.SetMid(a.GetMid()); n.SetEnd(a.GetEnd())
        n.SetLayer(a.GetLayer()); n.SetWidth(a.GetWidth())
    else:
        n = pcbnew.PCB_TRACK(b); n.SetStart(t.GetStart()); n.SetEnd(t.GetEnd()); n.SetLayer(t.GetLayer()); n.SetWidth(t.GetWidth())
    n.SetNet(net); b.Add(n); n_add += 1
moved = []
for ref in refs:
    f, g = b.FindFootprintByReference(ref), h.FindFootprintByReference(ref)
    if not f or not g:
        print(ref, "missing in", "BOARD" if not f else "FROM"); continue
    if f.GetLayer() != g.GetLayer():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(g.GetOrientationDegrees()); f.SetPosition(g.GetPosition()); moved.append(ref)
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(out)
print(f"restore_nets: {n_del} items removed, {n_add} restored on nets matching {pat.pattern!r}; footprints back: {' '.join(moved) or 'none'}")
