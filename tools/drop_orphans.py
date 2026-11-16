#!/usr/bin/env python3
"""Remove routes that reach no pin, and dangling vias (kipy; user, 2026-11-16, for a board in the middle of re-routing):
    tools/p2k/bin/kipy tools/drop_orphans.py IN.kicad_pcb OUT.kicad_pcb [DRC.json ...]
A route here is a group of tracks, arcs and vias of one net that touch each other. A group that touches no pad
of its net is removed: its tracks always; its vias unless the net has a plane or pour (a via into a plane is a
connection of its own and may be wanted again for a part that is parked). A route with a pin on one end and a
loose other end stays. Each DRC.json (kicad-cli pcb drc --format json of IN) adds its via_dangling items to
the vias to remove. Zones are refilled."""
import collections
import json
import math
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); out = sys.argv[2]
MM = pcbnew.FromMM


def seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def chords(t):
    s, e = t.GetStart(), t.GetEnd()
    if t.Type() == pcbnew.PCB_ARC_T:
        m = (pcbnew.Cast_to_PCB_ARC(t) if hasattr(pcbnew, "Cast_to_PCB_ARC") else t).GetMid()
        return [(s, m), (m, e)]
    return [(s, e)]


def run():
    by_net = collections.defaultdict(list)
    for t in b.GetTracks():
        by_net[t.GetNetCode()].append(t)
    pads = collections.defaultdict(list)
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.IsOnCopperLayer():
                pads[p.GetNetCode()].append(p)
    planes = {z.GetNetCode() for z in b.Zones() if not z.GetIsRuleArea()}
    n_t = n_v = 0; nets = collections.Counter()
    for nc, items in by_net.items():
        if nc == 0:
            continue
        par = list(range(len(items)))

        def find(i):
            while par[i] != i:
                par[i] = par[par[i]]; i = par[i]
            return i
        vias = [i for i, t in enumerate(items) if t.Type() == pcbnew.PCB_VIA_T]
        trk = [i for i, t in enumerate(items) if t.Type() != pcbnew.PCB_VIA_T]
        for i in trk:
            t = items[i]
            for end in (t.GetStart(), t.GetEnd()):
                for j in vias:
                    v = items[j]
                    if (v.GetPosition() - end).EuclideanNorm() <= v.GetWidth(pcbnew.F_Cu) // 2 + t.GetWidth() // 2:
                        par[find(i)] = find(j)
                for j in trk:
                    o = items[j]
                    if j != i and o.GetLayer() == t.GetLayer() and \
                       any(seg_d(end.x, end.y, a.x, a.y, c.x, c.y) <= o.GetWidth() // 2 + 1000 for a, c in chords(o)):
                        par[find(i)] = find(j)
        pinned = set()
        for i, t in enumerate(items):
            if t.Type() == pcbnew.PCB_VIA_T:
                if any(p.HitTest(t.GetPosition()) for p in pads[nc]):
                    pinned.add(find(i))
            else:
                for end in (t.GetStart(), t.GetEnd()):
                    if any(p.IsOnLayer(t.GetLayer()) and p.HitTest(end) for p in pads[nc]):
                        pinned.add(find(i))
        for i, t in enumerate(items):
            if find(i) in pinned:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                if nc in planes:
                    continue
                n_v += 1
            else:
                n_t += 1
            nets[t.GetNetname().split("/")[-1]] += 1
            b.Delete(t)
    return n_t, n_v, nets


n_t, n_v, nets = run()
drc_v = 0
for path in sys.argv[3:]:
    for v in json.load(open(path))["violations"]:
        if v["type"] != "via_dangling":
            continue
        x, y = v["items"][0]["pos"]["x"], v["items"][0]["pos"]["y"]
        for t in list(b.GetTracks()):
            if t.Type() == pcbnew.PCB_VIA_T and abs(t.GetPosition().x - MM(x)) < 2000 and abs(t.GetPosition().y - MM(y)) < 2000:
                nets[t.GetNetname().split("/")[-1]] += 1; b.Delete(t); drc_v += 1
if drc_v:                       # a route may have hung on such a via only
    a, c, more = run(); n_t += a; n_v += c; nets += more
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(out)
print(f"drop_orphans: {n_t} track segments and {n_v} vias of routes without a pin removed, {drc_v} dangling vias removed")
print("   by net:", dict(nets.most_common()))
