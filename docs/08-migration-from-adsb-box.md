# 08 — Migration from the old adsb-box snap

Captured from the old node **`youruser@192.168.1.14`** (`adsb-box` snap
**v1.8.3**, rev 1214) at `/var/snap/adsb-box/current`. This is the source of
truth for what to carry over.

## What the old box was doing

- **Receiver:** dump1090-fa, gain **unset → "max"** (snap had no `RECEIVER_GAIN`).
- **Location:** `43.7, -79.5` (pfclient: `43.7 / -79.5`).
- **Altitude:** ⚠️ never configured on the old box. **Now set to ~124 m ASL**
  = ground elevation (~120 m; DEMs report 115–123 m at the coordinates) + 14 ft
  (4.3 m) antenna AGL.
- **Hardware seen on old box:** 1× RTL2838 RTL-SDR **+ 1× SDRplay RSPduo**
  (the new build standardises on 2× RTL-SDR v4 instead).
- **Fed 5 aggregators:** FlightAware, FlightRadar24, AirNav RadarBox,
  PlaneFinder, OpenSky.

## Credential mapping (old file → new `.env`)

All of these are already filled into [`compose/adsb/.env`](../compose/adsb/.env)
(kept private via [`.gitignore`](../.gitignore)).

| Aggregator | Old location | Value | New `.env` var |
|---|---|---|---|
| **FlightAware** | `piaware/piaware.conf`, `piaware/feeder_id` | `YOUR-FA-FEEDER-ID` | `FEEDER_FA_ID` |
| **FlightRadar24** | `fr24feed/fr24feed.ini` → `fr24key` | `YOUR_FR24_SHARING_KEY` | `FR24_SHARING_KEY` |
| **AirNav RadarBox** | `rbfeeder/rbfeeder.ini` → `key` | `YOUR_RADARBOX_SHARING_KEY` | `RADARBOX_SHARING_KEY` |
| **PlaneFinder** | `pfclient/pfclient-config.json` → `sharecode` | `YOUR_PLANEFINDER_SHARECODE` | `PLANEFINDER_SHARECODE` |
| **OpenSky** | `snap get adsb-box` → `opensky-network` | user `YOUR_OPENSKY_USERNAME`, serial `YOUR_OPENSKY_SERIAL` | `OPENSKY_USERNAME` / `OPENSKY_SERIAL` |

> The old RadarBox `sn=YOUR_RADARBOX_SN` is a station serial RadarBox assigns; the
> **sharing key** is what the container needs, so `sn` isn't required.

## Reusing the FlightAware site (important)

Because you're carrying over the **same feeder-id**, FlightAware treats the new
box as the *same station* — you keep your stats, ranking, and Enterprise perks.
**Do not re-claim** a new site. Just make sure `FEEDER_FA_ID` is set before first
boot (it already is in `.env`). Same idea applies to the FR24 key, RadarBox key,
PlaneFinder sharecode, and OpenSky serial — reusing them = same identity, history
preserved.

## What changed on purpose (new ≠ old)

| Topic | Old | New | Why |
|---|---|---|---|
| Gain | max | **autogain** | autogain converges on a better value than fixed-max; pin it later if you want. |
| FR24 MLAT | `mlat=yes` | **off** | sdr-enthusiasts/FR24 guidance: don't run FR24 MLAT when multi-feeding. Flip `MLAT=no`→`yes` in `fr24` service to revert. |
| Community aggregators | none | adsb.lol / adsb.fi / airplanes.live / planespotters / theairtraffic | Free extra coverage; identified by `ULTRAFEEDER_UUID`. |
| ADSBExchange | not fed | **added** (own `adsbx` container, new UUID) | You wanted the major aggregators; comment the service out to skip. |
| Platform | Ubuntu snap | Docker on Pi OS Lite | See [README](../README.md) rationale. |

## Decisions (resolved)

1. ✅ **Altitude** — set to **124 m** (`FEEDER_ALT_M`) = ~120 m ground + 14 ft
   AGL. Refine if you ever get a survey-grade figure; 124 m is good for MLAT.
2. ✅ **ADSBExchange** — feeding it. New for this build; the `adsbx` service is
   enabled with a freshly generated `ADSBX_UUID`.
3. ✅ **SDRplay RSPduo** — kept as an option. Default build is 2× RTL-SDR v4
   (one ADS-B, one discone), but the RSPduo is documented as a swap-in for the
   discone receiver — it's a genuine upgrade there (14-bit, built-in
   preselectors → better dynamic range near YYZ/urban). See
   [docs/05 → Using the SDRplay RSPduo](05-openwebrx-discone.md). ADS-B stays on
   RTL-SDR regardless.

Net result: the new box feeds **6 aggregators** — your original 5 (FlightAware,
FR24, RadarBox, PlaneFinder, OpenSky) **plus ADSBExchange** — and the community
aggregators (adsb.lol/adsb.fi/airplanes.live/…) on top.

## Cut-over procedure

```bash
# On the new Pi, after docs/01–03 are done:
cp -r <repo>/compose/adsb/* /opt/adsb/      # includes the filled-in .env
cd /opt/adsb
docker compose up -d
docker compose logs -f                       # watch all feeders connect

# Verify each feeder is "connected"/green, then DECOMMISSION the old box so two
# stations don't feed the same keys simultaneously (it confuses FA/FR24 stats):
ssh youruser@192.168.1.14 'sudo snap stop adsb-box'   # or: sudo snap disable adsb-box
```

> Run them in parallel only briefly to confirm the new box works; then stop the
> old one. Feeding the same key from two boxes at once is the main migration
> footgun.

## Raw captured config (reference)

The exact contents pulled from the old node are reproduced inline above. The old
`dump1090-fa.conf` was just the snap's template (all values blank — the snap
injected them from its config store), so there's nothing else to carry beyond
the location and the keys listed here.

---
**Back to:** [README](../README.md) · **Deploy:** [04 — ADS-B feeder](04-adsb-feeder.md)
