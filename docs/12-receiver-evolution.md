# 12 — Receiver evolution: RTL-SDR → RSPduo → Airspy R2

> **Status: work in progress.** The discone / general-RF receiver has been through three
> SDRs. This page records the journey, **why** each move was made, what works today, and
> the **lessons learned** — especially the painful ones — so nobody re-learns them. ADS-B
> stays on its own RTL-SDR v4 (`1090`) the whole time; this is only about the *discone*.

## The path

| Stage | Receiver | Status | Why |
|------|----------|--------|-----|
| 1 | RTL-SDR Blog v4 (`discone`) | original | cheap, simple, best-supported — but 8-bit and ~2.4 MHz |
| 2 | **SDRplay RSPduo** | **current** | 14-bit, built-in preselection filters, up to 10 MHz wide |
| 3 | **Airspy R2** | **planned** (ordered) | native OpenWebRX support — escape the SDRplay-in-Docker pain |
| 4 | Airspy **+** RTL via splitter | future | two concurrent receivers on one antenna |

## Stage 1 → 2 — why the RSPduo

The RTL-SDR v4 is a great starting point but it's **8-bit** with ~**2.4 MHz** of usable
bandwidth. In a strong-signal urban environment near YYZ that means easy overload, and
2.4 MHz can't span the ACARS band. The **RSPduo** brings a **14-bit ADC**, **built-in
preselection filters** (dynamic-range/overload headroom), and **up to 10 MHz** of tuning
width — enough to watch the whole ACARS spread at once.

## What works today (RSPduo)

- **ACARS — the headline win.** `acarsdec` on the RSPduo via **native SoapySDR**
  (Tuner 1 50 Ω, preamp USB-powered), **14-bit**, decoding **all 12 North-American ACARS
  channels at once — 129.125–136.975 MHz at 8.4 MS/s** (including the 136.x company
  channels no RTL can reach). See [decoders & ACARS](06-decoders-and-trunking.md).
- **OpenWebRX** — on the RSPduo via an **rtl_tcp bridge** (8-bit; the connector can't
  drive SDRplay natively — see below). See [OpenWebRX](05-openwebrx-discone.md).
- Both are exclusive **"discone modes"** in the [control panel](09-integration-and-dashboards.md)
  — only one consumer uses the dongle at a time, until the splitter (Stage 4).

## Lessons learned — SDRplay in Docker is the hard part

The RSPduo's RF is excellent; getting it to behave in containers was a slog. The findings,
so they're never re-derived:

1. **acarsdec's native `--sdrplay` backend is broken.** It segfaults on any antenna/gain
   flag and wedges the device. Drive the RSPduo through **SoapySDR** instead
   (`acarsdec --soapysdr "driver=sdrplay" -a "Tuner 1 50 ohm"`).
2. **Go WIDE, not narrow.** The SDRplay only accepts sample rates that match its IF
   filters (~2 / 5 / 6 / 7 / 8 MHz). A 2.6 MHz span **fails** (`activateStream Init
   failed`); **8.4 MHz works** (8 MHz filter). Force it with `acarsdec -m 700`.
3. **OpenWebRX's `soapy_connector` cannot drive the RSPduo.** It fails `sdrplay_api_Init`
   at *every* sample rate — ruled out (with tests) rate, gain, device serial, **and**
   SoapySDRPlay3 module version. acarsdec works through the identical module, so the fault
   is in the connector's compiled stream-setup. It can't be reconfigured → use the bridge.
4. **The bridge = rsp_tcp.** [`compose/rsp/bridge/`](../compose/rsp/bridge/) runs
   **ON5HB/rsp_tcp_v2** (not SDRplay's official RSPTCPServer, which has *no* gain control
   and gives a weak −42 dBFS). It serves the RSPduo as **rtl_tcp**, which OpenWebRX's
   rock-solid rtl_tcp connector consumes (8-bit). Its entrypoint **probes for device
   readiness before launching** rsp_tcp — a bare launch on a not-yet-enumerated SDRplay
   wedges it. It exposes real gain (`-l` LNA, `-g` IF, `-G` AGC); the bridge runs AGC.
5. **HD Radio (nrsc5) is blocked on the RSPduo.** nrsc5 needs *exactly* 1.488 MHz; the
   SDRplay-over-rtl_tcp only approximates it via decimation, so HD never locks even with a
   strong signal (it's rate-critical). HD Radio is the **one casualty** of this migration —
   it needs a device nrsc5 drives natively at the exact rate (an RTL, or the Airspy).
6. **The device wedges easily.** A failed stream `Init`, or a `docker rm -f` (force-kill)
   of an SDRplay container, wedges the RSPduo. Recover with a **reboot** (USB
   deauthorize/reauthorize is unreliable). Operationally: **always `docker stop` (clean),
   never `docker rm -f`** an SDRplay container. The control panel uses clean stop.
7. **One API service per device.** Two `sdrplay_apiService` instances fight over the one
   RSPduo. The decoder containers each bundle the service and run exclusively (one mode at
   a time), so they never overlap.

## Stage 2 → 3 — why the Airspy R2

The friction above is relentless, so an **Airspy R2** is on the way. It's **native in
OpenWebRX via SoapySDR** (the `libairspySupport.so` module already ships in the image) —
**no proprietary API daemon, no rtl_tcp bridge, no soapy_connector bug, full gain
control.** It should simply work for OpenWebRX, and — because nrsc5/OpenWebRX can address
it directly at sane rates — it's the path to **getting HD Radio back**. Its 10 MSPS keeps
the wide-coverage ACARS win. When it lands: OpenWebRX → native SoapySDR `airspy` source;
re-test nrsc5 on it; retire the rsp_tcp bridge.

## Stage 4 — the splitter (future, once the Airspy is stable)

Add the Mini-Circuits ZFSC-2-2500-S+ splitter so the discone feeds **two receivers at
once**: the **Airspy** (web SDR / wide spectrum) **and** the freed **RTL-SDR v4** (a
dedicated decoder — ACARS, OP25, etc.), running **concurrently**. That finally beats the
single-consumer limit (today only one discone mode runs at a time). With ADS-B on its own
dongle, that's **three receivers** on the Pi. See [decoders → Phase 2](06-decoders-and-trunking.md)
and the [system diagram](10-system-diagram.md).
