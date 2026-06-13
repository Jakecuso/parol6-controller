# Raspberry Pi Setup — from a bare Pi to a running arm

Take a fresh Pi to a fully running PAROL6 in about 15 minutes — no prior Linux
experience needed. Once you're connected to the Pi, the whole install is:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/Jakecuso/parol6-controller.git
cd parol6-controller
bash scripts/setup_pi.sh
```

Everything below explains how to get there and what each part does.

---

## Which Pi to get

- ✅ **Raspberry Pi 5** (recommended) — 4GB or 8GB. Best for the kinematics math.
- ✅ **Raspberry Pi 4** (4GB+) — works fine, a little slower.
- ❌ **Not** a Pi 3, Pi Zero, or any 32-bit board — the robot libraries need a
  modern **64-bit** Pi.

> ⚠️ **OS requirement — this one matters:** use **Raspberry Pi OS Trixie
> (Debian 13) or newer, 64-bit**. The kinematics library (`pinokin`) needs
> glibc ≥ 2.39; the older *Bookworm* image (glibc 2.36) fails with
> `… is not a supported wheel on this platform`. The setup script checks this and
> stops early with a clear message if your OS is too old.

### What else you need

- A **microSD card**, 16GB or larger
- The **PAROL6 arm** + control board + a **USB cable** (Pi → control board)
- **Power** for the Pi. If powering from the arm's **24V rail, use a 24V→5V buck
  converter rated ≥5A** — never feed 24V into the Pi.
- Your **WiFi name + password**

---

## Step 1 — Flash the SD card (on your computer)

1. Install **[Raspberry Pi Imager](https://www.raspberrypi.com/software/)** and open it.
2. **Choose Device:** your Pi (e.g. Raspberry Pi 5).
3. **Choose OS:** **Raspberry Pi OS Lite (64-bit)** — it's under *Raspberry Pi OS
   (other)*. "Lite" = no desktop (headless), which is exactly what you want. Make
   sure it's the current **Trixie** release, not a Legacy/Bookworm one.
4. **Choose Storage:** your SD card.
5. Click **Next → Edit Settings** and fill these in so the Pi boots ready-to-go:
   - **Hostname:** `parol6` → you'll reach it at `http://parol6.local:5050`
     *(whatever you set here is the name you'll use — examples below assume `parol6`)*
   - **Set username + password:** pick your own (e.g. `pi` + a memorable password) —
     you'll use these to log in.
   - **Configure wireless LAN:** your WiFi name, password, and country — *this is how
     it gets online, no cable needed.*
   - **Enable SSH** (Services tab) → **Use password authentication** — *lets you set
     it up from your computer without a monitor.*
   - **Locale:** your timezone + keyboard.
6. **Save → Write.** When it finishes, put the card in the Pi.

---

## Step 2 — First boot (at the Pi)

1. Plug the **PAROL6 USB cable** into the Pi.
2. **Power the Pi on.**
3. Wait ~60 seconds for the first boot. It joins your WiFi automatically using the
   settings from Step 1.

That's the whole "Pi end" — **no monitor or keyboard needed on the Pi itself.**

---

## Step 3 — Connect once and install

You connect to the Pi **one time** to run the installer. Pick whichever is easier:

**Option A — SSH from your computer (recommended, no monitor):**
```bash
ssh pi@parol6.local
```
Use the username you set. Type `yes` to accept the fingerprint, then your password.
*(If `parol6.local` doesn't resolve, find the Pi's IP in your router and use
`ssh pi@192.168.x.x`.)*

**Option B — directly on the Pi (no SSH):** plug a monitor + USB keyboard into the
Pi and log in at the console with the username/password you set.

Then, either way, run the installer:
```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/Jakecuso/parol6-controller.git
cd parol6-controller
bash scripts/setup_pi.sh
```

The script does everything:
- checks the Pi is compatible (64-bit, glibc, Python) and stops early if not
- sets up swap so a low-RAM Pi doesn't choke
- creates the Python environment + installs the PAROL6 API
- grants serial-port access
- enables mDNS (`parol6.local`)
- installs a **systemd service** so the controller **auto-starts on every boot and
  restarts itself if it ever crashes**

It takes a few minutes (the robotics libraries are large). When it finishes:
```bash
sudo reboot
```
The reboot makes the serial-port permission take effect. **After this you never run
a command again** — the controller starts on its own at every power-on.

---

## Step 4 — Use it (from any device)

Open this from **any phone, laptop, or tablet on the same network**:
```
http://parol6.local:5050
```
Open the **Manual** app and jog the arm. Done. 🎉

Power-cycle anytime — pull the plug, plug it back in — and ~20s later it's back up
on its own, connected and ready. **Daily use never needs SSH or a screen — just the
web UI in a browser.**

---

## Optional — getting back into the Pi (SSH)

You only need this to **update or troubleshoot**, never for normal driving.
Reconnect anytime with:
```bash
ssh pi@parol6.local
```
(or the Pi's IP). For VS Code remote editing and reaching the Pi securely from
outside your home, see **[REMOTE_ACCESS.md](REMOTE_ACCESS.md)**.

---

## Keeping it updated

- **No SSH — in the app:** Settings → Software → **⟳ Update**, or
- **Over SSH:** `cd ~/parol6-controller && ./scripts/update.sh`

Both halt the arm first, pull the latest code, and restart cleanly.

---

## If something goes wrong

SSH in (Option A above), then:
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
See the main [README](../README.md#troubleshooting) for more.
