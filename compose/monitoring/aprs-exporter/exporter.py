#!/usr/bin/env python3
"""
APRS exporter for the VA3YMX station — polls the **WX3in1 Plus 2.0** over telnet
and exposes its `print stats` / `print voltage` / `print rfheard` / `print isheard`
counters as Prometheus metrics. This is the iGate's *own* numbers (RF received,
digipeated, gated to APRS-IS, decode efficiency, voltage, uptime, stations heard,
coverage distance) — far richer than counting APRS-IS traffic externally.

Metrics on :9101/metrics  (all gauges = absolute values; use rate()/increase()
in Grafana for per-minute rates).

Env: WX_HOST (192.168.1.235), WX_PORT (23), WX_USER (admin), WX_PASS (admin),
     WX_POLL_SECONDS (60), EXPORTER_PORT (9101).
"""
import os, re, socket, time
from prometheus_client import start_http_server, Gauge

HOST = os.environ.get("WX_HOST", "192.168.1.235")
PORT = int(os.environ.get("WX_PORT", "23"))
USER = os.environ.get("WX_USER", "admin")
PASS = os.environ.get("WX_PASS", "admin")
INTERVAL = int(os.environ.get("WX_POLL_SECONDS", "60"))
EXP_PORT = int(os.environ.get("EXPORTER_PORT", "9101"))

# ── metrics (gauges hold the device's absolute value; rate() them in Grafana) ──
G = lambda n, h: Gauge(n, h)
m_received   = G("aprs_rf_packets_received",      "RF packets received, CRC OK")
m_starts     = G("aprs_rf_packet_starts",         "RF packet starts detected")
m_hdr_err    = G("aprs_rf_header_errors",         "RF corrupted (header error)")
m_crc_err    = G("aprs_rf_crc_errors",            "RF corrupted (CRC error)")
m_end_err    = G("aprs_rf_endflag_errors",        "RF corrupted (end flag not found)")
m_bytes_rx   = G("aprs_rf_bytes_received",        "RF bytes received")
m_bytes_tx   = G("aprs_rf_bytes_sent",            "RF bytes sent")
m_beacons    = G("aprs_rf_beacons_sent",          "RF beacons sent")
m_msg_gated  = G("aprs_rf_messages_gated_from_is","RF messages gated from APRS-IS")
m_digi_rep   = G("aprs_digi_repeated",            "APRS packets digipeated")
m_digi_drop  = G("aprs_digi_dropped",             "APRS packets dropped by digi")
m_igated     = G("aprs_igate_rf_to_is",           "RF packets gated to APRS-IS")
m_reconnects = G("aprs_igate_reconnects",         "APRS-IS server reconnects")
m_eff_total  = G("aprs_rf_decode_efficiency_percent",      "RF decode efficiency, total")
m_eff_hour   = G("aprs_rf_decode_efficiency_hour_percent", "RF decode efficiency, last hour")
m_voltage    = G("aprs_input_voltage_volts",      "Input voltage")
m_uptime     = G("aprs_uptime_seconds",           "Device uptime")
m_connected  = G("aprs_igate_connected",          "APRS-IS connection authenticated (1/0)")
m_rf_heard   = G("aprs_rf_stations_heard",        "Distinct stations heard on RF")
m_is_heard   = G("aprs_is_stations_heard",        "Distinct stations heard on APRS-IS")
m_rf_maxdist = G("aprs_rf_max_distance_km",       "Farthest RF-heard station, km")
m_ok         = G("aprs_poll_success",             "Last telnet poll succeeded (1/0)")

STATS = [
    (m_received,  "RF packets received (CRC OK)"),
    (m_starts,    "RF packet starts detected"),
    (m_hdr_err,   "RF corrupted packets received (HEADER ERROR)"),
    (m_crc_err,   "RF corrupted packets received (CRC ERROR)"),
    (m_end_err,   "RF corrupted packets received (END FLAG NOT FOUND)"),
    (m_bytes_rx,  "RF bytes received"),
    (m_bytes_tx,  "RF bytes sent"),
    (m_beacons,   "RF beacons sent"),
    (m_msg_gated, "RF messages gated from APRS-IS"),
    (m_digi_rep,  "APRS packets repeated"),
    (m_digi_drop, "APRS packets dropped"),
    (m_igated,    "RF packets gated to APRS-IS"),
    (m_reconnects,"APRS-IS server reconnects"),
]


def _neg(data, sock):
    """Strip telnet IAC sequences; refuse all options."""
    out = bytearray(); resp = bytearray(); i = 0
    while i < len(data):
        b = data[i]
        if b == 255 and i + 2 < len(data):
            cmd, opt = data[i+1], data[i+2]
            if cmd in (251, 252): resp += bytes([255, 254, opt])   # WILL/WONT -> DONT
            elif cmd in (253, 254): resp += bytes([255, 252, opt]) # DO/DONT -> WONT
            i += 3; continue
        if b == 255: i += 2; continue
        out.append(b); i += 1
    if resp:
        try: sock.sendall(bytes(resp))
        except Exception: pass
    return bytes(out)


def _pump(sock, seconds):
    sock.settimeout(0.4); end = time.time() + seconds; got = b""
    while time.time() < end:
        try:
            d = sock.recv(4096)
            if not d: break
            got += _neg(d, sock)
        except socket.timeout:
            pass
    return got.decode("latin-1", "replace")


def query():
    """One telnet session: login, run the print commands, return {cmd: text}."""
    s = socket.create_connection((HOST, PORT), timeout=10)
    try:
        _pump(s, 2)
        s.sendall((USER + "\r\n").encode()); _pump(s, 1.0)
        s.sendall((PASS + "\r\n").encode()); _pump(s, 1.2)
        out = {}
        for cmd in ("print stats", "print voltage", "print rfheard", "print isheard"):
            s.sendall((cmd + "\r\n").encode())
            out[cmd] = _pump(s, 3.0)
        return out
    finally:
        try: s.close()
        except Exception: pass


def _int(text, label):
    m = re.search(re.escape(label) + r":\s*([0-9]+)", text)
    return int(m.group(1)) if m else None


def _count_stations(text):
    """Count 'CALLSIGN, loc, dist, areas, rxpkts, ...' rows; return (count, max_km)."""
    n = 0; maxd = 0.0
    for line in text.splitlines():
        m = re.match(r"^([A-Z0-9]{1,6}(?:-\d+)?),\s*[^,]+,\s*([^,]+),", line.strip())
        if not m:
            continue
        n += 1
        try:
            d = float(m.group(2))
            if d > maxd: maxd = d
        except ValueError:
            pass
    return n, maxd


def poll():
    out = query()
    st = out["print stats"]
    for gauge, label in STATS:
        v = _int(st, label)
        if v is not None:
            gauge.set(v)
    e1 = re.search(r"efficiency \(total\):\s*([\d.]+)%", st)
    if e1: m_eff_total.set(float(e1.group(1)))
    eh = re.search(r"efficiency \(last hour\):\s*([\d.]+)%", st)
    if eh: m_eff_hour.set(float(eh.group(1)))
    m_connected.set(1 if "connection status: authenticated" in st else 0)
    # uptime "2 days, 1 hours, 38 mins"
    days  = re.search(r"(\d+)\s*days?",  st)
    hours = re.search(r"(\d+)\s*hours?", st)
    mins  = re.search(r"(\d+)\s*mins?",  st)
    secs = (int(days.group(1))*86400 if days else 0) + (int(hours.group(1))*3600 if hours else 0) + (int(mins.group(1))*60 if mins else 0)
    if days or hours or mins: m_uptime.set(secs)
    # voltage "Input voltage: 12555 mV"
    mv = re.search(r"Input voltage:\s*(\d+)\s*mV", out["print voltage"])
    if mv: m_voltage.set(int(mv.group(1)) / 1000.0)
    # stations heard / coverage
    rf_n, rf_max = _count_stations(out["print rfheard"])
    m_rf_heard.set(rf_n); m_rf_maxdist.set(rf_max)
    is_total = re.search(r"Total:\s*(\d+)", out["print isheard"])
    if is_total:
        m_is_heard.set(int(is_total.group(1)))
    else:
        m_is_heard.set(_count_stations(out["print isheard"])[0])


if __name__ == "__main__":
    start_http_server(EXP_PORT)
    while True:
        try:
            poll(); m_ok.set(1)
        except Exception:
            m_ok.set(0)
        time.sleep(INTERVAL)
