#!/usr/bin/env bash
# Install the RTL-SDR Blog v4 driver + tools on the Pi host and blacklist the
# conflicting DVB-T kernel module.  Run on the Raspberry Pi, NOT your laptop.
# See docs/03-rtl-sdr-v4-drivers.md.
#
#   chmod +x scripts/01-install-rtlsdr-v4.sh
#   ./scripts/01-install-rtlsdr-v4.sh
#   sudo reboot          # then verify with: rtl_test
set -euo pipefail

[ "$(uname -m)" = "aarch64" ] || echo "WARN: expected aarch64 (Pi OS 64-bit); continuing anyway."

echo "==> Removing any old/conflicting rtl-sdr drivers"
sudo apt-get purge -y '^librtlsdr.*' rtl-sdr 2>/dev/null || true
sudo rm -rf /usr/lib/librtlsdr* /usr/include/rtl-sdr* /usr/local/lib/librtlsdr* || true

echo "==> Installing build deps"
sudo apt-get update
sudo apt-get install -y libusb-1.0-0-dev git cmake pkg-config build-essential

echo "==> Building RTL-SDR Blog v4 driver"
sudo rm -rf /usr/local/src/rtl-sdr-blog
sudo git clone https://github.com/rtlsdrblog/rtl-sdr-blog /usr/local/src/rtl-sdr-blog
sudo mkdir -p /usr/local/src/rtl-sdr-blog/build
cd /usr/local/src/rtl-sdr-blog/build
sudo cmake ../ -DINSTALL_UDEV_RULES=ON
sudo make -j"$(nproc)"
sudo make install
sudo ldconfig
sudo cp ../rtl-sdr.rules /etc/udev/rules.d/ 2>/dev/null || true

echo "==> Blacklisting DVB-T kernel module (dvb_usb_rtl28xxu)"
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf >/dev/null

cat <<'EOF'

Done.  Now:
  1) sudo reboot
  2) With ONE dongle plugged in:   rtl_test     (expect a 'Blog V4' tuner)
  3) Set serials, one dongle at a time:
        rtl_eeprom -s 1090       # the ADS-B dongle (tuned 1090 antenna)
        rtl_eeprom -s discone    # the discone dongle
     (unplug/replug or reboot between, then `rtl_test` should list 2 devices)
EOF
