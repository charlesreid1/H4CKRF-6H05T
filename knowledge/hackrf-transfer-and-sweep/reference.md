# hackrf-transfer-and-sweep/reference.md — the CLI surface

## hackrf_info

Enumerate connected HackRFs and print their firmware / serial:

```
hackrf_info
```

Output includes `Board ID: 2 (HackRF One)`, `Firmware Version:
2023.01.1 (API:1.07)`, `Part ID Number: 0xa000cb3c 0x00565749`,
`Serial Number: 0x0000000000000000 0x1234567890abcdef`.

## hackrf_transfer

**RX to file:**

```
hackrf_transfer -r out.cs8 -f 433920000 -s 2000000 -a 1 -l 24 -g 20 -n 4000000
```

- `-r <file>` — RX destination (writes signed-int8 interleaved).
- `-f <hz>` — center frequency.
- `-s <sample_rate_hz>` — supported: 2, 4, 8, 10, 20 MHz.
- `-a {0|1}` — RF amp bias (0=off, 1=on, +14 dB gain when on).
- `-l <db>` — LNA gain (IF stage): 0-40 in steps of 8.
- `-g <db>` — baseband VGA gain: 0-62 in steps of 2.
- `-n <samples>` — number of samples to capture.

**TX from file:**

```
hackrf_transfer -t payload.cs8 -f 433920000 -s 2000000 -x 20 -R
```

- `-t <file>` — TX source (reads signed-int8 interleaved).
- `-x <db>` — TX VGA gain: 0-47 in steps of 1.
- `-R` — repeat the file continuously (careful with duty cycle).

## hackrf_sweep

Wide-band spectrogram sweep:

```
hackrf_sweep -f 400:500 -w 100000 -n 4000
```

- `-f <lo:hi>` — MHz range. Multiple `-f` OK for narrowbands.
- `-w <bin_width_hz>` — target FFT bin width. Actual is quantized.
- `-n <count>` — samples per tune step.

Output: CSV with `date, time, hz_low, hz_high, hz_bin_width, num_samples,
db_bin1, db_bin2, ...` one line per sweep step.

## hackrf_operacake

Manages the Opera Cake 4-antenna switch add-on:

```
hackrf_operacake -o 0 -a 0    # antenna port A0
hackrf_operacake -m 0 -f 315000000:433000000:315000000  # freq-based switching
```

## hackrf_spiflash

Firmware update:

```
hackrf_spiflash -w hackrf_one_usb.bin
```

**Only** flash images from official Great Scott Gadgets releases. A
mis-flashed HackRF can require JTAG recovery.

## hackrf_debug

Register-level poking. Do **not** touch unless you know why — you can
mis-configure the MAX2837 into hardware misbehavior. Documented for
completeness only.

## Sample-rate reliability

- **2, 4, 8 Msps:** rock solid on any USB 2.0 host.
- **10 Msps:** solid on most hosts; some cheap Windows USB stacks
  drop samples.
- **20 Msps:** saturates USB 2.0 (480 Mbps ÷ 8-bit-interleaved-IQ =
  ~30 Msps ceiling — 20 Msps is close). Drops samples on many hosts.
- **Rule of thumb:** run at 10 Msps unless you specifically need the
  extra bandwidth; the ADC is only 8-bit so effective resolution isn't
  helped by faster sampling.

## Citations

- HackRF host tools GitHub (greatscottgadgets/hackrf, `host/hackrf-tools`).
- HackRF documentation (hackrf.readthedocs.io).
