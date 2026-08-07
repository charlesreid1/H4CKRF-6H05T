# antennas/walkthrough.md — build a 433 MHz dipole from a coax pigtail

## What you need

- 1 m of RG-58 coax with SMA male on one end.
- Wire cutters.
- Optional: heat-shrink tubing.

## Steps

- 433 MHz wavelength: `λ = 300 / 433 = 0.693 m`.
- Half-wave dipole: 34.6 cm total, split into two 17.3 cm elements.

1. Strip 17.3 cm of the outer jacket + shield from the SMA-terminated
   end of the coax.
2. Fold the shield braid back over the outer jacket — this becomes
   one half of the dipole (the "cold" side).
3. Trim the exposed inner conductor to exactly 17.3 cm — this becomes
   the other half (the "hot" side).
4. Straighten the two ~17.3 cm elements into a line.

That's it. Now:

- **Test:** connect to a NanoVNA (or the HackRF via `hackrf_sweep`) and
  measure S11 at 433 MHz. You should see a dip somewhere between
  400-450 MHz. Trim length in 5 mm increments to walk the dip toward
  433.92 MHz.

## A cleaner build for 2.4 GHz — biquad

A biquad is two same-size loops of wire in figure-8, spaced ~30 mm
above a metal reflector plate.

- **Wire loop side:** `λ/4 = 31.25 mm` per side of each square.
- **Reflector:** copper-clad PCB or a piece of sheet metal ~11 x 11 cm.
- **Spacing wire-to-reflector:** ~15 mm.
- **Feed:** center conductor to one loop, shield to the other. Solder
  to short pigtail with SMA female.

Result: ~11 dBi gain, ~65° beamwidth, 2.4 GHz. Total cost: <$10.

## Sanity checks with hackrf_sweep

To confirm the antenna is picking up the intended band:

```
hackrf_sweep -f 425:445 -w 100000 -n 4000 > sweep_433.csv
```

Then plot with any tool. A well-matched 433 MHz dipole with the local
ISM noise floor gives a clear pedestal centered on 433.92 MHz.

## When to reach for something bigger

- **ADS-B DX (>200 km):** DIY 1090 MHz Yagi or a collinear array.
- **Weather satellite (137 MHz APT):** turnstile antenna or a QFH
  (quadrifilar helix) — omni-and-elevated for LEO passes.
- **GPS L1:** active patch with integrated LNA (passive won't work).
- **HF (below 30 MHz):** a wire dipole or a long-wire + HackRF via
  Ham-It-Up upconverter. HackRF's 1 MHz native floor is the limit.
