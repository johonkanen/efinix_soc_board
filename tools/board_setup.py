#!/usr/bin/env python3
"""Stack-up, layer roles, net classes and DRC rules for kicad/ti135_card (run after tools/make_board.py).

- Stack-up and copper layer types: copied from the Agilex 5 card (JLC08161H-3313, 8 layers, 1.6 mm).
- Net classes (kicad/ti135_card.kicad_pro): the Agilex LPDDR4 classes with patterns for this board's net names
  (sheet 8: ddr_dq*, ddr_dm*, ddr_ca*, ddr_cke0, ddr_cs*_n, ddr_rst_n, ddr_dqs*_P/N, ddr_ck_P/N), plus power
  and RGMII classes.
- Design rules (kicad/ti135_card.kicad_dru): the Agilex LPDDR4 / JLC rules with U7 -> U501 (Ti135, 0.8 mm
  pitch: no sub-0.09 mm clearance exception needed) and U12 -> U801.
Plain python3 (s-expression edit of the saved board).
"""
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "p2k"))
from p2k.sexpr import find, find_all, load, save  # noqa: E402

AGX = os.path.expanduser("~/dev/agilex3_soc_control_card/agilex_3_soc.kicad_pcb")
PCB = os.path.join(ROOT, "kicad", "ti135_card.kicad_pcb")
PRO = os.path.join(ROOT, "kicad", "ti135_card.kicad_pro")
DRU = os.path.join(ROOT, "kicad", "ti135_card.kicad_dru")


def stackup():
    agx, ours = load(AGX), load(PCB)
    for key in ("layers",):
        i = next(k for k, c in enumerate(ours) if isinstance(c, list) and c[0] == key)
        ours[i] = find(agx, key)
    setup_ours, setup_agx = find(ours, "setup"), find(agx, "setup")
    st = find(setup_agx, "stackup")
    old = find(setup_ours, "stackup")
    if old is not None:
        setup_ours[setup_ours.index(old)] = st
    else:
        setup_ours.insert(1, st)
    save(PCB, ours)


NETCLASSES = [
    # name, track, clearance, via, via drill, diff width, diff gap
    ("Default", 0.1, 0.1, 0.3, 0.15, 0.1, 0.2),
    ("lpddr_dq", 0.12, 0.1, 0.3, 0.15, 0.1, 0.2),
    ("lpddr_ca", 0.12, 0.1, 0.3, 0.15, 0.1, 0.2),
    ("lpddr_diff", 0.12, 0.1, 0.3, 0.15, 0.11, 0.25),
    ("rgmii", 0.12, 0.1, 0.3, 0.15, 0.1, 0.2),
    ("PWR", 0.3, 0.1, 0.45, 0.25, 0.1, 0.2),
    ("PWR_CORE", 0.5, 0.1, 0.45, 0.25, 0.1, 0.2),
]
PATTERNS = [
    ("lpddr_dq", r".*ddr_dq([0-9]|[12][0-9]|3[01])$"),
    ("lpddr_dq", r".*ddr_dm[0-3]$"),
    ("lpddr_ca", r".*ddr_(ca[0-5]|cke0|cs[02]_n|rst_n)$"),
    ("lpddr_diff", r".*ddr_(dqs[0-3]|ck)_[PN]$"),
    ("rgmii", r".*(rgmii|phy)_(txc|tx_ctl|txd[0-3]|rxc|rx_ctl|rxd[0-3])$"),
    ("PWR", r"^(5V0|1V8|3V3|1V1|0V85|3V3_analog|phy_vdd10)$"),
    ("PWR_CORE", r"^VCORE$"),
]


def netclasses():
    pro = json.load(open(PRO))
    ns = pro.setdefault("net_settings", {})
    tmpl = (ns.get("classes") or [{}])[0]
    classes = []
    for name, tw, cl, via, drill, dpw, dpg in NETCLASSES:
        c = dict(tmpl)
        c.update({"name": name, "track_width": tw, "clearance": cl, "via_diameter": via, "via_drill": drill,
                  "diff_pair_width": dpw, "diff_pair_gap": dpg, "microvia_diameter": 0.2, "microvia_drill": 0.1,
                  "priority": len(classes) if name != "Default" else 2147483647})
        classes.append(c)
    ns["classes"] = classes
    ns["netclass_patterns"] = [{"netclass": c, "pattern": p} for c, p in PATTERNS]
    rules = pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    rules.update({"min_clearance": 0.09, "min_track_width": 0.09, "min_via_diameter": 0.25,
                  "min_via_annular_width": 0.05, "min_through_hole_diameter": 0.15, "min_hole_clearance": 0.175,
                  "min_hole_to_hole": 0.2, "min_copper_edge_clearance": 0.5, "min_silk_clearance": 0.15,
                  "min_text_height": 1.0, "min_text_thickness": 0.15, "use_height_for_length_calcs": True})
    json.dump(pro, open(PRO, "w"), indent=2)


def dru():
    src = open(os.path.splitext(AGX)[0] + ".kicad_dru").read()
    a = src.index('(rule "lpddr_bga_clearance"')
    b = src.index('(rule "lpddr_bga_clearance_u12"')
    src = src[:a] + src[b:]              # the 0.075 mm U7 exception: not needed at the Ti135's 0.8 mm pitch
    src = src.replace("'U7'", "'U501'").replace("'U12'", "'U801'").replace("clearance_u12", "clearance_u801")
    head = ("# Ti135 control card DRC rules: the Agilex 5 card's LPDDR4 / JLCPCB rules (tools/board_setup.py),\n"
            "# U7 -> U501 (Ti135N484, 0.8 mm pitch, no sub-0.09 mm exception), U12 -> U801 (LPDDR4).\n")
    lines = src.split("\n")
    out = [lines[0], head.rstrip("\n")] + lines[1:]
    out += ["",
            "# J3 corner pins 37/38: the hole positions come from the Ti60 card / baseboard (MECHANICAL.md) and sit",
            "# 0.89 mm from the top edge, so their pads are 0.39 mm from it. JLC's routed-edge minimum is 0.3 mm.",
            '(rule "j3_baseboard_edge"',
            "\t(condition \"A.memberOfFootprint('J3')\")",
            "\t(constraint edge_clearance (min 0.3mm)))", ""]
    open(DRU, "w").write("\n".join(out))


if __name__ == "__main__":
    stackup()
    netclasses()
    dru()
    print("board_setup: stack-up + layer roles (Agilex JLC08161H-3313), net classes, DRC rules written")
