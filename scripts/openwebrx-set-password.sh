#!/usr/bin/env bash
# Set the OpenWebRX admin password from compose/openwebrx/.env.
#
# This OpenWebRX+ image keeps its login in users.json (it does NOT read the
# password from env), so we push the password in via its admin CLI. Run on the
# Pi after editing the password in .env:
#
#   ./scripts/openwebrx-set-password.sh                  # uses /opt/openwebrx/.env
#   ./scripts/openwebrx-set-password.sh /path/to/.env
set -euo pipefail

ENV_FILE="${1:-/opt/openwebrx/.env}"
[ -f "$ENV_FILE" ] || { echo "no env file at $ENV_FILE"; exit 1; }
set -a; . "$ENV_FILE"; set +a
: "${OPENWEBRX_ADMIN_USER:?set OPENWEBRX_ADMIN_USER in $ENV_FILE}"
: "${OPENWEBRX_ADMIN_PASSWORD:?set OPENWEBRX_ADMIN_PASSWORD in $ENV_FILE}"

U="$OPENWEBRX_ADMIN_USER"; P="$OPENWEBRX_ADMIN_PASSWORD"

if docker exec openwebrx openwebrx admin hasuser "$U" >/dev/null 2>&1; then
  printf '%s\n%s\n' "$P" "$P" | docker exec -i openwebrx openwebrx admin resetpassword "$U" >/dev/null
else
  printf '%s\n%s\n' "$P" "$P" | docker exec -i openwebrx openwebrx admin adduser "$U" >/dev/null
fi
echo "OpenWebRX login for '$U' set from $ENV_FILE"
