#!/usr/bin/env python3
"""Summarise a kicad-cli DRC JSON report, optionally against an earlier one: drc_summary.py NEW [OLD]"""
import sys, json, re, collections, os


def load(p):
    d = json.load(open(p))
    c = collections.Counter()
    for v in d.get("violations", []):
        c[(v["severity"], v["type"])] += 1
    c[("error", "unconnected_items")] = len(d.get("unconnected_items", []))
    c[("error", "schematic_parity")] = len(d.get("schematic_parity", []))
    return d, c


new, cn = load(sys.argv[1])
co = load(sys.argv[2])[1] if len(sys.argv) > 2 and os.path.exists(sys.argv[2]) else None
for k in sorted(set(cn) | set(co or {}), key=lambda k: (k[0], k[1])):
    was = f"  (was {co[k]})" if co is not None and co[k] != cn[k] else ""
    print(f"  {k[0]:8s}{k[1]:24s}{cn[k]:5d}{was}")
errs = sum(n for (s, t), n in cn.items() if s == "error" and t not in ("unconnected_items",))
print(f"  errors excluding unconnected: {errs}; unconnected: {cn[('error', 'unconnected_items')]}")
if "-v" in sys.argv:
    for v in new["violations"]:
        if v["severity"] == "error":
            print("   ", v["type"], "|", " || ".join(i["description"] for i in v["items"]))
