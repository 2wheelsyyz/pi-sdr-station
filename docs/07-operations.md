# 07 — Operations & maintenance

## Day-to-day URLs (LAN)

| Service | URL |
|---------|-----|
| ADS-B map (tar1090) | `http://<pi-ip>:8080/` |
| Stats (graphs1090) | `http://<pi-ip>:8080/graphs1090/` |
| OpenWebRX+ | `http://<pi-ip>:8073/` |

Bookmark by hostname (`http://va3ymx-sdr.local:8080/`) so a DHCP change doesn't
break your links — but a reserved IP is still wise since you reach it over the
radio link.

## Updating

Containers pin to tags, so updates are deliberate:

```bash
cd /opt/adsb       && docker compose pull && docker compose up -d
cd /opt/openwebrx  && docker compose pull && docker compose up -d
docker image prune -f          # reclaim space from old layers
```

OS patches:

```bash
sudo apt update && sudo apt full-upgrade -y
# reboot if the kernel/firmware changed; both stacks auto-start (restart: unless-stopped)
```

> After a **kernel update**, re-check `rtl_test` still finds both dongles. The
> DVB blacklist persists, but it's a 5-second sanity check worth doing.

## Health checks

```bash
docker compose -f /opt/adsb/docker-compose.yml ps        # all 'Up'/healthy?
docker compose -f /opt/openwebrx/docker-compose.yml ps
vcgencmd measure_temp                                    # keep < ~70 °C
vcgencmd get_throttled                                   # 0x0 = never throttled
rtl_test                                                 # both dongles present?
df -h /                                                  # disk not filling
```

graphs1090's **system** page also charts CPU temp, load, and feed health over
time — your first stop when something feels off.

## Backups (what's worth saving)

The OS is disposable; reproducible config is not. Back up:

- This repo (the source of truth for compose + docs).
- `/opt/adsb/.env` and `/opt/openwebrx/` config (your keys, location, gains,
  OpenWebRX profiles). **These hold your feeder keys — keep them private.**
- Optionally `/opt/adsb/.../globe_history` if you care about ADS-B history.

```bash
# quick config snapshot to your laptop
rsync -av --exclude '*history*' \
  <user>@va3ymx-sdr:/opt/adsb/.env /opt/openwebrx/ ./backups/
```

## Remote access (when you want it from outside the LAN)

You said headless-over-LAN for now. When you want it from elsewhere, **don't
port-forward these UIs to the internet** (OpenWebRX admin + open ports = risk,
and it'd hammer the 45 Mbps link). Instead:

- **Tailscale** (recommended): `curl -fsSL https://tailscale.com/install.sh | sh`
  then `sudo tailscale up`. You reach the Pi by its tailnet IP from anywhere,
  encrypted, no firewall changes. Simplest and safest.
- Or a WireGuard VPN back to your home network.

Either way the bandwidth ceiling is still your home uplink + the 900 MHz hop, so
keep OpenWebRX's FFT/fps modest ([docs/05](05-openwebrx-discone.md)).

## Troubleshooting quick table

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Container can't open SDR / "device busy" | Both stacks (or OP25) fighting for a dongle, or wrong serial | One consumer per dongle; confirm serials `1090` vs `discone` |
| `usb_claim_interface error -6` | DVB module not blacklisted | Re-do [docs/03 step 3](03-rtl-sdr-v4-drivers.md), reboot |
| ADS-B range collapses with close traffic | Gain too high | Lower `READSB_GAIN` / use autogain |
| OpenWebRX laggy / link saturated | FFT too big, fps too high, too many clients | Drop fps to ~6–10, cap max clients |
| Dongles swap roles after reboot | Selecting by index, not serial | Always select by **serial** |
| Random dropouts / USB resets | 600 mA USB cap (PoE can't PD-negotiate), or weak PoE class | Add `usb_max_current_enable=1` to `/boot/firmware/config.txt`; ensure upstream is 802.3at (PoE+) |
| Undervoltage / `get_throttled` ≠ 0x0 | PoE source too weak (802.3af) or cable-run loss | Use an 802.3at injector/switch; check the Ethernet run + HAT seating |
| Pi throttling / hot | PoE HAT fan not running / airflow blocked | Confirm the HAT (F) fan spins; keep it clear; check `measure_temp` |

## The upgrade path (recap)

1. **Now:** 2 dongles — ADS-B always-on; discone runs OpenWebRX *or* a decoder.
2. **Storage:** move to NVMe/SSD for a 24/7 logger.
3. **Concurrency:** add dongles + a discone multicoupler + powered USB hub so
   web SDR and decoders run simultaneously ([docs/06](06-decoders-and-trunking.md)).
4. **Reach:** Tailscale for secure remote access; upgrade the 900 MHz link if you
   open the WebSDR to several users.

---
**Back to:** [README](../README.md)
