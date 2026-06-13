#!/bin/bash
# Start the SDRplay API service, WAIT until the device is enumerable (firmware load is
# slow just after a host boot), then run rsp_tcp. Probing first avoids the wedge that a
# bare rsp_tcp retry causes when it hits a not-yet-ready device.
sdrplay_apiService >/tmp/sdrplay_api.log 2>&1 &
for i in $(seq 1 15); do
  SoapySDRUtil --probe=driver=sdrplay >/dev/null 2>&1 && break
  sleep 3
done
sleep 1
exec rsp_tcp "$@"
