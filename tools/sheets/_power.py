"""TLV62585PDRL buck block shared by the power sheets (POWER_BUDGET.md: one part for every rail).

    buck(sh, n, x, y, rail, r1, en=None, pg=None, couts=1)

n: sheet-local number for the refs (U<n>, L<n>, R<n>a/b, C<n>...) given as a 3-4 digit prefix base, e.g. 201.
rail: output power net; r1: top divider resistor (R2 = 100 k bottom, Vout = 0.6 V x (1 + R1/R2));
en: None = EN tied to 5V0, else a hierarchical label name; pg: hierarchical label name for the open-drain PG output (None = no connect).
Cin 10 u 0805, L 1 uH 4x4 mm, Cout 22 u 0805 (couts of them), PWR_FLAG on the output.
"""
from _common import *  # noqa: F401,F403

L_PART = {"MPN": "WPN4020H1R0MT", "LCSC": "C98359"}   # 1 uH 4x4 mm; check Isat >= 4 A (TLV62585 limit)
U_PART = {"LCSC": "C485118"}


def buck(sh, refs, x, y, rail, r1, en=None, pg=None, couts=1, title=None):
    """refs: dict with keys U, L, R1, R2, CIN, COUT (list). Returns the output node."""
    u = sh.place("TLV62585PDRL", refs["U"], x, y, value="TLV62585PDRLR", fields=U_PART)
    vin, en_p, gnd = u.pin(3), u.pin(4), u.pin(1)
    sw, fb, pgp = u.pin(2), u.pin(5), u.pin(6)
    if title:
        sh.text(title, x - g(16), y - g(9))
    # input: 5V0 + Cin
    n_in = left(vin, 8)
    sh.wire(vin, n_in)
    power_at(sh, "5V0", up(n_in, 2), "up"); sh.wire(n_in, up(n_in, 2))
    _, ct, cb = vert2(sh, "C", refs["CIN"], n_in[0] - g(4), n_in[1] + g(5), "10u", text="left")
    sh.wire(n_in, (ct[0], n_in[1]), ct); sh.junction(*n_in)
    sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
    set_field(sh, refs["CIN"], "Footprint", C0805)
    # enable
    if en is None:
        sh.wire(en_p, (n_in[0], en_p[1]), n_in)
    else:
        hlabel_left(sh, en, en_p, 3, "passive")
    sh.wire(gnd, down(gnd, 2)); power_at(sh, "GND", down(gnd, 2), "down")
    # SW -> L -> output
    _, la, lb = horiz2(sh, "L_Power", refs["L"], sw[0] + g(9), sw[1], "1u", text="above", fields=L_PART)
    sh.wire(sw, la)
    out = right(lb, 6)
    sh.wire(lb, out)
    # divider: R1 from the output down to the FB node, R2 to GND
    xr = out[0] + g(6)
    _, r1t, r1b = vert2(sh, "R", refs["R1"], xr, out[1] + g(5), r1, text="right")
    sh.wire(out, (xr, out[1]), r1t)
    mid = down(r1b, 1)
    sh.wire(r1b, mid)
    _, r2t, r2b = vert2(sh, "R", refs["R2"], xr, mid[1] + g(4), "100k", text="right")
    sh.wire(mid, r2t); sh.junction(*mid)
    sh.wire(r2b, down(r2b, 2)); power_at(sh, "GND", down(r2b, 2), "down")
    xf = out[0] - g(1)
    sh.wire(fb, (xf, fb[1]), (xf, mid[1]), mid)
    # PG
    if pg:
        hlabel_right(sh, pg, pgp, 3, "passive")
    else:
        sh.no_connect(*pgp)
    # output caps, rail symbol, PWR_FLAG
    xo = xr + g(14)
    sh.wire((xr, out[1]), (xo + g(8) * (couts - 1), out[1]))
    sh.junction(xr, out[1])
    for k, cref in enumerate(refs["COUT"][:couts]):
        cx = xo + g(8) * k
        _, ct, cb = vert2(sh, "C", cref, cx, out[1] + g(5), "22u", text="right")
        sh.wire((cx, out[1]), ct)
        if k < couts - 1 or True:
            sh.junction(cx, out[1]) if cx != xo + g(8) * (couts - 1) else None
        sh.wire(cb, down(cb, 2)); power_at(sh, "GND", down(cb, 2), "down")
        set_field(sh, cref, "Footprint", C0805)
    pr = up(out, 3)
    sh.wire(out, pr); sh.junction(*out)
    power_at(sh, rail, pr, "up")
    sh.wire(pr, right(pr, 3)); sh.pwr_flag(*right(pr, 3), 270)
    return out
