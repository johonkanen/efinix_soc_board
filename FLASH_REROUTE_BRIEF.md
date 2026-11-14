# Brief: place the flash resistors at the FPGA and reroute the flash I/O

Board: `kicad/ti135_card.kicad_pcb` (Efinix Ti135N484 control card, 8 layers, KiCad 10).
Read `AGENTIC_PCB_ROUTING.md` first and work the way it describes: scripted and rerunnable steps,
staged routing, numeric checks plus a look at rendered layers after every run.

## Goal

The owner ripped out the configuration flash's series resistors and pull-ups because they sat at the
flash (U601) instead of at the FPGA (U501). Place them close to the FPGA's flash balls and reroute the
flash nets.

Done means, on the final board with zones refilled:

- every flash net connected (0 unconnected items on the whole board), 0 schematic parity issues;
- DRC shows nothing beyond the baseline: 11 `courtyards_overlap` (accepted) and the eMMC
  `length_out_of_range` items (the owner is meandering those by hand). No clearance, hole, dangling
  or new courtyard items;
- each 33R series resistor within about 5 mm of track from its FPGA ball, pull-ups next to them;
- few vias, no detours, planes untouched.

## The nets and parts

FPGA U501 is on F.Cu, centre (164.0, 81.0), 0.8 mm BGA, outer ball column at x = 172.4.
Flash U601 is on F.Cu at (192.0, 77.9), 1.0 mm pitch. All resistors are 0201 on B.Cu.

| Signal | FPGA ball (x, y) | Series 33R (pad 1 FPGA side, pad 2 flash side) | Flash ball (x, y) | Pull-up 10k to 1V8 |
| --- | --- | --- | --- | --- |
| sck | G4 (170.0, 84.6) | R623 | B2 (191.0, 78.9) | none |
| cs_n | C1 (172.4, 87.8) | R624 | C2 (192.0, 78.9) | R616 on `/flash_cs_n` |
| io0 | J4 (170.0, 83.0) | R625 | D3 (193.0, 77.9) | none |
| io1 | J5 (169.2, 83.0) | R626 | D2 (193.0, 78.9) | none |
| io2 | G3 (170.8, 84.6) | R627 | C4 (192.0, 76.9) | R617 on `/flash_io2` |
| io3 | C2 (171.6, 87.8) | R628, already placed and routed | D4 (193.0, 76.9) | R618 on `/flash_io3`, already placed |
| rst_n | not on the FPGA | none | A4 (190.0, 76.9) | R619 on `/06 fpga_config/flash_rst_n` |

Net names: FPGA side `/flash_<sig>`, flash side `/06 fpga_config/flash_<sig>_r`.

- R623–R627, R616, R617 and R619 are parked off the board at x ≈ 216–221. Place them.
- **io3 is the owner's example of what is wanted**: R628 at (173.6, 88.0) and R618 at (176.3, 90.25),
  just outside the BGA, then one inner-layer run to the flash. Do not change io3; copy its style.
- R619 pulls up a net that exists only at the flash, so it goes next to U601 ball A4.
- Pull-ups get 1V8 from the 1V8 plane (In4.Cu) through their own via.
- Leftover copper: the five other signals still have partial tracks and vias from the old layout
  (FPGA-side nets with ~20 mm inner runs that used to reach resistors at the flash, short stubs at
  U601, orphaned 1V8 vias at (191.975, 75.445) and (189.24, 79.61)). Rip up or reuse as you see fit;
  an old inner run can be kept by moving it to the `_r` net. Keep BGA escapes that are still useful.
- The area right of the BGA (x 173–178, y 81–91, B.Cu) already holds the eMMC series resistors and
  pull-ups. Find room among them; do not move them.

Signal quality: this is a quad-SPI flash. Keep the six flash-side runs of similar length (within
about 10 mm of each other) and on one inner layer where possible; no length-matching rules are needed.

## Do not touch

- Any eMMC net (`emmc_*`) or eMMC part: the owner is tuning them by hand.
- Footprints other than R616, R617, R619, R623–R627. Nets other than the flash nets and the 1V8 taps
  of these pull-ups.
- The schematic, `.kicad_pro`, `.kicad_dru`. Do not run `tools/board_setup.py`.
- git: do not commit, push, stash or reset. The working tree has the owner's uncommitted edits.

## Stackup and rules

- Signals: F.Cu, In2.Cu, In5.Cu, B.Cu. Never route on In1/In6 (GND) or In3/In4 (power).
- Track 0.10 mm (0.12 mm on inner layers is used elsewhere), clearance 0.10 mm, via 0.30/0.15 mm,
  hole-to-copper 0.175 mm, hole-to-hole 0.20 mm, copper to board edge 0.5 mm. Via-in-pad only in
  BGA pads. The project rules file enforces these in DRC.

## Tools

Work on a scratch copy, never directly on the card file:

```
S=<your scratch dir>; mkdir -p $S/kicad
cp kicad/ti135_card.kicad_p* kicad/ti135_card.kicad_dru kicad/fp-lib-table kicad/sym-lib-table kicad/*.kicad_sch $S/kicad/
cp -r lib $S/
```

The copy must keep this layout and file name (`kicad/` beside `lib/`); a board without its project
files next to it fills zones wrongly.

- **KiCad MCP server** (github.com/mixelpixx/KiCAD-MCP-Server, installed in `~/dev/KiCAD-MCP-Server`).
  Use it for placement and routing edits. It is not loaded as native tools in this session, so call it
  through `python3 tools/kicad_mcp.py` (read its docstring): `--list [WORD]`, `--schema TOOL`, or a
  JSON list of calls run in one server session, starting with `open_project` and ending with
  `save_project`. Useful tools: `get_component_properties`, `get_pad_position`, `move_component`,
  `batch_move_components`, `rotate_component`, `check_placement_clearance`, `get_net_pads`,
  `query_traces`, `delete_trace`, `route_trace`, `route_pad_to_pad`, `add_via`, `modify_trace`,
  `refill_zones`, `get_ratsnest`. The server's docs are in `~/dev/KiCAD-MCP-Server/docs`
  (`ROUTING_TOOLS_REFERENCE.md`, `TOOL_INVENTORY.md`). Check each tool's schema before first use and
  verify what it did (for example `route_pad_to_pad` picks its own via position). Do not use
  `autoroute` (Freerouting) or any `kicad_gui_*` / `launch_kicad_ui` tool.
- **KiCad Python** for anything the server cannot do: `tools/p2k/bin/kipy SCRIPT.py ARGS`
  (pcbnew 10). Known crashes: use `board.Delete(item)` not `Remove`, keep `zones = board.Zones()` in
  a variable before `ZONE_FILLER(board).Fill(zones)`.
- **Router**, if hand-placed tracks are not enough (one or two nets at a time, existing copper kept):
  `KICAD_RIP_PREEXISTING=0 ~/dev/KiCadRoutingTools/.venv/bin/python -X utf8 ~/dev/KiCadRoutingTools/py_router/route.py IN OUT --nets "<net>" --layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --track-width 0.1 --clearance 0.11 --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --no-bga-zones U501 --no-fix-drc-settings --board-edge-clearance 0.5 --escalation off --layer-costs 1 -1 1 -1 -1 1 -1 1`
- **Checks**: `source tools/p2k/bin/kicad_env.sh`, then
  `kicad-cli pcb drc --format json --severity-all --schematic-parity -o OUT.json BOARD`.
  DRC does not refill zones; refill and save first (MCP `refill_zones` or pcbnew).
- **Dangling cleanup**: `tools/p2k/bin/kipy tools/drop_dangling.py IN OUT DRC.json [UUID:X,Y ...]`
  in rounds with DRC, watching that unconnected stays 0 (see its docstring: a track that only
  overshoots its junction must be trimmed, not removed).
- **Renders**: `kicad-cli pcb export pdf --layers B.Cu,Edge.Cuts -o x.pdf BOARD`, then `pdftoppm`
  cropped to the area x 166–196, y 72–93 at about 1000 dpi, and read the PNG. Do this for F.Cu,
  In2.Cu, In5.Cu and B.Cu after each routing pass.

## Order of work

1. Baseline: DRC on the scratch copy, list of flash tracks/vias, renders of the area.
2. Plan the placement from the renders and the free space on B.Cu; write the plan down before moving.
3. Place the eight resistors; check courtyards and clearances.
4. Clean out leftover flash copper you will not reuse.
5. Route in stages: FPGA ball → resistor first (short, the hard part), then the flash-side runs,
   then the pull-up taps. Check and render after each stage.
6. Dangling cleanup, refill, final DRC with parity, final renders.
7. Only if every "done" item holds: confirm `kicad/ti135_card.kicad_pcb` has not changed since you
   copied it (compare a checksum taken at the start), then copy your board over it. If it changed or a
   check fails, leave the card file alone and say so.

## Report back

- Whether the card file was updated, and the path of your final scratch board.
- Final positions of the eight resistors, and per signal: track length FPGA ball → resistor, length
  resistor → flash, layers, via count.
- DRC counts by type before and after, unconnected, parity.
- Paths of the final renders.
- Anything you could not do, anything you changed outside the flash nets, and what in this brief was
  wrong or missing.
