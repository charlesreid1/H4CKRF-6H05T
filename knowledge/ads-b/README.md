# ads-b/

Mode S extended squitter at 1090 MHz. **RX-only.** TX on 1090 MHz is
BLOCKED in `RiskAssessor` and every record about ADS-B leads with that
fact. `decode_ads_b` operates on captured IQ files, never on the live
transceiver's TX path.

