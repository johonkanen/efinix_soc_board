#!/usr/bin/env python3
"""Copy the Agilex card's copper and parts under its LPDDR4 (U12) onto U801 (kipy):
    tools/p2k/bin/kipy tools/ddr/copy_dram_escape.py IN OUT [AGILEX_PCB]

Same DRAM (H9HCNNN8KUMLHR), same footprint, same rotation, so every offset from the DRAM centre carries over and
each Agilex net maps to ours through the ball it reaches (both CS balls share one Agilex net; there the nearest
ball decides).
- Decoupling: our C803-C840 (sheet 08, the Agilex values) go to the Agilex parts' positions, side and rotation
  (the 0201 100n on the via pairs under the DRAM, 22u at VDD1, the 1u/22u bulk row west of it); R802 (ZQ) to R43.
  Run tools/add_parts.py first so the new parts exist (it stages them off the board).
- Vias inside the DRAM body (+0.5 mm): the Agilex set. Our LPDDR4 vias that the Agilex does not have there are
  removed (their tracks were already taken up); power/GND vias are kept.
- B.Cu: the CA/CKE T-branches, the cap stubs and the ZQ stub. Not copied: the Agilex CS T (it ties both CS balls
  to one net; ours has cs0_n / cs2_n) and its reset, refclk and power routing.
The Agilex board is only read.
"""
import os
import sys

import pcbnew
from pcbnew import FromMM, ToMM

AGILEX = os.path.expanduser("~/dev/agilex3_soc_control_card/agilex_3_soc.kicad_pcb")
BOX = (9.0, 6.5)            # half sizes of the via/track window round the DRAM centre (body 8.5 x 6.0)
# Agilex ref -> ours. 1V1 100n: the 27 under the DRAM in Agilex reference order.
PARTS = {"C48": "C803", "C52": "C804", "C60": "C805",
         "C216": "C806", "C217": "C807", "C262": "C808", "C263": "C809",
         "C47": "C823", "C165": "C824", "C264": "C825", "C265": "C826",
         "R43": "R802"}
A100N = ["C49", "C50", "C53", "C54", "C57", "C58", "C61", "C62", "C63", "C65", "C66", "C67", "C69",
         "C71", "C73", "C74", "C75", "C77", "C78", "C79", "C81", "C82", "C83", "C85", "C87", "C89", "C93"]
OURS100N = [f"C{n}" for n in list(range(810, 823)) + list(range(827, 841))]


def rel(p, c):
    return ToMM(p.x) - c[0], ToMM(p.y) - c[1]


def inbox(x, y, m=0.0):
    return abs(x) < BOX[0] + m and abs(y) < BOX[1] + m


def main():
    src, out = sys.argv[1], sys.argv[2]
    ag = pcbnew.LoadBoard(sys.argv[3] if len(sys.argv) > 3 else AGILEX)
    b = pcbnew.LoadBoard(src)
    ua, ub = ag.FindFootprintByReference("U12"), b.FindFootprintByReference("U801")
    ca, cb = (ToMM(ua.GetPosition().x), ToMM(ua.GetPosition().y)), (ToMM(ub.GetPosition().x), ToMM(ub.GetPosition().y))
    assert ua.GetOrientationDegrees() == ub.GetOrientationDegrees()
    nets = {n.GetNetname(): n for n in b.GetNetInfo().NetsByName().values()}
    balls_a = {p.GetNumber(): p for p in ua.Pads()}
    ball_net = {p.GetNumber(): p.GetNetname() for p in ub.Pads()}
    netmap = {}
    for k, p in balls_a.items():
        netmap.setdefault(p.GetNetname(), set()).add(ball_net[k])

    def our_net(name, x, y):
        cand = netmap.get(name, {name})
        if len(cand) == 1:
            return nets[next(iter(cand))]
        k = min((k for k, p in balls_a.items() if p.GetNetname() == name),
                key=lambda k: (rel(balls_a[k].GetPosition(), ca)[0] - x) ** 2 + (rel(balls_a[k].GetPosition(), ca)[1] - y) ** 2)
        return nets[ball_net[k]]

    def at(x, y):
        return pcbnew.VECTOR2I(FromMM(cb[0] + x), FromMM(cb[1] + y))

    # ---- parts
    pairs = dict(PARTS)
    a100 = [r for r in A100N if ag.FindFootprintByReference(r)]
    assert len(a100) == len(OURS100N), (len(a100), len(OURS100N))
    pairs.update(zip(a100, OURS100N))
    for ra, rb in pairs.items():
        fa, fb = ag.FindFootprintByReference(ra), b.FindFootprintByReference(rb)
        x, y = rel(fa.GetPosition(), ca)
        if fb.IsFlipped() != fa.IsFlipped():
            fb.Flip(fb.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fb.SetPosition(at(x, y))
        fb.SetOrientationDegrees(fa.GetOrientationDegrees())
        # the rail pad must land where the Agilex rail pad is (the via pair under it)
        pa = {p.GetNumber(): rel(p.GetPosition(), ca) for p in fa.Pads() if p.GetNumber()}
        pb = {p.GetNumber(): rel(p.GetPosition(), cb) for p in fb.Pads() if p.GetNumber()}
        if abs(pa["1"][0] - pb["1"][0]) + abs(pa["1"][1] - pb["1"][1]) > 0.01:
            fb.SetOrientationDegrees(fa.GetOrientationDegrees() + 180)
        print(f"{rb:5s} <- {ra:5s} ({x:+.3f}, {y:+.3f}) {'B' if fb.IsFlipped() else 'F'} {fb.GetOrientationDegrees():g}")

    # ---- vias
    va = [v for v in ag.GetTracks() if v.GetClass() == "PCB_VIA" and inbox(*rel(v.GetPosition(), ca))]
    va += [v for v in ag.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == "1V1"
           and all(abs(a - e) < 0.02 for a, e in zip(rel(v.GetPosition(), ca), (10.17, -1.2)))]  # R43's 1V1 via
    spots = [rel(v.GetPosition(), ca) for v in va]
    drop, ours = [], []
    for v in b.GetTracks():
        if v.GetClass() != "PCB_VIA":
            continue
        x, y = rel(v.GetPosition(), cb)
        if inbox(x, y) and "lpddr4" in v.GetNetname() and not any(abs(x - a) < 0.02 and abs(y - e) < 0.02 for a, e in spots):
            drop.append(v)
        else:
            ours.append((x, y))
    for v in drop:
        b.Remove(v)
    removed, added = len(drop), 0
    for v, (x, y) in zip(va, spots):
        if any(abs(x - a) < 0.02 and abs(y - e) < 0.02 for a, e in ours):
            continue
        n = pcbnew.PCB_VIA(b)
        n.SetPosition(at(x, y))
        n.SetWidth(v.GetWidth(pcbnew.F_Cu))
        n.SetDrill(v.GetDrill())
        n.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        n.SetNet(our_net(v.GetNetname(), x, y))
        b.Add(n)
        added += 1
    print(f"vias: {removed} removed, {added} added")

    # ---- B.Cu tracks
    # pads of the Agilex parts not copied (e.g. R44, its reset pull-down): their stubs would dangle here
    skip = [p for f in ag.GetFootprints() if f.GetReference() not in pairs and f.GetReference() != "U12"
            for p in f.Pads() if inbox(*rel(p.GetPosition(), ca), m=1.0)]
    copied = 0
    for t in ag.GetTracks():
        if t.GetClass() == "PCB_VIA" or t.GetLayer() != pcbnew.B_Cu:
            continue
        s, e = rel(t.GetStart(), ca), rel(t.GetEnd(), ca)
        name = t.GetNetname()
        short = name.split("/")[-1]
        if not (short.startswith(("ca", "cke")) or short in ("GND", "1V8") or "ZQ0" in short):
            continue
        if not (inbox(*s, m=1.0) and inbox(*e, m=1.0)):
            continue
        if any(p.HitTest(q) for p in skip for q in (t.GetStart(), t.GetEnd())):
            continue
        n = pcbnew.PCB_TRACK(b)
        n.SetStart(at(*s))
        n.SetEnd(at(*e))
        n.SetWidth(t.GetWidth())
        n.SetLayer(pcbnew.B_Cu)
        n.SetNet(our_net(name, *s))
        b.Add(n)
        copied += 1
    print(f"B.Cu segments copied: {copied}")
    b.Save(out)


if __name__ == "__main__":
    main()
