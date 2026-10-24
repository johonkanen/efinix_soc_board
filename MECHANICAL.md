# Mechanical reference: outline and baseboard connectors

The card plugs into the AC PSU baseboard (`~/dev/ac_psu_kicad`, J11 and J12) the same way as the working Ti60F225
card. **The outline, J3 (signals), J6 (5 V) and the RJ45 J9 are hard requirements.** Everything here is taken
from the Ti60 card's fab data:

- `ti60f225_psu_control_card - CADCAM.ZIP` (Proteus, exported 2026-10-24)
- IPC-D-356 netlist for the hole centres
- `Mechanical 1` for the outline
- `Top Assembly` for the jack body

## Coordinate frames

- **Ti60 frame:** Proteus Gerber/IPC coordinates in mm, Y up.
- **KiCad frame** of this project: `x_kicad = X_ti60 + 100`, `y_kicad = 100 − Y_ti60` (Y down). Put the
  board's aux origin at KiCad (100, 100) so that Gerbers exported with the aux origin land on the Ti60 coordinates.

## Outline

Rectangle with square corners, 76.000 × 65.127 mm. Values are Gerber line centres (0.2032 mm aperture):

| | Ti60 frame | KiCad frame |
|---|---|---|
| left / right | X 31.531 / 107.531 | x 131.531 / 207.531 |
| bottom / top | Y −16.821 / 48.306 | y 116.821 / 51.694 |

The Agilex 5 card has the same size (76.000 × 65.125).

## J3: 2×19 1.27 mm socket on the bottom (baseboard J11)

- **Numbering:** J3 pin n = baseboard J11 pin n. Signals are in `reference/baseboard_j11_pinout.csv`.
- **Hole positions:** the hole for baseboard pin n is the Ti60 J11 hole of Ti60 pin n+1 (n odd) or n−1 (n even).
  Ti60 J11 holes: odd pins at X 33.832, even pins at X 35.102, Y = 24.555 + 1.27·⌊(p−1)/2⌋.

| J3 pin | Ti60 frame | KiCad frame |
|---|---|---|
| 1 | (35.102, 24.555) | (135.102, 75.445) |
| 2 | (33.832, 24.555) | (133.832, 75.445) |
| 37 | (35.102, 47.415) | (135.102, 52.585) |
| 38 | (33.832, 47.415) | (133.832, 52.585) |

Seen from the top: pin 2 is left of pin 1 and pin 37 is above pin 1. With the KiCad library footprint
`Connector_PinSocket_1.27mm:PinSocket_2x19_P1.27mm_Vertical` this is **B.Cu, orientation 180°, at the pin 1
position**. The Agilex 5 card (after its 2026-10-24 change) is the same within 0.03 mm.

## J6: 2×3 1.27 mm on the bottom (baseboard J12, 5 V supply)

- **Frame:** the baseboard and card frames differ by a pure translation, Ti60 = baseboard IPC + (−11.068, +1.945).
  It comes from J11 (baseboard J11.1 at IPC (46.17, 22.61) meets the Ti60 hole (35.102, 24.555)), and J12 checks out
  with it.
- **Nets (baseboard numbering):** baseboard J12 43/45/47 = ISOGND (row at Ti60 Y −13.754), 44/46/48 = 5V_ISOL (row at
  Ti60 Y −15.024). On the Ti60 card those rows are its own pins 44/46/48 = GND and 43/45/47 = 5 V, which is consistent.
- **Numbering:** J6 pin n = baseboard pin 42 + n. Pins 1, 3, 5 = GND; pins 2, 4, 6 = 5V0.

| J6 pin | baseboard pin | net | hole (Ti60 frame) | KiCad frame |
|---|---|---|---|---|
| 1 | 43 | GND | (103.072, −13.754) | (203.072, 113.754) |
| 2 | 44 | 5V0 | (103.072, −15.024) | (203.072, 115.024) |
| 3 | 45 | GND | (101.802, −13.754) | (201.802, 113.754) |
| 4 | 46 | 5V0 | (101.802, −15.024) | (201.802, 115.024) |
| 5 | 47 | GND | (100.532, −13.754) | (200.532, 113.754) |
| 6 | 48 | 5V0 | (100.532, −15.024) | (200.532, 115.024) |

- **Layout:** seen from the top, pin 2 is below pin 1 and pin 3 is left of pin 1. That is the same handedness as J3,
  so the library footprint `Connector_PinSocket_1.27mm:PinSocket_2x03_P1.27mm_Vertical` on **B.Cu** fits; rotate it
  so pin 2 lands below pin 1. (An earlier version of this file had the pin order reversed along the row; the
  nets per row were right.)

## Clearance to the baseboard U8 (5V_ISOL regulator)

- **Card outline in the baseboard IPC frame:** X 42.599…118.599, Y −18.766…46.361.
- Baseboard U8 (VXO7805-1000, to be replaced by a 2 A part) is at IPC (104.36, −20.1), **1.33 mm outside the card's
  bottom edge**. Anything on U8 that is taller than the card-to-baseboard gap must stay below Y −18.766 (bb frame).
- The gap is set by the J3/J6 socket + header stack: **measure it on the Ti60 card**.

## J9: RJ45 (UDE RB1-125B8G1A magjack), front face and centreline as on the Ti60

The Ti60 uses a Würth 615008140121 with separate magnetics. Its body in the Top Assembly drawing spans X 90.49…111.91,
Y 28.35…48.35, with locating pegs at (102.682, 32.630) and (102.682, 44.060). Decision 2026-10-24: use the UDE
magjack, **aligned to the Ti60 jack's front face (X 111.912) and centreline (Y 38.345, the peg midpoint)**.

KiCad footprint `Connector_RJ:RJ45_UDE_RB1-125B8G1A`:

- Local geometry: pin 1 at (0, 0), pegs at (0, 8.89) and (11.43, 8.89), body x −2.16…13.59, front at y = 19.78.
- Placement: **F.Cu, orientation 90°, at KiCad (192.132, 67.370)**. Local +y then points to +x (out of the right edge) and local x points to −y.
- Resulting pegs: KiCad (201.022, 67.370) and (201.022, 55.940), i.e. Ti60 (101.022, 32.630) / (101.022, 44.060).
  The front face is at Ti60 X 111.912 and the body centre at Ti60 Y 38.345.
- Compared with the Ti60 jack: pegs 1.66 mm further inboard, same Y. Compared with the Agilex card: 0.42 mm in Y and
  0.51 mm in X (its jack face sits at about X 111.40).

**[verify]** whether the Ti60 assembly outline's front edge is the jack's real front face. Check it against the
Würth 615008140121 drawing, and the RB1 front against the UDE drawing, before ordering.

## J5: LCD header (1×14, 2.54 mm), not a hard requirement

The LCD is connected with jumper wires. Keep the Ti60/Agilex position anyway: pin 1 at Ti60 (52.912, −14.454) =
KiCad (152.912, 114.454), pins along +x.

## Other Ti60 positions (for information)

- J1 JTAG 1×5 at X 58.332, Y 29.625…39.785.
- J8 UART 1×3 at X 52.432, Y 34.805…39.885.
- J3 1×3 (5 V / GND) at Y −11.054, X 97.892…102.972.

The Ti60 card has no mounting holes; it is held by J11/J12 (and the jack).
