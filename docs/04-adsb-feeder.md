# 04 — ADS-B feeder (ultrafeeder + aggregators)

This stack uses **`docker-adsb-ultrafeeder`** (readsb + tar1090 map +
graphs1090 stats + MLAT hub + multi-aggregator output) as the core, plus one
small container per *premium* aggregator that wants its own client
(**FlightAware/piaware**, **FlightRadar24/fr24**, **ADSBExchange/adsbx**). The
many free/community aggregators (adsb.lol, adsb.fi, airplanes.live,
planespotters, theairtraffic, …) are fed directly out of ultrafeeder via
`ULTRAFEEDER_CONFIG` — no extra containers needed.

Files: [`compose/adsb/docker-compose.yml`](../compose/adsb/docker-compose.yml)
and [`compose/adsb/.env.example`](../compose/adsb/.env.example).

## Step 1 — get your station details

You need:
- **Latitude / longitude** to ~5 decimals, and **antenna altitude** (metres,
  ground + mast height). Get precise lat/lon from a map; MLAT *requires*
  accuracy here (a wrong location desyncs multilateration).
- The ADS-B dongle's serial: **`1090`** (set in [docs/03](03-rtl-sdr-v4-drivers.md)).

## Step 2 — register with the premium aggregators (get your keys)

Do these once; they issue you a key/uuid the container needs:

| Aggregator | What you get | How to get the credential |
|------------|--------------|---------------------------|
| **FlightAware** | Free Enterprise account | Bring piaware up once; claim the site at flightaware.com/adsb/piaware/claim → gives a **feeder-id**. |
| **FlightRadar24** | Free Business plan | Run `docker run -it --rm ghcr.io/sdr-enthusiasts/docker-flightradar24 /scripts/signup` to get a **sharing key** (or use an existing one). |
| **ADSBExchange** | Member benefits / your stats | Generate a **uuid** (`cat /proc/sys/kernel/random/uuid`) and set it; they identify you by it. |

Community aggregators (adsb.lol etc.) don't need keys — just a stable
**feeder UUID** (one uuid reused across them via `ULTRAFEEDER_UUID`).

## Step 3 — configure `.env`

```bash
cp -r <this repo>/compose/adsb/* /opt/adsb/
cd /opt/adsb
cp .env.example .env
vim .env        # fill in lat/lon/alt, TZ, serial, gain, and the keys above
```

## Step 4 — bring it up

```bash
cd /opt/adsb
docker compose up -d
docker compose logs -f ultrafeeder      # watch it find the '1090' dongle & start readsb
```

Then open **`http://<pi-ip>:8080/`** — the tar1090 map. Aircraft should appear
within seconds. Stats build up at **`http://<pi-ip>:8080/graphs1090/`**.

## Step 5 — set gain by data (not guesswork)

You have a tuned 1090 antenna **plus the Uputronics 1090 preamp** (SAW + ~16 dB
LNA) in line, so there's extra gain ahead of the dongle — set the dongle gain
**lower** than you would bare, or you'll overload. Two good options:

- **Let it auto-tune:** set `READSB_GAIN=autogain` (or `auto`) and leave it for
  a day; ultrafeeder's autogain converges on a good value (it'll land lower with
  the LNA present).
- **Tune manually:** start around `READSB_GAIN=30` (lower than bare because of
  the LNA — rtl-sdr.com suggests ~32 dB with an LNA directly on the dongle), watch
  graphs1090 over a few days. Aim to **maximise message rate and max range** while
  keeping strong/over-range messages low. Close-in aircraft dropping out = step
  *down*; weak distant aircraft = step *up*.

> **Powering the preamp:** USB-C (5 V) is simplest. If you'd rather use the
> RTL-SDR v4 **bias-tee** to power it over the coax, enable the v4 bias-tee for
> this dongle (verify the exact ultrafeeder/readsb bias-tee flag for your image)
> — but USB-C avoids that and keeps it uniform with the discone preamp.

Near YYZ you'll have enormous traffic volume — expect very high message rates
and a healthy aircraft count quickly.

## What feeds what (data flow)

```
        tuned 1090 antenna
                │
          RTL-SDR v4  (serial 1090)
                │  USB
        ┌───────────────┐
        │  ultrafeeder  │  readsb → tar1090 / graphs1090 / MLAT hub
        └───────┬───────┘
   beast :30005 │ (internal)
   ┌────────────┼─────────────┬───────────────┐
   ▼            ▼             ▼                ▼
 piaware      fr24          adsbx     ULTRAFEEDER_CONFIG →
(FlightAware)(FR24)      (ADSBExch.)  adsb.lol / adsb.fi /
                                       airplanes.live / … (direct)
```

> **FR24 + MLAT:** per FlightRadar24's request, don't enable MLAT for FR24 when
> you're also feeding other aggregators (`MLAT=no` on the `fr24` service).
>
> *Why:* MLAT locates non-ADS-B (Mode S) aircraft by comparing a signal's exact
> arrival time across several nearby receivers — math so timing-sensitive that
> each aggregator's server continuously models *your* receiver's clock drift to
> compensate. Every MLAT network runs its own `mlat-client` process. The
> community aggregators (adsb.lol/fi/airplanes.live/…) all coordinate through the
> **single** mlat-hub inside ultrafeeder, so they cooperate cleanly; but FR24's
> `fr24feed` runs its **own separate** MLAT client. Two MLAT clients timestamping
> the same receiver add scheduling jitter that degrades each server's drift model
> — and produce conflicting position solutions for the same aircraft. FR24 found
> this hurt their network enough to ask multi-feeders to turn FR24 MLAT off.
>
> **You lose nothing:** you keep FR24's full ADS-B feed and Business-plan perks,
> and you *still* get MLAT positions on your map — they arrive via the other
> networks through the hub. (Note: your old adsb-box ran FR24 with `mlat=yes`;
> this is a deliberate change — see [docs/08](08-migration-from-adsb-box.md).)

## Verify it's actually feeding

- **FlightAware:** site shows "green"/online on your stats page after claiming.
- **FR24:** `docker compose logs fr24` shows "connected" + your radar id (`T-...`).
- **ADSBExchange:** appears on adsbexchange.com/myip after a few minutes.
- **Community:** check your feeder UUID on each aggregator's "my stations" page.

---
**Next:** [05 — OpenWebRX+ on the discone](05-openwebrx-discone.md)
