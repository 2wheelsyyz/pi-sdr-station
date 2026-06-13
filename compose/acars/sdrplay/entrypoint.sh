#!/bin/bash
# Start the SDRplay API service (manages the RSPduo over USB), wait until the device
# is actually enumerable — the first claim after a host boot loads firmware and can
# take many seconds — then hand off to acarsdec. Without this, acarsdec can race the
# service and die with "no available RSP devices" (and it has restart:"no").
sdrplay_apiService >/tmp/sdrplay_api.log 2>&1 &
for i in $(seq 1 15); do
  SoapySDRUtil --probe=driver=sdrplay >/dev/null 2>&1 && break
  sleep 3
done
sleep 1
exec acarsdec "$@"
