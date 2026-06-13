#!/bin/bash
# Start the SDRplay API service (manages the RSPduo over USB), wait, then run the command.
set -e
sdrplay_apiService >/tmp/sdrplay_api.log 2>&1 &
sleep 3
exec "$@"
