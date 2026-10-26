#!/usr/bin/env python3
"""LPDDR4 CK/CA trunk-and-branch topology (tools/p2k/bin/kipy tools/ddr/ca_trunk_branch.py prep|finish IN OUT).

U801's channel A and B balls of every shared CA/CKE/CK net are mirror images about the package centre x = 173.3,
with a 3.25 mm ball-free gap (four depopulated columns) between them. Each shared net gets:
- a T via in the ball-free columns L/M, in its own channel between ball rows (CHANNEL);
- two mirror-image branches from the T via along the channel to the two ball pads (identical by construction):
  F.Cu with no via at the balls, except CA5 on In2;
- one trunk U501 -> T via, routed by route.py as a point-to-point net in one length/time-matched group.

prep:   rip the nets' copper outside U501's courtyard (U501 escapes are kept), add the T vias, and park the U801 pads
        on TMP_<net> nets so the router can only reach the T via. CS0/CS2 (one channel each) are ripped outside both
        courtyards and stay point to point.
finish: put the U801 pads back on their nets, remove the TMP nets, draw the F.Cu branches, refill.
"""
import sys

import pcbnew

SHARED = ["ddr_ca0", "ddr_ca1", "ddr_ca2", "ddr_ca3", "ddr_ca4", "ddr_ca5", "ddr_cke0", "ddr_ck_P", "ddr_ck_N"]
SINGLE = ["ddr_cs0_n", "ddr_cs2_n"]
TX = 173.3                    # gap centre
GAP = (172.2, 53.6, 174.4, 62.7)   # U801's ball-free centre columns: reserved for the T points and branches
# Only columns L/M (x 172.65..173.95) are ball-free; K/N (174.275 / 172.325) carry GND/NC balls. So every branch runs
# in a CHANNEL between ball rows: T via at (TX, channel y), along the channel to the column gap beside the target
# column, a short drop in that gap, and a 45 deg entry onto the ball. Mirror images on the two sides.
CHANNEL = {  # net: (channel y, branch layer)
    "ddr_ca1": (54.1, "F.Cu"), "ddr_ca0": (54.9, "F.Cu"), "ddr_cke0": (55.7, "F.Cu"),
    "ddr_ca5": (57.3, "In2.Cu"),        # no free channel near its row: runs on In2 with via-in-pad at its balls
    "ddr_ck_P": (58.9, "F.Cu"), "ddr_ck_N": (59.7, "F.Cu"), "ddr_ca2": (60.5, "F.Cu"),
    "ddr_ca3": (61.3, "F.Cu"), "ddr_ca4": (62.1, "F.Cu"),
}
PITCH_X = 0.65
VIA, DRILL, BR_W = 0.25, 0.15, 0.1
mm, FM = pcbnew.ToMM, pcbnew.FromMM


def short(n):
    return n.split("/")[-1]


U801 = None


def u801_pads(b, s):
    return [p for p in U801.Pads() if short(p.GetNetname()) in (s, "TMP_" + s)]


def net_map(b):
    """short name -> NETINFO_ITEM (full names carry the sheet path)."""
    out = {}
    for i in range(b.GetNetCount()):
        n = b.FindNet(i)
        if n is not None:
            out[short(n.GetNetname())] = n
    return out


def t_point(b, s):
    return (TX, CHANNEL[s][0]), CHANNEL[s][1]


KRT_DELAY_SCALE = 1000   # see prep: the router reads die_delay in ps, KiCad stores ns
START_GAP = 0.25   # in prep the branches start this far from the T point (dummy net), finish joins them


def branch_paths(b, s):
    """[(layer name, [points], pad)] for the two branches of net s: T point -> channel -> column gap -> 45 deg -> ball."""
    (tx, ty), lname = t_point(b, s)
    out = []
    for p in u801_pads(b, s):
        px, py = mm(p.GetPosition().x), mm(p.GetPosition().y)
        side = 1 if px > TX else -1
        xc = px - side * PITCH_X / 2
        sy = 1 if ty > py else -1
        pts = [(tx, ty), (xc, ty), (xc, py + sy * PITCH_X / 2), (px, py)]
        pts = [q for i, q in enumerate(pts) if i == 0 or abs(q[0] - pts[i - 1][0]) + abs(q[1] - pts[i - 1][1]) > 1e-6]
        out.append((lname, pts, p, side))
    return out


PS_PER_MM = {"F.Cu": 6.11, "B.Cu": 6.11, "In2.Cu": 7.01, "In5.Cu": 7.01}   # field solve, TI135_PCB_NOTES.md §6.5
VIA_PS = 5.5


def branch_delay(b, s):
    """Delay T point -> ball along one branch (both are equal), with the joining stub and an inner layer's ball via."""
    lname, pts, p, side = branch_paths(b, s)[0]
    L = sum(((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5 for a, c in zip(pts, pts[1:]))
    return L * PS_PER_MM[lname] + (VIA_PS if lname != "F.Cu" else 0.0)


def add_track(b, a, c, w, layer, net):
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(a[0]), FM(a[1])))
    t.SetEnd(pcbnew.VECTOR2I(FM(c[0]), FM(c[1]))); t.SetWidth(FM(w)); t.SetLayer(layer); t.SetNet(net); b.Add(t)


def new_net(b, name):
    """A new net with an explicit unused code (two NETINFO_ITEMs added back to back otherwise share one)."""
    code = max(b.FindNet(i).GetNetCode() for i in range(b.GetNetCount()) if b.FindNet(i) is not None) + 1
    ni = pcbnew.NETINFO_ITEM(b, name, code); b.Add(ni)
    return ni


def bbox(b, ref):
    return b.FindFootprintByReference(ref).GetCourtyard(pcbnew.F_CrtYd).BBox()


def prep(b):
    # pads and vias first: removing hundreds of tracks through the SWIG bindings garbles later object lookups
    keep501 = bbox(b, "U501"); keep801 = bbox(b, "U801")
    names = net_map(b)
    for s in SHARED:
        (x, y), _ = t_point(b, s)
        # the T point as a temporary one-pad THT footprint: the router targets pads, not bare vias
        fp = pcbnew.FOOTPRINT(b); fp.SetReference("TP_" + s); fp.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))
        pad = pcbnew.PAD(fp); pad.SetNumber("1"); pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE); pad.SetSize(pcbnew.VECTOR2I(FM(VIA), FM(VIA)))
        pad.SetDrillSize(pcbnew.VECTOR2I(FM(DRILL), FM(DRILL))); pad.SetLayerSet(pcbnew.PAD.PTHMask())
        pad.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y))); pad.SetNet(names[s]); fp.Add(pad); b.Add(fp)
        # the branch's delay rides on the T pad as pad-to-die, so the trunk matching covers die -> ball
        # (KRT_DELAY_SCALE: see the U501 note below)
        pad.SetPadToDieDelay(int(round(branch_delay(b, s) * 1000 * KRT_DELAY_SCALE)))
        tmp = new_net(b, "TMP_" + s)
        br = new_net(b, "BR_" + s)
        for lname, pts, p, side in branch_paths(b, s):   # branches drawn now (dummy net) so trunks keep out
            layer = b.GetLayerID(lname)
            pts = [(pts[0][0] + side * START_GAP, pts[0][1])] + pts[1:]
            for a, c in zip(pts, pts[1:]):
                add_track(b, a, c, BR_W, layer, br)
            if lname != "F.Cu":
                v = pcbnew.PCB_VIA(b); v.SetPosition(p.GetPosition()); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(FM(VIA)); v.SetDrill(FM(DRILL)); v.SetNet(br); b.Add(v)
        for p in u801_pads(b, s):
            p.SetNet(tmp)
    # other DDR nets with copper in the gap give way: ripped outside both courtyards and in the gap, re-routed later
    gx0, gy0, gx1, gy1 = GAP
    def in_gap(q):
        return gx0 <= mm(q.x) <= gx1 and gy0 <= mm(q.y) <= gy1
    # ... and so does any other DDR net with copper within 0.2 mm of a planned branch on the same layer (or a via
    # on a branch): e.g. a DQS escape stub in CA5's In2 corridor
    corridors = []
    for s in SHARED:
        for lname, pts, p, side in branch_paths(b, s):
            corridors += [(lname, a, c) for a, c in zip(pts, pts[1:])]

    def seg_d(q, a, c):
        dx, dy = c[0] - a[0], c[1] - a[1]; l2 = dx * dx + dy * dy
        t = 0 if l2 == 0 else max(0, min(1, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / l2))
        return ((q[0] - a[0] - t * dx) ** 2 + (q[1] - a[1] - t * dy) ** 2) ** 0.5

    def near_branch(t):
        via = isinstance(t, pcbnew.PCB_VIA)
        L = None if via else b.GetLayerName(t.GetLayer())
        ends = [t.GetPosition()] if via else [t.GetStart(), t.GetEnd()]
        pts = [(mm(q.x), mm(q.y)) for q in ends]
        if not via:   # sample along the track
            pts = [(pts[0][0] + (pts[1][0] - pts[0][0]) * k / 8, pts[0][1] + (pts[1][1] - pts[0][1]) * k / 8) for k in range(9)]
        return any((via or lname == L) and seg_d(q, a, c) < 0.2 + (0.15 if via else 0.05)
                   for lname, a, c in corridors for q in pts)
    movers = set()
    for t in b.GetTracks():
        s = short(t.GetNetname())
        if "ddr_" in s and s not in SHARED + SINGLE and not s.startswith(("BR_", "TMP_")):
            ends = [t.GetPosition()] if isinstance(t, pcbnew.PCB_VIA) else [t.GetStart(), t.GetEnd()]
            if any(in_gap(q) for q in ends) or near_branch(t):
                movers.add(s)
    # KiCadRoutingTools reads (die_delay X) as ps while KiCad writes it in ns: on this temporary copy the U501 delays
    # are scaled x1000 so the router sees the right picoseconds. The chain restores them (tools/pad_to_die.py).
    for p in b.FindFootprintByReference("U501").Pads():
        if p.GetPadToDieDelay():
            p.SetPadToDieDelay(p.GetPadToDieDelay() * KRT_DELAY_SCALE)
    doomed = []
    for t in b.GetTracks():
        s = short(t.GetNetname())
        ends = [t.GetPosition()] if isinstance(t, pcbnew.PCB_VIA) else [t.GetStart(), t.GetEnd()]
        if s in SHARED or s in SINGLE:   # whole net: point-to-point trunks so time matching applies (leftover
            doomed.append(t)                # escape pieces count as extra terminals, and a multi-point member
                                            # switches the group's matching off)
        elif s in movers and (not all(keep501.Contains(q) or keep801.Contains(q) for q in ends)
                              or any(in_gap(q) for q in ends) or near_branch(t)):
            doomed.append(t)
    for t in doomed:
        b.Remove(t)
    open("movers.txt", "w").write("\n".join(sorted(movers)) + "\n")
    print(f"ca_trunk_branch prep: other DDR nets moved out of the gap (movers.txt): {', '.join(sorted(movers))}")
    print(f"ca_trunk_branch prep: {len(doomed)} tracks/vias ripped, {len(SHARED)} T points (temporary THT pads TP_<net>), U801 pads parked on TMP_ nets")


def finish(b):
    names = net_map(b)
    tps = [f for f in b.GetFootprints() if f.GetReference().startswith("TP_ddr_")]
    for f in tps:            # T points back to plain vias
        q = f.GetPosition(); n = list(f.Pads())[0].GetNet()
        v = pcbnew.PCB_VIA(b); v.SetPosition(q); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(FM(VIA)); v.SetDrill(FM(DRILL)); v.SetNet(n); b.Add(v)
    for t in list(b.GetTracks()):                      # branches: dummy BR_ net -> the real net
        n = t.GetNetname()
        if n.startswith(("BR_", "TMP_")):
            t.SetNet(names[n.split("_", 1)[1]])
    for s in SHARED:
        (tx, ty), lname = t_point(b, s)
        for _, pts, p, side in branch_paths(b, s):
            p.SetNet(names[s])
            add_track(b, (tx, ty), (tx + side * START_GAP, ty), BR_W, b.GetLayerID(lname), names[s])
        br = names.get("BR_" + s)
        if br is not None:
            b.Remove(br)
        tmp = names.get("TMP_" + s)
        if tmp is not None:
            b.Remove(tmp)
    for f in tps:
        b.Remove(f)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    print(f"ca_trunk_branch finish: F.Cu branches drawn for {len(SHARED)} nets, pads back on their nets")


if __name__ == "__main__":
    mode, src, dst = sys.argv[1:4]
    board = pcbnew.LoadBoard(src)
    U801 = board.FindFootprintByReference("U801")
    {"prep": prep, "finish": finish}[mode](board)
    pcbnew.SaveBoard(dst, board)
