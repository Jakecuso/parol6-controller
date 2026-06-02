# PAROL6 Web Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the terminal launcher with a Flask web app serving an iOS-style home screen and 5 fully-functional mini-apps for controlling the PAROL6 6-axis robot arm.

**Architecture:** Flask + Flask-SocketIO (eventlet) backend; Vanilla JS + WebSocket frontend. Each app is a Flask Blueprint that self-registers. A single background greenlet streams telemetry at 50 Hz. All robot calls go through `core/robot.py` — no app touches the PAROL6 API directly.

**Tech Stack:** Python 3.11, Flask 3.x, Flask-SocketIO 5.x, eventlet, pygame 2.5, PAROL6 Python API (local install)

---

## Pre-Task: Read the Waldo Commander Source

**Before writing any motion code**, read how the official software hooks into the API:

```
/Users/jake/Desktop/VOLT/Source-Files/PAROL-commander-software/GUI/files/GUI_PAROL_latest.py
/Users/jake/Desktop/VOLT/Source-Files/PAROL6-python-API/examples/
/Users/jake/Desktop/VOLT/Source-Files/PAROL6-python-API/parol6/client/sync_client.py
```

Key confirmed API signatures to use throughout this plan:

```python
# Joint jog — speed is signed fraction [-1.0, 1.0], duration in seconds
client.jog_j(joint=0, speed=0.8, duration=0.15)   # +direction
client.jog_j(joint=0, speed=-0.8, duration=0.15)  # -direction

# Cartesian jog — axis: "X","Y","Z","RX","RY","RZ"  frame: "WRF"
client.jog_l(frame="WRF", axis="X", speed=0.8, duration=0.15)

# Move to joint angles (degrees)
client.servo_j([90.0, -90.0, 180.0, 0.0, 0.0, 180.0])

# Home
client.home(wait=True)

# Telemetry
client.get_pose()   # verify return shape — likely dict or list[float]
client.get_status() # verify return shape
```

---

## File Map

```
parol6-controller/
├── run.py                          MODIFY — boot Flask instead of terminal
├── server.py                       CREATE — app factory + app discovery
├── requirements.txt                MODIFY — add flask, flask-socketio, eventlet, pygame
│
├── core/robot.py                   MODIFY — wire 4 TODO methods
│
├── static/
│   ├── style.css                   CREATE — shared dark iOS theme
│   └── socket.js                   CREATE — shared SocketIO helper
│
├── templates/
│   ├── base.html                   CREATE — shell with nav + STOP button
│   └── home.html                   CREATE — iOS grid launcher
│
├── apps/
│   ├── manual_control/
│   │   ├── app.py                  MODIFY — add NAME/ICON/COLOR/register()
│   │   └── templates/
│   │       └── manual.html         CREATE
│   ├── xbox_control/
│   │   ├── app.py                  MODIFY — add NAME="Remote"/register()
│   │   └── templates/
│   │       └── remote.html         CREATE
│   ├── telemetry/
│   │   ├── __init__.py             CREATE (empty)
│   │   ├── app.py                  CREATE
│   │   └── templates/
│   │       └── telemetry.html      CREATE
│   ├── sequences/
│   │   ├── __init__.py             CREATE (empty)
│   │   ├── app.py                  CREATE
│   │   └── templates/
│   │       └── sequences.html      CREATE
│   └── poses/
│       ├── __init__.py             CREATE (empty)
│       ├── app.py                  CREATE
│       └── templates/
│           └── poses.html          CREATE
│
├── data/                           CREATE dir (gitignored)
│   └── sequences/                  CREATE dir
│
└── tests/
    ├── test_robot.py               CREATE
    ├── test_server.py              CREATE
    └── test_apps.py                CREATE
```

---

## Task 1: Dependencies + Project Skeleton

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `data/.gitkeep`, `data/sequences/.gitkeep`
- Create: `apps/telemetry/__init__.py`, `apps/sequences/__init__.py`, `apps/poses/__init__.py`

- [ ] **Step 1: Update requirements.txt**

```
flask>=3.0
flask-socketio>=5.3
eventlet>=0.35
pygame>=2.5
```

- [ ] **Step 2: Install dependencies**

```bash
cd parol6-controller
source .venv/bin/activate
pip install flask flask-socketio eventlet pygame
pip freeze | grep -E "flask|eventlet|pygame" # verify installed
```

- [ ] **Step 3: Create data dirs and new app __init__ files**

```bash
mkdir -p data/sequences apps/telemetry apps/sequences apps/poses
touch data/.gitkeep data/sequences/.gitkeep
touch apps/telemetry/__init__.py apps/sequences/__init__.py apps/poses/__init__.py
```

- [ ] **Step 4: Add data/ to .gitignore**

Append to `.gitignore`:
```
data/
!data/.gitkeep
!data/sequences/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore data/ apps/telemetry/__init__.py apps/sequences/__init__.py apps/poses/__init__.py
git commit -m "chore: add web dependencies and scaffold new app dirs"
```

---

## Task 2: Wire core/robot.py Motion Methods

**Files:**
- Modify: `core/robot.py`
- Create: `tests/test_robot.py`

Read the actual `get_pose()` return format from the API before this task. It likely returns a `list[float]` with 12 values: `[j1,j2,j3,j4,j5,j6, x,y,z,rx,ry,rz]` — confirm from sync_client.py or examples.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_robot.py
import pytest
from unittest.mock import MagicMock, patch
from core.robot import Robot

@pytest.fixture
def mock_robot():
    with patch("core.robot.manage_server"), \
         patch("core.robot.RobotClient") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value.__enter__ = lambda s: mock_client
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        r = Robot(simulate=True)
        r.client = mock_client
        yield r, mock_client

def test_home_calls_api(mock_robot):
    r, client = mock_robot
    r.home()
    client.home.assert_called_once_with(wait=True)

def test_jog_joint_positive(mock_robot):
    r, client = mock_robot
    r.jog_joint(joint_index=0, direction=1)
    client.jog_j.assert_called_once_with(joint=0, speed=pytest.approx(0.8), duration=0.15)

def test_jog_joint_negative(mock_robot):
    r, client = mock_robot
    r.jog_joint(joint_index=2, direction=-1)
    client.jog_j.assert_called_once_with(joint=2, speed=pytest.approx(-0.8), duration=0.15)

def test_jog_cartesian(mock_robot):
    r, client = mock_robot
    r.jog_cartesian(axis="X", direction=1)
    client.jog_l.assert_called_once_with(frame="WRF", axis="X", speed=pytest.approx(0.8), duration=0.15)

def test_jog_cartesian_negative(mock_robot):
    r, client = mock_robot
    r.jog_cartesian(axis="RZ", direction=-1)
    client.jog_l.assert_called_once_with(frame="WRF", axis="RZ", speed=pytest.approx(-0.8), duration=0.15)

def test_go_to_joints(mock_robot):
    r, client = mock_robot
    angles = [90.0, -90.0, 180.0, 0.0, 0.0, 180.0]
    r.go_to_joints(angles)
    client.servo_j.assert_called_once_with(angles)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_robot.py -v
# Expected: FAIL — methods raise NotImplementedError or AttributeError
```

- [ ] **Step 3: Implement the 4 motion methods in core/robot.py**

Find the existing `TODO` stub methods and replace them:

```python
def home(self):
    """Move arm to standby position [90,-90,180,0,0,180] via firmware motion planner."""
    self.client.home(wait=True)

def jog_joint(self, joint_index: int, direction: int, speed_pct: float = 0.8):
    """Jog a single joint. direction: +1 or -1. speed_pct: 0-1 fraction of max speed."""
    speed = direction * speed_pct
    self.client.jog_j(joint=joint_index, speed=speed, duration=0.15)

def jog_cartesian(self, axis: str, direction: int, speed_pct: float = 0.8):
    """Jog in Cartesian space. axis: 'X','Y','Z','RX','RY','RZ'. direction: +1 or -1."""
    speed = direction * speed_pct
    self.client.jog_l(frame="WRF", axis=axis.upper(), speed=speed, duration=0.15)

def go_to_joints(self, angles_deg: list):
    """Stream arm to specific joint configuration. angles_deg: list of 6 floats (degrees)."""
    self.client.servo_j(angles_deg)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_robot.py -v
# Expected: 6 PASSED
```

- [ ] **Step 5: Commit**

```bash
git add core/robot.py tests/test_robot.py
git commit -m "feat: wire home, jog_joint, jog_cartesian, go_to_joints in robot wrapper"
```

---

## Task 3: Flask Server Foundation

**Files:**
- Create: `server.py`
- Modify: `run.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing server test**

```python
# tests/test_server.py
import pytest
from server import create_app

@pytest.fixture
def app():
    app, socketio = create_app(simulate=True)
    app.config["TESTING"] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_home_screen_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"PAROL6 Controller" in resp.data

def test_app_tiles_present(client):
    resp = client.get("/")
    data = resp.data.decode()
    assert "Manual" in data
    assert "Remote" in data
    assert "Telemetry" in data
    assert "Sequences" in data
    assert "Poses" in data

def test_unknown_route_404(client):
    resp = client.get("/apps/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_server.py -v
# Expected: FAIL — server.py doesn't exist
```

- [ ] **Step 3: Create server.py**

```python
# server.py
import importlib
import os
from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO()

APP_DIRS = [
    "manual_control",
    "xbox_control",
    "telemetry",
    "sequences",
    "poses",
]

def create_app(simulate: bool = True):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "parol6-dev"

    socketio.init_app(app, async_mode="eventlet", cors_allowed_origins="*")

    # Lazy import to avoid circular deps at test time
    from core.robot import Robot
    robot = Robot(simulate=simulate)
    app.robot = robot

    # Discover and register apps
    discovered = []
    for name in APP_DIRS:
        try:
            mod = importlib.import_module(f"apps.{name}.app")
            mod.register(app, robot, socketio)
            discovered.append({
                "name": mod.NAME,
                "icon": mod.ICON,
                "color": mod.COLOR,
                "slug": mod.SLUG,
            })
        except Exception as e:
            print(f"[server] Warning: could not load app '{name}': {e}")

    app.config["APPS"] = discovered

    # Global telemetry background task
    @socketio.on("connect")
    def on_connect():
        pass  # telemetry thread started once at server boot (see run.py)

    @socketio.on("stop")
    def on_stop():
        robot.stop()

    @socketio.on("home")
    def on_home():
        robot.home()

    return app, socketio
```

- [ ] **Step 4: Update run.py**

Replace the terminal-launcher boot with Flask:

```python
# run.py
import argparse
import webbrowser
import eventlet
eventlet.monkey_patch()

from server import create_app, socketio

def parse_args():
    p = argparse.ArgumentParser(description="PAROL6 Web Controller")
    p.add_argument("--real", action="store_true", help="Connect to real hardware")
    p.add_argument("--no-manage", action="store_true", help="Don't auto-start controller")
    p.add_argument("--port", type=int, default=5000)
    return p.parse_args()

def telemetry_loop(app, sock):
    """Background greenlet: push pose_update at ~50 Hz."""
    robot = app.robot
    with app.app_context():
        while True:
            try:
                pose = robot.get_pose()
                status = robot.get_status()
                # get_pose() returns list[float] — confirm shape from API
                # Assumed: first 6 = joint angles (deg), next 6 = xyz + rotation
                joints = list(pose[:6]) if pose else [0.0] * 6
                xyz = list(pose[6:12]) if pose and len(pose) >= 12 else [0.0] * 6
                sock.emit("pose_update", {
                    "joints": joints,
                    "xyz": xyz,
                    "status": str(status),
                    "error": False,
                }, broadcast=True)
            except Exception:
                sock.emit("pose_update", {
                    "joints": [0.0] * 6,
                    "xyz": [0.0] * 6,
                    "status": "error",
                    "error": True,
                }, broadcast=True)
            sock.sleep(0.02)  # 50 Hz

if __name__ == "__main__":
    args = parse_args()
    simulate = not args.real
    app, sock = create_app(simulate=simulate)

    # Start telemetry greenlet
    sock.start_background_task(telemetry_loop, app, sock)

    url = f"http://localhost:{args.port}"
    print(f"PAROL6 Controller → {url}")
    webbrowser.open(url)

    sock.run(app, host="0.0.0.0", port=args.port, debug=False)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_server.py -v
# Note: these will fail until templates exist — that's Task 5. Move on.
```

- [ ] **Step 6: Commit**

```bash
git add server.py run.py tests/test_server.py
git commit -m "feat: add Flask server factory and updated entry point"
```

---

## Task 4: Shared Static Assets (CSS + JS)

**Files:**
- Create: `static/style.css`
- Create: `static/socket.js`

- [ ] **Step 1: Create static/style.css**

```css
/* static/style.css */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #0a0a0f;
  --surface: #111117;
  --surface2: #1c1c24;
  --border: #2a2a35;
  --text: #ffffff;
  --text-dim: #8b8b9a;
  --accent: #1e90ff;
  --danger: #ff3b30;
  --success: #4caf50;
  --warn: #ff9800;
}

html, body {
  height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* App shell */
.app-shell {
  max-width: 480px;
  margin: 0 auto;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 0 0 32px;
}

/* Top nav bar */
.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px 10px;
  position: sticky;
  top: 0;
  background: rgba(10, 10, 15, 0.92);
  backdrop-filter: blur(12px);
  z-index: 100;
}

.nav-back { color: var(--accent); font-size: 15px; text-decoration: none; display: flex; align-items: center; gap: 4px; min-width: 60px; }
.nav-title { font-size: 16px; font-weight: 600; }
.btn-stop { background: var(--danger); color: #fff; border: none; border-radius: 10px; padding: 6px 14px; font-size: 12px; font-weight: 700; cursor: pointer; letter-spacing: 0.3px; }
.btn-stop:active { opacity: 0.8; }

/* Status pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: rgba(255,255,255,0.07);
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 11px;
  color: var(--text-dim);
}
.dot { width: 7px; height: 7px; border-radius: 50%; }
.dot-green { background: var(--success); box-shadow: 0 0 6px var(--success); }
.dot-red { background: var(--danger); box-shadow: 0 0 6px var(--danger); }

/* Cards / surfaces */
.card {
  background: var(--surface);
  border-radius: 14px;
  padding: 14px;
}
.card + .card { margin-top: 10px; }

.label-sm {
  color: var(--text-dim);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin-bottom: 8px;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: 10px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.12s;
}
.btn:active { opacity: 0.75; }
.btn:disabled { opacity: 0.35; cursor: default; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-home { background: linear-gradient(135deg, #26c6da, #00838f); color: #fff; }
.btn-danger { background: var(--danger); color: #fff; }
.btn-surface { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }

/* Toggle */
.toggle-row { display: flex; background: var(--surface2); border-radius: 10px; padding: 3px; gap: 2px; }
.toggle-btn { flex: 1; padding: 6px; border-radius: 8px; border: none; font-size: 12px; font-weight: 500; cursor: pointer; background: none; color: var(--text-dim); transition: all 0.15s; }
.toggle-btn.active { background: var(--accent); color: #fff; }

/* Joint bar */
.joint-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.joint-label { width: 22px; font-size: 10px; font-weight: 700; color: var(--text-dim); flex-shrink: 0; }
.joint-row.selected .joint-label { color: var(--accent); }
.jog-btn { width: 28px; height: 28px; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; color: var(--text-dim); font-size: 16px; font-weight: 300; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; user-select: none; }
.joint-row.selected .jog-btn { border-color: var(--accent); color: var(--accent); }
.jog-btn:active { background: var(--accent); color: #fff; border-color: var(--accent); }
.bar-wrap { flex: 1; height: 4px; background: var(--surface2); border-radius: 2px; position: relative; }
.bar-fill { height: 100%; border-radius: 2px; background: var(--border); transition: width 0.08s; }
.joint-row.selected .bar-fill { background: linear-gradient(90deg, var(--accent), #4fc3f7); }
.bar-cursor { position: absolute; top: -4px; width: 3px; height: 12px; background: #fff; border-radius: 2px; transition: left 0.08s; }
.angle-val { width: 52px; font-size: 11px; font-weight: 600; text-align: right; flex-shrink: 0; color: var(--text-dim); }
.joint-row.selected .angle-val { color: var(--accent); }

/* Kbd */
kbd { background: var(--surface2); border: 1px solid var(--border); border-radius: 5px; padding: 2px 6px; font-size: 10px; color: var(--text-dim); font-family: monospace; }
```

- [ ] **Step 2: Create static/socket.js**

```javascript
// static/socket.js
// Shared helpers for all app pages.

const socket = io();

// Latest pose state, updated by server
window.poseState = {
  joints: [0, 0, 0, 0, 0, 0],
  xyz:    [0, 0, 0, 0, 0, 0],
  status: "unknown",
  error:  false,
};

socket.on("pose_update", (data) => {
  window.poseState = data;
  document.dispatchEvent(new CustomEvent("pose_update", { detail: data }));
});

socket.on("connect", () => {
  const pill = document.getElementById("status-pill");
  if (pill) pill.innerHTML = '<span class="dot dot-green"></span> Connected';
});

socket.on("disconnect", () => {
  const pill = document.getElementById("status-pill");
  if (pill) pill.innerHTML = '<span class="dot dot-red"></span> Disconnected';
});

function sendStop() {
  socket.emit("stop");
}

function sendHome() {
  socket.emit("home");
}
```

- [ ] **Step 3: Commit**

```bash
git add static/style.css static/socket.js
git commit -m "feat: add shared CSS theme and SocketIO JS helper"
```

---

## Task 5: Base Template + Home Screen

**Files:**
- Create: `templates/base.html`
- Create: `templates/home.html`
- Create: `server.py` route for `/` (add to existing server.py)

- [ ] **Step 1: Create templates/base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}PAROL6{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
<div class="app-shell">
  {% block nav %}
  <div class="nav-bar">
    {% block nav_left %}<span></span>{% endblock %}
    <span class="nav-title">{% block nav_title %}PAROL6{% endblock %}</span>
    <button class="btn-stop" onclick="sendStop()">■ STOP</button>
  </div>
  {% endblock %}

  <main style="flex:1; padding: 16px 20px;">
    {% block content %}{% endblock %}
  </main>
</div>
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<script src="/static/socket.js"></script>
{% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Create templates/home.html**

```html
{% extends "base.html" %}
{% block title %}PAROL6 Controller{% endblock %}
{% block nav %}
<div class="nav-bar" style="justify-content:center; flex-direction:column; gap:6px; padding-top:20px;">
  <span class="nav-title" style="font-size:13px; letter-spacing:2px; text-transform:uppercase; color:var(--text-dim)">PAROL6 Controller</span>
  <span class="status-pill" id="status-pill">
    <span class="dot dot-green"></span> Simulator · Ready
  </span>
</div>
{% endblock %}

{% block content %}
<div style="
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px 16px;
  padding: 24px 8px;
  max-width: 340px;
  margin: 0 auto;
">
  {% for app in apps %}
  <a href="/apps/{{ app.slug }}" style="text-decoration:none; display:flex; flex-direction:column; align-items:center; gap:8px;">
    <div style="
      width: 76px; height: 76px;
      border-radius: 18px;
      background: {{ app.color }};
      display: flex; align-items: center; justify-content: center;
      font-size: 34px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
      position: relative; overflow: hidden;
    ">
      {{ app.icon }}
      <div style="position:absolute;top:0;left:0;right:0;height:50%;background:linear-gradient(180deg,rgba(255,255,255,0.15),transparent);border-radius:18px 18px 0 0;"></div>
    </div>
    <span style="font-size:11px; color:rgba(255,255,255,0.9); text-shadow:0 1px 4px rgba(0,0,0,0.8);">{{ app.name }}</span>
  </a>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 3: Add home route to server.py**

In `server.py`, inside `create_app()`, add the home route before `return`:

```python
    from flask import render_template

    @app.route("/")
    def home():
        return render_template("home.html", apps=app.config["APPS"])

    @app.errorhandler(404)
    def not_found(e):
        return "Not found", 404
```

- [ ] **Step 4: Run the server and verify home screen**

```bash
python run.py
# Browser should open to http://localhost:5000
# Expected: dark iOS grid with 5 app tiles
# Note: tiles will show but app routes won't work yet (Tasks 6-10)
```

- [ ] **Step 5: Run server tests**

```bash
pytest tests/test_server.py -v
# Expected: 3 PASSED
```

- [ ] **Step 6: Commit**

```bash
git add templates/base.html templates/home.html server.py
git commit -m "feat: home screen with iOS app grid"
```

---

## Task 6: Manual Control App

**Files:**
- Modify: `apps/manual_control/app.py`
- Create: `apps/manual_control/templates/manual_control/manual.html`

Joint limits (hard-coded from PAROL6_ROBOT.py):
```python
JOINT_LIMITS = [
    (-123.046875, 123.046875),   # J1
    (-145.0088,   -3.375),       # J2
    (107.866,     287.8675),     # J3
    (-105.46975,  105.46975),    # J4
    (-90.0,       90.0),         # J5
    (0.0,         360.0),        # J6
]
JOINT_NAMES = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Tool"]
HOME_ANGLES  = [90.0, -90.0, 180.0, 0.0, 0.0, 180.0]
```

- [ ] **Step 1: Rewrite apps/manual_control/app.py**

```python
# apps/manual_control/app.py
import threading
from flask import Blueprint, render_template

NAME  = "Manual"
ICON  = "🎮"
COLOR = "linear-gradient(145deg, #2196f3, #0d47a1)"
SLUG  = "manual"

JOINT_LIMITS = [
    (-123.046875, 123.046875),
    (-145.0088,   -3.375),
    (107.866,     287.8675),
    (-105.46975,  105.46975),
    (-90.0,       90.0),
    (0.0,         360.0),
]

_jog_stop = threading.Event()
_jog_thread = None


def register(app, robot, socketio):
    bp = Blueprint("manual", __name__, template_folder="templates")

    @bp.route("/apps/manual")
    def index():
        return render_template(
            "manual_control/manual.html",
            limits=JOINT_LIMITS,
            home_angles=[90.0, -90.0, 180.0, 0.0, 0.0, 180.0],
        )

    app.register_blueprint(bp)

    @socketio.on("manual:jog_start")
    def handle_jog_start(data):
        global _jog_thread, _jog_stop
        _jog_stop.set()  # stop any existing jog
        _jog_stop = threading.Event()
        stop_event = _jog_stop

        jog_type = data.get("type", "joint")
        joint_idx = data.get("joint", 0)
        direction = data.get("direction", 1)
        axis = data.get("axis", "X")

        def _loop():
            while not stop_event.is_set():
                try:
                    if jog_type == "joint":
                        robot.jog_joint(joint_idx, direction)
                    else:
                        robot.jog_cartesian(axis, direction)
                except Exception:
                    break
                socketio.sleep(0.1)

        _jog_thread = socketio.start_background_task(_loop)

    @socketio.on("manual:jog_stop")
    def handle_jog_stop():
        _jog_stop.set()
```

- [ ] **Step 2: Create apps/manual_control/templates/manual_control/manual.html**

```html
{% extends "base.html" %}
{% block title %}Manual Control — PAROL6{% endblock %}
{% block nav_left %}<a class="nav-back" href="/">‹ Home</a>{% endblock %}
{% block nav_title %}Manual Control{% endblock %}

{% block content %}
<!-- Mode + Home row -->
<div style="display:flex; gap:10px; margin-bottom:14px;">
  <div class="toggle-row" style="flex:1;">
    <button class="toggle-btn active" id="btn-joint" onclick="setMode('joint')">Joint</button>
    <button class="toggle-btn"        id="btn-cart"  onclick="setMode('cartesian')">Cartesian</button>
  </div>
  <button class="btn btn-home" onclick="sendHome()">⌂ Home</button>
</div>

<!-- Active joint card -->
<div class="card" style="margin-bottom:12px;">
  <div class="label-sm">Selected</div>
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div>
      <div id="sel-name" style="font-size:16px; font-weight:700;">J1 — Base</div>
      <div id="sel-range" style="font-size:11px; color:var(--text-dim); margin-top:2px;">12.4° · range: −123° to 123°</div>
    </div>
    <div style="text-align:center;">
      <div style="display:flex; gap:8px;">
        <div id="arrow-left"  class="jog-btn" style="width:40px;height:40px;font-size:20px;">←</div>
        <div id="arrow-right" class="jog-btn" style="width:40px;height:40px;font-size:20px;">→</div>
      </div>
      <div style="color:var(--text-dim);font-size:9px;margin-top:4px;">hold to jog</div>
    </div>
  </div>
</div>

<!-- Number selector -->
<div style="display:flex; gap:6px; justify-content:center; margin-bottom:14px;">
  {% for i in range(1,7) %}
  <button class="jog-btn" id="sel-{{ i }}" onclick="selectJoint({{ i-1 }})"
          style="width:32px;height:32px;font-size:12px;font-weight:700;flex-direction:column;gap:1px;">
    <span>{{ i }}</span>
    <span style="font-size:7px;opacity:0.6;">J{{ i }}</span>
  </button>
  {% endfor %}
</div>

<!-- Joint list -->
<div class="card" style="margin-bottom:12px;">
  <div class="label-sm">All Joints</div>
  {% set limits = [(-123.046875,123.046875),(-145.0088,-3.375),(107.866,287.8675),(-105.46975,105.46975),(-90.0,90.0),(0.0,360.0)] %}
  {% for i in range(6) %}
  {% set mn = limits[i][0] %}
  {% set mx = limits[i][1] %}
  <div class="joint-row" id="row-{{ i }}" {% if i==0 %}style="background:rgba(30,144,255,0.08);border-radius:8px;"{% endif %}>
    <div class="joint-label" id="lbl-{{ i }}">J{{ i+1 }}</div>
    <button class="jog-btn" onmousedown="startJog({{ i }},-1)" onmouseup="stopJog()" ontouchstart="startJog({{ i }},-1)" ontouchend="stopJog()">−</button>
    <div class="bar-wrap">
      <div class="bar-fill" id="bar-{{ i }}" style="width:50%;"></div>
      <div class="bar-cursor" id="cur-{{ i }}" style="left:50%;"></div>
    </div>
    <button class="jog-btn" onmousedown="startJog({{ i }},1)" onmouseup="stopJog()" ontouchstart="startJog({{ i }},1)" ontouchend="stopJog()">+</button>
    <div class="angle-val" id="ang-{{ i }}">—</div>
  </div>
  {% endfor %}
</div>

<!-- End effector -->
<div class="card" style="margin-bottom:12px;">
  <div class="label-sm">End Effector</div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;text-align:center;">
    {% for ax in ['X','Y','Z','RX','RY','RZ'] %}
    <div>
      <div id="xyz-{{ loop.index0 }}" style="font-size:13px;font-weight:600;color:var(--warn);">—</div>
      <div style="font-size:9px;color:var(--text-dim);">{{ ax }}</div>
    </div>
    {% endfor %}
  </div>
</div>

<!-- Keyboard legend -->
<div class="card">
  <div class="label-sm">Keyboard</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;">
    <div style="font-size:10px;color:var(--text-dim);"><kbd>1–6</kbd> Select joint</div>
    <div style="font-size:10px;color:var(--text-dim);"><kbd>← →</kbd> Jog selected</div>
    <div style="font-size:10px;color:var(--text-dim);"><kbd>Space</kbd> Stop motion</div>
    <div style="font-size:10px;color:var(--text-dim);"><kbd>H</kbd> Go home</div>
    <div style="font-size:10px;color:var(--text-dim);"><kbd>M</kbd> Toggle mode</div>
    <div style="font-size:10px;color:var(--text-dim);"><kbd>Esc</kbd> ← Back</div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
const LIMITS = [[-123.046875,123.046875],[-145.0088,-3.375],[107.866,287.8675],[-105.46975,105.46975],[-90,90],[0,360]];
const NAMES  = ["Base","Shoulder","Elbow","Wrist 1","Wrist 2","Tool"];
let selectedJoint = 0;
let mode = "joint";
let jogging = false;

function selectJoint(idx) {
  selectedJoint = idx;
  document.querySelectorAll(".joint-row").forEach((r,i) => {
    r.style.background = i===idx ? "rgba(30,144,255,0.08)" : "";
    r.style.borderRadius = i===idx ? "8px" : "";
  });
  document.querySelectorAll("[id^='lbl-']").forEach((el,i) => el.style.color = i===idx ? "var(--accent)" : "");
  document.querySelectorAll("[id^='sel-']").forEach((el,i) => {
    el.style.borderColor = i===idx ? "var(--accent)" : "";
    el.style.color = i===idx ? "var(--accent)" : "";
    el.style.background = i===idx ? "rgba(30,144,255,0.1)" : "";
  });
  const [mn,mx] = LIMITS[idx];
  const cur = parseFloat(document.getElementById(`ang-${idx}`).textContent) || 0;
  document.getElementById("sel-name").textContent = `J${idx+1} — ${NAMES[idx]}`;
  document.getElementById("sel-range").textContent = `${cur.toFixed(1)}° · range: ${mn}° to ${mx}°`;
}

function setMode(m) {
  mode = m;
  document.getElementById("btn-joint").className = "toggle-btn" + (m==="joint"?" active":"");
  document.getElementById("btn-cart").className  = "toggle-btn" + (m==="cartesian"?" active":"");
}

const CART_AXES = ["X","Y","Z","RX","RY","RZ"];

function startJog(joint, dir) {
  if (jogging) stopJog();
  jogging = true;
  if (mode === "joint") {
    socket.emit("manual:jog_start", { type:"joint", joint, direction:dir });
  } else {
    socket.emit("manual:jog_start", { type:"cartesian", axis:CART_AXES[joint], direction:dir });
  }
}

function stopJog() {
  if (!jogging) return;
  jogging = false;
  socket.emit("manual:jog_stop");
}

// Keyboard
const keys = {};
document.addEventListener("keydown", (e) => {
  if (e.repeat) return;
  if (e.key === "Escape") { window.location.href = "/"; return; }
  if (e.key === "h" || e.key === "H") { sendHome(); return; }
  if (e.key === "m" || e.key === "M") { setMode(mode==="joint"?"cartesian":"joint"); return; }
  if (e.key === " ") { e.preventDefault(); sendStop(); return; }
  const n = parseInt(e.key);
  if (n >= 1 && n <= 6) { selectJoint(n-1); return; }
  if (e.key === "ArrowLeft")  { e.preventDefault(); startJog(selectedJoint,-1); }
  if (e.key === "ArrowRight") { e.preventDefault(); startJog(selectedJoint, 1); }
});
document.addEventListener("keyup", (e) => {
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") stopJog();
});

// Telemetry update
document.addEventListener("pose_update", (e) => {
  const {joints, xyz} = e.detail;
  joints.forEach((v, i) => {
    const [mn, mx] = LIMITS[i];
    const pct = Math.max(0, Math.min(100, ((v - mn) / (mx - mn)) * 100));
    document.getElementById(`bar-${i}`).style.width  = pct + "%";
    document.getElementById(`cur-${i}`).style.left   = pct + "%";
    document.getElementById(`ang-${i}`).textContent  = v.toFixed(1) + "°";
  });
  xyz.forEach((v, i) => {
    const suffix = i < 3 ? "mm" : "°";
    document.getElementById(`xyz-${i}`).textContent = v.toFixed(1) + suffix;
  });
  const [mn,mx] = LIMITS[selectedJoint];
  const cur = joints[selectedJoint] || 0;
  document.getElementById("sel-range").textContent =
    `${cur.toFixed(1)}° · range: ${mn}° to ${mx}°`;
});

selectJoint(0);
</script>
{% endblock %}
```

- [ ] **Step 3: Verify app loads in browser**

```bash
python run.py
# Navigate to http://localhost:5000 → click Manual tile
# Expected: manual control page with 6 joint rows, select J1 with keyboard "1", hold → arrow
```

- [ ] **Step 4: Commit**

```bash
git add apps/manual_control/app.py apps/manual_control/templates/
git commit -m "feat: manual control app with keyboard jog and live joint bars"
```

---

## Task 7: Remote App (Xbox Controller)

**Files:**
- Modify: `apps/xbox_control/app.py`
- Create: `apps/xbox_control/templates/xbox_control/remote.html`

- [ ] **Step 1: Rewrite apps/xbox_control/app.py**

```python
# apps/xbox_control/app.py
import threading
from flask import Blueprint, render_template

NAME  = "Remote"
ICON  = "🕹️"
COLOR = "linear-gradient(145deg, #ff7043, #bf360c)"
SLUG  = "remote"

_gamepad_thread = None
_gamepad_stop   = threading.Event()
DEADZONE = 0.15

AXIS_MAP = {
    0: ("X",  1),   # left stick X  → Cartesian X
    1: ("Y", -1),   # left stick Y  → Cartesian Y (inverted)
    3: ("Z",  1),   # right stick Y → Cartesian Z
    2: ("RZ", 1),   # right stick X → rotation Z
}


def register(app, robot, socketio):
    bp = Blueprint("remote", __name__, template_folder="templates")

    @bp.route("/apps/remote")
    def index():
        return render_template("xbox_control/remote.html")

    app.register_blueprint(bp)

    @socketio.on("remote:start")
    def handle_start():
        global _gamepad_thread, _gamepad_stop
        _gamepad_stop.set()
        _gamepad_stop = threading.Event()
        stop_event = _gamepad_stop

        def _loop():
            import pygame
            pygame.init()
            pygame.joystick.init()

            while not stop_event.is_set():
                pygame.event.pump()
                count = pygame.joystick.get_count()
                if count == 0:
                    socketio.emit("remote:state", {"connected": False})
                    socketio.sleep(0.5)
                    continue

                js = pygame.joystick.Joystick(0)
                js.init()
                axes = [js.get_axis(i) for i in range(js.get_numaxes())]
                buttons = [js.get_button(i) for i in range(js.get_numbuttons())]

                state = {
                    "connected": True,
                    "lx": axes[0] if len(axes)>0 else 0,
                    "ly": axes[1] if len(axes)>1 else 0,
                    "rx": axes[2] if len(axes)>2 else 0,
                    "ry": axes[3] if len(axes)>3 else 0,
                    "lb": buttons[4] if len(buttons)>4 else 0,
                    "rb": buttons[5] if len(buttons)>5 else 0,
                }
                socketio.emit("remote:state", state)

                for axis_idx, (cart_axis, sign) in AXIS_MAP.items():
                    if axis_idx < len(axes):
                        val = axes[axis_idx] * sign
                        if abs(val) > DEADZONE:
                            speed = (abs(val) - DEADZONE) / (1.0 - DEADZONE) * 0.8
                            direction = 1 if val > 0 else -1
                            try:
                                robot.jog_cartesian(cart_axis, direction, speed)
                            except Exception:
                                pass

                socketio.sleep(0.02)

            pygame.quit()

        _gamepad_thread = socketio.start_background_task(_loop)

    @socketio.on("remote:stop")
    def handle_stop():
        _gamepad_stop.set()
```

- [ ] **Step 2: Create apps/xbox_control/templates/xbox_control/remote.html**

```html
{% extends "base.html" %}
{% block title %}Remote — PAROL6{% endblock %}
{% block nav_left %}<a class="nav-back" href="/">‹ Home</a>{% endblock %}
{% block nav_title %}Remote{% endblock %}

{% block content %}
<div class="card" style="text-align:center; padding:24px; margin-bottom:12px;">
  <div id="conn-icon" style="font-size:48px;">🕹️</div>
  <div id="conn-status" style="margin-top:8px; font-size:14px; color:var(--text-dim);">Searching for gamepad…</div>
</div>

<!-- Stick visualizers -->
<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:12px;">
  <div class="card" style="text-align:center;">
    <div class="label-sm">Left Stick (XY)</div>
    <canvas id="stick-left" width="80" height="80" style="display:block;margin:0 auto;"></canvas>
  </div>
  <div class="card" style="text-align:center;">
    <div class="label-sm">Right Stick (Z / RZ)</div>
    <canvas id="stick-right" width="80" height="80" style="display:block;margin:0 auto;"></canvas>
  </div>
</div>

<!-- Mapping legend -->
<div class="card">
  <div class="label-sm">Control Mapping</div>
  <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px 12px; font-size:11px; color:var(--text-dim);">
    <div>Left stick X → Cartesian X</div>
    <div>Left stick Y → Cartesian Y</div>
    <div>Right stick Y → Cartesian Z</div>
    <div>Right stick X → Rotate Z</div>
    <div>Space / STOP → Stop motion</div>
    <div>Esc → ← Home</div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
function drawStick(canvasId, x, y) {
  const c = document.getElementById(canvasId);
  const ctx = c.getContext("2d");
  ctx.clearRect(0,0,80,80);
  ctx.strokeStyle = "#2a2a35";
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(40,40,36,0,2*Math.PI); ctx.stroke();
  ctx.fillStyle = "#4fc3f7";
  ctx.beginPath(); ctx.arc(40 + x*32, 40 + y*32, 8, 0, 2*Math.PI); ctx.fill();
}

drawStick("stick-left",  0, 0);
drawStick("stick-right", 0, 0);

socket.emit("remote:start");

socket.on("remote:state", (data) => {
  if (data.connected) {
    document.getElementById("conn-icon").textContent = "✅";
    document.getElementById("conn-status").textContent = "Gamepad connected";
    drawStick("stick-left",  data.lx, data.ly);
    drawStick("stick-right", data.rx, data.ry);
  } else {
    document.getElementById("conn-icon").textContent = "🕹️";
    document.getElementById("conn-status").textContent = "Searching for gamepad…";
    drawStick("stick-left",  0, 0);
    drawStick("stick-right", 0, 0);
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { socket.emit("remote:stop"); window.location.href="/"; }
  if (e.key === " ") { e.preventDefault(); sendStop(); }
});

window.addEventListener("beforeunload", () => socket.emit("remote:stop"));
</script>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add apps/xbox_control/app.py apps/xbox_control/templates/
git commit -m "feat: remote (Xbox) app with live stick visualizer and cartesian jog"
```

---

## Task 8: Telemetry App

**Files:**
- Create: `apps/telemetry/app.py`
- Create: `apps/telemetry/templates/telemetry/telemetry.html`

- [ ] **Step 1: Create apps/telemetry/app.py**

```python
# apps/telemetry/app.py
from flask import Blueprint, render_template

NAME  = "Telemetry"
ICON  = "📊"
COLOR = "linear-gradient(145deg, #ab47bc, #4a148c)"
SLUG  = "telemetry"


def register(app, robot, socketio):
    bp = Blueprint("telemetry", __name__, template_folder="templates")

    @bp.route("/apps/telemetry")
    def index():
        return render_template("telemetry/telemetry.html")

    app.register_blueprint(bp)
```

- [ ] **Step 2: Create apps/telemetry/templates/telemetry/telemetry.html**

```html
{% extends "base.html" %}
{% block title %}Telemetry — PAROL6{% endblock %}
{% block nav_left %}<a class="nav-back" href="/">‹ Home</a>{% endblock %}
{% block nav_title %}Telemetry{% endblock %}

{% block content %}
<!-- Joint angles -->
<div class="card" style="margin-bottom:12px;">
  <div class="label-sm">Joint Angles</div>
  {% for i in range(6) %}
  <div style="display:flex; align-items:center; gap:10px; padding:6px 0; border-bottom:1px solid var(--border);">
    <span style="width:24px; font-size:11px; font-weight:700; color:var(--accent);">J{{ i+1 }}</span>
    <div style="flex:1; height:4px; background:var(--surface2); border-radius:2px; position:relative;">
      <div id="tbar-{{ i }}" style="height:100%; background:var(--accent); border-radius:2px; width:50%; transition:width 0.08s;"></div>
    </div>
    <span id="tang-{{ i }}" style="width:56px; font-size:12px; font-weight:600; text-align:right; color:var(--accent);">—</span>
  </div>
  {% endfor %}
</div>

<!-- XYZ -->
<div class="card" style="margin-bottom:12px;">
  <div class="label-sm">End Effector (World Frame)</div>
  <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:10px; text-align:center;">
    {% for ax, idx in [('X',0),('Y',1),('Z',2),('RX',3),('RY',4),('RZ',5)] %}
    <div>
      <div id="txyz-{{ idx }}" style="font-size:16px; font-weight:700; color:var(--warn);">—</div>
      <div style="font-size:10px; color:var(--text-dim);">{{ ax }}</div>
    </div>
    {% endfor %}
  </div>
</div>

<!-- Status -->
<div class="card">
  <div class="label-sm">Status</div>
  <div id="t-status" style="font-size:13px; color:var(--text-dim);">Waiting…</div>
</div>
{% endblock %}

{% block scripts %}
<script>
const LIMITS = [[-123.046875,123.046875],[-145.0088,-3.375],[107.866,287.8675],[-105.46975,105.46975],[-90,90],[0,360]];

document.addEventListener("pose_update", (e) => {
  const {joints, xyz, status} = e.detail;
  joints.forEach((v,i) => {
    const [mn,mx] = LIMITS[i];
    const pct = Math.max(0,Math.min(100,((v-mn)/(mx-mn))*100));
    document.getElementById(`tbar-${i}`).style.width = pct+"%";
    document.getElementById(`tang-${i}`).textContent = v.toFixed(2)+"°";
  });
  xyz.forEach((v,i) => {
    const suffix = i<3?"mm":"°";
    document.getElementById(`txyz-${i}`).textContent = v.toFixed(2)+suffix;
  });
  document.getElementById("t-status").textContent = status || "OK";
});

document.addEventListener("keydown", e => {
  if (e.key==="Escape") window.location.href="/";
});
</script>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add apps/telemetry/
git commit -m "feat: telemetry app with live joint bars and XYZ readout"
```

---

## Task 9: Sequences App

**Files:**
- Create: `apps/sequences/app.py`
- Create: `apps/sequences/templates/sequences/sequences.html`

- [ ] **Step 1: Create apps/sequences/app.py**

```python
# apps/sequences/app.py
import json
import os
import time
import threading
from flask import Blueprint, render_template, request, jsonify

NAME  = "Sequences"
ICON  = "⏺"
COLOR = "linear-gradient(145deg, #ffb300, #e65100)"
SLUG  = "sequences"

SEQ_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sequences")

_recording = False
_record_frames = []
_record_stop = threading.Event()
_playback_stop = threading.Event()


def _seq_path(name):
    os.makedirs(SEQ_DIR, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in "-_ ").strip().replace(" ", "_")
    return os.path.join(SEQ_DIR, f"{safe}.json")


def register(app, robot, socketio):
    bp = Blueprint("sequences", __name__, template_folder="templates")

    @bp.route("/apps/sequences")
    def index():
        seqs = []
        if os.path.isdir(SEQ_DIR):
            for f in os.listdir(SEQ_DIR):
                if f.endswith(".json"):
                    try:
                        with open(os.path.join(SEQ_DIR, f)) as fh:
                            data = json.load(fh)
                        seqs.append({
                            "name": f[:-5].replace("_", " "),
                            "frames": len(data),
                            "duration": round(len(data) / 10.0, 1),
                        })
                    except Exception:
                        pass
        return render_template("sequences/sequences.html", sequences=seqs)

    @bp.route("/api/sequences/record/start", methods=["POST"])
    def record_start():
        global _recording, _record_frames, _record_stop
        if _recording:
            return jsonify({"ok": False, "error": "already recording"})
        _recording = True
        _record_frames = []
        _record_stop = threading.Event()
        stop_ev = _record_stop

        def _loop():
            global _recording
            while not stop_ev.is_set():
                try:
                    pose = robot.get_pose()
                    _record_frames.append(list(pose))
                except Exception:
                    pass
                socketio.sleep(0.1)  # 10 Hz
            _recording = False

        socketio.start_background_task(_loop)
        return jsonify({"ok": True})

    @bp.route("/api/sequences/record/stop", methods=["POST"])
    def record_stop():
        name = request.json.get("name", f"seq_{int(time.time())}")
        _record_stop.set()
        if _record_frames:
            with open(_seq_path(name), "w") as f:
                json.dump(_record_frames, f)
        count = len(_record_frames)
        return jsonify({"ok": True, "frames": count, "name": name})

    @bp.route("/api/sequences/play", methods=["POST"])
    def play():
        global _playback_stop
        name = request.json.get("name", "")
        path = _seq_path(name)
        if not os.path.exists(path):
            return jsonify({"ok": False, "error": "not found"})
        with open(path) as f:
            frames = json.load(f)
        _playback_stop = threading.Event()
        stop_ev = _playback_stop

        def _loop():
            for frame in frames:
                if stop_ev.is_set():
                    break
                try:
                    robot.go_to_joints(frame[:6])
                except Exception:
                    break
                socketio.sleep(0.1)

        socketio.start_background_task(_loop)
        return jsonify({"ok": True})

    @bp.route("/api/sequences/stop", methods=["POST"])
    def stop_play():
        _playback_stop.set()
        return jsonify({"ok": True})

    @bp.route("/api/sequences/delete", methods=["POST"])
    def delete():
        name = request.json.get("name", "")
        path = _seq_path(name)
        if os.path.exists(path):
            os.remove(path)
        return jsonify({"ok": True})

    app.register_blueprint(bp)
```

- [ ] **Step 2: Create apps/sequences/templates/sequences/sequences.html**

```html
{% extends "base.html" %}
{% block title %}Sequences — PAROL6{% endblock %}
{% block nav_left %}<a class="nav-back" href="/">‹ Home</a>{% endblock %}
{% block nav_title %}Sequences{% endblock %}

{% block content %}
<!-- Record controls -->
<div class="card" style="margin-bottom:12px;">
  <div class="label-sm">Record New Sequence</div>
  <div style="display:flex; gap:8px; margin-bottom:10px;">
    <input id="seq-name" type="text" placeholder="Sequence name…"
      style="flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:8px 12px;color:var(--text);font-size:13px;outline:none;">
    <button class="btn btn-danger" id="btn-rec" onclick="toggleRecord()">⏺ Record</button>
  </div>
  <div id="rec-status" style="font-size:11px;color:var(--text-dim);">Press Record to start capturing poses at 10 Hz</div>
</div>

<!-- Sequence list -->
<div class="card">
  <div class="label-sm">Saved Sequences</div>
  {% if sequences %}
  {% for seq in sequences %}
  <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);" id="seq-{{ loop.index }}">
    <div style="flex:1;">
      <div style="font-size:13px;font-weight:600;">{{ seq.name }}</div>
      <div style="font-size:10px;color:var(--text-dim);">{{ seq.frames }} frames · {{ seq.duration }}s</div>
    </div>
    <button class="btn btn-primary" style="padding:5px 12px;font-size:11px;" onclick="playSeq('{{ seq.name }}')">▶ Play</button>
    <button class="btn btn-surface" style="padding:5px 10px;font-size:11px;" onclick="deleteSeq('{{ seq.name }}', this)">🗑</button>
  </div>
  {% endfor %}
  <button class="btn btn-danger" style="margin-top:10px;width:100%;" onclick="stopPlay()">■ Stop Playback</button>
  {% else %}
  <div style="color:var(--text-dim);font-size:13px;padding:12px 0;text-align:center;">No sequences yet. Record one above.</div>
  {% endif %}
</div>
{% endblock %}

{% block scripts %}
<script>
let recording = false;

async function toggleRecord() {
  if (!recording) {
    await fetch("/api/sequences/record/start", {method:"POST"});
    recording = true;
    document.getElementById("btn-rec").textContent = "⏹ Stop";
    document.getElementById("btn-rec").className = "btn btn-surface";
    document.getElementById("rec-status").textContent = "Recording… move the arm now";
  } else {
    const name = document.getElementById("seq-name").value || "sequence";
    const r = await fetch("/api/sequences/record/stop", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({name})
    });
    const d = await r.json();
    recording = false;
    document.getElementById("btn-rec").textContent = "⏺ Record";
    document.getElementById("btn-rec").className = "btn btn-danger";
    document.getElementById("rec-status").textContent = `Saved "${name}" — ${d.frames} frames. Reload to see it.`;
  }
}

async function playSeq(name) {
  await fetch("/api/sequences/play", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name})
  });
}

async function stopPlay() {
  await fetch("/api/sequences/stop", {method:"POST"});
}

async function deleteSeq(name, btn) {
  await fetch("/api/sequences/delete", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name})
  });
  btn.closest("[id^='seq-']").remove();
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") window.location.href = "/";
});
</script>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add apps/sequences/
git commit -m "feat: sequences app — record and replay joint motion at 10 Hz"
```

---

## Task 10: Poses App

**Files:**
- Create: `apps/poses/app.py`
- Create: `apps/poses/templates/poses/poses.html`

- [ ] **Step 1: Create apps/poses/app.py**

```python
# apps/poses/app.py
import json
import os
import time
from flask import Blueprint, render_template, request, jsonify

NAME  = "Poses"
ICON  = "📍"
COLOR = "linear-gradient(145deg, #26c6da, #006064)"
SLUG  = "poses"

POSES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "poses.json")


def _load():
    if os.path.exists(POSES_FILE):
        with open(POSES_FILE) as f:
            return json.load(f)
    return []


def _save(poses):
    os.makedirs(os.path.dirname(POSES_FILE), exist_ok=True)
    with open(POSES_FILE, "w") as f:
        json.dump(poses, f, indent=2)


def register(app, robot, socketio):
    bp = Blueprint("poses", __name__, template_folder="templates")

    @bp.route("/apps/poses")
    def index():
        return render_template("poses/poses.html", poses=_load())

    @bp.route("/api/poses/save", methods=["POST"])
    def save():
        name = request.json.get("name", f"pose_{int(time.time())}")
        try:
            pose = robot.get_pose()
            joints = list(pose[:6])
            xyz    = list(pose[6:12]) if len(pose) >= 12 else [0.0]*6
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
        poses = _load()
        poses.append({
            "name": name,
            "timestamp": int(time.time()),
            "joints": joints,
            "xyz": xyz,
        })
        _save(poses)
        return jsonify({"ok": True, "joints": joints, "xyz": xyz})

    @bp.route("/api/poses/goto", methods=["POST"])
    def goto():
        name = request.json.get("name", "")
        poses = _load()
        match = next((p for p in poses if p["name"] == name), None)
        if not match:
            return jsonify({"ok": False, "error": "not found"})
        try:
            robot.go_to_joints(match["joints"])
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
        return jsonify({"ok": True})

    @bp.route("/api/poses/delete", methods=["POST"])
    def delete():
        name = request.json.get("name", "")
        poses = [p for p in _load() if p["name"] != name]
        _save(poses)
        return jsonify({"ok": True})

    app.register_blueprint(bp)
```

- [ ] **Step 2: Create apps/poses/templates/poses/poses.html**

```html
{% extends "base.html" %}
{% block title %}Poses — PAROL6{% endblock %}
{% block nav_left %}<a class="nav-back" href="/">‹ Home</a>{% endblock %}
{% block nav_title %}Poses{% endblock %}

{% block content %}
<!-- Save current pose -->
<div class="card" style="margin-bottom:12px;">
  <div class="label-sm">Save Current Pose</div>
  <div style="display:flex;gap:8px;">
    <input id="pose-name" type="text" placeholder="Pose name…"
      style="flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:8px 12px;color:var(--text);font-size:13px;outline:none;">
    <button class="btn btn-primary" onclick="savePose()">Save</button>
  </div>
  <div id="save-status" style="font-size:11px;color:var(--text-dim);margin-top:6px;"></div>
</div>

<!-- Pose list -->
<div class="card">
  <div class="label-sm">Saved Poses</div>
  <div id="pose-list">
    {% if poses %}
    {% for p in poses %}
    <div class="pose-item" data-name="{{ p.name }}" style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);">
      <div style="flex:1;">
        <div style="font-size:13px;font-weight:600;">{{ p.name }}</div>
        <div style="font-size:10px;color:var(--text-dim);">
          J: {{ p.joints|map('round', 1)|join(', ') }}
        </div>
      </div>
      <button class="btn btn-primary" style="padding:5px 12px;font-size:11px;" onclick="goToPose('{{ p.name }}')">Go</button>
      <button class="btn btn-surface" style="padding:5px 10px;font-size:11px;" onclick="deletePose('{{ p.name }}', this)">🗑</button>
    </div>
    {% endfor %}
    {% else %}
    <div style="color:var(--text-dim);font-size:13px;padding:12px 0;text-align:center;" id="empty-msg">No poses saved yet.</div>
    {% endif %}
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
async function savePose() {
  const name = document.getElementById("pose-name").value.trim();
  if (!name) { document.getElementById("save-status").textContent = "Enter a name first."; return; }
  const r = await fetch("/api/poses/save", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name})
  });
  const d = await r.json();
  if (d.ok) {
    document.getElementById("save-status").textContent = `"${name}" saved.`;
    document.getElementById("pose-name").value = "";
    appendPoseRow(name, d.joints);
  } else {
    document.getElementById("save-status").textContent = "Error: " + d.error;
  }
}

function appendPoseRow(name, joints) {
  const list = document.getElementById("pose-list");
  const empty = document.getElementById("empty-msg");
  if (empty) empty.remove();
  const div = document.createElement("div");
  div.className = "pose-item";
  div.dataset.name = name;
  div.style.cssText = "display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);";
  div.innerHTML = `
    <div style="flex:1;">
      <div style="font-size:13px;font-weight:600;">${name}</div>
      <div style="font-size:10px;color:var(--text-dim);">J: ${joints.map(v=>v.toFixed(1)).join(", ")}</div>
    </div>
    <button class="btn btn-primary" style="padding:5px 12px;font-size:11px;" onclick="goToPose('${name}')">Go</button>
    <button class="btn btn-surface" style="padding:5px 10px;font-size:11px;" onclick="deletePose('${name}', this)">🗑</button>`;
  list.appendChild(div);
}

async function goToPose(name) {
  const r = await fetch("/api/poses/goto", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name})
  });
  const d = await r.json();
  if (!d.ok) alert("Error: " + d.error);
}

async function deletePose(name, btn) {
  await fetch("/api/poses/delete", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name})
  });
  btn.closest(".pose-item").remove();
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") window.location.href = "/";
});
</script>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add apps/poses/
git commit -m "feat: poses app — save and recall named joint configurations"
```

---

## Task 11: Integration Test + Final Verification

**Files:**
- Create: `tests/test_apps.py`

- [ ] **Step 1: Write integration tests**

```python
# tests/test_apps.py
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def app():
    with patch("core.robot.manage_server"), \
         patch("core.robot.RobotClient") as MockClient:
        mock_client = MagicMock()
        mock_client.get_pose.return_value = [90.0,-90.0,180.0,0.0,0.0,180.0,100.0,50.0,300.0,0.0,0.0,0.0]
        mock_client.get_status.return_value = "ok"
        MockClient.return_value.__enter__ = lambda s: mock_client
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        from server import create_app
        flask_app, _ = create_app(simulate=True)
        flask_app.config["TESTING"] = True
        yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

def test_all_app_routes_200(client):
    for slug in ["manual", "remote", "telemetry", "sequences", "poses"]:
        resp = client.get(f"/apps/{slug}")
        assert resp.status_code == 200, f"/apps/{slug} returned {resp.status_code}"

def test_poses_save_and_list(client):
    import json, os, tempfile
    resp = client.post("/api/poses/save",
        data=json.dumps({"name":"test_pose"}),
        content_type="application/json")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True

def test_sequences_record_start_stop(client):
    import json
    resp = client.post("/api/sequences/record/start", content_type="application/json")
    assert json.loads(resp.data)["ok"] is True
    resp = client.post("/api/sequences/record/stop",
        data=json.dumps({"name":"test_seq"}), content_type="application/json")
    assert json.loads(resp.data)["ok"] is True
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/ -v
# Expected: all tests pass (some may skip if simulator unavailable)
```

- [ ] **Step 3: Full manual smoke test**

```bash
python run.py
```

Check each item:
- [ ] Home screen loads — 5 tiles visible, status pill green
- [ ] Manual → press `1`, hold `→` arrow → J1 bar moves, angle updates
- [ ] Manual → press `H` → arm homes, all bars jump to home angles
- [ ] Manual → `■ STOP` button → motion halts
- [ ] Remote → page loads, stick visualizers shown
- [ ] Telemetry → all 6 joint bars updating live at ~50 Hz
- [ ] Sequences → record 5 seconds of motion, stop, see it in list, play it back
- [ ] Poses → save current pose, click Go → arm moves there
- [ ] `Esc` on any app page → returns to home screen

- [ ] **Step 4: Final commit**

```bash
git add tests/test_apps.py
git commit -m "feat: integration tests and full app suite complete"
```

---

## Joint Limits Reference (from PAROL6_ROBOT.py)

| Joint | Min | Max | Home | Notes |
|-------|-----|-----|------|-------|
| J1 Base | −123.05° | 123.05° | 90° | Symmetric |
| J2 Shoulder | −145.01° | −3.38° | −90° | Always negative range |
| J3 Elbow | 107.87° | 287.87° | 180° | Avoid near 287° (singularity) |
| J4 Wrist 1 | −105.47° | 105.47° | 0° | Symmetric |
| J5 Wrist 2 | −90° | 90° | 0° | Symmetric |
| J6 Tool | 0° | 360° | 180° | Full rotation |

Jog speed fraction: always use ≤ 0.8 (80% of max per PAROL6 safety spec).
