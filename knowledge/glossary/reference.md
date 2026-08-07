# glossary/reference.md — RF/SIGINT jargon

## A

- **ADC** — Analog-to-Digital Converter. HackRF's is 8-bit interleaved
  at up to 20 Msps.
- **ADS-B** — Automatic Dependent Surveillance-Broadcast. Aircraft
  transponder that broadcasts position on 1090 MHz.
- **AES** — Advanced Encryption Standard. AES-128 in CCM mode is used
  by LoRaWAN, Zigbee (with CCMP), and BLE (Bluetooth 4.2+).
- **AFSK** — Audio Frequency Shift Keying. FSK inside an audio band,
  typically 1200/2400 Hz tones over narrowband FM. AX.25 uses
  Bell 202 AFSK-1200.
- **AGC** — Automatic Gain Control. Amp adjusts its gain in real time
  to keep the ADC well-utilized.
- **AIS** — Automatic Identification System. Ships' 162 MHz GMSK
  transponder.
- **AM** — Amplitude Modulation.
- **APRS** — Automatic Packet Reporting System. Amateur-band packet-
  radio broadcast on 144.390 MHz (US).
- **ARFCN** — Absolute Radio Frequency Channel Number (GSM).
- **ASK** — Amplitude Shift Keying (generic; OOK is a special case).
- **AX.25** — HDLC-based packet radio protocol for the amateur band.

## B

- **BCH** — Bose-Chaudhuri-Hocquenghem code. FEC family; POCSAG uses
  BCH(31,21) with 2-bit correction.
- **Beast** — a binary output format used by dump1090/readsb for
  ADS-B frames.
- **BLE** — Bluetooth Low Energy. GFSK, 1 Mbaud, 40 channels at 2.4
  GHz.
- **BPSK** — Binary Phase-Shift Keying.
- **BT** — Bandwidth-Time product (Gaussian pulse-shape parameter).
  Bluetooth Classic uses BT=0.5; GSM downlink uses BT=0.3.

## C

- **C4FM** — Compatible 4-Frequency-Shift Keying. Used in P25 Phase 1.
- **CCK** — Complementary Code Keying. Used in older 802.11b.
- **CCSDS** — Consultative Committee for Space Data Systems. Standard
  channel codes for satellite links.
- **CFO** — Carrier Frequency Offset. The receiver's LO doesn't match
  the transmitter's; the receiver estimates and corrects.
- **CP** — Cyclic Prefix. Guard interval in OFDM symbols.
- **CPFSK** — Continuous-Phase FSK. Frequency changes continuously;
  no discontinuities. MSK is a special case.
- **CPR** — Compact Position Reporting. The encoding of lat/lon in
  ADS-B Mode S.
- **CRC** — Cyclic Redundancy Check. Integrity code; different polys
  and parameters per protocol.
- **CSS** — Chirp Spread Spectrum. LoRa's modulation family.

## D

- **DAB** — Digital Audio Broadcasting. EU/Asia digital replacement
  for FM broadcast.
- **DBPSK/DQPSK** — Differential BPSK/QPSK. Data encoded in phase
  differences rather than absolute phase.
- **DC spike** — LO leakage; appears at whatever frequency the tuner
  is set to.
- **DMR** — Digital Mobile Radio. ETSI TS 102 361.
- **dPMR** — digital Private Mobile Radio. ETSI TS 102 490.
- **DQPSK** — Differential QPSK.
- **DSB-LC/DSB-SC** — Double SideBand, Large Carrier / Suppressed
  Carrier. AM variants.
- **DSSS** — Direct-Sequence Spread Spectrum.
- **DVB-T** — Digital Video Broadcast, Terrestrial. OFDM.

## E-F

- **EIRP** — Effective Isotropic Radiated Power. TX power × antenna
  gain (dBi).
- **ENOB** — Effective Number of Bits (ADC's actual usable resolution).
- **ETSI** — European Telecommunications Standards Institute.
- **FCC** — US Federal Communications Commission.
- **FDMA** — Frequency-Division Multiple Access.
- **FEC** — Forward Error Correction.
- **FFT** — Fast Fourier Transform.
- **FHSS** — Frequency-Hopping Spread Spectrum.
- **FIR/IIR** — Finite/Infinite Impulse Response (filter families).
- **FLEX** — Motorola paging protocol, 4FSK.
- **FM** — Frequency Modulation.
- **FSK** — Frequency-Shift Keying.

## G-H

- **GFSK** — Gaussian-filtered FSK.
- **GMSK** — Gaussian-filtered MSK.
- **GNSS** — Global Navigation Satellite System (umbrella term
  covering GPS, GLONASS, Galileo, BeiDou).
- **GPSDO** — GPS Disciplined Oscillator. External timing reference
  for HackRF stability.
- **GRC** — GNU Radio Companion (the GUI).
- **HDLC** — High-Level Data Link Control. Bit-stuffed framing used
  by AX.25, AIS.
- **HRIT** — High Rate Information Transmission. GOES weather satellite
  L-band downlink.

## I-L

- **IIP3** — 3rd-order Intercept Point (amplifier linearity metric).
- **IQ** — In-phase and Quadrature. The two complex-baseband streams
  from a mixer.
- **ISM** — Industrial, Scientific, Medical band. Unlicensed shared
  RF spectrum (315 US, 433 EU, 902-928 US, 863-870 EU, 2.4 GHz).
- **LDPC** — Low-Density Parity Check (FEC code).
- **LFSR** — Linear Feedback Shift Register (used in scramblers and
  some ciphers).
- **LNA** — Low-Noise Amplifier.
- **LO** — Local Oscillator.
- **LoRa** — Long Range (Semtech's CSS PHY).
- **LoRaWAN** — LoRa Wide Area Network (MAC layer on top of LoRa PHY).
- **LTE** — Long Term Evolution (4G cellular). BLOCKED for TX in this
  MCP.

## M-O

- **MAC** — Media Access Control layer.
- **MSK** — Minimum Shift Keying.
- **MFSK** — Multi-tone FSK.
- **NCO** — Numerically-Controlled Oscillator (a software-generated
  sinusoid whose frequency is a running counter).
- **NF** — Noise Figure (dB).
- **NRZ / NRZI** — Non-Return-to-Zero / NRZ Inverted (line codes).
- **OFDM** — Orthogonal Frequency-Division Multiplexing.
- **OFDMA** — OFDM Access (multi-user variant).
- **OOK** — On-Off Keying.
- **OTA** — Over-the-Air.
- **OOT** — Out-of-Tree (a GNU Radio custom module).

## P-R

- **PAM** — Pulse Amplitude Modulation.
- **PAPR** — Peak-to-Average Power Ratio.
- **PDW** — Pulse Descriptor Word (radar).
- **PLL** — Phase-Locked Loop.
- **PN** — Pseudo-Noise (spread-spectrum chip sequence).
- **POCSAG** — Post Office Code Standardization Advisory Group
  (paging protocol).
- **PPM** — Pulse Position Modulation.
- **PSD** — Power Spectral Density (dB/Hz).
- **PSK** — Phase-Shift Keying.
- **PWM** — Pulse Width Modulation.
- **P25** — Project 25 (APCO digital voice standard).
- **QAM** — Quadrature Amplitude Modulation.
- **QPSK** — Quadrature Phase-Shift Keying.
- **RCS** — Radar Cross-Section.
- **RRC** — Root Raised Cosine (pulse shape).
- **RS** — Reed-Solomon (FEC code).
- **RSSI** — Received Signal Strength Indicator.
- **RTL-SDR** — Realtek DVB-T dongle repurposed as an SDR ($20 SDR).

## S-Z

- **SDR** — Software Defined Radio.
- **SF** — Spreading Factor (LoRa parameter, 7-12).
- **SFDR** — Spurious-Free Dynamic Range. HackRF is ~48 dB.
- **SigMF** — Signal Metadata Format (community IQ container).
- **SNR** — Signal-to-Noise Ratio.
- **SSB** — Single SideBand (USB / LSB).
- **SWR / VSWR** — (Voltage) Standing Wave Ratio. Antenna match metric.
- **TCXO** — Temperature-Compensated Crystal Oscillator. HackRF's
  reference clock (25 ppm stock).
- **TDMA** — Time-Division Multiple Access.
- **TETRA** — Terrestrial Trunked Radio (ETSI EN 300 392).
- **TPMS** — Tire Pressure Monitoring System.
- **UNB** — Ultra-Narrow-Band (Sigfox uplink is 100 bps).
- **VGA** — Variable Gain Amplifier (HackRF baseband gain).
- **VSWR** — Voltage Standing Wave Ratio (antenna match; 1.0 is
  perfect, >2.0 marginal).
