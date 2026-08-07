# regulatory/walkthrough.md — reading a rule to a legal TX plan

## Q: I want to TX at 315 MHz for a keyfob replay. Legal?

**Rule:** FCC Part 15 §15.231.

- Max field strength: 12,500 μV/m at 3 m at 433 MHz (315 MHz
  slightly lower).
- Converting: E-field of 12,500 μV/m at 3 m ≈ isotropic EIRP of
  `4πr²·E²/(120π) ≈ 4.7e-9 W`, i.e. ~5 nW EIRP.
- HackRF TX at minimum gain (VGA = 0 dB, RF amp off) puts out
  roughly 0 dBm = 1 mW at low frequencies. That's **200,000× over
  the §15.231 limit** at the antenna port before any antenna gain.

**Verdict:** transmitting a keyfob replay at 315 MHz with a HackRF
into a real antenna is likely non-compliant with §15.231 as-written.
For legitimate research the operator must:

1. Use a wired dummy load, not an antenna.
2. Alternatively, use a shielded chamber.
3. Alternatively, hold a Part 97 amateur license and stay within
   amateur privileges.

## Q: I want to sweep 108–137 MHz. Legal?

**Rule:** RX is unregulated in almost all cases. Sweeping is
receive-only.

**Verdict:** RX-only operations are fine. `sweep_spectrum` at LOW
risk. TX in this band would be BLOCKED regardless (aviation voice
118–137 is in the BLOCKED table).

## Q: I want to decode POCSAG at 466 MHz. Legal?

**Rule:** Reception is generally legal in the US
(Communications Act §705 has exceptions for radio communications
intended to be heard by the public; the ECPA has broader
protections but paging traffic sits in gray zones per jurisdiction).

**Verdict:** RX + decode is technically feasible and generally
legal. Never TX in paging bands. Never redistribute intercepted
personal messages.

## Q: I have a Part 97 license. Can I TX in 433 MHz?

**Rule:** 420–450 MHz is US amateur allocation. §97.313 sets max
power (1500 W PEP for General/Extra, less for lower classes). Also
some intra-band constraints (repeater sub-bands, weak-signal
segments).

**Verdict:** yes, within licensed privileges + your call sign + no
prohibited content. The MCP still requires a grant + approval;
holding a license doesn't waive the funnel.

## Q: Puzzle wants me to TX in a BLOCKED band. What do I do?

**Answer:** you don't. The gate refuses BLOCKED-band TX
deterministically; that's the correct behavior. If the puzzle
appears to require it, you have misread the puzzle — the flag is
almost certainly reachable via RX + decode, not via TX.
