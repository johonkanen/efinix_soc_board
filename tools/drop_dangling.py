#!/usr/bin/env python3
"""Remove the vias and track segments a DRC report lists as dangling.

    kipy tools/drop_dangling.py IN.kicad_pcb OUT.kicad_pcb DRC.json [SKIP_UUID | UUID:X,Y ...]

Takes the via_dangling / track_dangling items of a `kicad-cli pcb drc
--format json` report by UUID and deletes them, then refills the zones.
Removing one segment of a stub exposes the next, so run DRC and this
script in turns until the report has no dangling items left, and check
that the unconnected count stays at zero. DRC also flags a track whose
end touches other copper off-centre; removing such a track opens the
net, so pass its UUID as SKIP_UUID, or as UUID:X,Y to pull the
overshooting end (the one farther from X,Y in mm stays) onto X,Y.
"""
import json
import sys

import pcbnew

src, dst, rep = sys.argv[1:4]
trim = {}
for a in sys.argv[4:]:
    if ":" in a:
        u, xy = a.split(":")
        trim[u] = tuple(float(c) for c in xy.split(","))
skip = {a.split(":")[0] for a in sys.argv[4:]}
want = {}
for v in json.load(open(rep))["violations"]:
    if v["type"] in ("via_dangling", "track_dangling"):
        for i in v["items"]:
            if i["uuid"] in skip:
                continue
            want[i["uuid"]] = i["description"]

board = pcbnew.LoadBoard(src)
hit = [t for t in board.GetTracks() if t.m_Uuid.AsString() in want]
for t in hit:
    print("remove", want[t.m_Uuid.AsString()])
n = len(hit)
for t in board.GetTracks():
    xy = trim.get(t.m_Uuid.AsString())
    if xy:
        p = pcbnew.VECTOR2I(pcbnew.FromMM(xy[0]), pcbnew.FromMM(xy[1]))
        ds = (t.GetStart() - p).EuclideanNorm()
        de = (t.GetEnd() - p).EuclideanNorm()
        if ds < de:
            t.SetStart(p)
        else:
            t.SetEnd(p)
        print("trim", t.GetNetname(), "end to", xy)
for t in hit:
    board.Remove(t)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(dst, board)
print(f"{n} of {len(want)} listed items removed")
