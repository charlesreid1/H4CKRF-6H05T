# hackrf-hardware/recognition.md — HackRF-specific pathologies

Symptoms that are more common with the HackRF than with 12-bit SDRs.

## The DC spike is loud

A tall narrow spike at the tune frequency that consumes maybe 3–5 dB
of the useful dynamic range. Every zero-IF SDR has one; the HackRF's
is larger relative to signal than the LimeSDR's because the ADC is
8-bit. Fix: `target_freq_hz` (see `../sdr-fundamentals/`).

## Clipping cliff at ~−20 dBm antenna input

Strong nearby signals (FM broadcast, cellular basestation, WiFi
router) can drive the front end into compression well before the ADC
saturates. Symptoms are the ones in `../sdr-fundamentals/recognition.md`
under "Flat-topped envelope" and "Spurs at harmonics." External
bandpass filter at the antenna is the usual fix.

## USB-2 sample drops above 16 Msps

The HackRF asks USB 2.0 for a sustained 320 Mbps at 20 Msps. Any host
scheduling jitter causes dropped samples. Symptoms: horizontal streaks
on the spectrogram, sudden apparent frequency shifts. Fix: reduce
`sample_rate_hz`, or use a Linux host with `usb-storage` and other
noisy USB traffic quieted.

## Firmware/lib mismatch

`hackrf_info` shows the firmware version and the `libhackrf` version.
A gap of >2 major versions is worth updating; a gap of >4 causes API
call failures ("Cannot start RX", "Invalid parameter"). Symptom:
capture starts, produces zero samples, exits. Fix:
`hackrf_spiflash -w` with the matched firmware binary.

## LO leakage on adjacent SDR

If you have two SDRs in the same test setup, one HackRF's LO can
appear as a tone on the other's spectrum. It moves as you retune the
first HackRF. Not a bug — a physical reality of unshielded
consumer-grade SDRs.

## No enumeration on a laptop USB-C port

The HackRF has a USB-A connector; USB-C laptops need a USB-C-to-A
dongle or a hub. Some passive dongles don't deliver stable 500 mA
current, which the HackRF's ARM MCU tolerates poorly. Symptom:
`hackrf_info` shows the device intermittently, or reports "USB error
-1000". Fix: try a different dongle, a powered hub, or a different
port.

## "hackrf_info" works but "capture" times out

Almost always a permissions issue on Linux — the udev rules didn't
land. `sudo hackrf_info` succeeds; `hackrf-agent capture_iq` from an
unprivileged user times out. Fix:

```bash
sudo cp /usr/share/hackrf/53-hackrf.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
# Then unplug/replug the HackRF.
```

## PortaPack + HackRF plugged into a laptop

If a PortaPack is attached to the HackRF and the assembly is plugged
into a laptop, the PortaPack's LCD backlight can inject supply noise
that appears as a broadband raise on captures. Not a bug — a physical
reality of small consumer hardware. Detach the PortaPack for
laboratory-grade captures.
