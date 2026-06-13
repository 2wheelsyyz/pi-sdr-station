# 03 — RTL-SDR v4 drivers & dongle serials

The **v4 is not a drop-in for older RTL-SDRs.** It uses a different tuner
arrangement, so the generic/old `librtlsdr` shipped by some distros won't drive
it correctly (you get no device, or all-noise). You must use the **RTL-SDR Blog
v4 driver** and **blacklist the kernel DVB-T module** that grabs the dongle on
boot.

> Our Docker images bundle their own up-to-date `librtlsdr`, so the container
> talks to the hardware. But you still want the host driver + tools installed so
> you can run `rtl_test` / `rtl_eeprom` for setup and troubleshooting, and the
> **DVB blacklist is mandatory on the host regardless** — otherwise the kernel
> claims the dongle before any container can.

There's a helper script at [`scripts/01-install-rtlsdr-v4.sh`](../scripts/01-install-rtlsdr-v4.sh)
that does the steps below. Read it, then run it. Manual steps for reference:

## 1. Remove any old/conflicting driver

```bash
sudo apt purge -y '^librtlsdr.*' rtl-sdr 2>/dev/null || true
sudo rm -rf /usr/lib/librtlsdr* /usr/include/rtl-sdr* /usr/local/lib/librtlsdr*
```

## 2. Build & install the RTL-SDR Blog v4 driver

```bash
sudo apt update
sudo apt install -y libusb-1.0-0-dev git cmake pkg-config build-essential
cd /usr/local/src
sudo git clone https://github.com/rtlsdrblog/rtl-sdr-blog
cd rtl-sdr-blog
sudo mkdir -p build && cd build
sudo cmake ../ -DINSTALL_UDEV_RULES=ON
sudo make -j"$(nproc)"
sudo make install
sudo ldconfig
sudo cp ../rtl-sdr.rules /etc/udev/rules.d/   # idempotent if cmake already did it
```

## 3. Blacklist the DVB-T kernel module (mandatory)

```bash
echo 'blacklist dvb_usb_rtl28xxu' | \
  sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf
sudo reboot
```

After reboot, with **one dongle plugged in**:

```bash
rtl_test
```

You want to see it find a `Realtek RTL2832U` / **`Blog V4`** tuner and start
reading samples. `Ctrl-C` to stop. If you see "usb_claim_interface error -6",
the DVB module is still loaded — recheck the blacklist and reboot.

## 4. Give each dongle a unique serial

This is what lets ultrafeeder and OpenWebRX each grab the *right* dongle. Do this
**one dongle at a time** so you know which is which.

Plug in **only the ADS-B dongle** (the one going to your tuned 1090 antenna):

```bash
rtl_eeprom -s 1090
# answer 'y' to write; then unplug/replug (or reboot) for it to re-enumerate
```

Now unplug it, plug in **only the discone dongle**:

```bash
rtl_eeprom -s discone
```

> Serial is stored in the dongle's EEPROM (persistent). Max 8 chars — `1090`
> and `discone` are fine. Pick anything memorable; the compose files reference
> these exact strings.

Verify both, with **both plugged in**:

```bash
rtl_test          # should list 2 devices
# or, more explicitly:
rtl_eeprom        # run per-device with -d 0 / -d 1 to read each serial back
```

You should see two devices with serials `1090` and `discone`. Physically label
the dongles/cables to match.

## 5. (Optional) confirm from inside Docker later

Once a container is running you can sanity-check device access:

```bash
docker exec ultrafeeder rtl_test -d 0   # (ultrafeeder selects by serial, not index)
```

---
**Gotcha recap**
- v4 ⇒ RTL-SDR Blog driver, not distro `librtlsdr`.
- DVB module **must** be blacklisted on the host.
- Bias-tee is OFF by default — leave it off (you're not powering an LNA).
- Select dongles by **serial**, never by index (index order isn't stable across reboots/replugs).

**Next:** [04 — ADS-B feeder](04-adsb-feeder.md)
