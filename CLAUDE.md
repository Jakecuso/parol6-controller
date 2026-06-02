# PAROL6 Controller — Claude Code guide

Read this first every session. It explains the project so we don't have to
re-explain it each time.

## What this is

Custom control software for a PAROL6 6-axis robotic arm. Built on the official
PAROL6 Python API (the `waldoctl` interface). It's structured like a phone:
a `ui/launcher.py` "home screen" runs self-contained "mini apps" from `apps/`.

## The architecture — and the one hard rule

**All robot communication goes through `core/robot.py`.** Apps import the
`Robot` wrapper from core and call its methods. Apps must NEVER import `parol6`
directly or open their own UDP/serial connection. This keeps every app sharing
one safe, consistent connection layer.

- `core/robot.py` — wraps `parol6.RobotClient` (sync) and the server lifecycle.
- `ui/launcher.py` — discovers apps and runs them. Don't put robot logic here.
- `apps/<name>/app.py` — one mini app. Must expose `NAME: str` and
  `run(robot)`. The launcher relies on that contract.

## How to add a new app

1. Copy an existing folder in `apps/` (e.g. `cp -r apps/manual_control apps/my_app`).
2. Edit `apps/my_app/app.py`: set `NAME`, write `run(robot)`.
3. That's it — the launcher auto-discovers it. Don't edit the launcher.

## Simulator vs real hardware

This is the most important runtime distinction.

- **Simulator (default, use on the Mac):** `core/robot.py` starts a managed
  controller and calls `simulator_on()`. No hardware, no serial port. The env
  var `PAROL6_FAKE_SERIAL=1` is what the API uses under the hood.
- **Real arm (on the Pi):** start the controller against the USB serial port
  (`parol6-server --serial=/dev/ttyUSB0`) and connect `core/robot.py` to it
  without enabling the simulator.

The switch is the `simulate` flag passed into `Robot(...)`. Default it to
`True` so accidental runs never move a real arm.

## Key API facts (verified against installed parol6 0.2.7 / waldoctl)

- Install via `pip install git+https://github.com/PCrnjak/PAROL6-python-API.git`
- Venv is at `.venv/`; activate with `source .venv/bin/activate`.
- Sync client: `from parol6 import Robot, RobotClient`
  - `Robot(host, port).start()` — starts the controller subprocess (blocks until ready)
  - `Robot(host, port).stop()` — stops it
  - `RobotClient(host, port)` — sync wrapper; call `.close()` when done
  - `client.simulator(True/False)` — enable/disable sim (NOT simulator_on/off)
  - `client.wait_ready(timeout)` — wait until controller is ready (NOT wait_for_server_ready)
  - `client.halt()` — stop all motion (NOT stop())
  - `client.home(wait, timeout)` — home the arm
  - `client.angles()` — joint angles in degrees (list of 6)
  - `client.pose(frame)` — TCP pose [x,y,z,rx,ry,rz]
  - `client.status()` — robot status struct
  - `client.jog_j(joint_0idx, speed_frac, duration)` — joint jog; joints are 0-indexed, speed is 0.0–1.0
  - `client.jog_l(frame, axis, speed_frac, duration)` — cartesian jog; frame='WRF', axis='X' etc
  - `client.move_j(angles_deg, speed=0-1, wait=True)` — move to joint angles
  - `client.select_tool(name)` — set active tool
  - `manage_server` does NOT exist — use `Robot.start()/stop()` instead
  - `stream_on/stream_off` do NOT exist in this version
- Default controller UDP port is **5001**, host `127.0.0.1` for local.

## Safety rules for any code we write

- Default to the simulator. Never default a script to real-hardware mode.
- Keep a stop path available; the API exposes `stop()` / `disable()`.
- Don't expose the controller's UDP port to untrusted networks.

## Current apps

- `manual_control` — keyboard jog. STATUS: working; jog_joint() wired to real API.
- `poses` — save/replay named joint-angle poses. STATUS: working.
- `sequences` — record/replay multi-waypoint sequences. STATUS: working.
- `telemetry` — live readout of joints, TCP pose, status. STATUS: working.
- `xbox_control` — Bluetooth Xbox gamepad teleop. STATUS: logic correct; needs
  a paired Xbox controller (Bluetooth system setting). pygame already installed.

## Planned / ideas

- (add new app ideas here as you think of them)
