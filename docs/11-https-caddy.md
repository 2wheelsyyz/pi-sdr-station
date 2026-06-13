# 11 — HTTPS (Caddy + DreamHost DNS-01)

All the web UIs are fronted by a **Caddy reverse proxy** with a **real Let's
Encrypt wildcard cert** (`*.example.org`), so every service is reachable over
trusted HTTPS with **no browser warnings**. This also fixes OpenWebRX in Firefox,
which refuses to start its audio engine without a *secure context*
([docs/05](05-openwebrx-discone.md)).

LAN-only: the hostnames resolve to the Pi's **private** address `192.168.1.230`.
Nothing is exposed to the internet.

Files: [`compose/caddy/`](../compose/caddy/).

## Subdomain → service map

| Hostname | Service | Backend on the Pi |
|----------|---------|-------------------|
| `sdr.example.org` | OpenWebRX+ | `:8073` |
| `adsb.example.org` | tar1090 (+ `/graphs1090/`) | `:8080` |
| `grafana.example.org` | Grafana | `:3000` |
| `control.example.org` | Control panel | `:8093` |
| `prometheus.example.org` | Prometheus | `:9090` |
| `station.example.org` | Homepage portal | `:80` |
| `portainer.example.org` | Portainer | `:9443` (HTTPS backend, skip-verify) |
| `hd.example.org` | Icecast HD Radio stream (`/hd.mp3`) | `:8000` |
| `acars.example.org` | ACARSHub (aircraft datalink, WebSockets) | `:8094` |
| `acars-reader.example.org` | ACARS Reader (readable multipart view) | `:8095` |

## Architecture

One Caddy site `*.example.org` obtains a **single wildcard cert** via
**ACME DNS-01** (DreamHost), then routes by `Host` header to each backend
(see the [`Caddyfile`](../compose/caddy/Caddyfile)). DNS-01 means the Pi needs
**no inbound ports** — Caddy proves domain ownership by writing a TXT record
through the DreamHost API.

```
browser ──https──► Caddy :443 (wildcard cert) ──http──► 192.168.1.230:<port>
                      └─ cert via ACME DNS-01 ──► DreamHost API (TXT record)
```

## DNS setup (two parts)

**1. LAN A records** — one per hostname, all pointing at `192.168.1.230`. These
were created via the DreamHost API (they can also be added in the panel):

```bash
# example (key from compose/caddy/.env)
curl -s "https://api.dreamhost.com/?key=$KEY&cmd=dns-add_record\
&record=sdr.example.org&type=A&value=192.168.1.230&format=json"
```

**2. pfSense rebind fix (REQUIRED on this network).** pfSense's Unbound resolver
strips RFC1918 (private) answers from public DNS by default — DNS-rebinding
protection — so LAN clients got NXDOMAIN for the `*.example.org → 192.168.1.230`
names (public resolvers like 1.1.1.1 returned them fine; the gateway was the one
filtering). Fix, in **pfSense → Services → DNS Resolver → Custom options**:

```
private-domain: "example.org"
```

That whitelists the domain so Unbound allows its private-address answers. (If you
ever move off pfSense, the equivalent is "disable DNS rebind protection" / add a
local override for the domain.)

## The custom Caddy image (and the version-pin gotcha)

Caddy needs the DreamHost DNS module compiled in. [`Dockerfile`](../compose/caddy/Dockerfile)
builds it with xcaddy — but **pin the Caddy version explicitly**:

```dockerfile
FROM caddy:2.8.4-builder AS builder
RUN xcaddy build v2.8.4 --with github.com/caddy-dns/dreamhost
FROM caddy:2.8.4
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

Why pinned: `caddy-dns/dreamhost` pulls `libdns/dreamhost v0.1.1`, which uses the
**old libdns API** and only compiles against **Caddy < 2.10**. And `xcaddy build`
defaults to the *latest* Caddy regardless of the builder image tag — so without
the explicit `v2.8.4`, the build fails with `libdns.Record has no field Value`.

## DreamHost DNS-01 gotchas

DreamHost's DNS API is slow and rate-limited. Two things matter:

- **Use ONE wildcard cert, not one-per-host.** Issuing 7 certs at once overwhelms
  it (`timed out waiting for record to fully propagate` / `expected one record,
  got 0`). The single `*.example.org` cert = one challenge = reliable.
- **Generous propagation settings** (in the `tls` block):
  `propagation_delay 2m`, `propagation_timeout 15m`, `resolvers 1.1.1.1 8.8.8.8`.
- **Stale challenge records wedge it.** The `libdns/dreamhost` module returns
  "got 0 records" if a `_acme-challenge` TXT for that name already exists. If
  issuance gets stuck, purge them and let Caddy retry:

  ```bash
  # list + remove any _acme-challenge.* TXT records via the DreamHost API
  curl -s "https://api.dreamhost.com/?key=$KEY&cmd=dns-list_records&format=json" \
   | python3 -c "import sys,json;[print(r['record']+'|'+r['value']) for r in json.load(sys.stdin)['data'] if 'acme-challenge' in r['record']]" \
   | while IFS='|' read rec val; do \
       curl -s "https://api.dreamhost.com/?key=$KEY&cmd=dns-remove_record&record=$rec&type=TXT&value=$val&format=json"; done
  ```

## Deploy / operate

```bash
sudo mkdir -p /opt/caddy && sudo chown $USER /opt/caddy
cp <repo>/compose/caddy/{Dockerfile,Caddyfile,docker-compose.yml,.env} /opt/caddy/
cd /opt/caddy
# set DREAMHOST_API_KEY in .env (gitignored; "All DNS functions" permission)
docker compose up -d --build
docker logs -f caddy        # watch for "certificate obtained successfully"
```

- Caddy owns **:80 and :443**. On :443 it serves the wildcard sites; on :80 it
  **redirects to HTTPS** — named hosts auto-redirect (e.g. `http://sdr…` → 308 →
  `https://sdr…`), and the bare IP `http://192.168.1.230/` → **301** →
  `https://station.example.org/`. Because Caddy needs :80, **Homepage was moved
  to host port `8088`** (Caddy proxies `station` → `:8088`).
- The wildcard cert **auto-renews** (single DNS-01 challenge — no multi-cert
  flakiness at renewal). Certs persist in the `caddy_data` volume.

To add a service: add its `@host`/`handle` block in the Caddyfile, add an A
record → `192.168.1.230`, `docker compose restart caddy`. No new cert needed —
the wildcard already covers it.

---
**Back to:** [README](../README.md) · **Related:** [05 — OpenWebRX](05-openwebrx-discone.md) · [09 — Dashboards](09-integration-and-dashboards.md)
