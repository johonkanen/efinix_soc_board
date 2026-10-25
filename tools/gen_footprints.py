#!/usr/bin/env python3
"""Project footprints written by script (lib/ti135_card.pretty).

RJ45_Hanrun_HR911130A_Horizontal: HanRun HR911130A 1x1 RJ45 with 10/100/1000 magnetics and 2 LEDs
(LCSC C54408), from the HanRun drawing (Rev A, page 2, "Component Side View / Mounting Pattern"):
  origin = midpoint of the two 3.25 mm locating pegs, local -y = toward the jack front (cable side),
  pegs 11.43 apart, LED pins (1.02 drill) 4.90 toward the front, shield pins (1.63 drill) 15.49 apart and
  3.05 behind the pegs, signal pins (0.89 drill) in two rows 6.35 / 8.89 behind the pegs:
  even pins 10..2 in the nearer row, odd pins 9..1 in the farther row, pin 1 at +x (seen from the top with
  the front up, pin 1 is on the right), pins 1.27 apart alternating rows, pin 5 at +0.635.
  Body 16.04 x 21.30: front edge 10.92 in front of the pegs, back edge 10.38 behind.
"""
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "lib", "ti135_card.pretty")


def hr911130a():
    pads = []
    # signal pins: odd at y = +8.89 (farther from the front), even at +6.35; pin n x = 5.715 - (n - 1) * 1.27
    for n in range(1, 11):
        x = round(5.715 - (n - 1) * 1.27, 3)
        y = 8.89 if n % 2 else 6.35
        shape = "roundrect" if n == 1 else "circle"
        pads.append((str(n), "thru_hole", shape, x, y, 1.5, 0.89))
    # LEDs 4.90 in front of the pegs (local -y): 14 / 13 on -x, 12 / 11 on +x (seen from the top, front up)
    for num, x in (("14", -6.625), ("13", -4.085), ("12", 4.085), ("11", 6.625)):
        pads.append((num, "thru_hole", "circle", x, -4.90, 1.6, 1.02))
    for x in (-7.745, 7.745):
        pads.append(("SH", "thru_hole", "circle", x, 3.05, 2.5, 1.63))
    for x in (-5.715, 5.715):
        pads.append(("", "np_thru_hole", "circle", x, 0.0, 3.25, 3.25))

    def pad(num, kind, shape, x, y, size, drill):
        uid = uuid.uuid5(uuid.NAMESPACE_URL, "HR911130A/%s/%s/%s" % (num, x, y))
        extra = "(roundrect_rratio 0.25) " if shape == "roundrect" else ""
        layers = '"*.Cu" "*.Mask"' if kind == "thru_hole" else '"*.Cu" "*.Mask"'
        return (f'\t(pad "{num}" {kind} {shape} (at {x} {y}) (size {size} {size}) (drill {drill}) '
                f'(layers {layers}) {extra}(uuid "{uid}"))')

    xl, xr, yf, yb = -8.02, 8.02, -10.92, 10.38

    def rect(layer, x1, y1, x2, y2, w):
        return "\n".join(f'\t(fp_line (start {a} {b}) (end {c} {d}) (stroke (width {w}) (type solid)) (layer "{layer}"))'
                         for a, b, c, d in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)))

    lines = [
        '(footprint "RJ45_Hanrun_HR911130A_Horizontal"',
        '\t(version 20241229)',
        '\t(generator "ti135_card_gen_footprints")',
        '\t(layer "F.Cu")',
        '\t(descr "HanRun HR911130A RJ45 8P8C with 10/100/1000Base-T magnetics and 2 LEDs, tab down, shielded, '
        'THT (LCSC C54408), from the HanRun drawing Rev A")',
        '\t(tags "RJ45 magjack gigabit HanRun")',
        '\t(property "Reference" "J**" (at 0 -12.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
        '\t(property "Value" "HR911130A" (at 0 12 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
        '\t(attr through_hole)',
        rect("F.Fab", xl, yf, xr, yb, 0.1),
        rect("F.SilkS", xl - 0.12, yf - 0.12, xr + 0.12, yb + 0.12, 0.12),
        rect("F.CrtYd", xl - 0.5, yf - 0.5, xr + 0.5, yb + 0.5, 0.05),
        f'\t(fp_line (start {xl} {yf + 0.8}) (end {xr} {yf + 0.8}) (stroke (width 0.1) (type dash)) (layer "F.Fab"))',
        '\t(fp_text user "front (cable)" (at 0 -9.6 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.1))))',
        '\t(fp_circle (center 5.715 10.4) (end 5.9 10.4) (stroke (width 0.2) (type solid)) (fill yes) (layer "F.SilkS"))',
    ]
    lines += [pad(*p) for p in pads]
    lines.append(")")
    return "RJ45_Hanrun_HR911130A_Horizontal", "\n".join(lines) + "\n"


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, text in (hr911130a(),):
        with open(os.path.join(OUT, name + ".kicad_mod"), "w") as f:
            f.write(text)
        print("wrote", name)


if __name__ == "__main__":
    sys.exit(main())
