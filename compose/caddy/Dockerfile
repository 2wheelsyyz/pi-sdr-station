# Custom Caddy with the DreamHost DNS provider (for ACME DNS-01 challenges).
# NOTE: caddy-dns/dreamhost (libdns/dreamhost v0.1.1) uses the OLD libdns API,
# which only compiles against Caddy < 2.10. xcaddy defaults to the LATEST Caddy,
# so we pin the core version explicitly (the builder image tag alone doesn't).
FROM caddy:2.8.4-builder AS builder
RUN xcaddy build v2.8.4 --with github.com/caddy-dns/dreamhost

FROM caddy:2.8.4
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
