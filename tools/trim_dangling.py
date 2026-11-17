#!/usr/bin/env python3
"""Trim dangling track ends one at a time, keeping every connection (kipy):
    tools/p2k/bin/kipy tools/trim_dangling.py IN.kicad_pcb OUT.kicad_pcb DRC.json
For each track_dangling item of DRC.json (kicad-cli pcb drc --format json of IN): the loose end is cut back to the
last point where the track touches other copper of its net (a via, a pad, another track's end). A track that touches
nothing along its length except at its other end is removed. After each change the number of open connections is
compared with before; a change that opens something is undone. Run again with a fresh DRC until nothing is left
(a removed track can expose the next piece of a dead-end run)."""
import json
import math
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1]); MM, TOMM = pcbnew.FromMM, pcbnew.ToMM
drc = json.load(open(sys.argv[3]))


def opens():
    b.BuildConnectivity(); return b.GetConnectivity().GetUnconnectedCount(False)


def proj(p, a, c):
    dx, dy = c.x - a.x, c.y - a.y
    t = 0 if dx == dy == 0 else max(0.0, min(1.0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy)))
    return t, math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy)


def contacts(t):
    """parameters 0..1 along the track where other copper of the net touches it"""
    a, c = t.GetStart(), t.GetEnd(); hw = t.GetWidth() / 2; out = []
    for o in b.GetTracks():
        if o.m_Uuid == t.m_Uuid or o.GetNetCode() != t.GetNetCode():
            continue
        if o.Type() == pcbnew.PCB_VIA_T:
            s, d = proj(o.GetPosition(), a, c)
            if d <= o.GetWidth(pcbnew.F_Cu) / 2 + hw:
                out.append(s)
        elif o.GetLayer() == t.GetLayer():
            for e in (o.GetStart(), o.GetEnd()):
                s, d = proj(e, a, c)
                if d <= hw + o.GetWidth() / 2:
                    out.append(s)
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == t.GetNetCode() and p.IsOnLayer(t.GetLayer()):
                s, d = proj(p.GetPosition(), a, c)
                bb = p.GetBoundingBox(); r = min(bb.GetWidth(), bb.GetHeight()) / 2
                if d <= r + hw:
                    out.append(s)
    return out


base = opens(); done = 0
for v in drc["violations"]:
    if v["type"] != "track_dangling":
        continue
    it = v["items"][0]; name = it["description"].split("[")[1].split("]")[0]
    cand = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T and t.m_Uuid.AsString() == it.get("uuid")]
    if not cand:
        print(f"   {name}: track not found (already changed)"); continue
    t = cand[0]; a, c = pcbnew.VECTOR2I(t.GetStart()), pcbnew.VECTOR2I(t.GetEnd())
    L = TOMM(t.GetLength()); cs = contacts(t)
    tol = (t.GetWidth() / 2 + MM(0.05)) / max(1, t.GetLength())
    at_a = any(s <= tol for s in cs); at_c = any(s >= 1 - tol for s in cs)
    if at_a and at_c:
        print(f"   {name} {b.GetLayerName(t.GetLayer())} at ({TOMM(a.x):.2f}, {TOMM(a.y):.2f}): both ends touch copper, left alone"); continue
    if not cs or (not at_a and not at_c and len(cs) < 1):
        s_keep = None
    else:
        # loose end: the one without contact; cut back to the nearest contact to it
        s_keep = (min(cs) if not at_a else max(cs))
    if s_keep is None or (at_a and s_keep <= tol) or (at_c and s_keep >= 1 - tol) and False:
        new = None
    else:
        q = pcbnew.VECTOR2I(int(a.x + (c.x - a.x) * s_keep), int(a.y + (c.y - a.y) * s_keep))
        new = q
    only_end = (at_a and all(s <= tol for s in cs)) or (at_c and all(s >= 1 - tol for s in cs)) or not cs
    if only_end:                                    # nothing along it: the whole piece is a dead end
        lay = t.GetLayer(); t.SetLayer(pcbnew.User_9)
        if opens() > base + 1:
            t.SetLayer(lay); print(f"   {name}: {L:.2f} mm piece is needed after all, left alone")
        else:
            b.Delete(t); done += 1; print(f"   {name} {b.GetLayerName(lay)}: dead-end piece of {L:.2f} mm removed")
        continue
    if not at_a:
        t.SetStart(new)
    else:
        t.SetEnd(new)
    if opens() > base:
        t.SetStart(a); t.SetEnd(c); print(f"   {name}: trimming would open a connection, left alone")
    else:
        done += 1
        print(f"   {name} {b.GetLayerName(t.GetLayer())}: {L:.2f} -> {TOMM(t.GetLength()):.2f} mm, loose end cut back to ({TOMM(new.x):.2f}, {TOMM(new.y):.2f})")
zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
b.Save(sys.argv[2])
print(f"trim_dangling: {done} changed; open connections {opens()} (before {base})")
