#!/usr/bin/env bash
# hdradio <freq-MHz> [program] — stream an HD Radio station to Icecast.
#   program: 0=HD1 (default), 1=HD2, 2=HD3, …
#
# Run on the Pi. It pauses OpenWebRX (shares the discone dongle), decodes the
# station with nrsc5, pushes the audio to Icecast, and restarts OpenWebRX on exit.
#   ./hdradio.sh 98.1 0       # CHFI HD1
#   then listen:  https://hd.example.org/hd.mp3   (or http://192.168.1.230:8000/hd.mp3)
set -euo pipefail

FREQ="${1:?usage: hdradio <freq-MHz> [program 0=HD1,1=HD2,...]}"
PROG="${2:-0}"
ENVF="${ICECAST_ENV:-/opt/icecast/.env}"
[ -f "$ENVF" ] || { echo "missing $ENVF (icecast source password)"; exit 1; }
set -a; . "$ENVF"; set +a

# Clear any prior stream container (named or stray) — `docker run -i` doesn't always
# forward Ctrl-C, so an earlier run can survive and hold both the dongle and the
# /hd.mp3 mount (→ "usb_claim error -6" + Icecast "403 Forbidden" on the next run).
docker ps -aq --filter ancestor=va3ymx/nrsc5:latest | xargs -r docker rm -f >/dev/null 2>&1 || true

echo "Pausing OpenWebRX (frees the discone dongle)…"
docker stop openwebrx >/dev/null 2>&1 || true
# On exit (incl. Ctrl-C): stop the stream container explicitly, then restore the web SDR.
trap 'docker stop hdradio >/dev/null 2>&1 || true; echo; echo "Restarting OpenWebRX…"; docker start openwebrx >/dev/null 2>&1 || true' EXIT INT TERM

echo "Streaming ${FREQ} MHz HD$((PROG+1)) → https://hd.example.org/hd.mp3   (Ctrl-C to stop)"
docker run --rm -i --name hdradio --entrypoint /usr/local/bin/hdstream \
  -v /dev/bus/usb:/dev/bus/usb --device-cgroup-rule 'c 189:* rwm' \
  -e ICECAST_SOURCE_PASSWORD="$ICECAST_SOURCE_PASSWORD" \
  -e ICECAST_HOST=192.168.1.230 -e NRSC5_DEVICE=1 \
  va3ymx/nrsc5:latest "$FREQ" "$PROG"
