<div align="center">
  <img src="assets/VA3YMX_logo.png" alt="VA3YMX SDR / ADS-B Receiver" width="180">

  # VA3YMX SDR / ADS-B Receiver

  Dual RTL-SDR v4 receiver on a Raspberry Pi 5 — ADS-B feeding to the major
  aggregators, plus a general-purpose web SDR + decoder station on a discone
  antenna. Headless, near YYZ (Toronto Pearson).
</div>

---

> **Sanitized public mirror — work in progress.** Domain (`example.org`), LAN IPs
> (`192.168.1.x`), and coordinates are **placeholders** — adapt them to your setup. Real
> secrets live in gitignored `.env` files; the committed `.env.example` files are templates.
> The discone receiver is mid-migration (RTL-SDR → RSPduo → Airspy R2) — see [docs/12](docs/12-receiver-evolution.md).

## What this is

A 24/7 headless receiver built around **two RTL-SDR Blog v4 dongles** on a
**Raspberry Pi 5**:

| Dongle | EEPROM serial | Antenna | Job |
|--------|---------------|---------|-----|
| **A** | `1090` | Tuned 1090 MHz ADS-B antenna | ADS-B reception, feeding FlightAware / FR24 / ADSBExchange / community aggregators |
| **B** | `discone` | Discone (wideband) + FM band-stop filter | General RF: OpenWebRX+ web SDR with built-in decoders, plus on-demand trunking/decoders |

Everything runs in **Docker** on **Raspberry Pi OS Lite (64-bit, Trixie)** so
the two roles stay isolated, reproducible, and easy to rebuild.

## The one constraint that shapes the design

**An RTL-SDR can only have one consumer at a time, and only sees ~2.4 MHz of
spectrum at once.** Dongle A is permanently dedicated to ADS-B. Dongle B can run
**either** OpenWebRX+ **or** a dedicated decoder (e.g. OP25 trunking) — not both
simultaneously.

The good news: **OpenWebRX+ runs many background decoders itself** (ACARS, VDL2,
HFDL, POCSAG/FLEX pagers, AIS, SSTV, FT8, etc.) on whatever slice it's tuned to,
while still serving the live waterfall. So a single dongle on the discone
already does a lot. The main exception is **trunked P25 voice-following**, which
needs OP25 with exclusive use of the dongle.

➡️ **Phase 2 upgrade (recommended):** add a 3rd/4th RTL-SDR + a discone
**multicoupler/splitter** so the web SDR and a trunking decoder run at the same
time. See [docs/06](docs/06-decoders-and-trunking.md).

## Why this approach (vs. the old `adsb-box.snap`)

The old snap was a single-purpose, Ubuntu-specific bundle. This build is:

- **Multi-role** — ADS-B *and* a general RF station coexist on one Pi.
- **Container-based** — each role is a `docker compose` stack you can update,
  move, or rebuild independently; no host-level package conflicts.
- **Current & maintained** — uses [`sdr-enthusiasts/docker-adsb-ultrafeeder`](https://github.com/sdr-enthusiasts/docker-adsb-ultrafeeder)
  (the de-facto standard ADS-B stack: readsb + tar1090 + graphs1090 + mlat-hub +
  multi-aggregator feeding) and [OpenWebRX+](https://github.com/luarvique/openwebrx),
  the actively-developed fork with the richest built-in decoder set.

## Build order

Work through these in sequence. Each is self-contained and ends with a
verification step.

1. **[Hardware & RF](docs/01-hardware-and-rf.md)** — Pi 5, power/cooling, USB,
   the YYZ strong-signal problem, antennas, filtering.
2. **[OS base setup](docs/02-os-base-setup.md)** — Raspberry Pi OS Lite,
   headless config, Docker, the 900 MHz / 45 Mbps link considerations.
3. **[RTL-SDR v4 drivers](docs/03-rtl-sdr-v4-drivers.md)** — the v4-specific
   driver, blacklisting the DVB module, and naming each dongle by serial.
4. **[ADS-B feeder](docs/04-adsb-feeder.md)** — ultrafeeder + aggregator
   containers, gain/overload tuning for an airport-adjacent site.
5. **[OpenWebRX+ on the discone](docs/05-openwebrx-discone.md)** — web SDR,
   bandwidth-aware settings for the wifi link, profiles, built-in decoders.
6. **[Decoders & trunking](docs/06-decoders-and-trunking.md)** — OP25 for P25
   trunking (and the Ontario encryption reality), plus other targeted decoders.
7. **[Operations & maintenance](docs/07-operations.md)** — updates, backups,
   monitoring, remote access, the upgrade path.
8. **[Migration from adsb-box](docs/08-migration-from-adsb-box.md)** — config
   recovered from your old node: feeder keys, location, gain, the old→new map,
   and the cut-over procedure.
9. **[Integration & dashboards](docs/09-integration-and-dashboards.md)** — tying
   in the WX3in1 APRS iGate: a Homepage portal + a Grafana/Prometheus dashboard
   with message stats for both stations.
10. **[System diagram](docs/10-system-diagram.md)** — the whole station drawn
    out: RF chains (antennas → preamps → filters/splitter → receivers), power,
    network, and the APRS sibling.
11. **[HTTPS (Caddy + DreamHost)](docs/11-https-caddy.md)** — trusted Let's
    Encrypt wildcard cert via DNS-01, reverse proxy, the pfSense rebind fix, and
    the http→https redirect.
12. **[Receiver evolution](docs/12-receiver-evolution.md)** — the RTL-SDR → RSPduo
    → Airspy R2 journey, what works today, the hard-won SDRplay-in-Docker lessons,
    and the future splitter (two receivers on one antenna). **Work in progress.**

## Ready-to-use config

- [`compose/adsb/`](compose/adsb/) — ultrafeeder + piaware + fr24 + adsbx +
  airnavradar + planefinder + opensky stack (the 5 aggregators migrated from
  your old box, plus ADSBExchange + community feeds). `.env` is pre-filled with
  your recovered keys; `.env.example` is the sanitized template.
- [`compose/openwebrx/`](compose/openwebrx/) — OpenWebRX+ stack.
- [`compose/nrsc5/`](compose/nrsc5/) + [`compose/icecast/`](compose/icecast/) —
  HD Radio (NRSC-5) decoder + Icecast streaming server (`scripts/hdradio.sh`).
- [`compose/acars/`](compose/acars/) — ACARS aircraft datalink: `acarsdec` decoder
  (discone mode, on the RSPduo via SoapySDR) + ACARSHub web UI at `acars.example.org`.
- [`compose/rsp/`](compose/rsp/) — SDRplay RSPduo support: SoapySDR+API base image and
  the `rsp_tcp` bridge (serves the RSPduo as rtl_tcp for OpenWebRX, which can't drive
  it via SoapySDR).
- [`compose/homepage/`](compose/homepage/) — station portal linking both projects.
- [`compose/monitoring/`](compose/monitoring/) — Prometheus + Grafana + an
  APRS-IS exporter for unified ADS-B + APRS message stats.
- [`compose/control/`](compose/control/) — control panel embedded in Homepage:
  start/stop buttons + exclusive discone-dongle "mode" switching.
- [`compose/portainer/`](compose/portainer/) — optional full container manager
  (logs, console, stacks).
- [`compose/caddy/`](compose/caddy/) — HTTPS reverse proxy (wildcard cert via
  DreamHost DNS-01) fronting every UI at `*.example.org`.
- [`scripts/`](scripts/) — driver install, dongle-serial, OpenWebRX-password helpers.

> ⚠️ [`compose/adsb/.env`](compose/adsb/.env) contains your **real feeder keys**
> (migrated from the old node) and is `.gitignore`'d. Set a real `FEEDER_ALT_M`
> before deploying — the old box never had altitude configured.

## Quick reference (deployed)

Trusted HTTPS via the Caddy proxy (LAN-only names → `192.168.1.230`). Plain
`http://192.168.1.230/` 301-redirects to the portal.

| Service | URL |
|---------|-----|
| Station portal (Homepage) | `https://station.example.org/` |
| OpenWebRX+ | `https://sdr.example.org/` |
| ADS-B map (tar1090) | `https://adsb.example.org/` (+ `/graphs1090/`) |
| Grafana | `https://grafana.example.org/` |
| Control panel | `https://control.example.org/` |
| Prometheus | `https://prometheus.example.org/` |
| Portainer | `https://portainer.example.org/` |
| APRS iGate (WX3in1, sibling) | `http://192.168.1.235/` |

---
<sub>Station: **VA3YMX** · Pi `192.168.1.230` · Logo in [`assets/`](assets/) (vinyl-cut SVG + Silhouette `.studio3`).</sub>
