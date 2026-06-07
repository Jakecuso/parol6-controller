# PAROL6 Controller

A self-hosted web controller for the **[PAROL6](https://source-robotics.com/products/parol6)**
6-axis desktop robotic arm. Runs headless on a **Raspberry Pi**, plug-and-play:
power it on and it auto-starts, connects to the arm, and serves a phone-friendly
control panel on your local network.

It's built like a little phone — a home screen of **mini apps**, each
self-contained:

| App | What it does |
|-----|--------------|
| 🕹 **Manual** | Jog joints or Cartesian X/Y/Z/RX/RY/RZ with a speed dial |
| 🎮 **Remote** | Drive the arm with a Bluetooth/USB gamepad + programmable buttons |
| 🦾 **3D View** | Live 3D model of the arm that mirrors the real joints (from the URDF) |
| 📊 **Telemetry** | Live joint angles, TCP pose, and status |
| 💾 **Poses** | Save and recall named joint positions |
| 🎬 **Sequences** | Record and replay multi-waypoint motions |
| ⚙️ **Settings** | Pick simulator/real hardware, COM port, and one-tap software update |

All robot communication goes through one layer (`core/robot.py`) — apps never
touch the hardware directly.

---

## What you need

- A **Raspberry Pi** (tested on a **Pi 5**; a Pi 4 works fine too)
- A **PAROL6 arm** with its control board
- A **USB cable** from the Pi to the control board
- Power. If you're running the Pi off the arm's **24 V supply, you need a
  24 V → 5 V buck converter rated for ≥ 5 A** — do **not** feed 24 V into the Pi.

---

## Install on the Pi (one command)

```bash
git clone https://github.com/Jakecuso/parol6-controller.git
cd parol6-controller
bash scripts/setup_pi.sh
```

That script sets up everything:

- Python venv + the PAROL6 API + dependencies
- serial-port access (adds you to the `dialout` group)
- **mDNS** so the Pi is reachable by name
- a **systemd service** so the controller **auto-starts on boot and
  auto-restarts if it ever crashes** — no more babysitting a terminal

Reboot once (so the serial-group change takes effect), and you're done.

## Use it

From **any device on the same network** — phone, laptop, tablet — open:

```
http://raspberrypi.local:5050
```

(Replace `raspberrypi` with your Pi's hostname if you changed it.)

The arm connects automatically when it's plugged in and powered. Open **Manual**
and start jogging.

### Plug-and-play behavior

Cut power to the Pi, the arm, or both. Plug it all back in. ~20 seconds later the
service is up and the arm is connected and live again — nothing to launch. If the
arm's USB takes a few seconds to appear after power-on, the controller just keeps
retrying until it connects.

---

## Updating — push from your dev machine, pull on the Pi

You develop on your own machine, push to GitHub, and update the Pi. Two ways to
pull the update onto the Pi:

**1. The in-app button (easiest).** Open **Settings → Software → ⟳ Update**. It
halts the arm, pulls the latest code, reinstalls any changed dependencies, and
restarts itself. The page reconnects automatically when it's back.

**2. Over SSH.**
```bash
cd ~/parol6-controller && ./scripts/update.sh
```

Both halt the arm before restarting, so an update never happens mid-motion.

---

## Developing on your own machine (simulator)

No hardware needed — the PAROL6 API ships a simulator, and the same code runs on
macOS and the Pi.

```bash
git clone https://github.com/Jakecuso/parol6-controller.git
cd parol6-controller
bash scripts/setup_mac.sh      # one time
source .venv/bin/activate
python run.py                  # opens http://localhost:5050 (simulator)
```

`run.py` defaults to the **simulator** for safety. The Pi's systemd service
flips it to real hardware via `PAROL6_SIMULATE=0`.

### Configuration knobs (env vars)

| Variable | Default | Meaning |
|----------|---------|---------|
| `PAROL6_SIMULATE` | `1` | `0` = real hardware, `1` = simulator |
| `PAROL6_PORT` | `5050` | Web port |
| `PAROL6_NO_BROWSER` | `0` | `1` = don't open a browser (headless) |

CLI overrides: `python run.py --real`, `--sim`, `--port 8080`, `--no-browser`.

### Add your own app

1. `cp -r apps/manual_control apps/my_app`
2. Edit `apps/my_app/app.py` — set `NAME`/`ICON`/`SLUG` and a `register()`.
3. Add `"my_app"` to `APP_DIRS` in `server.py`. Done — it shows up on the home screen.

---

## ⚠️ Safety

- **LAN only.** There is **no login** — anyone who can reach the page can drive
  the arm. Never expose it to the internet or untrusted networks.
- Keep the physical **E-Stop** reachable whenever the real arm is powered. The
  app shows a flashing **E-STOP** banner on every screen when it's pressed.
- The simulator validates motion sequences but can't guarantee a sim-valid move
  is safe on the real arm (current limits, payload, singularities).
- **Power-loss note:** if you kill the 24 V supply to shut everything off, the
  Pi loses power ungracefully each time, which can corrupt the SD card over
  time. For a always-on deployment, consider a clean shutdown or a read-only
  root filesystem.

---

## Troubleshooting

**The Pi froze / locked up during install, or `parol6` won't import.**
Almost always **out of memory** — the PAROL6 stack (pinokin/pinocchio,
robotics-toolbox) is heavy, and a 2-4GB Pi needs swap, especially if you're also
running something like an SSH AI session at the same time. `setup_pi.sh` now sets
up 2GB of swap automatically, but if a previous run got interrupted it may have
left a half-built environment. Rebuild it cleanly:

```bash
cd ~/parol6-controller
git pull
bash scripts/setup_pi.sh --clean     # wipes .venv and reinstalls from scratch
```

Check memory/swap any time with `free -h`. If you froze mid-install before swap
existed, just rerun the line above — the swap step runs first now.

## Useful commands (on the Pi)

```bash
sudo systemctl status parol6     # is it running?
sudo systemctl restart parol6    # restart it
sudo systemctl stop parol6       # stop (e.g. to run manually)
journalctl -u parol6 -f          # live logs
```

Built on the official **[PAROL6 Python API](https://github.com/PCrnjak/PAROL6-python-API)**.
