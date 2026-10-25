"""Pre-flip the parts that belong on B.Cu before placing (run under KiCad's python: kipy flip_bottom.py BOARD).
- the 90 BGA / LPDDR4 decaps (C509-C565, C803-C835), under their packages;
- the power supplies (5 x TLV62585 cells, J6 input caps), on the underside as on the Ti60 card (MECHANICAL.md:
  the 1.27 mm socket/header gap is about 5.3 mm). Their templates are fitted after the flip (prep.sh)."""
import sys

import pcbnew

DECAPS = [f"C{i}" for i in list(range(509, 566)) + list(range(803, 836))]
POWER = ["C101", "C102", "C103"]
for u, l, cin, couts, r1, r2 in (("U201", "L201", "C201", ["C202", "C203"], "R201", "R202"),
                                ("U301", "L301", "C301", ["C302", "C303"], "R301", "R302"),
                                ("U311", "L311", "C311", ["C312", "C313"], "R311", "R312"),
                                ("U331", "L331", "C331", ["C332"], "R331", "R332"),
                                ("U341", "L341", "C341", ["C342", "C343"], "R341", "R342")):
    POWER += [u, l, cin, r1, r2] + couts
b = pcbnew.LoadBoard(sys.argv[1])
n = 0
for fp in b.GetFootprints():
    if fp.GetReference() in set(DECAPS + POWER) and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        n += 1
pcbnew.SaveBoard(sys.argv[1], b)
print("flip_bottom: flipped", n)
