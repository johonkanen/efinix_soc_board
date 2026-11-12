#!/usr/bin/env python3
"""PHY passives placed as on the Agilex card (tools/p2k/bin/kipy tools/eth_place.py IN.kicad_pcb OUT.kicad_pcb).

Run after tools/swap_footprint.py has made these parts 0201 (the Agilex card's size; 0402 does not fit its 0.7 mm
pitch). Each part takes the position, side and rotation of its Agilex counterpart by function, relative to the PHY
(U901 here, U10 there; both at 180 deg). ~/dev/agilex3_soc_control_card is read only.
- RX series R907-R912 (pins 27, 26, 25..22), bypass caps of phy_vdd10 / phy_avdd33 / phy_dvdd_rg / 3V3, and the
  strap resistors R920-R925. Pad 1 / pad 2 carry the same functions on both cards, so the rotation is copied as is.
  Our straps hang on the PHY side of the series resistor, the Agilex ones on the MAC side; the spots are the same.
- C940 (1u on pin 29) has no Agilex counterpart: it goes beside C941, 0.7 mm further from the PHY.
- C920 (10u 0805; the Agilex card has a 0402 there) moves 0.7 mm north to clear C921. The TX resistors R901-R906
  stay. The LCSC field follows the 0201 part.
"""
import os
import sys

import pcbnew

AGILEX = os.path.expanduser("~/dev/agilex3_soc_control_card/agilex_3_soc.kicad_pcb")
MAP = {"R912": "R261", "R911": "R260", "R910": "R259", "R909": "R258", "R908": "R257", "R907": "R262",
       "C930": "C21", "C931": "C23", "C934": "C22", "C933": "C30", "C932": "C28",
       "C921": "C25", "C922": "C29", "C936": "C257", "C935": "C258", "C941": "C26",
       "R920": "R32", "R923": "R269", "R924": "R270", "R925": "R39", "R922": "R31", "R921": "R33"}
EXTRA = {"C940": ("C26", -0.7, 0.0)}          # beside its counterpart, offset in mm
LCSC = {"22R": "C155743", "4k7": "C270346", "1u": "C272877", "100n": "C190183"}   # as the Agilex card
mm = pcbnew.FromMM
b, a = pcbnew.LoadBoard(sys.argv[1]), pcbnew.LoadBoard(AGILEX)
u, u10 = b.FindFootprintByReference("U901"), a.FindFootprintByReference("U10")
assert u.GetOrientationDegrees() == u10.GetOrientationDegrees()
off = u.GetPosition() - u10.GetPosition()
for ref, (src, dx, dy) in {**{k: (v, 0, 0) for k, v in MAP.items()}, **EXTRA}.items():
    f, s = b.FindFootprintByReference(ref), a.FindFootprintByReference(src)
    assert "0201" in str(f.GetFPID().GetLibItemName()), f"{ref} is not 0201: run swap_footprint.py first"
    assert f.GetValue().lower() == s.GetValue().lower() or ref in EXTRA, (ref, f.GetValue(), src, s.GetValue())
    if f.IsFlipped() != s.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientation(s.GetOrientation())
    f.SetPosition(s.GetPosition() + off + pcbnew.VECTOR2I(mm(dx), mm(dy)))
    f.SetField("LCSC", LCSC[f.GetValue()])
c920 = b.FindFootprintByReference("C920")
c920.SetPosition(c920.GetPosition() + pcbnew.VECTOR2I(0, mm(-0.7)))
print(f"eth_place: {len(MAP) + len(EXTRA)} parts placed from the Agilex card")
b.Save(sys.argv[2])
