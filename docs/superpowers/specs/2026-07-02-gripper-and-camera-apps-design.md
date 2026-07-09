# Gripper + Camera Apps — Design

**Date:** 2026-07-02
**Status:** Approved (pending spec review)

## Overview

Add two new mini-apps to the PAROL6 Controller so the operator can, from the
phone/touchscreen home screen:

1. **Gripper** — open/close the MSG electric gripper and set any jaw position.
2. **Camera** — watch a live video feed from a USB webcam on the Pi.

Both follow the existing mini-app pattern (`apps/<name>/app.py` exposing
`NAME/ICON/COLOR/SLUG/register(app, robot, socketio)`, registered by adding the
name to `APP_DIRS` in `server.py`). All hardware access stays behind
`core/robot.py` for the gripper; the camera is Pi-local hardware and lives in its
own app module.

## Goals

- Gripper: **Open** and **Close** buttons plus a **position slider (0–100%)**, with
  a live position readout.
- Camera: a **live MJPEG feed** shown full-frame; graceful placeholder if no camera.
- Fit the existing architecture; no new comms layer, no bypassing `core/robot.py`
  for robot hardware.
- Sim-safe: on the Mac (`simulate=True`) the gripper controls no-op with a log;
  the camera falls back to a placeholder when `/dev/video0` is absent.

## Non-goals (v1)

- Grip-force/strength UI (the API's default current + built-in object-detection is
  used; explicit force control is a future enhancement).
- Snapshot/record or object detection / vision pipeline (future).
- Combined gripper+camera screen (kept as two separate apps).
- WebRTC / low-latency transport (MJPEG is sufficient for a LAN touchscreen).

## Architecture & data flow

**Gripper:**
```
apps/gripper (SocketIO)  →  core/robot.py gripper_* methods  →  parol6 sync client
    .tool_action(<electric-gripper key>, "move"|"calibrate", [pos, speed, current])
    →  PAR6 controller  →  CAN  →  STEPFOC gripper (node 6)
```
The gripper is an `ElectricGripperTool` in the parol6 API. Actions: `"move"`
(params: position 0.0–1.0, speed 0.0–1.0, current mA) and `"calibrate"` (the
`#Gripcal` one-shot). `core/robot.py` resolves the tool key from the client's tool
collection (electric-gripper type) rather than hardcoding a string.

**Camera:**
```
apps/camera  →  background OpenCV capture thread (/dev/video0)
    →  Flask route /apps/camera/stream  (multipart/x-mixed-replace: JPEG frames)
    →  <img> tag in template
```

## Component 1 — `core/robot.py` (gripper methods)

Add, alongside the existing arm wrappers:

- `gripper_move(position: float, speed: float = 0.5, current: int = 500) -> None`
  — clamps `position` to 0.0–1.0; calls `client.tool_action(key, "move", [position, speed, current])`.
- `gripper_open() -> None` — `gripper_move(0.0)`.
- `gripper_close() -> None` — `gripper_move(1.0)`.
- `gripper_calibrate() -> None` — `client.tool_action(key, "calibrate")`.
- `gripper_position() -> float | None` — last known jaw position (0.0–1.0) from
  tool status/feedback, or `None` if unavailable.

Behavior:
- **Simulate mode / not connected:** methods return immediately after logging
  (`[robot] gripper_move ignored (sim/not connected)`); never raise.
- **Errors:** wrap `tool_action` calls; on timeout/exception, log and surface a
  status string to the app rather than crashing the SocketIO handler.

## Component 2 — `apps/gripper/`

- `app.py`: `NAME="Gripper"`, an icon, a color gradient, `SLUG="gripper"`,
  `register(app, robot, socketio)`:
  - Blueprint route `/apps/gripper` → renders template.
  - SocketIO handlers: `gripper_open`, `gripper_close`, `gripper_set` (payload:
    `{position: 0..100}` → `robot.gripper_move(position/100)`), `gripper_calibrate`.
  - Emit a `gripper_status` event with the current position/connection state so the
    UI slider/readout can reflect reality.
- `templates/gripper/gripper.html`: two large touch buttons (**Open**, **Close**),
  a horizontal **position slider 0–100%** that sends `gripper_set` on release, a
  numeric position readout, and a small **Calibrate** action (guarded with a
  confirm, since it moves the jaws through full travel).

## Component 3 — `apps/camera/`

- `app.py`: `NAME="Camera"`, icon, color, `SLUG="camera"`,
  `register(app, robot, socketio)`:
  - A capture module/thread opens `/dev/video0` via OpenCV, grabs frames, JPEG-encodes
    the latest frame (single-slot, newest-wins) so slow clients don't back up.
  - Route `/apps/camera/stream` yields `multipart/x-mixed-replace; boundary=frame`.
  - Capture starts lazily on first stream request and stops when idle (ref-count or
    timeout) to free the webcam.
  - If the camera can't be opened, the stream serves a static "No camera" placeholder
    JPEG instead of erroring.
- `templates/camera/camera.html`: full-frame `<img src="/apps/camera/stream">` with
  the standard app chrome.
- Resolution/FPS modest by default (e.g. 640×480 @ ~15 fps) to keep Pi CPU low;
  values defined as module constants.

## Registration & dependencies

- Add `"gripper"` and `"camera"` to `APP_DIRS` in `server.py` (per README step).
- Add `opencv-python-headless` to `requirements.txt` (headless = no GUI libs, right
  for a Pi). Note in `PI_SETUP` that the camera app needs it and a USB webcam.

## Error handling summary

| Failure | Behavior |
|---|---|
| Gripper: sim mode / arm not connected | Log + no-op; UI shows "not connected" |
| Gripper: `tool_action` timeout/error | Log; emit status; UI stays responsive |
| Camera: no `/dev/video0` | Stream serves "No camera" placeholder frame |
| Camera: capture thread dies | Auto-restart on next stream request; placeholder meanwhile |

## Testing

- **Gripper (Mac, sim):** handlers call `robot.gripper_*` and no-op cleanly; UI
  loads, buttons/slider emit correct SocketIO payloads.
- **Gripper (Pi, real):** Open/Close/slider move the jaws; Calibrate runs `#Gripcal`;
  position readout tracks feedback.
- **Camera (Mac):** no `/dev/video0` → placeholder shown, no crash.
- **Camera (Pi):** live feed visible on the touchscreen; capture stops when the app
  is closed (webcam LED off / freed).
- Both new apps appear on the home screen and don't break existing app loading.

## Open questions

None — scope is fixed for v1. Force control, snapshot/record, and vision are
explicitly deferred to future work.
