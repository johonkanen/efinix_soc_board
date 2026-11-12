#!/usr/bin/env python3
"""Board geometry as JSON for tools/grid_router.py:  tools/p2k/bin/kipy tools/dump_geom.py BOARD OUT.json

Pads (bounding box, copper layers, net, drill), tracks, vias, the board edge box, net classes, and for
every item of a net that has zones whether it sits in a fill of its net (so the router knows what is
already tied to a plane)."""
import sys, json, math, collections
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
cu = [l for l in pcbnew.LSET.AllCuMask(b.GetCopperLayerCount()).Seq()]
name = {l: b.GetLayerName(l) for l in cu}
zones = collections.defaultdict(list)
for z in b.Zones():
    if not z.GetIsRuleArea() and z.GetNetname():
        for l in z.GetLayerSet().Seq():
            zones[z.GetNetname()].append((z, l))


def in_fill(net, pos, layers):
    return any(l in layers and z.HitTestFilledArea(l, pos, 0) for z, l in zones.get(net, ()))


bb = b.GetBoardEdgesBoundingBox()
o = {"edge": [mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())], "layers": [name[l] for l in cu],
     "pads": [], "tracks": [], "vias": [], "netclass": {}, "zone_nets": sorted(zones)}
for f in b.GetFootprints():
    for p in f.Pads():
        tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        layers = cu if tht else [l for l in cu if p.IsOnLayer(l)]
        if not layers:
            continue
        r = p.GetBoundingBox(); net = p.GetNetname()
        o["pads"].append({"ref": f.GetReference(), "num": p.GetNumber(), "net": net, "x": mm(p.GetPosition().x), "y": mm(p.GetPosition().y),
                          "box": [mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())], "layers": [name[l] for l in layers],
                          "drill": mm(p.GetDrillSize().x) if tht else 0, "fill": in_fill(net, p.GetPosition(), layers), "fn": p.GetPinFunction()})
for t in b.GetTracks():
    net = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        o["vias"].append({"x": mm(t.GetPosition().x), "y": mm(t.GetPosition().y), "d": mm(t.GetWidth(pcbnew.F_Cu)), "drill": mm(t.GetDrillValue()),
                          "net": net, "fill": in_fill(net, t.GetPosition(), cu), "locked": t.IsLocked()})
    elif t.Type() == pcbnew.PCB_ARC_T:
        # arcs (the LPDDR4 meanders) as short chords, so the router sees where the copper really is
        l = t.GetLayer(); c = t.GetCenter(); r = t.GetRadius()
        a0 = math.atan2(t.GetStart().y - c.y, t.GetStart().x - c.x); am = math.atan2(t.GetMid().y - c.y, t.GetMid().x - c.x)
        a1 = math.atan2(t.GetEnd().y - c.y, t.GetEnd().x - c.x)
        d1 = (am - a0) % (2 * math.pi); d2 = (a1 - a0) % (2 * math.pi)
        sweep = d2 if d1 <= d2 else d2 - 2 * math.pi
        n = max(2, int(abs(sweep) * mm(r) / 0.05) + 1)
        pts = [(mm(c.x) + mm(r) * math.cos(a0 + sweep * k / n), mm(c.y) + mm(r) * math.sin(a0 + sweep * k / n)) for k in range(n + 1)]
        fl = in_fill(net, t.GetStart(), [l]) or in_fill(net, t.GetEnd(), [l])
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            o["tracks"].append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": mm(t.GetWidth()), "layer": name[l], "net": net, "fill": fl, "locked": t.IsLocked()})
    else:
        l = t.GetLayer()
        o["tracks"].append({"x1": mm(t.GetStart().x), "y1": mm(t.GetStart().y), "x2": mm(t.GetEnd().x), "y2": mm(t.GetEnd().y), "w": mm(t.GetWidth()),
                            "layer": name[l], "net": net, "fill": in_fill(net, t.GetStart(), [l]) or in_fill(net, t.GetEnd(), [l]), "locked": t.IsLocked()})
o["fills"] = []
for netname, zl in zones.items():
    for z, l in zl:
        ps = z.GetFilledPolysList(l)
        for i in range(ps.OutlineCount()):
            ol = ps.Outline(i)
            pts = [[mm(ol.CPoint(k).x), mm(ol.CPoint(k).y)] for k in range(ol.PointCount())]
            holes = []
            for hk in range(ps.HoleCount(i)):
                ho = ps.Hole(i, hk)
                holes.append([[mm(ho.CPoint(k).x), mm(ho.CPoint(k).y)] for k in range(ho.PointCount())])
            o["fills"].append({"net": netname, "layer": name[l], "pts": pts, "holes": holes})
for n in b.GetNetInfo().NetsByName():
    net = b.FindNet(str(n))
    if net:
        o["netclass"][str(n)] = net.GetNetClassName()
json.dump(o, open(sys.argv[2], "w"))
print(len(o["pads"]), "pads", len(o["tracks"]), "tracks", len(o["vias"]), "vias")
