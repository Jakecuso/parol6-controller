# PAROL6 Controller — Design Spec

**Date:** 2026-06-01
**Status:** Approved for implementation

---

## Context

The PAROL6 arm has a working Python API and a terminal-based launcher with two stub apps (manual control, Xbox). The goal is to replace the terminal launcher with a browser-based iOS-style home screen and implement 5 fully working mini-apps. The app runs as a local Flask server — same code on Mac Mini and Raspberry Pi.

---

## Architecture

### Layers

```
Browser (HTML/CSS/JS)
      ↕ HTTP + WebSocket (Flask-SocketIO)
Flask server  (server.py)
      ↕
App modules   (apps/<name>/app.py)
      ↕
core/robot.py  ← single gateway to PAROL6 API (unchanged contract)
      ↕
PAROL6 Python API (parol6 package)
```

### Key decisions
- **Flask + Flask-SocketIO** for backend; WebSocket used for all live telemetry (50 Hz)
- **Vanilla JS** on the frontend — no React/Vue, no build step, runs on Pi without Node
- **Each app registers itself** via `register(blueprint, robot, socketio)` — Flask Blueprints replace the old `run(robot)` contract
- **Home screen auto-discovers apps** by importing each `apps/<name>/app.py` and reading `NAME`, `ICON`, `COLOR`, and `register()`
- **Single entry point** `run.py` unchanged in CLI signature: `python run.py [--real] [--no-manage]`

---

## File Structure Changes

```
parol6-controller/
├── run.py                     ← updated: boots Flask instead of terminal launcher
├── server.py                  ← NEW: Flask app factory, SocketIO setup, app discovery
├── requirements.txt           ← add flask, flask-socketio, pygame
│
├── core/
│   └── robot.py               ← wire home(), jog_joint(), jog_cartesian() TODOs
│
├── static/
│   ├── style.css              ← shared dark iOS theme
│   └── socket.js              ← shared WebSocket helper
│
├── templates/
│   ├── base.html              ← shell: status bar, back nav, STOP button
│   └── home.html              ← iOS grid launcher
│
└── apps/
    ├── manual_control/
    │   ├── app.py             ← NAME, ICON, COLOR, register()
    │   └── templates/manual.html
    ├── xbox_control/          ← renamed display: "Remote"
    │   ├── app.py
    │   └── templates/remote.html
    ├── telemetry/             ← NEW
    │   ├── app.py
    │   └── templates/telemetry.html
    ├── sequences/             ← NEW
    │   ├── app.py
    │   └── templates/sequences.html
    └── poses/                 ← NEW
        ├── app.py
        └── templates/poses.html
```

---

## Home Screen (`/`)

Dark iOS grid. 5 app tiles in a 3-column grid on a `#0a0a0f` background with a subtle top blue glow. Each tile: 76×76px rounded-square icon (gradient), emoji icon, label below.

Status pill at bottom: green dot + "Simulator · PAROL6 ready" or red dot + "Disconnected".

App tile metadata (from each `app.py`):

| App | `NAME` | `ICON` | `COLOR` |
|-----|--------|--------|---------|
| manual_control | Manual | 🎮 | `#2196f3 → #0d47a1` |
| xbox_control | Remote | 🕹️ | `#ff7043 → #bf360c` |
| telemetry | Telemetry | 📊 | `#ab47bc → #4a148c` |
| sequences | Sequences | ⏺ | `#ffb300 → #e65100` |
| poses | Poses | 📍 | `#26c6da → #006064` |

---

## core/robot.py — Wire Up TODOs

Three methods need implementing using the installed PAROL6 sync client:

```python
def home(self):
    self.client.home(wait=True)

def jog_joint(self, joint_index: int, direction: int, speed_pct: float = 0.8):
    # direction: +1 or -1
    # use client.jog() or equivalent streaming API at 80% max speed

def jog_cartesian(self, axis: str, direction: int, speed_pct: float = 0.8):
    # axis: 'x','y','z','rx','ry','rz'
    # use streaming Cartesian jog at 80% max linear velocity (160 mm/s)

def go_to_joints(self, angles_deg: list[float]):
    # move arm to specific joint configuration (used by Poses app)
    # exact method name to confirm from examples/
```

Exact API call signatures to confirm from two sources before implementing:
- Local: `/Users/jake/Desktop/VOLT/Source-Files/PAROL6-python-API/examples/`
- GitHub: `PCrnjak/PAROL-commander-software` (the official Waldo Commander GUI) — read how it calls jog, home, and motion commands to make sure our wiring matches exactly how the official software hooks in.

---

## App Specs

### Manual Control (`/apps/manual`)

**UI:**
- Header: `‹ Home` | `Manual Control` | `■ STOP` (red, always visible)
- Row 2: `[Joint | Cartesian]` mode toggle + `⌂ Home` button
- Active-joint card: shows selected joint name, current angle, range; ← → arrow indicators
- Number selector row: keys 1–6 highlighted when selected
- Joint list: 6 rows, each with −/+ buttons, progress bar (within real limits), live angle
- End effector box: X Y Z RX RY RZ (mm / °)
- Keyboard legend: 1–6 select, ← → jog, Space stop, H home, M mode, Esc back

**Joint limits (from PAROL6_ROBOT.py):**

| Joint | Min | Max | Home |
|-------|-----|-----|------|
| J1 | −123.05° | 123.05° | 90° |
| J2 | −145.01° | −3.38° | −90° |
| J3 | 107.87° | 287.87° | 180° |
| J4 | −105.47° | 105.47° | 0° |
| J5 | −90° | 90° | 0° |
| J6 | 0° | 360° | 180° |

**Behavior:**
- Keyboard events captured via JS `keydown`/`keyup`; `keydown` with `repeat` ignored (hold = continuous jog loop at 50ms intervals via `setInterval`)
- Arrow key hold sends `jog_start` SocketIO event; `keyup` sends `jog_stop`
- `⌂ Home` → `robot.home(wait=False)`, button grays out + spinner until telemetry shows home position reached
- `■ STOP` → `robot.stop()` always, from any app page
- Telemetry updates via WebSocket at 50 Hz, pushes `pose_update` events

### Remote (`/apps/remote`) — Xbox Controller

**UI:**
- Shows gamepad connection status (connected / searching…)
- Live visual: left stick XY indicator, right stick XY indicator, bumper states
- Mapping display: left stick = XY, right stick = Z+rotation, LB/RB = mode

**Behavior:**
- Background thread reads pygame gamepad at 50 Hz, applies 0.15 deadzone, emits `gamepad_state` SocketIO events to browser
- Jogging calls `robot.jog_cartesian()` per tick when above deadzone
- Disconnects cleanly on back-navigation (stops jog thread)

### Telemetry (`/apps/telemetry`)

- Live display of all 6 joint angles, XYZ end-effector, arm status, error state
- Updates from shared `pose_update` WebSocket stream (no separate polling needed)
- No controls — read-only monitoring

### Sequences (`/apps/sequences`)

- **Record mode:** Start/Stop recording — captures `get_pose()` at 10 Hz, saves to `data/sequences/<name>.json`
- **Playback mode:** Select a saved sequence, play / pause / stop
- Sequence list: name, duration, frame count, delete button
- Storage: `data/sequences/` folder, plain JSON arrays of pose snapshots

### Poses (`/apps/poses`)

- **Save current pose:** text input for name → saves `get_pose()` snapshot to `data/poses.json`
- **Pose list:** name, joint angles summary, "Go" button → `robot.go_to_joints(pose.joints, wait=False)`
- **Delete** per pose
- Storage: `data/poses.json`, array of `{name, timestamp, joints[6], xyz[6]}`

---

## Data Storage

```
data/
├── poses.json          ← saved named poses
└── sequences/
    └── <name>.json     ← recorded joint sequences
```

Created on first write. Gitignored.

---

## WebSocket Events

| Event | Direction | Payload |
|-------|-----------|---------|
| `pose_update` | server→client | `{joints:[6], xyz:[6], status, error}` |
| `jog_start` | client→server | `{type:'joint'|'cartesian', axis, direction}` |
| `jog_stop` | client→server | `{}` |
| `home` | client→server | `{}` |
| `stop` | client→server | `{}` |
| `gamepad_state` | server→client | `{connected, lx,ly,rx,ry,lb,rb}` |

---

## Dependencies

Add to `requirements.txt`:
```
flask>=3.0
flask-socketio>=5.3
pygame>=2.5
```

---

## Verification

1. `python run.py` → browser opens at `http://localhost:5000`, home screen shows 5 tiles, status pill shows "Simulator · PAROL6 ready"
2. Click Manual → select J1 with `1` key, hold `→`, arm moves in simulator, bar updates live
3. Click `⌂ Home` → arm returns to `[90, -90, 180, 0, 0, 180]`, angles confirmed in telemetry
4. `■ STOP` from any app → motion halts immediately
5. Click Remote → gamepad connects, move stick, cartesian jog fires
6. Telemetry → live values update at ~50 Hz
7. Poses → save current pose, navigate away, come back, hit Go → arm moves there
8. Sequences → record a short sequence, play it back, arm repeats motion
9. `python run.py --real --no-manage` on Pi → same browser UI, real hardware responds
