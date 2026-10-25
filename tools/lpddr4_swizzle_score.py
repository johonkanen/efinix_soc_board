#!/usr/bin/env python3
"""Score the LPDDR4 DQ swizzle U501 (Ti135N484) -> U801 (H9HCNNN8KUMLHR) on the placed board (LPDDR4_SWIZZLE.md).

Run with KiCad's python:  tools/p2k/bin/kipy tools/lpddr4_swizzle_score.py [--search]
Prints, per byte, the wiring now on the board (read from the pads' nets) and its metrics:
  cross   straight-line crossings among the byte's 11 FPGA->DRAM lines (8 DQ, DM, DQS_P, DQS_N; the method of the
          Agilex 5 card's LPDDR4_SWIZZLE_PLAN.md)
  inv     river-route order inversions: FPGA escape order (north, west->east) against the DRAM entry order (near
          bytes from the south; far bytes around the package's outer side), equal positions count as free
  len     estimated length (straight, or via the U801 corner for far bytes) and DQ/DM minus DQS spread
--search also brute-forces all 8! DQ orders per byte (DM, DQS fixed) and prints the best by cross + inv.
"""
import itertools, math, os, sys
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_b = pcbnew.LoadBoard(os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb"))
d = {}
for _ref in ("U501", "U801"):
    d[_ref] = {"pads": {p.GetNumber(): dict(x=p.GetPosition().x / 1e6, y=p.GetPosition().y / 1e6,
                                             net=p.GetNetname(), fn=p.GetPinFunction())
                        for p in _b.FindFootprintByReference(_ref).Pads()}}

def fn2pos(ref):
    out = {}
    for n, p in d[ref]["pads"].items():
        f = p["fn"].rsplit("_", 1)[0] if p["fn"] else ""
        out[f] = (p["x"], p["y"], n)
    return out
F = fn2pos("U501"); M = fn2pos("U801")

# byte n: FPGA pins, memory channel/byte; memory side names
BYTES = {0: ("A", 0), 1: ("A", 1), 2: ("B", 0), 3: ("B", 1)}
# entry model: near bytes (mem byte 1) enter from the south heading north; far bytes (mem byte 0) wrap the
# package's outer side: channel A (east side) heading west, channel B (west side) heading east.
HEAD = {("A", 1): (0, -1), ("B", 1): (0, -1), ("A", 0): (-1, 0), ("B", 0): (1, 0)}
# waypoints for length estimates of far bytes (outside the package corner nearest the FPGA)
WAY = {("A", 0): (181.0, 63.0), ("B", 0): (165.6, 63.0)}

def seg_cross(a, b, c, e):
    def o(p, q, r):
        v = (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    return o(a, b, c)*o(a, b, e) < 0 and o(c, e, a)*o(c, e, b) < 0

def proj(pt, head):
    hx, hy = head
    rx, ry = -hy, hx  # right-hand perpendicular in y-down coordinates
    return pt[0]*rx + pt[1]*ry

def byte_objects(n):
    ch, mb = BYTES[n]
    fp = {k: F[f"DDR_DQ[{8*n+k}]"][:2] for k in range(8)}
    mp = {j: M[f"DQ{8*mb+j}_{ch}"][:2] for j in range(8)}
    fixed = [(F[f"DDR_DM[{n}]"][:2], M[f"DMI{mb}_{ch}"][:2], "DM"),
             (F[f"DDR_DQS[{n}]"][:2], M[f"DQS{mb}_T_{ch}"][:2], "DQS_P"),
             (F[f"DDR_DQS_N[{n}]"][:2], M[f"DQS{mb}_C_{ch}"][:2], "DQS_N")]
    return ch, mb, fp, mp, fixed

def metrics(n, perm):
    """perm[k] = memory DQ bit (within the byte) that FPGA DQ[8n+k] connects to."""
    ch, mb, fp, mp, fixed = byte_objects(n)
    lines = [(fp[k], mp[perm[k]]) for k in range(8)] + [(a, b) for a, b, _ in fixed]
    x = sum(seg_cross(*lines[i], *lines[j]) for i in range(len(lines)) for j in range(i+1, len(lines)))
    hf, hm = (0, -1), HEAD[(ch, mb)]
    inv = 0
    for i in range(len(lines)):
        for j in range(i+1, len(lines)):
            a = proj(lines[i][0], hf) - proj(lines[j][0], hf)
            b = proj(lines[i][1], hm) - proj(lines[j][1], hm)
            if abs(a) > 1e-6 and abs(b) > 1e-6 and (a > 0) != (b > 0):
                inv += 1
    def L(a, b):
        if (ch, mb) in WAY:
            w = WAY[(ch, mb)]
            return math.dist(a, w) + math.dist(w, b)
        return math.dist(a, b)
    lens = [L(*l) for l in lines]
    dqs = (lens[9] + lens[10]) / 2
    rel = [l - dqs for l in lens[:9]]
    return dict(cross=x, inv=inv, total=sum(lens[:9]), spread=max(rel)-min(rel), relmin=min(rel), relmax=max(rel))

def best(n):
    res = []
    for perm in itertools.permutations(range(8)):
        m = metrics(n, perm)
        res.append(((m["inv"] + m["cross"], m["cross"], m["inv"], m["spread"]), perm, m))
    res.sort(key=lambda r: r[0])
    return res


def board_perm(n):
    """memory bit (within its byte) on each FPGA DDR_DQ[8n+k], read from the board nets"""
    nets = {}
    for ref in ("U501", "U801"):
        for p in d[ref]["pads"].values():
            nets.setdefault(p["net"], []).append((ref, p["fn"].rsplit("_", 1)[0]))
    ch, mb = BYTES[n]
    perm = []
    for k in range(8):
        net = next(nm for nm, v in nets.items() if ("U501", f"DDR_DQ[{8 * n + k}]") in v)
        mem = next(f for r, f in nets[net] if r == "U801")
        perm.append(int(mem.split("_")[0][2:]) - 8 * mb)
    return perm


if __name__ == "__main__":
    tot = [0, 0]
    for n in range(4):
        perm = board_perm(n)
        m = metrics(n, perm)
        tot[0] += m["cross"]; tot[1] += m["inv"]
        print(f"byte {n} -> ch {BYTES[n][0]} byte {BYTES[n][1]}: board {perm} cross {m['cross']} inv {m['inv']} "
              f"len {m['total']:.1f} mm, DQ/DM-DQS {m['relmin']:+.2f}..{m['relmax']:+.2f} mm")
        if "--search" in sys.argv:
            r = best(n)
            print(f"    best {list(r[0][1])} cross {r[0][2]['cross']} inv {r[0][2]['inv']}")
    print(f"total cross {tot[0]} inv {tot[1]}")
