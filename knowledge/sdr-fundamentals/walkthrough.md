# sdr-fundamentals/walkthrough.md — worked examples

## 1. Capture a signal without letting the DC spike land on it

Say you want to capture 433.920 MHz (EU ISM keyfob band) at 10 Msps.

Using `target_freq_hz`:

```python
capture_iq(target_freq_hz=433_920_000,
           sample_rate_hz=10_000_000,
           duration_s=2.0,
           lna_gain_db=16,
           vga_gain_db=20)
```

The agent internally tunes the HackRF to `target_freq_hz + fs/4 =
436.42 MHz`. The DC spike lands at 436.42 MHz in the RF world (2.5 MHz
above your target). Your target signal at 433.92 MHz appears as a tone
at `-2.5 MHz` in the resulting complex baseband. Post-capture, the
agent frequency-shifts the file so the target lands at 0 in the
delivered IQ.

Using `center_freq_hz` directly (only when you know you want raw
control):

```python
capture_iq(center_freq_hz=433_920_000,
           sample_rate_hz=10_000_000,
           duration_s=2.0)
# DC spike sits at 0 Hz in the IQ, right on top of your signal.
```

## 2. IQ imbalance correction

A quick affine correction that fixes amplitude mismatch and a small
phase error. Real-world calibrations get more sophisticated
(Rice-decomposition, blind adaptive), but this is enough to knock a
ghost image down 15–20 dB.

```python
import numpy as np

def rebalance(x):
    I = x.real
    Q = x.imag
    alpha = np.std(I) / np.std(Q)                # amplitude ratio
    sin_phi = np.mean(I * Q) / (np.std(I) * np.std(Q))
    cos_phi = np.sqrt(max(0.0, 1 - sin_phi**2))
    Q_corr = (alpha * Q - sin_phi * I) / cos_phi
    return I + 1j * Q_corr
```

## 3. Sweep-then-zoom

Broad sweep first (LOW risk, unattended):

```python
sweep_spectrum(start_freq_hz=430_000_000,
               end_freq_hz=440_000_000,
               dwell_s=0.5)
```

Find a peak (say at 433.925 MHz). Zoomed capture with the target
frequency, not the peak — capture at exactly the peak means the DC
spike hides it:

```python
capture_iq(target_freq_hz=433_925_000,
           sample_rate_hz=2_000_000,
           duration_s=5.0)
```

Then `read_iq_summary` and `analyze_iq_modulation` (planned) to
identify the signal.

## 4. Choosing gain for an unknown band

1. Turn RF amp OFF (`rf_amp_db=0`).
2. Start at `lna_gain_db=16`, `vga_gain_db=20`.
3. Run a short sweep. Look for clipping (broadband raise) in the
   `read_iq_summary` output.
4. If the noise floor looks flat and no signal is visible, add 8 dB
   LNA and 4 dB VGA. Retry.
5. Only enable the RF amp (`+14 dB`) after you've confirmed there's
   no strong nearby signal (no clipping visible with `rf_amp_db=0`
   and full LNA).
