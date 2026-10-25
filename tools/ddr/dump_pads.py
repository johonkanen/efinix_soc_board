import pcbnew, json
b = pcbnew.LoadBoard("/home/jari/dev/efinix_soc_board/kicad/ti135_card.kicad_pcb")
out = {}
for r in ("U501", "U801"):
    f = b.FindFootprintByReference(r); c = f.GetPosition()
    out[r] = {"centre": [c.x / 1e6, c.y / 1e6], "rot": f.GetOrientationDegrees(),
              "pads": [[p.GetNumber(), p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, p.GetNetname(), p.GetPinFunction()] for p in f.Pads()]}
json.dump(out, open("pads.json", "w"))
