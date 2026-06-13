#!/bin/sh
set -e
mkdir -p /var/log/icecast2
chown -R icecast2:icecast /var/log/icecast2 2>/dev/null || true
envsubst < /icecast.xml.tmpl > /tmp/icecast.xml
exec icecast2 -c /tmp/icecast.xml
