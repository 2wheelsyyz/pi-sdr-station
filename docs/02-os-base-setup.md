# 02 — OS base setup

## Why Raspberry Pi OS Lite (64-bit, Trixie)

- First-class Pi 5 support (kernel, firmware, thermal management).
- 64-bit is required for best performance and for the arm64 Docker images we use.
- **Lite** = no desktop. This is a headless station; the desktop just wastes RAM
  and CPU. You're CLI-comfortable, so Lite is the right call.

The current Raspberry Pi OS (2025-10-01 and later) is based on **Debian 13
"Trixie"** with the Linux 6.12 LTS kernel — that's what you'll flash. Everything
here is Trixie-clean: the Docker convenience script, the RTL-SDR Blog v4 build
from source, and our containers all run fine on it. (Since our two stacks run in
Docker, the host's Debian release barely matters anyway — but flash the current
Trixie image rather than hunting down an old Bookworm one.)

(Ubuntu Server arm64 also works, but Raspberry Pi OS gets Pi-specific fixes
first and is the path of least resistance.)

## Flash & headless first boot

Use **Raspberry Pi Imager** on your laptop:

1. Choose device **Raspberry Pi 5**, OS **Raspberry Pi OS Lite (64-bit)**,
   target your SD/SSD.
2. Click the gear / **Edit Settings** and pre-configure headless access:
   - Hostname: `va3ymx-sdr` (example).
   - Enable **SSH** → use *public-key* auth (paste your laptop's
     `~/.ssh/id_ed25519.pub`).
   - Set username/password.
   - **Wireless LAN**: only if the Pi joins wifi directly. If your 900 MHz link
     presents as wired Ethernet to the Pi, leave wifi off and use the Ethernet
     port. Set your country code regardless.
   - Locale / timezone: `America/Toronto`.
3. Write, boot, and find it: `ssh <user>@va3ymx-sdr.local` (or by IP).

## First-login hardening & basics

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git curl ca-certificates vim htop tmux

# Static-ish address: reserve a DHCP lease for the Pi's MAC on your router,
# OR set a static IP. A stable IP matters since you reach it over the radio link.

sudo timedatectl set-timezone America/Toronto
```

Consider `unattended-upgrades` for security patches, and disable password SSH
once key auth works (`PasswordAuthentication no` in
`/etc/ssh/sshd_config.d/`).

## PoE power: unlock the USB current limit (do this now)

Because the Pi is powered by the **Waveshare PoE HAT (F)** through the GPIO rail
(not USB-C PD), the Pi 5 defaults to a 600 mA total USB cap — too tight for two
RTL-SDR v4 dongles. Raise it (the HAT's 4.5 A rail supports it):

```bash
# add the override (idempotent) and reboot
grep -q '^usb_max_current_enable=1' /boot/firmware/config.txt || \
  echo 'usb_max_current_enable=1' | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

After reboot, confirm power is healthy:

```bash
vcgencmd get_throttled        # want 0x0 (no undervoltage / no throttle)
```

See [docs/01 → Power](01-hardware-and-rf.md) for the why, and make sure the
upstream switch/injector is **802.3at (PoE+)**, not plain 802.3af.

## Storage & boot media

**This build boots from a SanDisk Extreme 128 GB microSD (`SDSQXAA-128G-GN6MA`).**
128 GB is far more than the ~10–15 GB this uses; the spare capacity gives the
card's controller more cells to wear-level across, which extends life under the
constant write load (readsb history + graphs1090 + OpenWebRX recordings).

To protect the card, churny scratch paths are routed to RAM — the compose files
already declare `tmpfs` mounts for `/tmp`, `/run`, and `/var/log`, so the bulk of
the high-frequency writes never touch the SD card.

If this card ever wears out (symptoms: filesystem read-only, boot failures), the
durable upgrades, cheapest first, are: a **SanDisk High/Max Endurance** microSD
(drop-in), or booting a **USB SSD** (Pi 5 boots USB natively — most reliable for
24/7, no card wear). PXE/network boot is *not* a good fit here — the Pi is behind
the 900 MHz radio link, too far from any boot server to serve a root filesystem
reliably.

## Install Docker (official convenience script)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# log out / back in (or: newgrp docker) so the group takes effect
docker version
docker compose version   # v2 plugin comes with the install
```

We use **`docker compose`** (v2, the plugin) — note the space, not the old
`docker-compose` binary.

## Directory layout on the Pi

We'll keep everything under `/opt`:

```
/opt/adsb/         # ADS-B compose stack + persistent volumes
/opt/openwebrx/    # OpenWebRX+ compose stack + config volume
```

```bash
sudo mkdir -p /opt/adsb /opt/openwebrx
sudo chown -R "$USER":"$USER" /opt/adsb /opt/openwebrx
```

You'll copy the files from this repo's [`compose/`](../compose/) into those
directories in the next docs.

## A note on the network link

Because you administer this box **over the 900 MHz link**, do two things:
- Reserve/lock its IP so you never lose it after a reboot.
- Run long jobs inside `tmux` so a link blip doesn't kill an `apt upgrade` or a
  driver build mid-flight.

---
**Next:** [03 — RTL-SDR v4 drivers](03-rtl-sdr-v4-drivers.md)
