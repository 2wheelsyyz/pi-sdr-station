# 06 — Decoders & trunking (P25 / OP25)

This covers the things OpenWebRX+ *doesn't* do well — chiefly **following a
trunked radio system** — and how to fit them around the single-dongle limit.

## Read this first: the Ontario encryption reality

Be clear-eyed before investing time. In the Toronto / YYZ area, **most primary
public-safety voice is now encrypted P25** (AES). You cannot decode encrypted
traffic with any SDR — that's by design, and OP25 will simply show
`ENCRYPTED` / no audio on those talkgroups. What *is* typically still in the
clear and worth chasing:

- **Aeronautical voice** — Pearson tower/ground/approach/ATIS. This is plain
  **AM in the airband**, not trunked — just listen in OpenWebRX
  ([docs/05](05-openwebrx-discone.md)). Easiest, most reliable local win.
- Some **fire/EMS dispatch**, **public works / transit / utility**, **railway
  (AAR channels)**, **business/GMRS**, and **ham** systems — varies by agency.
- Unencrypted **talkgroups** on otherwise-mixed trunked systems.

➡️ **Check [RadioReference](https://www.radioreference.com/) for your county
(Peel / Toronto / Halton / York)** to see which systems and talkgroups are
unencrypted *before* building a trunk follower. That tells you whether OP25 is
worth it for your specific area.

## The hardware reality (single dongle)

A trunked system has a **control channel** + several **voice channels** spread
across a band. To *follow* it, the receiver must watch the control channel and
retune to voice frequencies on the fly. A single RTL-SDR can do this **only if
the control + active voice channels fall within its ~2.4 MHz instantaneous
window** — true for many (not all) systems.

While OP25 owns the `discone` dongle, **OpenWebRX cannot use it** (one consumer
per dongle). So you choose, per session:

- **Default:** OpenWebRX+ owns `discone` (web SDR + background decoders).
- **Trunking session:** stop OpenWebRX, run OP25 on `discone`, stop it when done.

**From the web (recommended):** use **Portainer** at `https://192.168.1.230:9443/`
(see [docs/09](09-integration-and-dashboards.md)). Containers → `openwebrx` →
**Stop** frees the dongle; **Start** gives it back. The same one-click Start/Stop
applies to **every** decoder container that wants the discone — `op25`,
`acarsdec`, `dumpvdl2`, `satdump`, etc. No SSH needed.

**From the CLI (equivalent):**

```bash
# free the dongle for OP25
cd /opt/openwebrx && docker compose stop
# ... run OP25 (below) ...
# give it back to the web SDR
cd /opt/openwebrx && docker compose start
```

> Tip: also reachable from the **station portal** ([Homepage](09-integration-and-dashboards.md))
> — a Portainer tile shows running/stopped containers and links straight in.

## OP25 — quickest path (Docker)

OP25 (the boatbod fork) is the standard P25 trunk follower. Easiest is a
container so you don't pollute the host:

```bash
# example image; confirm current tag on the project page
docker run --rm -it \
  --device /dev/bus/usb \
  -e ... \
  <op25-image>   # e.g. an boatbod/op25 community image
```

You configure OP25 with a **trunk.tsv** (system control channels + system type)
and a **talkgroup CSV** (from RadioReference). Point it at the dongle by serial
`discone`. Start with a system RadioReference lists as **unencrypted** so you
get audio and know the chain works before fighting a marginal one.

> If you'd rather not containerise OP25, it also installs natively; but keep it
> off the ADS-B/OpenWebRX host's package set where practical. A container keeps
> the box clean.

## Other targeted decoders (mostly already covered)

Before standing up separate tools, remember **OpenWebRX+ already decodes**:
ACARS, VDL2, HFDL, POCSAG/FLEX pagers, AIS, SSTV/FAX, RDS, CW, RTTY, FT8/WSPR.
For most "what's this signal?" curiosity, just tune to it in OpenWebRX.

Standalone decoders worth knowing for dedicated, unattended capture:

| Want | Tool | Note |
|------|------|------|
| Aircraft text (ACARS) 24/7 | `acarsdec` / `dumpvdl2` | Dedicated, logs continuously — but needs the dongle. |
| NOAA / Meteor weather images | `satdump` | Polar sats are timed passes; would monopolise the dongle during a pass. |
| AIS ships | OpenWebRX built-in, or `rtl-ais` | Built-in is enough for casual use. |
| Trunking (P25) | **OP25** | As above. |

All of these compete for the **one** discone dongle. That's the cue for Phase 2.

## ACARS — aircraft datalink (`acarsdec` → ACARSHub)

ACARS is the VHF text datalink airliners use for ops messages (position, OOOI
times, free text, FANS/CPDLC logons). Near YYZ it's busy — a quick local test
decoded **55 messages a minute**. Two containers in [`compose/acars/`](../compose/acars/):

- **`acarsdec`** — the decoder, and a **discone mode** (control panel starts/stops it).
  It runs on the **SDRplay RSPduo via SoapySDR** (Tuner 1 50 ohm, preamp USB-powered) —
  `--soapysdr "driver=sdrplay" -a "Tuner 1 50 ohm" -m 700` — at full **14-bit**. The
  `-m 700` sets **8.4 MS/s**, so it covers **all 12 NA ACARS channels at once,
  129.125–136.975 MHz** (incl. the **136.x company channels** an RTL can't reach) —
  this is the RSPduo's reason for being. See [`sdrplay/`](../compose/acars/sdrplay/) for
  the image (SDRplay API + SoapySDRPlay3).

  > **Gotchas, hard-won:** acarsdec's *native* `--sdrplay` backend **segfaults** on any
  > `-a`/`-G` flag and wedges the device — use the **SoapySDR** backend. **Go wide, not
  > narrow:** the SDRplay only accepts sample rates matching its IF filters (~2 / 5 / 6 /
  > 7 / 8 MHz), so a 2.6 MHz span **fails** (`activateStream Init failed`) while **8.4 MHz
  > works** (8 MHz filter). A wedged RSPduo recovers with a **reboot** (USB
  > deauthorize/reauthorize sometimes works but is unreliable). **Don't `docker rm -f` a
  > streaming SDRplay container** — an unclean kill wedges the device; use `docker stop`
  > (SIGTERM + grace) so it releases cleanly. The decoder also waits for the API service
  > to enumerate the device before starting
  > ([`entrypoint.sh`](../compose/acars/sdrplay/entrypoint.sh)), else it races the
  > firmware load and dies with "no available RSP devices".
- **`acarshub`** — an always-on **web UI** at **`https://acars.example.org`** (live
  messages, aircraft list, full-text search, alerts, signal/level stats) backed by a
  SQLite message DB (persisted at `/opt/acarshub/data`). It keeps history even when
  ACARS isn't the active mode, and also listens for **VDLM2** (UDP 5555) so a future
  `dumpvdl2` plugs straight in.
- **`acars-reader`** ([`reader/`](../compose/acars/reader/)) — a small custom page at
  **`https://acars-reader.example.org`** for *reading multipart messages*, which
  ACARSHub's per-block cards scatter. It reads ACARSHub's DB **read-only** and
  re-renders it **grouped by aircraft**: one card per aircraft burst, the **full
  decoded text** (ACARSHub's stored libacars decode) on top, then each **raw block**
  below with its label, message part (MSN) and block id. Live-updating, with a
  **tail/flight search** that queries the full history. Reuses the stored decode
  (doesn't re-decode), so it's a thin read-only view.

```bash
sudo mkdir -p /opt/acars /opt/acarshub/data
cp <repo>/compose/acars/docker-compose.yml /opt/acars/
cd /opt/acars && docker compose up -d acarshub          # web UI (always on)
docker compose create acarsdec                          # decoder: created stopped…
# …then activate "ACARS" from the control panel when you want it (it frees the dongle)
```

`acarsdec` uses `restart: "no"` on purpose, so it doesn't grab the dongle at boot —
**OpenWebRX is the default discone consumer**; bring ACARS up on demand. Data path is
`acarsdec → JSON/UDP :5550 → acarshub → messages.db`, all on a private `acars` Docker
network. No feeder keys — this is **local-only** (no airframes.io feed); the discone
is shared, so 24/7 community feeding isn't the goal here.

## HD Radio (NRSC-5 / IBOC) — `nrsc5` → Icecast

OpenWebRX decodes analog FM and **RDS**, but not the **digital HD Radio**
sidebands (the IBOC carriers above and below the analog centre). Lots of GTA
stations run HD — e.g. **98.1 CHFI** (HD1 main, HD2 secondary). Decode them with
[`nrsc5`](https://github.com/theori-io/nrsc5) and serve the audio over the LAN
through a small **Icecast** server, so any media player can listen.

**Two pieces, both in this repo:**

- `compose/icecast/` — a persistent Icecast2 server (port **8000**, mount
  **`/hd.mp3`**). It's the streaming *destination* and stays running.
  Passwords live in `compose/icecast/.env` (gitignored; `openssl rand -hex 12`).
  Runs as the `icecast2` user via the config's `<changeowner>` (Icecast refuses
  to run as root).
- `compose/nrsc5/` — the `va3ymx/nrsc5:latest` image (builds nrsc5 + the
  rtl-sdr-blog driver, plus `ffmpeg`). Its `hdstream` helper pipes
  `nrsc5 … -o - -t raw` → `ffmpeg` (s16le 44100 stereo → MP3 128 k) → Icecast.

**Bring up the destination once:**

```bash
cd /opt/icecast && docker compose up -d --build      # Icecast on :8000
```

**Tune a station from the CLI** (`scripts/hdradio.sh`, runs on the Pi):

```bash
./hdradio.sh 98.1 0      # 98.1 CHFI, program 0 = HD1   (1 = HD2, …)
```

The wrapper pauses OpenWebRX (HD shares the **discone** dongle, device index
**1** — nrsc5 `-d` is index-based, not by serial), runs the decoder with bias-tee
on (`-T`), and restarts OpenWebRX on `Ctrl-C`. While it runs, listen at:

- `http://192.168.1.230:8000/hd.mp3` (LAN), or
- **`https://hd.example.org/hd.mp3`** (via Caddy — see [11](11-https-caddy.md)).

Sanity check from `nrsc5`'s log: `Synchronized`, a positive **MER** (dB), low
**BER**, and station/title/artist metadata mean a clean lock. CHFI locks at
MER ≈ 7 dB through the FM-trap chain and decodes HD1/HD2 cleanly.

> **One consumer per dongle.** HD Radio and OpenWebRX can't both use the discone
> at once — the wrapper handles the hand-off. Concurrent web-SDR + HD decode is a
> Phase 2 (splitter) capability, below.

## Phase 2 — run things concurrently (recommended upgrade)

To stop time-sharing, add hardware:

1. **More RTL-SDR v4 dongles** (cheap, ~1 per concurrent job). Give each a unique
   EEPROM serial (e.g. `op25`, `acars`, `wxsat`).
2. **A discone multicoupler** so the D3000N feeds several receivers at once
   without big signal loss — see recommendations below.
3. **A powered USB hub** once you exceed two dongles, to stay within the Pi's USB
   power budget.

Then OpenWebRX, OP25, and a couple of standalone decoders can all run at once,
each pinned to its own dongle by serial. The Pi 5 has the CPU headroom; the
constraints are USB power and antenna signal split.

### Multicoupler — what to buy

A passive splitter loses ~3.5 dB per port (2-way) and offers limited isolation;
RTL-SDR dongles also leak LO/digital hash back out their antenna port, so
**port-to-port isolation matters** — it stops one dongle's noise from polluting
the others. An **active multicoupler** (a splitter with a low-noise distribution
amp) restores the split loss and provides that isolation. Near YYZ/urban Toronto
you're in a strong-signal environment, so you want **modest gain** (just enough to
offset the split) to avoid overload — not a high-gain preamp.

| Pick | Coverage | Connectors | Notes |
|------|----------|-----------|-------|
| **Stridsberg MCA204M** (4-port active) | 25 MHz–1 GHz | N in / **BNC** out | The enthusiast standard. Near-unity gain (+2/−1 dB), 22 dB isolation, high overload point. 8-port **MCA208M** if you grow. |
| **Mini-Circuits ZFSC-4-1WB** (passive) | 1–1000 MHz | **BNC** (or order **SMA**) | Excellent isolation (~25 dB) and low loss; passive so ~6 dB split loss on 4-way. Available SMA-connectorized (`…-S+`). |
| **Mini-Circuits ZFSC-2-2500-S+** (2-way, passive) ✅ *ordered* | 10–2500 MHz | **SMA-female** ×3 | Direct SMA in/out → near-zero adapters. Transformer-isolated (covers VHF→L-band in one part). Ordered direct from Mini-Circuits. |
| **Electroline EDA2800** (budget) | 5–1000 MHz | **F** (75 Ω) | CATV amp/splitter, ~$25; works fine for RX but F-type + 75 Ω means adapters and a slight mismatch. |

### Connectors — minimizing junctions

Your instinct is right: the discone (**D3000N = N-female**) and the dongles
(**RTL-SDR v4 and the RSPduo = SMA**) are SMA at the receiver end, while the good
active multicouplers are **BNC**-out — so naively you'd stack a BNC→SMA barrel on
every port. Don't. Two clean ways to keep junctions to a minimum:

- **Use pigtails, not stacked adapters.** A single **BNC-male → SMA-male RG316
  pigtail** makes the multicoupler-output→dongle transition *one* properly-made
  part instead of a barrel adapter + a separate cable. One pigtail per port. (The
  RTL-SDR Blog adapter/pigtail kit covers the odd N/BNC/SMA transition cleanly.)
- **For just two receivers, go all-SMA:** one **N-female→SMA pigtail** off the
  discone into an **SMA 2-way isolated splitter**, then SMA straight to the two
  dongles → exactly **one** adapter in the whole chain.

**Splitter:** ✅ **Mini-Circuits ZFSC-2-2500-S+** ordered direct from
Mini-Circuits (SMA, 10–2500 MHz — covers the whole discone range).

**Cables you'll also want** (all three of its ports are **SMA-female**):
- **1× N-male → SMA-male** RG316 pigtail — discone (N-female) into the splitter
  input. *This is the only adapter in the chain.*
- **2× SMA-male → SMA-male** short coax — splitter outputs to the two receivers
  (RTL-SDR v4 and RSPduo are both SMA-female).

> Keep the runs short (RG316/RG402 pigtails). Full discone chain order:
> **antenna → FM band-stop → Uputronics WB preamp → ZFSC splitter → receivers**
> (filter before the LNA; LNA before the split). The preamp is **USB-C powered**
> — the splitter blocks DC so a dongle's bias-tee can't reach it. See the
> [system diagram](10-system-diagram.md).

> Reality check: in a *receive* path at VHF/UHF, a quality adapter costs ~0.1 dB
> and a negligible reflection — the reason to minimize isn't signal loss, it's
> mechanical (every junction is a potential intermittent + moisture-ingress
> point). Pigtails win on both counts. Near the city you have signal to spare, so
> a passive splitter's loss is a non-issue; the active multicoupler is about
> **isolation**, not gain.

> **The 1 GHz ceiling** on the Stridsberg/Electroline is fine for virtually all
> VHF/UHF scanning, trunking, ACARS, pagers, AIS, and ham — the busy bands. You'd
> only feel it for L-band (>1 GHz) on the discone. Your **ADS-B is on its own
> antenna**, unaffected either way. Keep the FM band-stop filter inline ahead of
> the multicoupler.

---
**Next:** [07 — Operations & maintenance](07-operations.md)
