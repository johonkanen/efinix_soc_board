#!/usr/bin/env python3
"""Delete parts from sheet 05 and the board (user, 2026-11-16: the PLL filter parts that found no room at the balls):
    source tools/p2k/bin/kicad_env.sh; python3 tools/pi_delete_parts.py C502 C508 C5073 C5060
The symbols go, then every wire that kicad-cli's ERC reports with an unconnected end, until none is left (this
also clears the stubs left where C5061-C5063 were deleted by hand). The footprints go from the board with the
tracks that only led to them in a second step: tools/p2k/bin/kipy tools/pi_fixes.py BOARD BOARD drop.
A GND symbol left alone on a stub (as under C502 and C508) has to be deleted by hand; ERC then shows the stub."""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCH = os.path.join(ROOT, "kicad", "05_fpga_power.kicad_sch")
refs = sys.argv[1:]
t = open(SCH).read()
for ref in refs:
    m = re.search(rf'^\t\t\(property "Reference" "{re.escape(ref)}"$', t, re.M)
    if not m:
        print(ref, "is not in the schematic"); continue
    a = t.rfind("\n\t(symbol\n", 0, m.start()) + 1; e = t.index("\n\t)\n", m.start()) + 4
    t = t[:a] + t[e:]; print("05_fpga_power:", ref, "deleted")
open(SCH, "w").write(t)
WIRE = re.compile(r'\t\(wire\n\t\t\(pts\n\t\t\t\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)\n\t\t\)\n(?:.*\n)*?\t\)\n')
def erc():
    out = os.path.join(tempfile.gettempdir(), "pi_delete_erc.json")
    subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", out,
                    os.path.join(ROOT, "kicad", "ti135_card.kicad_sch")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    v = [x for s in json.load(open(out))["sheets"] for x in s["violations"]]
    loose = [(round(x["items"][0]["pos"]["x"], 2), round(x["items"][0]["pos"]["y"], 2)) for x in v if x["type"] == "unconnected_wire_endpoint"]
    return loose, len([x for x in v if x["type"] != "unconnected_wire_endpoint"])


# ERC names a point of a wire with a loose end, not the wire: try each wire at that point, one at a time, and keep
# the deletion only if no other ERC item (an unconnected pin, a dangling label) appears
n = 0; loose, base = erc(); refused = set()
while loose:
    t = open(SCH).read(); done = False
    for m in WIRE.finditer(t):
        x1, y1, x2, y2 = (round(float(g), 2) for g in m.groups())
        if (x1, y1, x2, y2) in refused or not ((x1, y1) in loose or (x2, y2) in loose):
            continue
        open(SCH, "w").write(t[:m.start()] + t[m.end():])
        l2, other = erc()
        if other > base:
            open(SCH, "w").write(t); refused.add((x1, y1, x2, y2))
        else:
            loose = l2; n += 1; done = True
        break
    else:
        print("loose wire ends left on sheet 05:", loose); break
print("05_fpga_power:", n, "dangling wires removed")
