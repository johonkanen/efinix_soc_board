"""Impedance cases for the JLC08161H-3313 stack-up (TI135_PCB_NOTES.md §6.5): python3 tools/zsolve_cases.py JOB,
JOB = outer | outer_nomask | L3 | L3_noL4 | L7cur | L4cur. Uses tools/zsolve.py."""
import sys
from zsolve import z_se, z_diff
H = 0.0025
TC_OUT, TC_IN = 0.035, 0.0152

def tr(ws, g, y0, y1):
    if g is None:
        return [(-ws / 2, ws / 2, y0, y1, 1.0)]
    c = g / 2 + ws / 2
    return [(-c - ws / 2, -c + ws / 2, y0, y1, 1.0), (c - ws / 2, c + ws / 2, y0, y1, -1.0)]

def outer(w, g=None, mask=True):
    hp = 0.0994; y0, y1 = hp, hp + TC_OUT
    t = tr(w, g, y0, y1)
    st = [(0, hp, 4.1)]
    if mask:
        st.append((hp, hp + 0.03, 3.8))
        for x0, x1, *_ in t:
            st.append((hp, y1 + 0.03, 3.8, x0 - 0.03, x1 + 0.03))
    return dict(stack=st, planes=[0], traces=t, top_open=True, width=3.0, h=H)

def strip_L3(w, g=None, l4_plane=True):
    # L2 plane at 0, core 0.1 (4.6), L3 trace on the core, prepreg 0.3568 (4.16) to L4
    t = tr(w, g, 0.1, 0.1 + TC_IN)
    if l4_plane:
        return dict(stack=[(0, 0.1, 4.6), (0.1, 0.4568, 4.16)], planes=[0, 0.4568], traces=t, top_open=False, width=3.0, h=H)
    top = 0.4568 + TC_IN + 0.3
    return dict(stack=[(0, 0.1, 4.6), (0.1, 0.4568 + TC_IN, 4.16), (0.4568 + TC_IN, top, 4.6)],
                planes=[0, top], traces=t, top_open=False, width=3.0, h=H)

def l7_current(w, g=None):
    # In6 (L7) as a signal layer: B.Cu poured plane 0.0994 below, L6 (signal) 0.1 core above, then L5 (In4) plane
    top = 0.0994 + 0.1 + TC_IN + 0.3568
    t = tr(w, g, 0.0994 - TC_IN, 0.0994)
    return dict(stack=[(0, 0.0994, 4.1), (0.0994, 0.1994, 4.6), (0.1994, top, 4.16)], planes=[0, top], traces=t,
                top_open=False, width=3.0, h=H)

def l4_current(w, g=None):
    # In3 (L4) as a signal layer: L5 (In4 plane) 0.3 core below, L3 (signal) 0.3568 prepreg above, L2 (In1 GND) beyond
    top = 0.3 + 0.3568 + TC_IN + 0.1
    t = tr(w, g, 0.3, 0.3 + TC_IN)
    return dict(stack=[(0, 0.3, 4.6), (0.3, 0.3 + 0.3568, 4.16), (0.3 + 0.3568, top, 4.6)], planes=[0, top],
                traces=t, top_open=False, width=3.0, h=H)

job = sys.argv[1]
rows = {
 "outer": [("SE", w, None) for w in (0.10, 0.12, 0.13, 0.15, 0.16)] + [("DIFF", 0.13, 0.25), ("DIFF", 0.12, 0.20), ("DIFF", 0.10, 0.20)],
 "inner": [("SE", w, None) for w in (0.09, 0.10, 0.11, 0.12, 0.13)] + [("DIFF", 0.11, 0.25), ("DIFF", 0.10, 0.20), ("DIFF", 0.09, 0.20)],
}
for kind, w, g in rows["outer" if job.startswith("outer") else "inner"]:
    f = {"outer": lambda w, g: outer(w, g), "outer_nomask": lambda w, g: outer(w, g, False),
         "L3": strip_L3, "L3_noL4": lambda w, g: strip_L3(w, g, False), "L7cur": l7_current, "L4cur": l4_current}[job]
    z, ee = (z_se if g is None else z_diff)(**f(w, g))
    print(f"{job:12} {kind:4} w={w:.2f}" + (f" gap={g:.2f}" if g else "         ") + f"  Z={z:6.1f} ohm  eeff={ee:.2f}", flush=True)
