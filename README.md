# PAROL6 Controller

Custom control software for a **PAROL6** 6-axis desktop robotic arm.

The idea: a little "home screen" launcher (think mini-iPhone) where each
**mini app** is a self-contained program you can run — manual control,
Xbox controller teleop, and whatever you build next.

It is built on top of the official **PAROL6 Python API** (the `waldoctl`
interface). All robot communication goes through that API, wrapped in
`core/` so the apps never talk to the hardware directly.

---

## How it's organized

```
parol6-controller/
├── README.md              You are here
├── CLAUDE.md              Persistent instructions for Claude Code
├── requirements.txt       Python dependencies
├── run.py                 Entry point — launches the home screen
│
├── core/                  ALL robot communication lives here
│   ├── __init__.py
│   └── robot.py           Thin wrapper around the PAROL6 RobotClient
│
├── ui/                    The "home screen" / app launcher (the phone shell)
│   ├── __init__.py
│   └── launcher.py        Discovers apps in apps/ and runs them
│
├── apps/                  Each mini app is a folder with an app.py
│   ├── manual_control/    App 1: normal jog control
│   │   ├── __init__.py
│   │   └── app.py
│   └── xbox_control/      App 2: Bluetooth Xbox controller teleop
│       ├── __init__.py
│       └── app.py
│
└── scripts/
    ├── setup_mac.sh       One-time setup on your Mac (dev machine)
    └── setup_pi.sh        One-time setup on the Raspberry Pi (deploy target)
```

The contract every app follows: an app is a folder under `apps/` containing
`app.py`, and `app.py` exposes two things — a `NAME` string and a `run(robot)`
function. The launcher finds them automatically. To add an app, copy an
existing folder and edit it. Nothing else needs to change.

---

## The Mac → Pi workflow

You develop on the Mac, then ship the same folder to the Pi. The PAROL6 API
ships prebuilt wheels for **both** macOS (arm64/x86_64) and Linux aarch64
(Raspberry Pi 5), so the *exact same code* runs on both — only the connection
target changes.

**On the Mac (development):**
1. Run `scripts/setup_mac.sh` once.
2. Develop against the **simulator** — no hardware needed. The simulator is
   the default and is toggled in code via `simulator_on()`.
3. Test each app in sim until it behaves.

**Shipping to the Pi:**
1. Copy this whole folder to the Pi (e.g. `scp -r parol6-controller pi@<pi-ip>:~/`
   or push to git and `git clone` on the Pi).
2. On the Pi, run `scripts/setup_pi.sh` once.
3. Plug the PAROL6 control board into the Pi over USB.
4. Start the controller pointed at the real serial port, then run the launcher.

See `scripts/setup_pi.sh` for the exact commands, and CLAUDE.md for the
"sim vs real" switch.

---

## Quick start (Mac, simulator)

```bash
cd parol6-controller
bash scripts/setup_mac.sh          # one time
source .venv/bin/activate
python run.py                      # opens the home screen in the terminal
```

---

## Safety

- Develop in the **simulator** first. The sim validates motion sequences but
  cannot guarantee a move that works in sim will work on the real arm
  (motor/current limits, payload, singularities).
- Keep the physical **E-Stop** reachable whenever the real arm is powered.
- The PAROL6 controller has **no authentication** — only run it on a trusted
  local network, never exposed to the internet.
