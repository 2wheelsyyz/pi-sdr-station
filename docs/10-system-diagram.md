# 10 — System diagram

Full signal/power/data flow for both projects. (Regenerate the image from
[`assets/system-diagram.svg`](../assets/system-diagram.svg) with
`cairosvg assets/system-diagram.svg -o assets/system-diagram.png --output-width 1240`.)

![VA3YMX SDR / ADS-B system diagram](../assets/system-diagram.png)

## RF chains (antenna → receiver)

**ADS-B path**

```
Tuned 1090 antenna ─N coax─► [box: N→SMA pigtail] ─► Uputronics 1090
   (SAW + LNA ~16 dB) ─► RTL-SDR v4 "1090" ─USB─► Pi (ultrafeeder)
```

**Discone / general-RF path** — *now direct to the RSPduo; the splitter is Stage 4.*
The receiver here has evolved RTL-SDR → RSPduo → (planned) Airspy R2 — see
[receiver evolution](12-receiver-evolution.md).

```
NOW:
Diamond D3000N ─N coax─► [box: N→SMA pigtail] ─► FM band-stop filter
   ─► Uputronics Wideband (100 MHz–4 GHz LNA) ─► SDRplay RSPduo (Tuner 1 50Ω, 14-bit) ─USB─► Pi

STAGE 4 (after the Airspy is stable):
   ...Uputronics WB ─► ZFSC-2-2500-S+ 2-way split ─┬─► Airspy R2  ─USB─► Pi (OpenWebRX / wide)
                                                    └─► RTL-SDR v4 ─USB─► Pi (a decoder)   ← two receivers at once
```

Order matters: **FM band-stop before the LNA** (so strong broadcast FM can't
overload the preamp), and — once it's in — the **LNA before the splitter** (so its
gain overcomes the ~3.5 dB split loss and sets the system noise figure ahead of the
split). Today there's no split: the preamp feeds the RSPduo directly.

## Preamp power & gain (important with the new LNAs)

- **Power the preamps via USB-C (5 V).** Simplest and uniform, and the discone is on
  the RSPduo's **Tuner 1 50 Ω port, which has no bias-T** anyway. The **wideband one
  must be USB-C** once the **Stage-4 splitter** goes in — the ZFSC is transformer-coupled
  and blocks DC, so a downstream dongle's bias-tee couldn't reach it through the split.
  The **1090 preamp** runs off the RTL-SDR v4's bias-tee — but USB-C keeps both identical.
- **Back the receiver gain down.** An LNA ahead of the dongle means you no longer
  want high RF gain at the dongle, or you'll overload — especially on the
  wideband discone path near urban Toronto. Tune ADS-B gain by message-rate data
  ([docs/04](04-adsb-feeder.md)); drop the discone profile gain in OpenWebRX
  ([docs/05](05-openwebrx-discone.md)). The RSPduo's preselectors help here.
- **Placement:** these sit at the **project-box entry** (after the coax run),
  per the build. Mounting a preamp right at the antenna would set the noise
  figure even better (before coax loss) — a future option, not required.

## Power & network

```
900 MHz link (~45 Mbps) ─► PoE+ injector (802.3at·60 W·2.5G) ─Cat6 power+data─► PoE HAT (F) ─► Pi 5
                          └─► Internet ─► ADS-B aggregators + APRS-IS
```

The PoE injector carries **both power and data** to the Pi on one cable. The HAT
also cools the Pi (fan + heatsink). The Pi needs `usb_max_current_enable=1` so
the dongles + preamp USB draw fit the budget ([docs/01](01-hardware-and-rf.md)).

## Sibling project (APRS iGate)

Independent on the air (2 m / 144.390 on the CP22E + FT-2800M), the WX3in1
(`VA3YMX-1`, `.235`) gates to APRS-IS. It shares only the **LAN and the
dashboard** — the Pi's APRS-IS exporter reads the iGate's throughput back into
Grafana ([docs/09](09-integration-and-dashboards.md)).

---
**Back to:** [README](../README.md) · **Prev:** [09 — Integration & dashboards](09-integration-and-dashboards.md)
