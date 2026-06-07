# Raspberry Pi Setup — from a bare Pi to a running arm

This is the full walkthrough: grab a Pi, flash it, run three commands, done. No
prior Linux experience needed. If you just want the short version, it's:

```bash
git clone https://github.com/Jakecuso/parol6-controller.git
cd parol6-controller
bash scripts/setup_pi.sh
```

…but read on for how to get to that point on a fresh Pi.

---

## What you need

- A **Raspberry Pi 5** (a Pi 4 works too) — **64-bit**
- A **microSD card** (16GB+)
- The **PAROL6 arm** + control board + a **USB cable** Pi → board
- Power for the Pi (if powering from the arm's 24V rail, use a **24V→5V buck
  converter rated ≥5A** — never feed 24V into the Pi)
- Your **WiFi name + password**

> ⚠️ **OS requirement:** you must use **Raspberry Pi OS Trixie (Debian 13) or
> newer.** The robot kinematics library (`pinokin`) needs glibc ≥ 2.39, and the
> older *Bookworm* image (glibc 2.36) will fail with
> `… is not a supported wheel on this platform`. The setup script checks this and
> stops with a clear message if your OS is too old.

---

## Step 1 — Flash the SD card

1. Install **[Raspberry Pi Imager](https://www.raspberrypi.com/software/)** on your
   computer and open it.
2. **Choose Device:** Raspberry Pi 5.
3. **Choose OS:** `Raspberry Pi OS Lite (64-bit)`.
   - It's under **Raspberry Pi OS (other)**.
   - "Lite" = no desktop. That's what you want — it's headless and saves memory.
   - Make sure it's the current (Trixie) release, not a "Legacy/Bookworm" one.
4. **Choose Storage:** your SD card.
5. Click **Next → Edit Settings** and fill in (this makes it boot ready-to-go):
   - **Hostname:** `parol6`  → you'll reach it at `http://parol6.local:5050`
   - ✅ **Enable SSH** (use password authentication for simplicity)
   - **Username / password:** pick your own (e.g. `pi` / something memorable)
   - **Configure wireless LAN:** your WiFi name, password, and country
   - **Locale:** your timezone/keyboard
6. **Save → Write.** When it's done, put the card in the Pi.

---

## Step 2 — Boot and connect

1. Plug the **PAROL6 USB cable** into the Pi, then **power the Pi on**.
2. Give it ~60 seconds for the first boot.
3. From your computer's terminal, SSH in (use the username you set):
   ```bash
   ssh pi@parol6.local
   ```
   - Type `yes` to accept the fingerprint the first time, then your password.
   - If `parol6.local` doesn't resolve, find the Pi's IP in your router and use
     that instead (`ssh pi@192.168.x.x`).

You're now "on" the Pi from your own computer — no monitor or keyboard needed on
the Pi itself.

---

## Step 3 — Install

The Lite image doesn't ship `git`, so install it first, then clone and run:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/Jakecuso/parol6-controller.git
cd parol6-controller
bash scripts/setup_pi.sh
```

The script does everything:

- checks your Pi is compatible (64-bit, glibc, Python) and stops early if not
- sets up swap (so a low-RAM Pi doesn't choke)
- creates the Python environment + installs the PAROL6 API
- grants serial-port access
- enables mDNS (`parol6.local`)
- installs a **systemd service** so the controller **auto-starts on every boot
  and restarts itself if it ever crashes**

It takes a few minutes (the robotics libraries are large). When it finishes:

```bash
sudo reboot
```

The reboot makes the serial-port permission take effect. After it comes back up,
**you never run a command again** — it starts on its own.

---

## Step 4 — Use it

From **any device on your network** (phone, laptop, tablet), open:

```
http://parol6.local:5050
```

Open the **Manual** app and jog the arm. Done. 🎉

Power-cycle anytime — pull the plug, plug it back in — and ~20s later it's back
up on its own, connected and ready.

---

## Keeping it updated

When there's a new version, either:

- **In the app:** Settings → Software → **⟳ Update**, or
- **Over SSH:** `cd ~/parol6-controller && ./scripts/update.sh`

Both halt the arm first, pull the latest code, and restart cleanly.

---

## If something goes wrong

```bash
sudo systemctl status parol6     # is it running?
journalctl -u parol6 -n 50       # recent logs / errors
free -h                          # RAM + swap
ldd --version | head -1          # glibc (need >= 2.39)
```

If a previous install got interrupted, rebuild cleanly:
```bash
cd ~/parol6-controller && git pull && bash scripts/setup_pi.sh --clean
```

See the main [README](../README.md#troubleshooting) for more, and
[REMOTE_ACCESS.md](REMOTE_ACCESS.md) for editing/debugging the Pi from your
computer.
