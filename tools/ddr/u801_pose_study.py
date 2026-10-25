import json, re, itertools, math
import numpy as np
d = json.load(open("pads.json"))
cx, cy = d["U801"]["centre"]
def byte(n):
    m = re.search(r'ddr_(dq|dm|dqs)(\d+)', n)
    if not m: return None
    i = int(m.group(2)); return i // 8 if m.group(1) == 'dq' else i
F = {}
for num, x, y, net, fn in d["U501"]["pads"]:
    if "ddr_" in net and "CAL" not in net: F[net] = (x, y)
M = {}   # net -> list of U801 ball positions (relative to centre)
for num, x, y, net, fn in d["U801"]["pads"]:
    if net in F: M.setdefault(net, []).append((x - cx, y - cy))
nets = sorted(F)
# within-byte swizzle: DQ nets of a byte can be permuted among that byte's DRAM DQ balls
bytes_ = {k: [n for n in nets if byte(n) == k and re.search(r'ddr_dq\d', n)] for k in range(4)}
def rot(p, a):
    t = math.radians(a); return (p[0] * math.cos(t) + p[1] * math.sin(t), -p[0] * math.sin(t) + p[1] * math.cos(t))  # KiCad: +a = CCW on screen (y down)
def segx(a, b, c, e):
    def o(p, q, r): return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    return (o(a, b, c) * o(a, b, e) < 0) and (o(c, e, a) * o(c, e, b) < 0)
def weight(n1, n2):
    b1, b2 = byte(n1), byte(n2)
    if b1 is None and b2 is None: return 0      # CA vs CA (branches to both channels): not counted
    if b1 is None or b2 is None: return 3
    return 1 if b1 == b2 else 10
def evaluate(a, ox, oy):
    end = {n: min(((ox + rot(p, a)[0], oy + rot(p, a)[1]) for p in M[n]), key=lambda q: math.hypot(q[0]-F[n][0], q[1]-F[n][1])) for n in nets}
    # best within-byte assignment (brute force 8!), crossings counted against everything else fixed
    for k, dq in bytes_.items():
        slots = [end[n] for n in dq]; best = None
        others = [n for n in nets if n not in dq]
        for perm in itertools.permutations(range(len(dq))):
            e = {dq[i]: slots[perm[i]] for i in range(len(dq))}
            c = sum(segx(F[dq[i]], e[dq[i]], F[dq[j]], e[dq[j]]) for i in range(len(dq)) for j in range(i+1, len(dq)))
            c += 3 * 0  # cross-group terms do not change much with a within-byte permutation; ignored for speed
            if best is None or c < best[0]: best = (c, e)
        end.update(best[1])
    W = intra = inter = byca = 0
    for i, n1 in enumerate(nets):
        for n2 in nets[i+1:]:
            if segx(F[n1], end[n1], F[n2], end[n2]):
                w = weight(n1, n2); W += w
                intra += w == 1; inter += w == 10; byca += w == 3
    L = sum(math.hypot(end[n][0]-F[n][0], end[n][1]-F[n][1]) for n in nets)
    return W, intra, inter, byca, L
# U801 body 10 x 15 mm; at rot 90/270 it is 15 wide, 10 tall; at 0/180 10 wide, 15 tall.
# free box north of U501 (board top 51.7, U501 top 71.5; keep a 3 mm corridor; x from the translators ~153 to J9 ~190)
res = []
for a in (0, 90, 180, 270):          # relative to the current -90 deg: absolute rotation = -90 + a
    w, h = (15, 10) if a in (0, 180) else (10, 15)
    for ox in np.arange(153 + w / 2, 190 - w / 2 + 0.01, 1.0):
        oy = 52.4 + h / 2
        if oy + h / 2 > 68.5: continue
        res.append((evaluate(a, ox, oy), a, ox, oy))
res.sort()
print("weighted, intra, inter-byte, byte-vs-CA, total length mm | absolute rotation, centre x, y")
for r in res[:10]: print(r[0][:4], round(r[0][4]), "|", -90 + r[1], round(float(r[2]), 1), round(r[3], 1))
print("best per rotation:")
for a in (0, 90, 180, 270):
    rr = [r for r in res if r[1] == a]
    if rr: r = rr[0]; print("  ", -90 + a, r[0][:4], round(r[0][4]), "x", round(float(r[2]), 1))
c = evaluate(0, cx, cy); print("CURRENT pose (-90 deg at", cx, cy, "):", c[:4], round(c[4]))
