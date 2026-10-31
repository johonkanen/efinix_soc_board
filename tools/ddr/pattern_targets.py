#!/usr/bin/env python3
"""Give the tuning patterns of the shared CA/CK nets their path target as an override:
    python3 tools/ddr/pattern_targets.py BOARD TARGETS.json      (from ddr_timing.py --kicad ... --patterns)

pcbnew's tuner reads the pad-to-pad path, DRC the whole net. On a shared net (U501 -> T -> both U801 channels) the
DRC rule (tools/ddr/delay_rules.sh) is the path target plus the net's second branch, so the tuner would aim one branch
too long. Each pattern on such a net gets override_custom_rules yes and target_delay min/opt/max = the path target, so
the tuner and DRC agree. Edits the board text in place: close the board in pcbnew first.
"""
import json
import re
import sys

board, targets = sys.argv[1], json.load(open(sys.argv[2]))
s = open(board).read()
out, n, pos = [], 0, 0
for m in re.finditer(r"\n\t\(generated\n", s):
    start = m.start()
    end = s.find("\n\t)", start + 1) + 3
    blk = s[start:end]
    net = re.search(r'\(last_netname "([^"]*)"\)', blk)
    if ("(type tuning_pattern)" not in blk or '(tuning_mode "diff_pair_skew")' in blk or not net
            or net.group(1) not in targets):
        continue
    lo, opt, hi = targets[net.group(1)]
    new = re.sub(r"\(override_custom_rules \w+\)", "(override_custom_rules yes)", blk)
    for key, v in (("target_delay", opt), ("target_delay_min", lo), ("target_delay_max", hi)):
        new = re.sub(rf"\({key} [-0-9.e]+\)", f"({key} {v})", new)
    out.append(s[pos:start] + new)
    pos = end
    n += 1
    print(f"{net.group(1).split('/')[-1]:10} {lo} / {opt} / {hi} ps")
out.append(s[pos:])
open(board, "w").write("".join(out))
print(f"{n} tuning patterns set")
