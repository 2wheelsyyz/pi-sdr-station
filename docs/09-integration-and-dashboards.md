# 09 — Integration & dashboards (with the WX3in1 APRS iGate)

You run two stations on the same LAN. This doc covers how they relate and how to
get **one pane of glass with message stats for everything**.

## Topology — two independent projects, one monitoring hub

| | This project (SDR / ADS-B) | Sibling (APRS iGate) |
|---|---|---|
| **Host** | Raspberry Pi 5 — `192.168.1.230` | Microsat WX3in1 Plus 2.0 `VA3YMX-1` — `192.168.1.235` |
| **Radios** | 2× RTL-SDR v4 | Yaesu FT-2800M |
| **Antennas** | Tuned 1090 MHz · Diamond D3000N discone | Diamond CP22E (2 m vertical) |
| **Bands** | 1090 MHz ADS-B · 25–3000 MHz RX | 144.390 MHz (APRS) |
| **Feeds** | FA / FR24 / RadarBox / PlaneFinder / OpenSky / ADSBExchange / community | APRS-IS |

### On-air: keep them separate (by design)

There is **no RF integration worth doing**, and that's the right call:

- APRS on the **CP22E** (a resonant 2 m vertical) outperforms APRS on a discone.
- ADS-B has its own tuned 1090 antenna.
- The WX3in1 is a dedicated hardware TNC/iGate — more reliable for 24/7 APRS than
  software-decoding it on the SDR.

> Could the SDR *also* watch 144.390 in OpenWebRX? Yes — but it would tie up the
> single discone dongle and duplicate what the WX3in1 already does well. Skip it
> unless you're just curious one afternoon.

So the integration is **at the data/monitoring layer**: make the Pi (`.230`) the
hub that displays stats from both. Two tiers, both Docker stacks on the Pi.

---

## Tier 1 — Station portal (Homepage)

A single landing page at **`http://192.168.1.230/`** linking — and live
status-checking — every UI across both projects, plus external stat pages.

Files: [`compose/homepage/`](../compose/homepage/).

```bash
sudo mkdir -p /opt/homepage/config
sudo chown -R "$USER":"$USER" /opt/homepage
cp -r <repo>/compose/homepage/config/* /opt/homepage/config/
cp <repo>/compose/homepage/docker-compose.yml /opt/homepage/
cd /opt/homepage && docker compose up -d
```

What it shows (edit the YAML to taste):
- **ADS-B**: tar1090, graphs1090, Grafana — with up/down pings.
- **SDR**: OpenWebRX+.
- **APRS**: the WX3in1 web UI (`.235`) + your aprs.fi station page.
- **Monitoring**: Grafana, Prometheus.
- **Bookmarks**: each aggregator's stats page, RadioReference, this doc set.
- **Top widgets**: Pi CPU/RAM/temp/disk + clock.

> Homepage needs `HOMEPAGE_ALLOWED_HOSTS` set (already done in the compose for
> `192.168.1.230`). The optional `customapi` widget on tar1090 is left commented
> because readsb's JSON schema varies by version — enable it once you've checked
> the field paths, or just rely on Grafana (Tier 2) for live numbers.

---

## Tier 2 — Unified message-rate graphs (Prometheus + Grafana)

The real "stats for everything": historical graphs of ADS-B **and** APRS message
rates in one Grafana.

Files: [`compose/monitoring/`](../compose/monitoring/).

```bash
sudo mkdir -p /opt/monitoring
sudo chown -R "$USER":"$USER" /opt/monitoring
cp -r <repo>/compose/monitoring/* /opt/monitoring/
cd /opt/monitoring
cp .env.example .env && vim .env        # set GRAFANA_ADMIN_PASSWORD
docker compose up -d
```

### ADS-B metrics (fully wired)

The ADS-B stack already exports metrics: [`compose/adsb/docker-compose.yml`](../compose/adsb/docker-compose.yml)
uses the **`:telegraf`** image with `PROMETHEUS_ENABLE=true`, exposing:
- `:9274` — readsb metrics (messages/sec, aircraft, positions, range)
- `:9273` — telegraf/system metrics

Prometheus ([`prometheus.yml`](../compose/monitoring/prometheus/prometheus.yml))
scrapes both. In Grafana (`http://192.168.1.230:3000/`, log in with your
`.env` password):
1. The Prometheus datasource is auto-provisioned.
2. **Import dashboard ID `18398`** ("Ultrafeeder Stats") — Dashboards → Import →
   `18398` → pick the Prometheus datasource. Done: live ADS-B message graphs.

### APRS metrics (polled from the WX3in1 over telnet)

The WX3in1 Plus 2.0 has no SNMP, but its **telnet** interface (admin/admin) has a
`print stats` command with proper counters — the iGate's *own* numbers, which
beat counting APRS-IS traffic externally. The exporter
([`compose/monitoring/aprs-exporter/`](../compose/monitoring/aprs-exporter/)) logs
in every 60 s, runs `print stats` / `print voltage` / `print rfheard` /
`print isheard`, parses them, and exposes on `:9101`:

| Metric | From |
|--------|------|
| `aprs_rf_packets_received` · `aprs_rf_packet_starts` · `aprs_rf_{header,crc,endflag}_errors` | RF reception + decode quality |
| `aprs_rf_decode_efficiency_percent` (+ `_hour`) | decode efficiency |
| `aprs_igate_rf_to_is` | **RF packets gated to APRS-IS** (the headline iGate number) |
| `aprs_digi_repeated` · `aprs_digi_dropped` | digipeater |
| `aprs_rf_messages_gated_from_is` · `aprs_rf_beacons_sent` · `aprs_rf_bytes_{received,sent}` | tx / messages |
| `aprs_igate_connected` · `aprs_igate_reconnects` | APRS-IS link health |
| `aprs_input_voltage_volts` · `aprs_uptime_seconds` | hardware health |
| `aprs_rf_stations_heard` · `aprs_is_stations_heard` · `aprs_rf_max_distance_km` | coverage (farthest heard) |
| `aprs_poll_success` | 1 = last telnet poll OK |

Counters are exposed as gauges holding the device's absolute value — use
`rate(metric[5m])*60` in Grafana for per-minute rates (it reset-corrects on a
WX3in1 reboot). Telnet host/creds are env on the `aprs-exporter` service
(`WX_HOST`/`WX_USER`/`WX_PASS`, default `192.168.1.235` admin/admin).

The Grafana dashboard **APRS VA3YMX-1** (`/d/aprs-va3ymx`) charts all of the
above; it's the tile embedded on the Homepage portal.

> The temperature sensor reads −64 °C (nothing connected), so it's not exported.
> Other commands worth a look in the WX3in1 manual: `print rfheard`/`isheard`
> (station lists), `debug rf/digi/aprsis on` (live packet streams), telemetry.

---

## Management — start/stop buttons in the dashboard

Homepage on its own is a launcher/status board — it shows whether a service is up
but has no action buttons. To get **real start/stop controls inside the portal**,
a tiny purpose-built **control panel** ([`compose/control/`](../compose/control/))
is embedded into Homepage via its **iframe widget** (the "Station Control" tile at
the top of the page).

It's smart about the **single-dongle reality**: the discone "modes"
(OpenWebRX / OP25 / ACARS / …) behave like **radio buttons** — click one and it
stops the others and starts your choice, freeing the dongle in one action. The
**active** mode shows a **■ release** button that stops it and leaves the dongle
free. Other services (ultrafeeder, Grafana, Icecast, …) get plain start/stop.
Decoder containers you haven't created yet show as *absent* with a disabled button
until they exist.

**HD Radio tuner.** [nrsc5 → Icecast](06-decoders-and-trunking.md) gets its own
block right in the panel: type a **frequency**, pick **HD1–HD4**, hit **▶ Tune**.
The panel stops the web SDR, launches the decoder container, and once it locks
shows **now-playing** (station · title — artist, parsed from the decoder log) plus
an embedded **audio player** for the stream — so you get a play button on the
dashboard, no separate app. **■ Stop** ends it and frees the dongle. (The CLI
`./hdradio.sh <freq> <prog>` still works and does the same thing.)

> The page is **AJAX-driven** (it polls `/api/state` and patches the DOM in place)
> specifically so the embedded audio player keeps playing instead of cutting out on
> a refresh. The panel launches the stream container itself, so it mounts the
> Icecast source password read-only (`/opt/icecast/.env`) — keep it LAN-only (below).

```bash
sudo mkdir -p /opt/control
cp <repo>/compose/control/{app.py,Dockerfile,config.yaml,docker-compose.yml} /opt/control/
cd /opt/control && docker compose up -d --build
```

Edit [`config.yaml`](../compose/control/config.yaml) to list which containers are
discone "modes" vs always-on services. The panel is also reachable directly at
`http://192.168.1.230:8093/`.

> The control panel uses the Docker socket, so keep it **LAN-only**. For remote
> access reach it via Tailscale ([docs/07](07-operations.md)), not a public port.

### Portainer (optional, advanced)

For full container management — logs, console, stats, editing stacks —
[`compose/portainer/`](../compose/portainer/) adds Portainer:

```bash
sudo mkdir -p /opt/portainer && cp <repo>/compose/portainer/docker-compose.yml /opt/portainer/
cd /opt/portainer && docker compose up -d
```

Open **`https://192.168.1.230:9443/`** and set the admin password **right away**
(first-run setup locks after a few minutes). Same LAN-only caution applies. The
day-to-day start/stop you'll do from the Homepage control panel above; Portainer
is for when you need to dig into a container.

## End state

`http://192.168.1.230/` (Homepage) is your front door → from there, one click to
the ADS-B map, the web SDR, the APRS iGate, and a Grafana that charts **message
rates for both stations** over time. The WX3in1 stays a standalone appliance; the
Pi just reads from it.

> Ports added on the Pi by this doc: `80` (Homepage), `3000` (Grafana),
> `9090` (Prometheus), `9101` (APRS exporter), `8093` (control panel), `9443`
> (Portainer), `9273-9274` (ultrafeeder metrics). None collide with the ADS-B
> (`8080`) or OpenWebRX (`8073`) UIs.

---
**Back to:** [README](../README.md) · **Prev:** [08 — Migration](08-migration-from-adsb-box.md)
