#!/usr/bin/env python3
"""Stack-up, layer roles, net classes and DRC rules for kicad/ti135_card (run after tools/make_board.py).

- Stack-up: copied from the Agilex 5 card (JLC08161H-3313, 8 layers, 1.6 mm). Copper layer types are set here
  (LAYER_TYPES): the stack-up's thin 0.1 mm cores pair In2 with In1 and In5 with In6, so the controlled-impedance
  widths only hold with In1 / In6 as GND planes and In3 / In4 as planes. Signals go on F.Cu, In2, In5, B.Cu
  (field solve in TI135_PCB_NOTES.md §6.5).
- KiCad 10 time-domain tuning profiles (40 ohm SE / 80 ohm diff, per-layer delays from the field solve) on the
  LPDDR4 net classes, so the pcbnew tuners and length/skew DRC work in ps, die to die (U501 pad-to-die).
- Net classes (kicad/ti135_card.kicad_pro): the Agilex LPDDR4 classes with patterns for this board's net names
  (sheet 8: ddr_dq*, ddr_dm*, ddr_ca*, ddr_cke0, ddr_cs*_n, ddr_rst_n, ddr_dqs*_P/N, ddr_ck_P/N), plus power
  and RGMII classes.
- Design rules (kicad/ti135_card.kicad_dru): the Agilex LPDDR4 / JLC rules with U7 -> U501 (Ti135, 0.8 mm
  pitch: no sub-0.09 mm clearance exception needed) and U12 -> U801.
Plain python3 (s-expression edit of the saved board).
"""
import json
import re
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


# KiCad "power" = plane layer. F.Cu S | In1 GND | In2 S | In3 plane | In4 plane | In5 S | In6 GND | B.Cu S
LAYER_TYPES = {"F.Cu": "signal", "In1.Cu": "power", "In2.Cu": "signal", "In3.Cu": "power", "In4.Cu": "power",
               "In5.Cu": "signal", "In6.Cu": "power", "B.Cu": "signal"}


def stackup():
    agx, ours = load(AGX), load(PCB)
    for key in ("layers",):
        i = next(k for k, c in enumerate(ours) if isinstance(c, list) and c[0] == key)
        ours[i] = find(agx, key)
        for entry in ours[i][1:]:
            if isinstance(entry, list) and len(entry) > 2 and str(entry[1]) in LAYER_TYPES:
                entry[2] = type(entry[2])(LAYER_TYPES[str(entry[1])])
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
    # LPDDR4: Efinix Titanium DDR PCB guide targets 40 ohm SE / 80 ohm diff (TI135_PCB_NOTES.md §6.3, §6.5)
    ("lpddr_dq", 0.18, 0.1, 0.3, 0.15, 0.14, 0.15),
    ("lpddr_ca", 0.18, 0.1, 0.3, 0.15, 0.14, 0.15),
    ("lpddr_diff", 0.14, 0.1, 0.3, 0.15, 0.14, 0.15),
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


# KiCad 10 time-domain tuning profiles (Board Setup -> Tuning Profiles), assigned to the LPDDR4 net classes. Delays from
# the field solve (TI135_PCB_NOTES.md §6.5): microstrip with mask 6.11 ps/mm, In2/In5 stripline 7.01 ps/mm, the plane
# layers about 7.0, via 7.2 ps/mm of height. Widths are the 40 ohm SE / 80 ohm diff geometry (Efinix DDR PCB guide).
# Units: pcbIUScale.IU_PER_PS_PER_MM = 1e6 (6.11 ps/mm -> 6110000), lengths in nm.
LAYER_STACK = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "In5.Cu", "In6.Cu", "B.Cu"]
LAYER_DELAY = {"F.Cu": 6.11, "In1.Cu": 6.97, "In2.Cu": 7.01, "In3.Cu": 7.00, "In4.Cu": 7.00, "In5.Cu": 7.01,
               "In6.Cu": 6.97, "B.Cu": 6.11}
TUNING = {  # profile: (type 0 SE / 1 diff, target ohms, {outer|inner: (width mm, gap mm)}, net classes)
    "LPDDR4 SE 40R JLC08161H-3313": (0, 40.0, {"outer": (0.25, 0.0), "inner": (0.18, 0.0)}, ["lpddr_dq", "lpddr_ca"]),
    "LPDDR4 DIFF 80R JLC08161H-3313": (1, 80.0, {"outer": (0.20, 0.20), "inner": (0.14, 0.15)}, ["lpddr_diff"]),
}


def tuning_profiles():
    profiles = []
    for name, (kind, z, geo, _) in TUNING.items():
        entries = []
        for i, L in enumerate(LAYER_STACK):
            w, gap = geo["outer" if L in ("F.Cu", "B.Cu") else "inner"]
            entries.append({"signal_layer": L,
                            "top_reference_layer": LAYER_STACK[i - 1] if i > 0 else "UNDEFINED",
                            "bottom_reference_layer": LAYER_STACK[i + 1] if i < len(LAYER_STACK) - 1 else "UNDEFINED",
                            "width": int(round(w * 1e6)), "diff_pair_gap": int(round(gap * 1e6)),
                            "delay": int(round(LAYER_DELAY[L] * 1e6))})
        profiles.append({"profile_name": name, "type": kind, "target_impedance": z,
                         "enable_time_domain_tuning": True, "via_prop_delay": 7200000, "via_overrides": [],
                         "layer_entries": entries})
    return {"meta": {"version": 0}, "tuning_profiles_impedance_geometric": profiles}


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
    profile_of = {c: name for name, (_, _, _, cls) in TUNING.items() for c in cls}
    for c in classes:
        c["tuning_profile"] = profile_of.get(c["name"], "")
    ns["classes"] = classes
    pro["tuning_profiles"] = tuning_profiles()
    ns["netclass_patterns"] = [{"netclass": c, "pattern": p} for c, p in PATTERNS]
    sev = pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {})
    sev["missing_tuning_profile"] = "warning"
    sev["tuning_profile_track_geometries"] = "ignore"   # the 0.1 mm neck-down inside the BGAs differs from the profile
    # no reference-designator silkscreen on this card, only a few custom markings (user, 2026-10-26)
    for k in ("silk_overlap", "silk_over_copper", "silk_edge_clearance"):
        sev[k] = "ignore"
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
    # LPDDR4 widths: 40 ohm SE / 80 ohm diff (Efinix Titanium DDR PCB guide; field solve TI135_PCB_NOTES.md §6.5),
    # replacing the Agilex card's 50 / 100 ohm values
    widths = {
        "lpddr_se_outer": "(constraint track_width (min 0.23mm) (opt 0.25mm) (max 0.27mm)))",
        "lpddr_se_inner": "(constraint track_width (min 0.17mm) (opt 0.18mm) (max 0.19mm)))",
        "lpddr_diff_outer": "(constraint track_width (min 0.19mm) (opt 0.2mm) (max 0.21mm))\n\t(constraint diff_pair_gap (min 0.18mm) (opt 0.2mm) (max 0.22mm)))",
        "lpddr_diff_inner": "(constraint track_width (min 0.13mm) (opt 0.14mm) (max 0.15mm))\n\t(constraint diff_pair_gap (min 0.14mm) (opt 0.15mm) (max 0.17mm)))",
    }
    for name, body in widths.items():
        src, n = re.subn(r'(\(rule "%s"\n\t\(condition [^\n]*\n)(?:\t\(constraint [^\n]*\n?)+' % name,
                         lambda m: m.group(1) + "\t" + body.replace("\\n", "\n") + "\n", src)
        assert n == 1, name
    src = src.replace("DQS / CK pairs outside the BGAs: 100 ohm geometry per layer", "DQS / CK pairs outside the BGAs: 80 ohm geometry per layer")
    src = src.replace("# Stack-up: JLC08161H-3313.  50 ohm SE: 0.15 mm F/B.Cu, 0.12 mm inner.  100 ohm pair: 0.13/0.25 mm\n"
                      "# F/B.Cu, 0.11/0.25 mm inner.",
                      "# Stack-up: JLC08161H-3313.  Ti135 card: 40 ohm SE 0.25 mm F/B.Cu, 0.18 mm In2/In5;  80 ohm pair\n"
                      "# 0.20/0.20 mm F/B.Cu, 0.14/0.15 mm In2/In5 (Efinix DDR PCB guide; TI135_PCB_NOTES.md §6.5).")
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
