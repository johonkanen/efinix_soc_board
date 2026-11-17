#!/usr/bin/env python3
"""Move FPGA signals to other balls (user, 2026-11-17: the FPGA allows it, choose the assignment that routes simply):
    python3 tools/io_swap.py                               schematic sheet 11, pin plan CSV, pinplan.py
    tools/p2k/bin/kipy tools/io_swap.py IN.kicad_pcb OUT.kicad_pcb     board: U501 pad nets, old routes ripped up
MOVES maps signal -> new ball. It must be a permutation of balls that carry a signal today (a move to an unused ball
would also need the no-connect flag taken off and a label added in sheet 11: not handled here).
The 3.3 V group (banks BL3, BR0, TR1; 20 signals to J3 in the west, J5 in the south and the UART) was assigned by a
search that minimises crossings of the straight lines ball -> far end: 45 crossings before, 2 after; with J5
turned 78 before and 2 after. The four
signals that go west to J3 (mdata_inu, mdata_dab, mdata_iso, sdata1_iso) keep their balls: moving them made
their routes longer. Route the moved nets afterwards with the router (tools/rgmii_tx.py has the command line;
--layer-costs 2 -1 1 -1 -1 1 -1 2), then refill the zones."""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# second assignment, for the LCD header J5 turned 180 degrees (pin 1 east, 3V3 at the west end as on the Agilex card).
# The first one (2026-11-17, header not yet turned) was: t_irq M22, t_do L22, t_din L21, t_cs_n H9, t_clk H8,
# lcd_mosi K7, lcd_led H7, uart_rx G6, uart_tx J6, lcd_sck H6, lcd_miso K6, lcd_dc F5, lcd_reset_n H5, lcd_cs_n F4,
# led1_n M8, led0_n L8.
MOVES = {"lcd_cs_n": "L22", "lcd_reset_n": "L21", "lcd_dc": "H9", "lcd_miso": "L8", "lcd_sck": "H8", "uart_rx": "K7",
         "uart_tx": "G6", "lcd_mosi": "H6", "t_clk": "J6", "t_cs_n": "F5", "t_din": "H5", "t_do": "F4", "t_irq": "K6",
         "led0_n": "M22"}
CSV = os.path.join(ROOT, "efinity", "pinplan", "ti135_pinplan.csv")
rows = list(csv.DictReader(open(CSV)))
ball_of = {r["signal"]: r["ball"] for r in rows}
old_sig = {r["ball"]: r["signal"] for r in rows}
assert sorted(MOVES.values()) == sorted(ball_of[s] for s in MOVES), "MOVES is not a permutation of used balls"
new_sig = {ball: s for s, ball in MOVES.items()}            # ball -> the signal it gets

if len(sys.argv) == 1:
    pins = {r["ball"]: r for r in csv.DictReader(open(os.path.join(ROOT, "reference", "ti135n484_pinout.csv")))}
    p = os.path.join(ROOT, "kicad", "11_fpga_io.kicad_sch"); t = open(p).read()
    lab = {m.group(1): m for m in re.finditer(r'\t\(hierarchical_label "([^"]+)"\n\t\t\(shape (\w+)\)', t)}
    shape = {s: lab[s].group(2) for s in MOVES}
    edits = []
    for ball, s in new_sig.items():                         # the label at this ball is the one named after its old signal
        m = lab[old_sig[ball]]
        edits.append((m.start(), m.end(), f'\t(hierarchical_label "{s}"\n\t\t(shape {shape[s]})'))
    for a, e, new in sorted(edits, reverse=True):
        t = t[:a] + new + t[e:]
    open(p, "w").write(t)
    for r in rows:
        if r["signal"] in MOVES:
            b_ = MOVES[r["signal"]]; r["ball"] = b_; r["pad"] = pins[b_]["pad"]; r["bank"] = pins[b_]["bank"]
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\r\n"); w.writeheader(); w.writerows(rows)
    pp = os.path.join(ROOT, "efinity", "pinplan", "pinplan.py"); s = open(pp).read(); n = 0
    for sig, b_ in MOVES.items():
        s, k = re.subn(rf'(\("{sig}", "\w+", ")[^"]+(")', rf"\g<1>{pins[b_]['pad']}\g<2>", s, count=1); n += k
    open(pp, "w").write(s)
    print(f"io_swap: {len(MOVES)} signals moved in sheet 11 and the pin plan CSV; {n} lines of pinplan.py updated")
else:
    import pcbnew
    b = pcbnew.LoadBoard(sys.argv[1]); u = b.FindFootprintByReference("U501")
    full = {}                                               # signal -> full net name on the board (from U501's pads)
    for p in u.Pads():
        base = p.GetNetname().split("/")[-1]
        if base in MOVES:
            full[base] = p.GetNetname()
    assert len(full) == len(MOVES), sorted(set(MOVES) - set(full))
    todo = [p for p in u.Pads() if p.GetNumber() in new_sig and p.GetNetname() != full[new_sig[p.GetNumber()]]]
    ripped = 0
    if todo:
        for s in MOVES:
            for t in list(b.GetTracks()):
                if t.GetNetname() == full[s]:
                    b.Delete(t); ripped += 1
        for p in u.Pads():
            if p.GetNumber() in new_sig:
                p.SetNet(b.FindNet(full[new_sig[p.GetNumber()]]))
    zs = b.Zones(); pcbnew.ZONE_FILLER(b).Fill(zs)
    b.Save(sys.argv[2])
    print(f"io_swap: U501 pads re-assigned for {len(MOVES)} signals, {ripped} tracks and vias of their old routes removed")
