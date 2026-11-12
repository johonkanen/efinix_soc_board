#!/usr/bin/env python3
"""Snapshot and diff the geometry of the frozen interfaces (LPDDR4, QSPI flash, eMMC).

    tools/p2k/bin/kipy verify_protected.py snapshot [BOARD]   write protected_baseline.json
    tools/p2k/bin/kipy verify_protected.py check    [BOARD]   diff against it; exit 1 on any difference

Inputs: protected_nets.txt and protected_footprints.txt (tools/protected_nets.py).

What is compared (coordinates in nm, so any move shows):
  tier A nets   every track segment/arc and via: ends, width, layer, via size/drill/layer span.
                Any added, removed or changed item is a difference.
  tier B rails  the rail's tracks and vias inside the frozen regions at snapshot time: within
                REGION_MM of a protected footprint's pads (for the FPGA: of its DDR-bank balls
                only). Removing or changing one is a difference; new rail copper is allowed.
  footprints    position, rotation, side, and every pad's position and net.
Zone outlines are recorded per zone and reported when they change, but are not a failure:
power planes are extended in the power phase (they must not be split under the LPDDR4; that
is checked by DRC connectivity and by eye, not here).
"""
import sys
import json
import collections
import pcbnew

BASELINE = "protected_baseline.json"
REGION_MM = 1.0
SOC = "U501"


def read_list(path):
    rows = []
    for line in open(path):
        if line.strip() and not line.startswith("#"):
            rows.append(line.rstrip("\n").split("\t"))
    return rows


def item_key(b, t):
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition()
        return ["via", p.x, p.y, t.GetWidth(pcbnew.F_Cu), t.GetDrillValue(),
                b.GetLayerName(t.TopLayer()), b.GetLayerName(t.BottomLayer())]
    s, e = t.GetStart(), t.GetEnd()
    a, z = sorted([(s.x, s.y), (e.x, e.y)])
    key = ["arc" if t.Type() == pcbnew.PCB_ARC_T else "seg", a[0], a[1], z[0], z[1], t.GetWidth(), t.GetLayerName()]
    if t.Type() == pcbnew.PCB_ARC_T:
        m = t.GetMid()
        key += [m.x, m.y]
    return key


def snapshot(board_path):
    b = pcbnew.LoadBoard(board_path)
    tier = {r[1]: r[0] for r in read_list("protected_nets.txt")}
    refs = [r[0] for r in read_list("protected_footprints.txt")]
    fps = {f.GetReference(): f for f in b.GetFootprints()}

    # frozen regions for the tier B rails: boxes around the protected pads
    boxes = []
    for ref in refs:
        for p in fps[ref].Pads():
            if ref == SOC and "DDR" not in p.GetPinFunction().upper():
                continue
            bb = p.GetBoundingBox()
            bb.Inflate(pcbnew.FromMM(REGION_MM))
            boxes.append((bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
    x0 = min(q[0] for q in boxes); y0 = min(q[1] for q in boxes)
    cell = pcbnew.FromMM(2.0)
    grid = collections.defaultdict(list)
    for q in boxes:
        for gx in range((q[0] - x0) // cell, (q[2] - x0) // cell + 1):
            for gy in range((q[1] - y0) // cell, (q[3] - y0) // cell + 1):
                grid[(gx, gy)].append(q)

    def in_region(x, y):
        return any(q[0] <= x <= q[2] and q[1] <= y <= q[3] for q in grid.get(((x - x0) // cell, (y - y0) // cell), ()))

    nets = collections.defaultdict(list)
    for t in b.GetTracks():
        n = t.GetNetname()
        if n not in tier:
            continue
        if tier[n] == "B":
            pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
            if not any(in_region(p.x, p.y) for p in pts):
                continue
        nets[n].append(item_key(b, t))
    snap = {"board": board_path, "tier": tier, "nets": {n: sorted(v, key=str) for n, v in nets.items()}, "footprints": {}, "zones": {}}
    for n in tier:
        snap["nets"].setdefault(n, [])
    for ref in refs:
        f = fps[ref]
        p = f.GetPosition()
        snap["footprints"][ref] = {
            "x": p.x, "y": p.y, "rot": f.GetOrientationDegrees(), "layer": f.GetLayerName(),
            "pads": sorted([q.GetNumber(), q.GetPosition().x, q.GetPosition().y, q.GetNetname()] for q in f.Pads()),
        }
    for z in b.Zones():
        o = z.Outline()
        pts = [(o.CVertex(i).x, o.CVertex(i).y) for i in range(o.TotalVertices())]
        layers = "+".join(b.GetLayerName(l) for l in z.GetLayerSet().Seq())
        snap["zones"][f"{z.GetNetname() or 'rule area'} {layers} {z.m_Uuid.AsString()[:8]}"] = hash(tuple(pts)) & 0xFFFFFFFF
    return snap


def check(board_path):
    base = json.load(open(BASELINE))
    now = snapshot(board_path)
    diffs, notes = [], []
    if base["tier"] != now["tier"]:
        diffs.append("protected_nets.txt differs from the list the baseline was taken with")
    for n, tier in sorted(base["tier"].items()):
        old = collections.Counter(json.dumps(k) for k in base["nets"].get(n, []))
        new = collections.Counter(json.dumps(k) for k in now["nets"].get(n, []))
        for k in (old - new).elements():
            diffs.append(f"[{tier}] {n}: removed/changed {k}")
        if tier == "A":
            for k in (new - old).elements():
                diffs.append(f"[A] {n}: added {k}")
    for ref, o in base["footprints"].items():
        c = now["footprints"].get(ref)
        if c is None:
            diffs.append(f"footprint {ref}: missing")
            continue
        for key in ("x", "y", "rot", "layer"):
            if o[key] != c[key]:
                diffs.append(f"footprint {ref}: {key} {o[key]} -> {c[key]}")
        if o["pads"] != [list(q) for q in c["pads"]]:
            diffs.append(f"footprint {ref}: pad positions or nets changed")
    for ref in now["footprints"]:
        if ref not in base["footprints"]:
            diffs.append(f"footprint {ref}: not in the baseline")
    for z in sorted(set(base["zones"]) | set(now["zones"])):
        if base["zones"].get(z) != now["zones"].get(z):
            notes.append(f"zone outline changed/added/removed: {z}")
    return diffs, notes


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    board = sys.argv[2] if len(sys.argv) > 2 else "kicad/ti135_card.kicad_pcb"
    if cmd == "snapshot":
        s = snapshot(board)
        json.dump(s, open(BASELINE, "w"), indent=0, sort_keys=True)
        a = sum(len(v) for n, v in s["nets"].items() if s["tier"][n] == "A")
        bb = sum(len(v) for n, v in s["nets"].items() if s["tier"][n] == "B")
        print(f"baseline: {a} items on tier A nets, {bb} rail items in the frozen regions, {len(s['footprints'])} footprints, {len(s['zones'])} zones")
    elif cmd == "check":
        diffs, notes = check(board)
        for n in notes:
            print("note:", n)
        for d in diffs:
            print("DIFF:", d)
        print(f"verify_protected: {len(diffs)} difference(s)" if diffs else "verify_protected: OK, no differences")
        sys.exit(1 if diffs else 0)
    else:
        sys.exit(__doc__)
