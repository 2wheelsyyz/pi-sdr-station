# 01 — Hardware & RF

## Bill of materials

| Item | Notes |
|------|-------|
| **Raspberry Pi 5 — 8 GB** ✅ (on hand) | Plenty for both stacks; 8 GB gives comfortable headroom. |
| **Waveshare PoE HAT (F)** ✅ (your setup) | Powers the Pi over PoE **and** provides the active fan + heatsink. Needs config — see *Power* below. |
| **PoE+ injector: 2.5G, 60 W, 802.3at/af, 55 V** ✅ (your setup) | Active 802.3at — does the handshake the HAT needs; 60 W is ample headroom. Confirmed good. |
| **SanDisk Extreme 128 GB microSD** ✅ (`SDSQXAA-128G-GN6MA`) | Boot media. 128 GB is far more than needed (~10–15 GB used) — the extra capacity buys wear-leveling headroom for 24/7 logging. Scratch writes routed to `tmpfs`. |
| 2× RTL-SDR Blog v4 ✅ (on hand) | Serials to be set to `1090` and `discone` (see [docs/03](03-rtl-sdr-v4-drivers.md)). |
| SDRplay RSPduo ✅ (on hand, optional) | Better receiver for the discone role (14-bit, built-in preselectors). Documented as a swap-in for the discone — see [docs/05](05-openwebrx-discone.md). ADS-B stays on RTL-SDR. |
| Short, good-quality USB extension cables (×2) | Move dongles off the Pi body — reduces RFI and lets the dongles breathe. |
| Clip-on ferrites — **optional, not yet on hand** | Cheap insurance against self-interference. **Not a blocker** — build without them; add only if you see a noise spur or ADS-B rate dip that shifts when you reroute cables. |
| Tuned 1090 MHz ADS-B antenna | ✅ Already have. |
| **Diamond D3000N** super-discone (25–3000 MHz RX) + FM band-stop filter | ✅ Already have. Covers the RTL-SDR v4's whole usable range. |
| **Uputronics 1090 ADS-B filtered preamp** ✅ (SAW + LNA ~16 dB) | On the ADS-B path. SMA. Powered USB-C or v4 bias-tee (5 V). |
| **Uputronics Wideband 100 MHz–4 GHz filtered preamp** ✅ | On the discone path, ahead of the splitter. SMA. Powered USB-C (5 V). |
| N→SMA pigtail ×(antennas) + SMA jumpers | Antennas arrive on N coax; one N→SMA pigtail per antenna at the box entry. |

## Power — you're on PoE (Waveshare PoE HAT (F))

Your Pi is powered by the **Waveshare PoE HAT (F)**: 802.3af/at, fully-isolated
SMPS, **5 V @ up to 4.5 A (~22 W)** to the Pi, plus an onboard fan + heatsink.
That's plenty of capacity for a Pi 5 + two RTL-SDR v4s — but two things need
attention.

### 1. Upstream PoE class — ✅ confirmed good

Your injector is a **2.5G, 60 W, IEEE 802.3at/af, 55 V active PoE+ injector** —
exactly right:
- **Active 802.3at/af**: it performs the PoE negotiation handshake the Waveshare
  HAT requires (a *passive* 48 V injector would not power the HAT at all).
- **55 V** is within the 802.3at PSE range (50–57 V).
- **60 W** budget vs. the ~16–18 W this station peaks at = large headroom.

For reference, why this matters: plain **802.3af** guarantees only ~12.95 W at
the device — marginal-to-insufficient for a Pi 5 under load + two dongles + fan.
**802.3at** (your injector) guarantees ~25.5 W. If you ever see undervoltage
symptoms, the upstream PoE class is the first suspect — but yours is well-specced.

### 2. Unlock the USB current limit (important — PoE-specific)

The Pi 5 only raises its total USB budget to **1.6 A** when it negotiates a 5 A
supply **over the USB-C port**. A PoE HAT feeds power through the **GPIO 5 V
rail**, so the Pi can't detect that and falls back to a **600 mA total** USB cap.
Two v4 dongles (~300 mA each ≈ 600 mA) sit right at that edge → brownouts and
dropouts that look like driver bugs.

Fix — add this line to `/boot/firmware/config.txt` and reboot:

```
usb_max_current_enable=1
```

This is safe here because the HAT's 4.5 A rail can actually back the higher draw.
(This step is in [docs/02](02-os-base-setup.md) as part of OS setup.)

### USB layout

- Plug each dongle into its **own** USB port.
- Prefer the **USB 3.0 (blue) ports**, but note USB 3 can radiate noise around
  1.5 GHz — if you ever see a noise spike, try USB 2 ports or add ferrites.
- A **powered USB hub** becomes the right answer once you add a 3rd/4th dongle
  (Phase 2) — it takes the dongles entirely off the Pi's USB power budget.

## Cooling — covered by the HAT

The PoE HAT (F)'s onboard fan + heatsink **is** your active cooling, so no
separate cooler is needed. readsb + MLAT + OpenWebRX DSP keep the CPU busy, so
keep an eye on it: under ~70 °C is the target.

```bash
vcgencmd measure_temp        # current SoC temperature
vcgencmd get_throttled       # 0x0 = never throttled / no undervoltage
```

`get_throttled` is doubly useful on PoE: a non-zero value flags both thermal
*and* undervoltage events, so it's your single best "is the power adequate?"
check.

## RF front-end — your setup is well-matched

You've already made the two decisions that matter most:

- **ADS-B → tuned 1090 MHz antenna + Uputronics 1090 preamp.** The resonant
  antenna already rejects most out-of-band energy; the **Uputronics 1090 filtered
  preamp** (SAW filter + ~16 dB LNA) adds sensitivity for distant aircraft while
  its SAW filter keeps out-of-band signals from overloading the dongle — a good
  combination near YYZ. With the LNA in line, set the dongle gain **lower** /
  by data (see [docs/04](04-adsb-feeder.md)); if close aircraft drop out, lower
  gain first.

- **Discone → FM band-stop filter.** Exactly right. A wideband discone hears
  everything, and the single biggest overload source on a wideband RTL-SDR is the
  local **broadcast FM band (88–108 MHz)**. The FM trap keeps those strong
  stations from desensitising the front end across the whole spectrum. Living
  near YYZ you may also have strong pager/paging and cellular nearby — if a
  particular band looks hashy, that's a hint to drop RF gain on that profile in
  OpenWebRX rather than to add more hardware.

### Preamps (Uputronics filtered LNAs)

Both paths now have a **Uputronics filtered preamp** (SAW/filter + LNA) at the
project-box entry. See the [system diagram](10-system-diagram.md) for the full
chain. Key points:

- **Power them via USB-C (5 V).** The wideband one *must* be USB-C — it sits
  before the ZFSC splitter, which blocks DC, so no downstream bias-tee reaches
  it. The 1090 one can use USB-C or the v4 bias-tee; USB-C keeps them uniform.
- **Chain order on the discone:** antenna → **FM band-stop → LNA → splitter** →
  receivers. Filter before the LNA (overload protection); LNA before the splitter
  (its gain covers the split loss and sets the noise figure).
- **Reduce dongle gain** now that there's gain ahead of them, or you'll overload
  — especially the wideband discone path in an urban/airport RF environment. The
  RSPduo's built-in preselectors give extra overload margin there.
- **Placement:** at the box entry (after the coax run) per your build. Mounting a
  preamp at the antenna itself would set a slightly better noise figure (before
  coax loss) — a future tweak, not required.

### Physical layout tips

- Keep the **two dongles physically apart** (USB extensions) so the ADS-B dongle
  doesn't pick up digital hash from the discone dongle and vice-versa.
- Keep coax runs away from the Pi's switching supply and the wifi link radio.
- Ground/strain-relief the discone feedline; a wideband vertical outdoors is a
  static and surge magnet — an inline lightning/surge arrestor on the discone
  coax is worth it given it's an outdoor antenna.

## The network link (900 MHz, ~45 Mbps)

This is a real design input, not a footnote. It affects **OpenWebRX** the most
(it streams a waterfall + audio per connected browser). It barely affects ADS-B
(tar1090 is tiny) and feeding the aggregators is a trickle (a few kbps).

Planning numbers:
- tar1090 map + graphs1090: **negligible** (well under 1 Mbps).
- Outbound ADS-B feeding: **~10–50 kbps** total.
- OpenWebRX per browser client: roughly **0.3–2 Mbps** depending on FFT size,
  waterfall resolution, and audio codec. One or two listeners is comfortable on
  45 Mbps; a high-res waterfall with several simultaneous clients is where you'd
  feel it. Tuning guidance is in [docs/05](05-openwebrx-discone.md).

Bottom line: the link is **fine for this build**. Just keep OpenWebRX's FFT/
waterfall settings modest and you'll never notice it. Revisit if you open the
WebSDR to multiple outside users.

---
**Next:** [02 — OS base setup](02-os-base-setup.md)
