# 05 — OpenWebRX+ on the discone

**OpenWebRX+** (the actively-developed [luarvique fork](https://github.com/luarvique/openwebrx))
is the web SDR for the discone dongle. From any browser on your LAN you get a
live waterfall you can tune across HF–UHF, demodulate AM/FM/SSB/CW, **and** it
runs a deep set of **built-in background decoders** on the side: ACARS, VDL2,
HFDL, POCSAG/FLEX pagers, AIS, RDS, SSTV/FAX, FT8/WSPR, CW, RTTY, and more.

That decoder set is why a *single* discone dongle already covers most of the
"interesting signals" goal — without extra hardware. (Trunked P25
voice-following is the exception → [docs/06](06-decoders-and-trunking.md).)

Files: [`compose/openwebrx/docker-compose.yml`](../compose/openwebrx/docker-compose.yml).

## Bring it up

```bash
cp -r <this repo>/compose/openwebrx/* /opt/openwebrx/
cd /opt/openwebrx
docker compose up -d
docker compose logs -f
```

Open **`http://<pi-ip>:8073/`**. First run: log in to the **Settings** UI with
the default admin account (the image prompts you / set via env — see the compose
file comments) and **change the password immediately** since it's reachable on
your LAN.

## Point it at the `discone` dongle (not the 1090 one)

In **Settings → SDR devices**, add an **RTL-SDR** device and set its
**Device identifier / serial** to **`discone`**. This is what stops OpenWebRX
from grabbing the ADS-B dongle. Confirm the ADS-B stack keeps running after you
start OpenWebRX — they should never touch each other's hardware.

> One consumer per dongle: if OpenWebRX can't open the device, make sure no
> decoder from [docs/06](06-decoders-and-trunking.md) is currently holding
> `discone`.

## Using the SDRplay RSPduo (optional upgrade for the discone)

You have an **SDRplay RSPduo** on hand. For the discone/general-RF role it's a
real step up from an RTL-SDR — 14-bit ADC and **built-in preselection filters**
give much better dynamic range and overload resistance, which matters in your
strong-signal environment near YYZ and urban Toronto. It also covers 1 kHz–2 GHz.
**ADS-B stays on the RTL-SDR** either way (RTL-SDR is the simplest, best-supported
path there — no benefit to swapping it).

This is documented as a **swap-in**: run the discone on *either* the RTL-SDR
(`discone` serial, the default everywhere else in these docs) *or* the RSPduo.
Pick one as OpenWebRX's device.

### Why it needs a bridge (NOT native SoapySDR)

The obvious approach — point OpenWebRX's SoapySDR `sdrplay` source at the RSPduo —
**does not work.** OpenWebRX's `soapy_connector` fails `sdrplay_api_Init` on the
RSPduo at *every* sample rate, even though `acarsdec` drives the dongle fine through
the **identical** SoapySDRPlay3 module (this was isolated exhaustively: ruled out
rate, gain, device serial, and module version). The fault is in the compiled
connector's stream setup, which can't be reconfigured.

The working path is an **rsp_tcp bridge**: SDRplay's `RSPTCPServer` (API v3) talks to
the SDRplay API *directly* — bypassing soapy_connector — and serves the RSPduo as a
plain **rtl_tcp** stream, which OpenWebRX's rock-solid rtl_tcp connector consumes.
Trade-off: **8-bit** (vs the RSP's 14-bit), but reliable; the RSPduo's preselection
filters still improve the front end. (ACARS keeps full 14-bit — it runs `acarsdec`
native, where SoapySDR works.)

### How it's wired

- **`compose/rsp/bridge/`** builds `va3ymx/rsp-tcp` — **ON5HB/rsp_tcp_v2** (not SDRplay's
  official RSPTCPServer, which has *no* gain control and gives a weak −42 dBFS). ON5HB
  exposes `-l` (LNA), `-g` (IF gain), `-G` (AGC); the bridge runs `-l 2` (AGC) — tune
  against the waterfall. It serves the RSPduo as rtl_tcp on **`rsp-tcp:1234`**, and its
  entrypoint **probes the device for readiness before launching rsp_tcp** — a bare
  rsp_tcp hitting a not-yet-enumerated SDRplay wedges it (needs a reboot).

> **HD Radio (nrsc5) can't use this bridge.** nrsc5 needs *exactly* 1.488 MHz and the
> SDRplay-over-rtl_tcp only approximates it via decimation — so HD never locks even with
> a strong signal. HD Radio needs a device nrsc5 drives natively at the exact rate (an
> RTL-SDR, or possibly the Airspy). It's the one casualty of moving the discone to the RSPduo.
- **OpenWebRX** ([`compose/openwebrx/`](../compose/openwebrx/)) — its discone device
  in `settings.json` is **`type: rtl_tcp, remote: rsp-tcp:1234`** (2 MHz profiles;
  the SDRplay rejects odd rates like 2.4 MHz). The bridge is a service in the same
  compose, and both join the `sdr` Docker network.
- **Physical:** antenna on the **RSPduo Tuner 1 50 Ω SMA**, preamp **USB-powered**,
  RSPduo **bias-T off**.

### Using it (control panel)

The **"Web SDR (OpenWebRX)"** mode has `with: [rsp-tcp]`, so activating it starts the
**bridge *and* OpenWebRX together**; **release** stops both and frees the RSPduo for
ACARS. Switch modes from the [control panel](09-integration-and-dashboards.md) — it
uses clean `docker stop` (force-killing an SDRplay container wedges the device).

### Gotchas & how it fits the plan

- **Dual-tuner mode is too CPU-heavy for a Pi** — even a Pi 5. Plan on
  **single-tuner**: the RSPduo is one excellent receiver, not two.
- Because it's one receiver, the RSPduo alone doesn't beat the
  single-discone-consumer limit. The high-value **Phase 2** combo is: **RSPduo on
  the discone for OpenWebRX** + your **freed RTL-SDR v4 as a decoder**, both fed
  from the discone via the [splitter](06-decoders-and-trunking.md) → web SDR and a
  decoder running concurrently, with ADS-B on the third receiver.
- If you run both concurrently, cable the RSPduo to one splitter output and the
  RTL-SDR decoder to the other (see the [system diagram](10-system-diagram.md)).

## Profiles to set up (good starting set near YYZ)

Create profiles (band presets) under the device. Each profile = a centre
frequency + sample rate (the dongle sees ~2.4 MHz at once). Suggested:

| Profile | Centre / range | Why, near YYZ |
|---------|----------------|---------------|
| **Airband (AM)** | 118–137 MHz (a 2.4 MHz slice, e.g. centred 124 MHz) | Pearson tower/ground/approach/ATIS — plain AM voice, easy and very active. |
| **2 m ham** | 144–148 MHz | Local repeaters, simplex. |
| **VHF marine / business** | ~150–160 MHz | AIS (built-in decoder), marine, business radio. |
| **70 cm ham / UHF** | 430–450 MHz | Repeaters; near public-safety bands. |
| **Pagers** | ~929–932 MHz | POCSAG/FLEX built-in decoder — surprisingly active. |
| **ACARS** | 131.55 / 130.025 / 130.45 MHz | Aircraft text msgs — built-in ACARS decoder. |
| **FM broadcast** | 88–108 MHz | Your FM band-stop filter attenuates this, but useful to confirm the trap is working / RDS demo. |
| **HF (SSB/digital)** | needs the v4 direct-sampling/HF range, antenna permitting | The discone is poor on HF, but the v4 can do 0.5–24 MHz; mostly for experimentation. |

Toronto airband and pagers will be your most rewarding everyday listens.

## Gain with the wideband preamp in line

The discone path has the **Uputronics Wideband preamp** (LNA) ahead of the
splitter, so there's ~20 dB of gain before the receiver. **Turn the device RF
gain down** in OpenWebRX (and per-profile) — with an LNA + a wideband antenna in
urban Toronto, leaving the dongle at high gain will overload it (you'll see a
raised noise floor and intermod "ghost" signals). Start low and raise only until
weak signals appear; if a band looks hashy, drop that profile's gain. The
**RSPduo** handles this best thanks to its built-in preselectors. The preamp
itself is powered via **USB-C (5 V)** — not bias-tee, since the splitter blocks
DC (see [docs/10](10-system-diagram.md)).

## Tune for the 900 MHz / 45 Mbps link

OpenWebRX streams a waterfall + audio **per connected browser**. To keep it light
on the radio link, set (Settings → per-profile / general):

- **FFT size**: keep modest (e.g. 4096), not huge.
- **Waterfall / FFT frame rate** ("fps"): lower it (e.g. 6–10 fps) — this is the
  single biggest bandwidth lever.
- **Audio compression**: leave the default compressed audio on (don't force
  uncompressed).
- **Max clients**: cap it (e.g. 2–3) so one forgotten open tab can't saturate
  the link.

With those, a single listener is ~0.3–1 Mbps — invisible on 45 Mbps. You only
need to care if you later expose it to multiple outside users.

## Recordings & decoder output

OpenWebRX+ can log decoder output (ACARS/AIS/pager messages, SSTV images, an MP3
recorder). On microSD, point recording paths at a volume on SSD or prune
regularly so you don't wear the card — see the compose file's volume comments.

---
**Next:** [06 — Decoders & trunking](06-decoders-and-trunking.md)
