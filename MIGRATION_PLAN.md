# Plan: control card from Agilex 5 (A5EB013B) to Efinix Ti135N484I3

Written 2026-10-23. Starting point is `~/dev/agilex3_soc_control_card` at commit `0792d44`. Despite the
repository name, that board uses an Agilex 5 **A5EB013B-B23B** SoC as U7. All Ti135 facts below come from
the Ti135 data sheet (DSTi135 v1.6, Dec 2025, most pages still marked *preliminary*) and from the Efinity 2026.1
device database installed in `~/efinity/2026.1`. `reference/ti135n484_pinout.csv` was extracted from that
database (`pt/db/resource/Ti135N484.db`) and lists the ball, pad name and I/O bank of all 484 balls.

Device-specific PCB rules (banks, sequencing, configuration pins, LPDDR4 wiring and swizzling, required pull
resistors) are in `TI135_PCB_NOTES.md`.

Legend: **[keep]** reuse as is, **[mod]** reuse with changes, **[new]** new part or block, **[drop]** remove.

---

## 1. What the Ti135N484I3 gives us

| Item | Ti135N484I3 | Agilex 5 A5EB013B (today) |
|---|---|---|
| Fabric | 132k LE, 9.83 Mbit RAM, 480 DSP | 138k LE |
| Processor | **Hardened quad-core RV32IMAFDC**, 6-stage, MMU (Linux SV32), FPU, 4-way 16 KB I$/D$ per core, up to 1 GHz. Used through the *High-Performance Sapphire RV32 SoC* IP (`efx_hard_soc`), which lists Ti135 as supported | Hard HPS: 2× A55 + 2× A76, 64-bit |
| Hard peripherals | **None**: only the CPUs, 16 KB boot RAM, timers, PLIC and the LPDDR4 controller are hard. UART, SPI, I2C, GPIO, Ethernet MAC and eMMC host are soft IP in the fabric, attached over AXI/APB | HPS EMAC, SD/MMC, UART, I2C, USB… |
| DRAM | **Hard LPDDR4/4x PHY + controller, x32 (or x16)** on dedicated balls; LPDDR4 at 1.1 V VDDQ or LPDDR4x at 0.6 V; up to 3,300 Mbps (LPDDR4). CPU is wired to controller port 1 | Bank 3A LPDDR4 x32 |
| Package | 484-ball FBGA, **18 × 18 mm, 0.8 mm pitch**, full 22 × 22 array | B23B 795 balls, 0.65 mm-class pitch |
| HVIO (1.8/2.5/3.0/3.3 V) | **20** in 3 banks: BL3 (7), BR0 (6), TR1 (7). (Advisory ADV-2604-001: K8 / GPIOR_125 became GND in Efinity 2026.1; the extracted table already reflects that) | ~120 HVIO on 6A–6H |
| HSIO (1.2–1.8 V, LVDS, MIPI) | **85** single-ended / 42 LVDS pairs in 5 banks: top 2A (7), 2B (18), 2C (8); bottom 4A (24, holds the SPI config pins), 4B (28) | 2A |
| Other hard IP | 1× MIPI D-PHY RX + 1× TX, 2 transceiver quads (Q0 with PCIe Gen4, Q1: SGMII / 10GBASE-KR), 8 PLLs | – |
| Configuration | SPI active ×1/×2/×4 (×8 with two flashes), passive, JTAG. Multi-image via CBSEL[1:0] | SDM, AS ×4 |
| Core voltage (I3) | **0.95 V** (0.92–0.98) for VCC, VCCA, VDD_SOC | 0.75 V |
| Temperature | Industrial, Tj −40…100 °C | – |

**Conclusion:** the Ti135N484 covers everything the board does (Linux, 1 GB LPDDR4 x32, Ethernet, eMMC storage,
ADC, PWM/SPI I/O). It costs two things: the Linux peripherals become soft IP, and 3.3 V I/O is scarce (§3.2).

---

## 2. Block-by-block mapping of the existing board

| Agilex board block (sheet) | Fate | Notes |
|---|---|---|
| U7 Agilex 5 + `fpga_power`, `fpga_gnd`, `sdm`, `hps`, `iobank*` sheets | **[drop]** → new Ti135 symbol split into units: power, GND, config/JTAG, DDR, HSIO-top, HSIO-bottom, HVIO, transceiver/MIPI (unused, tied off) | Generate the symbol from `reference/ti135n484_pinout.csv` |
| U12 IS43LQ32256A LPDDR4 x32 1 GB + decoupling (`mem1`) | **[keep]** footprint and decoupling, **[mod]** part (ISSI not stocked at JLC, see §3.6), **re-route** | Efinity's Interface Designer offers LPDDR4 and LPDDR4x, so the 1.1 V part works. Ball map on the FPGA side is completely different → LPDDR4 routing redone. The tuning profiles, stack-up and net classes in `LPDDR4_DELAY_MATCHING.md` carry over |
| U15 TDA38812 VCORE buck (`ps`) | **[mod]** set to **0.95 V** | FB divider 0.6 V × (1 + R2/R1) → R2/R1 = 0.583 (e.g. 5.83 k / 10 k, or 7.15 k / 12.1 k E96). Ti135 has **no core sense balls**: run the Kelvin sense to a VCC via under the BGA. Size the current from the Efinity Power Estimator (§5 step 0.2) |
| U18 1V8, U8 3V3, U16 1V1 bucks (`ps1`) | **[keep]** (re-check load currents) | 1V8 now also feeds VCCAUX, all HSIO banks and LPDDR4 VDD1. 1V1 feeds the DDR PHY VDDQ/VDDQX/VDDQ_CK and the LPDDR4 VDD2/VDDQ |
| U19 1V2 buck | **[mod]** only the KSZ9031 needs 1.2 V now | Keep it (simplest), or replace with a small LDO from 1V8 |
| — | **[new]** **0V85** regulator (another AP61202, R2/R1 = 0.417) | VDD_PHY_DDR (15 balls) + VDDPLL_MCB_TOP_PHY_DDR (via ferrite). Transceiver VCC_SERDES/VDDA_C/D are also 0.85 V but stay unconnected while transceivers are unused |
| U6 NCP163 3V3_analog | **[keep]** | ADC |
| PG wired-AND, R249 `pg_all` | **[mod]** new sequencing (§4) + **[new]** CRESET_N delay | |
| Y2 SiT8924 25 MHz 1.8 V | **[keep]** → PLLIN pin on a 1.8 V HSIO bank | Single board reference for the SoC/fabric/DDR PLLs. Check which PLL (BL0/BL1/BL2 for the RISC-V; DDR PLL) can reach which PLLIN, in Interface Designer |
| U9 100 MHz LVDS oscillator | **[drop]** (unless a transceiver is used later) | Was the Agilex LPDDR4 refclk |
| U2 MX25U25645G 256 Mbit 1.8 V QSPI | **[mod]** → 24-ball 6 × 8 mm BGA (existing footprint and symbol), on bank 4A (SPI active ×4). **Decided 2026-10-23: ISSI IS25WP128-RHLE (C1349419, 128 Mbit)**, to be bought from JLC stock (68 pcs; $3.52 each at 30–99, $3.91 at 10–29) for all three boards; drop-in alternative **Micron MT25QU256ABA8E12-1SIT (C2061023, 256 Mbit, ~$20, 248 pcs)** | Flash holds only the FPGA image + bootloader; Linux lives on the eMMC. **Size budget:** Ti135N484 uncompressed bitstream = **4,371,669 B (≈35 Mbit)**. Measured 2026-10-23 with Efinity 2026.1 on a minimal design. The uncompressed size does not depend on the design, so this is the worst case. Add OpenSBI + U-Boot + env ≈ 1–1.5 MB → ~6 MB for one image, ~10.5 MB with a fallback image. Agilex 5 A5E013 RBF ≤ 4 MB, including the HPS FSBL; U-Boot can sit on the eMMC. Agilex 3 ~1–2 MB. → **128 Mbit is enough for all three, including a fallback image.** 64 Mbit would fit one image only. **Compatibility:** both parts are 1.8 V and have SFDP and a dedicated RESET# on A4, and match the existing ball map (A4 RESET#, B2 CLK, B3 GND, B4 VCC, C2 CS#, C4 DQ2, D2 DQ1, D3 DQ0, D4 DQ3). Both families (IS25WP, MT25Q) are on Efinix's verified list for Titanium. MT25QU is Altera-tested; IS25WP meets Altera's generic SFDP + dedicated-reset rule but is not on Altera's tested list: verify .jic programming on the first Agilex board. Fitting the MT25QU256 instead needs no layout change. Not in stock at JLC: MX25U25645G BGA, MT25QU128 BGA. On the Ti135, RESET# has no configuration role: pull it up, or drive it from a GPIO. |
| SDM strap resistors (MSEL, nCONFIG …) | **[drop]** → **[new]** Efinix config straps | CRESET_N pull-up + delay, CDONE pull-up (+ LED), SSL_N pull-up (= active mode), CBSEL[1:0] pulls (single image: don't care), TEST_N pull-up, CSI pull-up, NSTATUS (optional LED), REF_RES_2A/2C/4A/4B 10 k 1 % to GND, DDR_CAL 240 Ω 1 % to GND, Q0/Q1_CAL_RES 3.01 k (only if transceivers used), VQPS to GND |
| U10 KSZ9031 RGMII PHY + J9 + Y3 (`eth`) | **[keep]** PHY side unchanged | MAC becomes Efinix **TSEMAC** soft IP (`efx_tsemac`) on a 1.8 V HSIO bank. RX_CLK on a GCLK-capable pin (`…_CLKn`). RGMII TX delay from the HSIO delay chain or the PHY pad-skew registers (as noted in `ETH_PHY_REVIEW.md`). Fix the missing FB1/FB2 at the same time |
| microSD: J8, U11 NXS0506, U40, U41, R241–R243, C240–C248 (`hps`) | **[drop]** → **[new]** soldered **eMMC** (§3.5) | eMMC VCCQ = 1.8 V connects straight to an HSIO bank: no translator, no rail switching, no card detect |
| ADC: U3 CD4051B mux, U4 AD8603, U5 ADS7056 | **[keep]** | ADS7056 DVDD accepts 1.65–3.6 V: powering DVDD from 1V8 moves its 3 SPI pins onto HSIO and saves 3 HVIO. Check the CD4051B select thresholds before doing the same with the mux |
| J1 JTAG + U1 level shifter | **[mod]** JTAG sits in bank BR1_BL3 | VCCIO33_BR1_BL3 at 3.3 V → JTAG is 3.3 V (leave JTAG_VCCIO_SEL floating) → **U1 can go**. Efinix programming cables are FTDI-based (FT2232H/FT4232H); see §3.4 |
| U42 (UART, PHY LED, PG to 3.3 V) + J10, J2 FPGA UART | **[mod]** | Console UART from a soft UART. Either keep U42 (UART on HSIO) or put the UART on HVIO and drop U42 |
| J3 2×19 + J5 1×14 power-board headers | **[keep]** connectors, **[new]** 4 × SN74AXC8T245 for 31 outputs; inputs and LCD outputs on HVIO, see §3.2 | Same scheme as the existing Ti60F225 card, with OE gated |
| J6/J4 5 V input | **[keep]** | |

---

## 3. Key design decisions

### 3.1 Processor: hard SoC vs soft Sapphire

Use the **hardened High-Performance Sapphire RV32 SoC** (`efx_hard_soc`). Its ISA, MMU and caches are the same as the
soft Linux Sapphire, it runs up to 1 GHz, it has a hard path to the LPDDR4 controller, and it costs no LUTs. It also
needs VDD_SOC (3 balls, 0.95 V). The soft Sapphire would only be a fallback if the hard SoC flow were not ready for
Ti135.

Software status, and the main project risk:

- `br2-efinix` (Buildroot 2025.02, Linux 6.6, U-Boot 2025.01, OpenSBI 1.6, needs Efinity 2026.1) supports the
  hard SoC only on the **Ti375C529** dev kit. There is no Ti135 board in it. Porting means a new board defconfig and
  device tree (memory size, soft peripherals, clocks), with the same CPU block.
- The `efx_hard_soc` example designs in Efinity 2026.1 are only for `Ti375C529_devkit`.
- → Bring up the full Linux stack (SoC + TSEMAC + eMMC host + UART) on a **Ti375C529 dev kit** before the PCB is
  ordered (§5 phase 1). The same CPU block and the same IP mean the device tree and FPGA top level move almost
  unchanged.

### 3.2 3.3 V I/O budget (the hard constraint)

Signals on the current board that leave U7 fabric banks at 3.3 V (from the netlist):

| Group | Signals |
|---|---|
| J3 (iob6d, 6e, 6f10–18, 6g5, 6h) | 32 |
| J5 (iob6b, 6f0–2) | 12 |
| ADC SPI (cs, sclk, sdo) | 3 |
| ADC mux select | 3 |
| FPGA UART (J2) | 2 |
| User LED | 1 |
| **Total** | **53** |

The Ti135N484 has **20 HVIO**. HSIO cannot go above 1.8 V.

#### Reference: the existing Efinix Ti60F225 version of this card

The user's earlier Efinix board (`…/psu_control_card/efinix_titanium_control_card/ti60f225_psu_control_card`,
Proteus, schematic dated 2023-04-19, PDF and CADCAM exported 2026-10-24) already solves the same problem. Read from
its schematic PDF and IPC-356 netlist:

- 4 layers, 76.0 × 65.1 mm. Same headers: **J11 2×19 (= J3 here)** to the power board and **J4 1×14 (= J5 here)**
  for an SPI LCD + touch.
- **5 × SN74AXC8T245** (U1, U2, U7, U8, U9), VCCA = 1V8, VCCB = 3V3. In all five, DIR1 = 1V8, DIR2 = GND and
  OE = GND. Per the TI function table (SCES875C, Table 7-1), DIR1 = H with DIR2 = L means **all 8 bits A→B**. So all
  40 channels are FPGA outputs, always enabled.
- **3.3 V inputs bypass the translators** and go straight to HVIO: MDATA_INU, MDATA_DAB, MDATA_ISO, SDATA1_ISO (the
  sigma-delta / SPI data from the power board), T_DO, MISO and T_IRQ from the LCD, plus the UART (1 k series).
- ADS7056 DVDD = 1V8, so its SPI is on 1.8 V HSIO directly (as proposed in §2). The mux selects (ADBSEL0–2) go
  through a translator because the SN74LV4051 runs at AD_3V3.
- The Ethernet PHY (PEF7071) RGMII is on 3.3 V HVIO. That is **not possible on the N484**; the KSZ9031 goes on
  1.8 V HSIO instead.
- It has a "FIX BUGS!" note at the J11 header and "check logic" at the mux; the bugs are not described in the PDF.

The signal counts match the Agilex board's 44 header signals:

| Group | Out (FPGA → 3.3 V) | In (3.3 V → FPGA) |
|---|---|---|
| J3 power board (32) | 28: PWM_Q5–Q8, PWM_TRANS1–6, PWM_G1–G4, DAB_PWM_*, ADCLK/INU_ADCLK/ADCLK_DAB, CLK1, CS1, ADASEL0–2, bypass relay | 4: MDATA_INU, MDATA_DAB, MDATA_ISO, SDATA1 |
| J5 LCD + touch (12) | 9: LCD_CS, LCD_RESET, D/C, SCK, MOSI, LED, T_CS, T_CK, T_DIN | 3: MISO, T_DO, T_IRQ |
| ADC mux select | 3 | – |
| FPGA UART | 1 | 1 |
| **Total** | **41** | **8** |

(The Agilex board's 53 also counted the 3 ADC SPI pins, which move to 1.8 V, and the user LED, which can go on HSIO.)

#### Decision: N484 + translators (option A, same scheme as the Ti60 card)

- **All 8 inputs on HVIO.** A translator would need a direction per nibble; direct is simpler and proven.
- **LCD outputs (9) also on HVIO.** That makes 18 of 20 HVIO in use, with 2 spare. The LCD does not care about the
  weak pull-up during configuration (its CS stays high, i.e. deselected).
- **J3 outputs (28) + mux selects (3) through 4 × SN74AXC8T245** (32 channels, 1 spare), all A→B (DIR1 = 1V8,
  DIR2 = GND). That is one translator fewer than on the Ti60 card. Up to 380 Mbps at 1.8 → 3.3 V, so the PWM edges
  are fine, as already shown on the Ti60 card.
- HSIO budget: translators 31, config/flash ~8, RGMII + MDIO + INT/RST 16, eMMC 12, ADC SPI 3, LEDs 2–3, refclk 1,
  translator OE 1 → **~75 of 85**, ~10 spare.
- **Change from the Ti60 card: do not tie OE to GND.** Every Titanium GPIO is *input, tri-state, weak pull-up*
  during reset and configuration (Ti135 data sheet, *Pin States*). With OE = GND the translators pass that pull-up
  through, so **every PWM/gate line on J3 is driven high to 3.3 V until the FPGA is configured** (power-up, CRESET_N,
  reconfiguration, JTAG programming). The 288 kΩ internal pull-downs in the AXC8T245 cannot beat the FPGA pull-up.
  Fix:
  - OE (active low) of all four translators from one HSIO pin, with a **10 k pull-up to 1V8**. The outputs stay
    Hi-Z until the user logic drives OE low after the PWM logic is in a safe state.
  - **10 k pull-downs on all 32 J3 digital pins**, as 8 × 4-resistor arrays: **4D02WGJ0103TCE, 0402×4, LCSC C25725**
    (82,191 in stock on 2026-10-24, extended part). The basic-part alternative is 4D03WGJ0103T5E, 0603×4, C29718. They go on
    the header side, so Hi-Z reads as low on the power board. Putting them on every J3 pin, inputs included, removes
    any dependence on the pin directions or pin order (see the note below); the inputs are driven by the power board,
    and a 10 k load at 3.3 V is 0.33 mA. On the translator outputs the pull-down only works against the
    AXC8T245's internal 288 kΩ. On HVIO inputs it works against the Titanium weak pull-up, which only affects what
    the FPGA reads before configuration.
  - The **baseboard is shared** by the Ti60F225, Agilex 5 and Ti135 cards and is not changed. So the safe state has
    to be guaranteed on each control card. The same pull-downs are recommended for the Agilex 5 card; notes were
    sent to its session.
  - This may be one of the "FIX BUGS!" items. Check whether the power board had problems at power-up.

Translator stock at JLC, 2026-10-24:

| Part | LCSC | Package | Stock | 30+ price |
|---|---|---|---|---|
| **SN74AXC8T245PWR** (chosen, same as the Ti60 card) | C882718 | TSSOP-24 | 8,645 | $0.82 |
| SN74AXC8T245RHLR | C2677358 | VQFN-24 3.5 × 5.5 | 46 | $1.41 |
| SN74LXC8T245RHLR (pin compatible, slower, Schmitt inputs) | C2925682 | VQFN-24 | 4,819 | $1.07 |
| SN74AVC8T245PWR (older; no DIR2, all 8 bits one direction, enough here) | C465742 | TSSOP-24 | 15,836 | $1.04 |

**J3 pin order (resolved 2026-10-24).** The baseboard is being converted to KiCad in `~/dev/ac_psu_kicad`
(`kicad/02_fpga_connector.kicad_sch`). Its J11 netlist is the authority and is extracted to
`reference/baseboard_j11_pinout.csv`, which gives the baseboard pin, signal, direction and the matching Ti60 and
Agilex pins. The baseboard has GND (ISOGND) on 2 and 5, the analog mux inputs ISOADA3/2/1 on 1/3/4, MDATA_ISO on 6,
PWM_Q7 on 37 and NC on 38.

- How to map pins: J11/J3 are through-hole, so the **hole positions** decide which pin meets which, whichever side
  the header is soldered on. Compare hole coordinates from the fab files, with both boards face-up in the same
  orientation (RJ45 on the same side). Pin-number arithmetic alone is not enough.
- **Ti60F225 card (verified working):** female header underneath, card face-up. Ti60 holes: pin 2 is right of pin 1,
  pin 37 is above it. Baseboard holes: pin 2 is left of pin 1, pin 37 is above it. That gives the odd ↔ even mapping
  (Ti60 p = baseboard p + 1 for p odd, p − 1 for p even); all 38 pins agree. The pink bodge wire was PWM_Q7: on
  the original baseboard PWM_Q7 did not reach its connector pin. This is fixed in the new KiCad baseboard
  (J11.37 → J8.43).
- **Agilex 5 card:** mounted the same way as the Ti60 (female header underneath, face-up, RJ45 on the same side). Its
  holes have pin 2 right of pin 1 and pin 37 below it, which gives Agilex J3.q = baseboard 39 − q. The only wrong
  mounting would be rotating the card 180°. The MDATA_ISO pin was missing (J3.33 NC). **Fixed by the Agilex
  session (uncommitted, 2026-10-24):** iob6d4 moved to J3.33 for MDATA_ISO, J3.1 is now NC, and RN1–RN7 (4 × 10 k)
  pull down the 28 outputs.
- **Ti135 card (decided 2026-10-24): J3 on the bottom side, shown that way in the schematic and the PCB.** Use the footprint
  `Connector_PinSocket_1.27mm:PinSocket_2x19_P1.27mm_Vertical` on **B.Cu**, rotated so that, seen from the top with the
  card face-up and the RJ45 on the same side as on the Ti60, pin 2 is left of pin 1 and pin 37 is above it. That is the
  baseboard's own view. KiCad numbers socket footprints mirror-wise to pin headers (socket pin 2 at x = −1.27,
  header pin 2 at +1.27), so this placement makes **J3 pin n = baseboard J11 pin n**. The schematic J3 then uses the
  `baseboard_pin` column of `reference/baseboard_j11_pinout.csv` directly. Silk and fab on the bottom with a pin 1 mark.
  The Ti60 and current Agilex columns in the CSV are only for comparison: both use a top-side header footprint with
  the part fitted underneath. The Agilex card was changed the same way by its session (uncommitted, 2026-10-24): socket on B.Cu, J3 pin n = baseboard pin n, holes, tracks and nets unchanged, schematic parity 0. J5 (LCD) stays as it is; the LCD is connected with jumper wires, as intended.
- Rejected for now: Ti135N676 (84 HVIO), because translators are proven and keep the smaller 18 × 18 mm BGA.
  Cutting header pins is also rejected, because the board must stay compatible with the existing power board.

### 3.3 Bank voltages (proposal)

| Bank | Pins | VCCIO | Use |
|---|---|---|---|
| 4A (bottom HSIO) | 24 | 1.8 V | SPI config flash (CCK, CDI0–3, SSL_N), CBSEL, NSTATUS, TEST_N, CSI, + spare |
| 4B (bottom HSIO) | 28 | 1.8 V | RGMII (KSZ9031 DVDDH = 1.8 V), MDIO/MDC, PHY INT/RST, 25 MHz refclk → PLLIN0 |
| 2A/2B/2C (top HSIO) | 33 | 1.8 V | eMMC (12, direct), ADC SPI, LEDs, A side of the 4 translators (31 + OE) |
| BL3 + BR1 (merged supply `VCCIO33_BR1_BL3`) | 7 + JTAG | 3.3 V | JTAG (3.3 V), header inputs / LCD outputs |
| BR0 | 6 | 3.3 V | header inputs / LCD outputs (GPIOR_131 = PERST_Q0_N, usable as GPIO) |
| TR1 | 7 | 3.3 V | header inputs / LCD outputs, FPGA UART |

The translator A side does not fit entirely in 2A/2B/2C next to the eMMC. The spare pins of 4A/4B take the rest;
Interface Designer decides.

Final pin placement is done in the Efinity **Interface Designer** with a dummy project (§5 step 0.3). It checks bank
voltages, GCLK/PLLIN reachability, the DDR block and the SoC clocks, and exports the pinout CSV used for the KiCad
symbol.

### 3.5 Storage: eMMC instead of microSD (checked 2026-10-23)

**Controller:** Efinix's *eMMC Host Controller* (RTL in
[EmbeddedSystem-Solution](https://github.com/Efinix-Inc/EmbeddedSystem-Solution), `source/submodules/emmc.f`, guide
`docs/app/ug_emmc.md`). It supports HS200 SDR x4/x8 and HS400 DDR x8, up to 200 MHz, with AXI4-Lite registers and an
ADMA AXI4 master. Drivers are in br2-efinix: Linux 6.6 (`efinix,emmc-host-controller`) and U-Boot 2025.01, RV32 only,
proven on the Ti375C529 unified hardware design, which boots Linux from eMMC by default. The `efx_sd_host_controller`
in the Efinity IP catalogue is **SD-only** (1/4-bit, SDR12–50), so it is not the one to use.

**Pins:** CLK, CMD, DAT0–7, RST_n, plus DS (strobe, only for HS400) = 12 HSIO at 1.8 V. Supplies are VCCQ = 1V8 and
VCC = 3V3, plus a VDDi cap (~0.1–1 µF, per data sheet). The 8 SD pins drop out of the HSIO budget and 12 come in.

**JLCPCB stock**, from JLC's parts API on 2026-10-23. All are extended parts, minimum order 1, with JLC's single-piece
price. All are 153-ball 11.5 × 13 mm (or 10 × 11) BGA at 0.5 mm pitch.

| Capacity | LCSC | Part | Temp | JLC stock | ≈ unit price |
|---|---|---|---|---|---|
| 4 GB | C500273 | Samsung KLM4G1FETE-B041 (10 × 11) | −25…85 °C | 1,314 | $18.6 |
| 4 GB | C5197299 | KIOXIA THGBMTG5D1LBAIL | −25…85 °C | 343 | $18.7 |
| 8 GB | C499918 | Samsung KLM8G1GETF-B041 | −25…85 °C | 759 | $21.6 |
| 8 GB | C7509349 | KIOXIA THGBMUG6C1LBAIL | −25…85 °C | 562 | $28.1 |
| 8 GB | C577445 | SanDisk SDINBDG4-8G-XI1 | −40…85 °C | 1,717 | $69.3 |
| 8 GB | C3249966 | FORESEE FEMDRW008G-88A39 | −40…85 °C | 232 | $54.1 |
| 16 GB | C7599693 | KIOXIA THGAMVG7T13BAIL | −25…85 °C | 179 | $23.1 |
| 16 GB | C3002775 | SK hynix H26M51002KPR | −25…85 °C | 210 | $30.7 |
| 16 GB | C2841376 | FORESEE FEMDRW016G-88A43 | −40…85 °C | 252 | $56.9 |
| 32 GB | C2803245 | Samsung KLMBG2JETD-B041 | −25…85 °C | 477 | $45.0 |

100 different eMMC parts were in stock in total, 4 GB to 128 GB. Recommendation: **Samsung KLM8G1GETF-B041
(C499918)**. If the card needs the full industrial range, use **SanDisk SDINBDG4-8G-XI1 (C577445)**. All of these share
the JEDEC 153-ball land pattern, so they are interchangeable. Re-check stock right before ordering.

**Footprint choice:** use the JEDEC **153-ball 11.5 × 13 mm, 0.5 mm pitch (14 × 14 matrix)**. Of the in-stock parts of
8 GB or more, about 39 list 11.5 × 13 explicitly. Another ~44 list only "153-ball", but their families (SanDisk SDINBDG4,
FORESEE FEMDRW/FEMDNN, Samsung KLMxG, SK hynix H26M, MK) are 11.5 × 13 as well. **Check the data sheet of the part you
pick.** Only 2 parts at 8 GB or more come in 7.5 × 8. 10 × 11 shows up only at 4 GB. At 8 GB alone that is ~25 parts
and ~4,800 pieces in stock, from Samsung, KIOXIA, SanDisk, FORESEE, MK, Rayson, BIW and ISSI.

**Decided 2026-10-23: KIOXIA THGAMVG7T13BAIL (C7599693, 16 GB), to be bought from JLC stock.** Checked against its data sheet (2021):
- **VCCQ = 1.7–1.95 V only.** OCR bit 7 = 1.70–1.95 V; this is a 1.8 V-only I/O part.
- VCC = 2.7–3.6 V, for the NAND.
- The data sheet requires host and device VCCQ to come from the same supply. So the FPGA HSIO bank (Ti135) or
  the HPS I/O (Agilex 5) and the eMMC VCCQ all go on `1V8`, and no level shifter is needed.

Board parts:
- Pull-ups to VCCQ: CMD 4.7–100 kΩ, DAT0–7 10–100 kΩ. The internal ones on DAT1–7 are 10–150 kΩ and are not relied on.
- DS (HS400 strobe) needs a 10–100 kΩ pull-down.
- Decoupling: VDDi 2.2 µF (1–4.7 µF), VCC 4.7 µF + 0.22 µF, VCCQ 4.7 µF + 0.1 µF.
- RST_n is disabled by default (EXT_CSD[162] RST_n_FUNCTION = 0). Software must enable it if a hardware reset is wanted.

Package: P-WFBGA153, 11.5 × 13 × 0.8 mm max.

**Consequences:**
- **Layout:** 0.5 mm pitch BGA. Most balls are NC, but the used ones (DAT0–7, VCCQ, VSS) sit close together, so
  expect via-in-pad (filled and capped) under the eMMC. JLC already did that for the Agilex board.
- **First programming / recovery** without a removable card. The FPGA bitstream, the RISC-V bootloader and U-Boot sit in
  the SPI flash (U2). The first Linux image goes onto the eMMC through U-Boot (TFTP over Ethernet + `mmc write`, or
  `ums`/`fastboot` if added), or through a small Linux + initramfs held in the SPI flash. If the latter is wanted,
  consider a 512 Mbit–1 Gbit 1.8 V QSPI flash instead of the 256 Mbit MX25U25645G.
- **Optional:** keep a 4-bit microSD footprint as **DNP** for development/recovery. It still needs U11 (3.3 V card I/O),
  so only do this if board space allows. Dropping it is the cleaner choice.

### 3.6 LPDDR4 part (JLC stock checked 2026-10-23)

**Ti135 DDR options**, from Efinity 2026.1 `ddr32_configuration.db`:
- Types: LPDDR4 or LPDDR4x.
- Width: x16 or x32.
- Density: 1/2/3/4/6/8/12/16 Gbit **per channel**.
- Ranks: 1 or 2. N484 has CS_N[0..3] and CKE[0..1].

x32 uses both channels of a standard 200-ball LPDDR4 package with a common CA bus, as on the Agilex board, so
**1 GB = 8 Gbit package**. The hard SoC addresses at most ~3.7 GB, so a 4 GB part leaves ~0.3 GB unused.

**The current part, ISSI IS43LQ32256A, has 0 stock at JLC**, and so does every other ISSI IS43/46LQ part.

All candidates use the JEDEC 200-ball LPDDR4 package (10 × 14.5 mm, or 10 × 15 for SK hynix) with the same ball map.
**The U12 footprint can stay.** Check the outline/courtyard for 10 × 15 bodies.

LPDDR4 (VDDQ 1.1 V), which fits the current power tree unchanged:

| Size | LCSC | Part | Ranks/dies | Temp | Stock | ≈ price |
|---|---|---|---|---|---|---|
| 1 GB | C2912103 | SK hynix H9HCNNN8KUMLHR-NME | 1 | −25…85 | 121 | $26.6 |
| 1 GB | C51891855 | SK hynix H9HCNNN8KUMLHR-NMO | 1 | −25…85 | 40 | $22.4 |
| 1 GB | C2920231 | Samsung K4F8E3S4HD-MGCL | 1 | −25…85 | 13 | $33 |
| 1 GB | C2838451 | Micron MT53E256M32D2DS-053 WT:B | 1 rank, 2 die | −30…85 | 10 | $57 |
| 2 GB | C2842431 | Samsung K4F6E3S4HM-MGCJ | 1 | −25…85 | 206 | $111 |
| 2 GB | C5330500 | Micron MT53E512M32D1ZW-046 WT:B | 1 | −25…85 | 36 | $149 |
| 2 GB | C476209 | Micron MT53D512M32D2DS-053 WT:D | 1 | **−40…85** | 9 | $163 |
| 4 GB | C22437471 | Micron MT53D1024M32D4DT-046 WT:D | **2 ranks**, 4 die | −30…85 | 102 | $93 |
| 4 GB | C19188580 | Samsung K4FBE3D4HM-MGCJ | 2 ranks | −25…85 | 81 | $127 |

LPDDR4X (VDDQ 0.6 V). These need an extra **0V6** rail for the memory VDDQ and the FPGA VDDQ_PHY_DDR and
VDDQ_CK_PHY_DDR. VDDQX_PHY_DDR and the memory VDD2 stay at 1.1 V.

| Size | LCSC | Part | Temp | Stock | ≈ price |
|---|---|---|---|---|---|
| 1 GB | C46681827 | Winbond W66DP2RQQAGJ | **−40…105** | 21 | $36 |
| 2 GB | C2920249 | Samsung K4U6E3S4AA-MGCL | −25…85 | 251 | $50 |
| 2 GB | C21912322 | SK hynix H9HCNNNBKUMLXR-NEE (JLC lists only 1.1 V; the "LXR" suffix suggests LPDDR4X, so **verify**) | −25…85 | 1,400 | $66 |
| 4 GB | C5827966 | Samsung K4UBE3D4AB-MGCL | −25…85 | 234 | $82 |

**Decision (2026-10-23): LPDDR4 (1.1 V), so the same part works on the Agilex 5 board and the Ti135 board.**
Chosen part: the cheapest 1 GB part that is single-rank x32. Single-rank sidesteps the open question of whether the
Agilex 5 EMIF supports dual-rank LPDDR4; the ISSI part it replaces is also single-rank.

- **U12 = SK hynix H9HCNNN8KUMLHR-NME, C2912103.** Checked against the SK hynix data sheet
  (H9HCNNN8KUMLHR Series Rev 1.1, via LCSC): **LPDDR4, 8 Gb, x16 × 2 channels, 1 CS**, VDD1/VDD2/VDDQ = 1.8/1.1/1.1 V,
  3733 Mbps, −25…85 °C. 200 balls, 0.8 × 0.65 mm pitch, **body 10 × 15 mm**. ~$26.6 (30+: $25.1), 121 in stock.
- The -NMO (C51891855, ~$22, 40 pcs) is **not in the data sheet's ordering table**, which lists only -NLE, -NME, -NLI and -NMI.
  It is not used, because its type and voltage cannot be confirmed.
- **Footprint:** the ball map is the standard JEDEC LPDDR4 200-ball 2-channel map and matches the existing U12 pin use:
  ZQ0 A5, A8 NC, RESET_n T11, ODT_CA_A/B G2/T2 (tied to 1V1 as now), CKE0/CS0, and CS1/CKE1 positions NC.
  The ball array is identical, but the body is 0.5 mm longer than the ISSI part's 14.5 mm.
  → Change the footprint to the 10 × 15 mm variant (same pads), and check clearance to the neighbouring parts.

Efinity setting: LPDDR4, width 32, density **4G per channel**, rank 1.
Quartus: LPDDR4 1ch × 32, 8 Gbit, 1 rank.

### 3.4 Debug / programming

**Decided 2026-10-24: JTAG header + Efinix USB cable** (3.3 V JTAG from bank BR1_BL3, so no level shifter: U1 goes). It is
only needed until updates over the network work, so no on-board FTDI. Keep the header pinout of the Agilex card's J1
if it matches the Efinix cable; otherwise use the Efinix cable pinout. The console UART stays a separate 3-pin header
(J2/J10 style, 3.3 V on HVIO).

---

## 4. Power tree and sequencing

### 4.1 Rails

| Net | V | Source | FPGA loads | Other loads |
|---|---|---|---|---|
| `5V0` | 5.0 | J6 | – | all regulators |
| `VCORE` (0V95) | 0.95 | U15 TDA38812 | VCC (31), VCCA_BL/BR/TR (ferrite-filtered, sub-net `VCCA`), VDD_SOC (3), **VCC18A_MIPI1_TX/RX (MIPI unused → tie to VCC per data sheet)** | – |
| `0V85` [new] | 0.85 | new AP61202 | VDD_PHY_DDR (15), VDDPLL_MCB_TOP_PHY_DDR (ferrite) | – |
| `1V1` | 1.1 | U16 | VDDQ_PHY_DDR (15), VDDQX_PHY_DDR (8), VDDQ_CK_PHY_DDR (1) | U12 VDD2, VDDQ |
| `1V8` | 1.8 | U18 | VCCAUX (4), VCCIO2A/2B/2C/4A/4B | U12 VDD1, U2 flash, Y2, KSZ9031 DVDDH, eMMC VCCQ, translators A side |
| `3V3` | 3.3 | U8 | VCCIO33_BR0, VCCIO33_BR1_BL3, VCCIO33_TR1 | PHY AVDDH, eMMC VCC, translators B side, headers |
| `1V2` | 1.2 | U19 | – | KSZ9031 AVDDL/DVDDL/AVDDL_PLL |
| `3V3_analog` | 3.3 | U6 | – | ADC |
| GND | | | VQPS (keep at 0 V; fuse programming not planned) | |
| unconnected | | | VCC_SERDES01, VDDA_C_Q01, VDDA_D_Q01, VDDA_H_Q01, Q0/Q1 pins (transceivers unused, per "Unused Resources") | |

Check the "Unused Resources" rule for **VCC18A_MIPI → VCC** against the pinout file / Titanium Hardware Design
Checklist before layout; it is unusual and easy to get wrong.

### 4.2 Required order (Ti135 data sheet, Power-Up Sequence)

- **Group 1, any order:** VCC, VCCA, VDD_SOC, VCCAUX, VCCIO, VCCIO33.
- **Group 2, any order, ≥ 10 µs after all of Group 1 reached 90 %:** DDR PHY rails (VDD_PHY, VDDPLL_MCB, VDDQ, VDDQX, VDDQ_CK), MIPI, transceiver rails.
- LPDDR4/4x supplies fully up **before CRESET_N is released**. LPDDR4 itself: VDD1 (1.8 V) must ramp before or with VDD2/VDDQ (1.1 V).
- CRESET_N low until all supplies are up, release ≥ 10 µs after the last reaches 90 %; configuration must not start before **4.5 ms** after supplies are at 90 % (in SPI active mode it starts at the CRESET_N rising edge → delay CRESET_N ≥ 4.5 ms).

### 4.3 Proposed enable chain

```
5V0 ─┬─ U6 3V3_analog (EN = VIN)
     └─ U15 VCORE 0.95 V (EN = VIN)                          Group 1
          PGOOD → U18 1V8                                    Group 1
                   PG → U8 3V3, U19 1V2                      Group 1 (+ PHY)
                         PG(3V3) → U16 1V1, new 0V85         Group 2 (1V8 = LPDDR4 VDD1 already up)
                                    pg_all (wired-AND of all PGs)
                                      → reset supervisor, ~10–20 ms delay (e.g. TPS3808 / TPS3839 class)
                                      → CRESET_N (open-drain, also driveable from FTDI / button)
```

The chain keeps the existing parts and the existing PGOOD style, and meets every rule with margin: Group 2 starts
only after the last Group 1 rail (3V3) is in regulation, and the supervisor covers the 4.5 ms.

---

## 5. Work plan

### Phase 0: feasibility and decisions (desk work, no hardware)

1. ~~Decide §3.2~~ **Done 2026-10-24**: N484 + 4 × SN74AXC8T245, from the Ti60F225 card's header directions. Remaining: confirm that the J3/J5 pin order on the Agilex board matches the Ti60 card's J11/J4, and find out what the Ti60 "FIX BUGS!" note on J11 refers to.
2. **Power estimate:** Efinity Power Estimator for Ti135N484I3 with a realistic design (hard SoC at ~600–800 MHz, LPDDR4 at the chosen rate, TSEMAC, eMMC, PWM logic) → VCC/VDD_SOC, 0V85, 1V1, 1V8 currents → confirm U15 and the AP61202s (2 A) are sufficient.
3. **Done 2026-10-24 (first pass):** `efinity/pinplan/pinplan.py` builds the Interface Designer project, which passes the design check. It writes `efinity/pinplan/ti135_pinplan.csv` (signal → ball). Banks used: 2A/2B/2C full (30 translator lines + ADC SPI), 4A 19/24 (flash, eMMC, status LED), 4B 22/28 (RGMII, MDIO, PHY ctrl, 3 × PLL reference, translator OE), HVIO 18/20 (J3 inputs, LCD, UART). The BGA is assumed rotated 180° (DDR edge toward the LPDDR4, 2A/2B/2C toward J3). The 25 MHz clock fans out to N7/R3/L2 (PLL_BL0/1/2). Original task description: **Dummy Efinity project** for Ti135N484I3: hard SoC + DDR block (LPDDR4, x32, IS43LQ32256A timing) + TSEMAC + eMMC host + UART + all header pins as GPIO. Interface Designer → legal pin placement, PLL/refclk plan, exported pinout. It also gives the bitstream size (flash sizing).
4. **LPDDR4 data rate:** choose a conservative rate for Linux (e.g. 1,600–2,133 Mbps). This sets routing tolerances.
5. Check stock/price of Ti135N484I3 and translators (JLC Global Sourcing as for the Agilex parts).

### Phase 1: software proof on a Ti375C529 dev kit (in parallel with phase 2)

1. Generate the hard SoC for Ti375C529 with the Efinity 2026.1 example, build `br2-efinix`, boot Linux from SD, then from the kit eMMC (the unified hardware design already does this).
2. Add TSEMAC + RGMII PHY (kit Ethernet) and the eMMC host; confirm drivers, network, rootfs on eMMC, and the first-programming path without SD (§3.5).
3. Re-target the FPGA project to Ti135N484I3 (compile only) and write the custom board device tree / defconfig.
4. Firmware for the control functions: PWM, ADC sequencer, register access from Linux (UIO or a small driver, or reuse the SPI register access from `efinix_spi_communication`).

### Phase 2: schematic (new KiCad project in this folder)

**Status 2026-10-24:**
- Scripted KiCad 10 project in `kicad/` using the user's proteus2kicad helpers (`tools/p2k` → `~/dev/proteus2kicad`).
- `tools/gen_symbols.py` builds `lib/ti135_card.kicad_sym`, including the 9-unit Ti135N484I3 symbol made from the pinout CSV.
- `tools/sheets/NN_*.py` draw one sheet each. `tools/sync_root.py` creates the root sheet pins.
- `tools/build_schematic.sh` regenerates everything and runs ERC.
- Done: 01–05 (power input, VCORE, rails, sequencing, FPGA power/decoupling), 06 fpga_config, 07 clocks, 08 lpddr4 (netlist-checked against §6.1 of the notes), 11 fpga_io, 12 level_shift, 14 connectors.
- 2026-10-25: 09 ethernet, 10 emmc and 13 adc are drawn as well, so all 14 sheets are done. The ADC front end comes from the Agilex 3 card (OPA365, 33 R + 680 p).
- **Regulators changed 2026-10-24:** six TLV62585PDRLR replace the TDA38812 and the AP61202s; the AP61202 is nearly out of stock at JLC. See `POWER_BUDGET.md`.
- Mechanics: `MECHANICAL.md`.

1. Copy the KiCad project from `agilex3_soc_control_card`, keep refs of reused parts (as recommended in its `SCHEMATIC_REORG_PLAN.md` §3.7) so the reused layout blocks can be pasted.
2. Apply the reorg plan conventions from the start (flat hierarchy, no global labels, per-rail power symbols, `_n` active-low, sheet names `pwr_*`, `soc_*`, …) instead of repairing the old sheets.
3. New symbol `Ti135N484` (multi-unit) and footprint (BGA-484, 18 × 18, 0.8 mm, 22 × 22; check the KiCad library first, verify against the Efinix package drawing) generated from `reference/ti135n484_pinout.csv`.
4. Sheets: `pwr_input`, `pwr_vcore` (0V95), `pwr_rails` (1V8, 3V3, 1V2, 1V1, 0V85, 3V3_analog), `pwr_seq` (PG + supervisor), `soc_power`, `soc_gnd`, `soc_config` (flash, straps, JTAG/FTDI), `clocks`, `soc_lpddr4_ctrl` + `lpddr4_mem`, `ethernet`, `emmc`, `debug_status`, `soc_hsio`, `soc_hvio`, `level_shift`, `adc`, `io_headers`.
5. Decoupling per Efinix "Titanium Hardware Design Checklist and Guidelines" (Support Center) and AN 033 (configuration resistors).
6. Review against the Ti135 data sheet: power sequence, unused resources, configuration pins, pin states during configuration (HSIO/HVIO weak pull-ups; make sure PWM outputs to the power board are safe while unconfigured: pull-downs on gate-drive enables!).

### Phase 3: layout

- **Check KiCadRoutingTools first** (user request 2026-10-24): https://github.com/drandyhaas/KiCadRoutingTools/discussions/1364. See whether it helps with the BGA fan-out, the LPDDR4 length-matched routing or general autorouting before routing by hand.
- Mechanics (outline, J3/J6 on the bottom, RJ45 aligned to the Ti60 jack) are fixed: see `MECHANICAL.md`.

- New FPGA area: 0.8 mm pitch allows dog-bone fan-out with ordinary 0.2/0.4 mm vias, **no via-in-pad** (cheaper at JLC than the B23B). **8 layers (decided 2026-10-24)**, the same JLC08161H-3313 stack-up as the Agilex card, so its impedance net classes and LPDDR4 rules carry over.
- Reuse placement/routing blocks: Ethernet (U10, J9, Y3), ADC, power stages, LPDDR4 decoupling around U12.
- LPDDR4: re-route with the existing tuning profiles (JLC08161H-3313) and net classes; add the Ti135 package delays from Efinity to the FPGA end.
- Fix the open items from the Agilex board on the way: Y3 placement, FB1/FB2 for the PHY. (SD card detect no longer applies.)

### Phase 4: bring-up

Adapted `bringup_checklist.md` from the Agilex 3 card: rails & sequence, CRESET_N timing, JTAG ID, flash program,
DDR calibration (Efinity DDR test), U-Boot, Linux, Ethernet, eMMC, ADC, header I/O.

---

## 6. Open questions for you

1. ~~Header I/O directions~~: answered by the Ti60F225 card (§3.2). Still open: **what were the J11 "FIX BUGS!" bugs**, and does the power board define its input states while the control card is unconfigured (pull-downs)?
2. ~~N484 fixed?~~ N484 kept (§3.2).
3. ~~Board outline~~ **Decided:** keep the Agilex card outline (J3 socket on the bottom, RJ45 side, mounting holes); 8 layers.
4. ~~Debug~~ **Decided:** JTAG header + Efinix cable, only until network updates work (§3.4).
5. **Dev kit:** do you have (or can you get) a Ti375C529 kit for the Linux bring-up? Which Efinix kit do you have now (the SPI test used a Trion kit)?
6. **Repo:** new git repo here with a copy of the KiCad project, or a branch in `agilex3_soc_control_card`?
7. **Transceivers / MIPI:** definitely unused (tie off), or should an SGMII PHY / camera be kept possible?
8. **Ethernet:** keep KSZ9031 RGMII (recommended, lowest risk), or move to SGMII via Q1 with another PHY? **2026-10-25: RGMII kept, PHY changed to the RTL8211FDI-CG for stock (sheet 09); the 1V2 rail is gone.**

## Sources

- Ti135 data sheet (HTML): features and package resources `ds-features-ti135.html`, packages `ds-pkg-ti135.html`, power-up `ref_ti_power_up-ti375.html`, DC characteristics `ref_dc_switch_ti60.html`, unused resources `ref_ti_unused-ti375.html`, config pins `ref_pinout_desc-ti-config.html`, DDR pins `ref_pinout_desc-ti-ddr.html`, RISC-V `titanium-riscv.html`, all under https://www.efinixinc.com/docs-html/dsti135/topics/
- Advisory ADV-2604-001 (GPIOR_125 / K8 → GND): https://www.efinixinc.com/docs/ADV-2604-001-v1.0.pdf
- Ti135 pin states during reset/configuration: https://www.efinixinc.com/docs-html/dsti135/topics/titanium-io-pin-states.html
- TI SN74AXC8T245 data sheet SCES875C (Jan 2024): https://www.ti.com/lit/ds/symlink/sn74axc8t245.pdf
- Ti60F225 card: `C:\Users\jaarh\Sync\proteus_projektit\Projects\single_phase_inverter\psu\psu_control_card\efinix_titanium_control_card\ti60f225_psu_control_card.PDF` and `… - CADCAM.ZIP` (netlist `… CADCAM Netlist.IPC`)
- br2-efinix: https://github.com/Efinix-Inc/br2-efinix
- Efinity 2026.1: `ipm/ip/efx_hard_soc` documentation (device support table), `pt/db/resource/Ti135N484.db`
