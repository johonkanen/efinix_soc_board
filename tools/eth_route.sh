#!/usr/bin/env bash
# Ethernet routing recipe (2026-11-11):  tools/eth_route.sh IN.kicad_pcb WORKDIR   -> WORKDIR/final.kicad_pcb
# IN is the board without Ethernet copper and with the PHY passives placed: tools/swap_footprint.py (0201) for
# R907-R912, R920-R925, C921, C922, C930-C936, C940, C941, then tools/eth_place.py.
# 1. tools/eth_fanout.py: MDI pairs copied from the Agilex card, U901 pins 12-20 fan-out vias, R931 moved.
# 2. Temporary rule areas: no tracks on In2/In5 under the PHY's thermal vias, none on In2/In5/B.Cu east of the PHY
#    (the MDI side); without them route.py runs TX between the thermal vias or loops a net around the PHY.
# 3. route.py, RGMII TX first with In5 cheap, then RX with In2 cheap (In5 allowed: rxd2/rxd3 escape the BGA on In5).
#    In1/In3/In4/In6 are planes (-1). KICAD_RIP_PREEXISTING=0 as always (KRT_LEARNING.md).
# 4. Slow nets: MDC/MDIO/INT/LED on the inner layers (an F.Cu run would lie along the DDR serpentines), the local
#    ones (reset, crystal, RSET, LEDs, CT) on F.Cu/B.Cu.
# 5. Rule areas removed, zones refilled.
# Not routed here: phy_vdd10 / phy_avdd33 / phy_dvdd_rg pin-to-pour connections. route.py on those nets also
# touched GND/VCORE/1V1 ("plane finalize") and put a via beside J9 pin 3, so that run was dropped.
set -eu
export KICAD_RIP_PREEXISTING=0
R="$(cd "$(dirname "$0")/.." && pwd)"; IN=$(realpath "$1"); W="$2"; mkdir -p "$W"; cd "$W"
K=~/dev/KiCadRoutingTools; P="$K/.venv/bin/python -X utf8"; KP="$R/tools/p2k/bin/kipy"
pro(){ for e in kicad_pro kicad_dru; do cp "$R/kicad/ti135_card.$e" "$1.$e"; done; }
C="--layers F.Cu In1.Cu In2.Cu In3.Cu In4.Cu In5.Cu In6.Cu B.Cu --track-width 0.12 --clearance 0.11 --via-size 0.3 --via-drill 0.15 --grid-step 0.05 --no-bga-zones U501 --no-fix-drc-settings --board-edge-clearance 0.5 --escalation off"
route(){ in=$1; out=$2; costs=($3); shift 3   # costs: F In2 In5 B
  $P $K/py_router/route.py $in.kicad_pcb $out.kicad_pcb --nets "$@" --layer-costs ${costs[0]} -1 ${costs[1]} -1 -1 ${costs[2]} -1 ${costs[3]} $C > $out.log 2>&1
  pro $out; echo "$out: $(grep -E '^  (Single-ended|Multi-point)' $out.log | tail -2 | tr -s ' ' | tr '\n' ' ')"; }
$KP "$R/tools/eth_fanout.py" "$IN" fan.kicad_pcb 2>&1 | grep -E 'MDI|fan-out'
$P $K/py_router/add_rule_area.py fan.kicad_pcb k1.kicad_pcb --name ETH_TMP_PHY --rect 183.3 59.3 187.7 63.8 --layers In2.Cu In5.Cu --forbid tracks > /dev/null
$P $K/py_router/add_rule_area.py k1.kicad_pcb k2.kicad_pcb --name ETH_TMP_EAST --rect 187.9 54.5 191.5 71 --layers In2.Cu In5.Cu B.Cu --forbid tracks > /dev/null; pro k2
route k2 tx "8 8 1 8" '*phy_tx*' '*rgmii_tx*'
route tx rx "4 1 2 4" '*rgmii_rx*' '*phy_rx*'
$KP "$R/tools/eth_finish.py" rx.kicad_pcb rx2.kicad_pcb ETH_TMP_EAST 2>&1 | grep removed; pro rx2
route rx2 slow "6 1 1 6" '*eth_mdc' '*eth_mdio' '*eth_int_n' '*eth_led_k'
route slow local "1 3 3 1" '*phy_rstb' '*eth_rst_n' '*phy_xi' '*phy_xo' '*phy_rset' '*phy_led0' '*phy_led1' '*eth_led_a' '*eth_ct'
$KP "$R/tools/eth_finish.py" local.kicad_pcb final.kicad_pcb ETH_TMP_PHY --fill 2>&1 | grep -E 'removed|refilled'
