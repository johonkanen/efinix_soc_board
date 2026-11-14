#!/usr/bin/env python3
"""eMMC delay matching as DRC length rules, for meandering by hand in pcbnew (user request 2026-11-13):
    python3 tools/emmc_delay_rules.py [--tol PS] [--target PS]      (kicad-cli on PATH: source tools/p2k/bin/kicad_env.sh)

The eMMC signals were routed without matching: CLK, CMD, DAT0-7 and DS differ by up to about 190 ps, FPGA ball to
eMMC ball. Each signal is two nets, split by its series resistor: /emmc_x (U501 -> R) and /10 emmc/emmc_x_r (R -> U1001).
This script
  1. gives those 22 nets the net class `emmc` with the single-ended tuning profile, so KiCad measures them in
     picoseconds (layer delays, via height, U501 pad-to-die), like the LPDDR4 nets;
  2. asks KiCad for each net's delay (a probe rule on a temporary copy);
  3. takes the longest signal as the target and writes one length rule per signal on its eMMC-side net (`_r`):
     opt = target - (delay of the FPGA-side net), min / max = opt -/+ tol (default 10 ps, about 1.5 mm).
The rules go between markers at the end of kicad/ti135_card.kicad_dru. Meander the `_r` nets with the length tuner
until DRC stops reporting length_out_of_range. Rerun this script after re-routing an FPGA-side net or the longest
signal: the targets are absolute. The resistor itself counts as zero delay on every signal.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRO = os.path.join(ROOT, "kicad", "ti135_card.kicad_pro")
DRU = os.path.join(ROOT, "kicad", "ti135_card.kicad_dru")
PCB = os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb")
PATTERN = r".*emmc_(clk|cmd|dat[0-7]|ds)(_r)?$"
PROFILE = "LPDDR4 SE 40R JLC08161H-3313"
SIGS = ["clk", "cmd"] + [f"dat{i}" for i in range(8)] + ["ds"]
BEGIN = "# ---- BEGIN generated eMMC delay targets (tools/emmc_delay_rules.py; do not edit by hand) ----"
END = "# ---- END generated eMMC delay targets ----"
tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 10.0

pro = json.load(open(PRO))
ns = pro["net_settings"]
if not any(c["name"] == "emmc" for c in ns["classes"]):
    c = dict(next(c for c in ns["classes"] if c["name"] == "Default"))
    c.update(name="emmc", priority=len(ns["classes"]) - 1, tuning_profile=PROFILE)
    ns["classes"].append(c)
    ns["netclass_patterns"].append({"netclass": "emmc", "pattern": PATTERN})
    json.dump(pro, open(PRO, "w"), indent=2); open(PRO, "a").write("\n")
    print("net class emmc added to the project (Default geometry, profile", PROFILE + ")")

w = tempfile.mkdtemp()
for ext in ("kicad_pcb", "kicad_pro", "kicad_dru"):
    shutil.copy(os.path.join(ROOT, "kicad", "ti135_card." + ext), os.path.join(w, "p." + ext))
s = open(os.path.join(w, "p.kicad_dru")).read()
if BEGIN in s:
    s = s[:s.index(BEGIN)] + s[s.index(END) + len(END):]
s += '\n(rule "probe_emmc"\n\t(condition "A.hasNetclass(\'emmc\')")\n\t(constraint length (min 1ps) (max 2ps)))\n'
open(os.path.join(w, "p.kicad_dru"), "w").write(s)
subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "-o", os.path.join(w, "p.rpt"), os.path.join(w, "p.kicad_pcb")],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
d = {}
for it in re.split(r"\n(?=\[)", open(os.path.join(w, "p.rpt")).read()):
    if it.startswith("[length_out_of_range]") and "probe_emmc" in it:
        a = re.search(r"actual ([0-9.]+) ps", it); n = re.search(r"\[([^\]]*emmc_[^\]]*)\]", it)
        if a and n:
            d[n.group(1)] = float(a.group(1))
shutil.rmtree(w)
assert len(d) == 2 * len(SIGS), sorted(d)
fp = {x: d[f"/emmc_{x}"] for x in SIGS}
em = {x: d[f"/10 emmc/emmc_{x}_r"] for x in SIGS}
tot = {x: fp[x] + em[x] for x in SIGS}
ref = max(tot, key=tot.get); T = tot[ref]
why = f"the longest signal, {ref}"
if "--target" in sys.argv:  # e.g. the middle of the already tuned signals, so none of them needs touching
    T = float(sys.argv[sys.argv.index("--target") + 1]); why = "given with --target"
rules = ""
print(f"target {T:.1f} ps ({why}); tolerance +-{tol:g} ps")
print("signal   FPGA side   eMMC side    total   to add   rule on the eMMC-side net (min / opt / max ps)")
for x in SIGS:
    opt = T - fp[x]
    rules += (f'(rule "emmc_delay_{x}"\n\t(condition "A.NetName == \'/10 emmc/emmc_{x}_r\'")\n'
              f"\t(constraint length (min {opt - tol:.1f}ps) (opt {opt:.1f}ps) (max {opt + tol:.1f}ps)))\n")
    print(f"{x:6s} {fp[x]:9.1f} {em[x]:11.1f} {tot[x]:9.1f} {T - tot[x]:8.1f}   {opt - tol:.1f} / {opt:.1f} / {opt + tol:.1f}")
s = open(DRU).read()
if BEGIN in s:
    s = s[:s.index(BEGIN)].rstrip("\n") + "\n" + s[s.index(END) + len(END):].lstrip("\n")
head = (f"# eMMC: every signal (FPGA ball -> series resistor -> eMMC ball) to {T:.1f} ps +-{tol:g} ({why}), by\n"
        "# meandering the eMMC-side net. opt = target - delay of the FPGA-side net as routed when this was generated.\n")
open(DRU, "w").write(s.rstrip("\n") + "\n\n" + BEGIN + "\n" + head + rules + END + "\n")
