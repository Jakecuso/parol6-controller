import argparse
import os
import time
import webbrowser

from server import create_app, socketio


def _env_flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def parse_args():
    # Env vars are the deploy-time knobs (systemd sets them on the Pi); the CLI
    # flags override them for ad-hoc runs on the dev machine.
    #   PAROL6_SIMULATE=0   → real hardware   (default 1 = simulator, safe)
    #   PAROL6_PORT=5050    → web port
    #   PAROL6_NO_BROWSER=1 → don't try to open a browser (headless Pi)
    env_simulate = _env_flag("PAROL6_SIMULATE", True)
    env_port = int(os.environ.get("PAROL6_PORT", "5050"))
    env_no_browser = _env_flag("PAROL6_NO_BROWSER", False)

    p = argparse.ArgumentParser(description="PAROL6 Web Controller")
    p.add_argument("--real", action="store_true", default=not env_simulate,
                   help="Connect to real hardware (default from PAROL6_SIMULATE)")
    p.add_argument("--sim", dest="real", action="store_false",
                   help="Force simulator mode")
    p.add_argument("--port", type=int, default=env_port)
    p.add_argument("--no-browser", action="store_true", default=env_no_browser,
                   help="Don't open a browser on start (for headless/Pi)")
    return p.parse_args()

_last_telem_err_time = 0.0
_TELEM_ERR_INTERVAL = 2.0  # only print/emit errors this often


def telemetry_loop(app, sock):
    """Background thread: push pose_update at ~50 Hz."""
    global _last_telem_err_time
    robot = app.robot
    with app.app_context():
        while True:
            try:
                joints = list(robot.get_angles() or [0.0]*6)
                xyz = list(robot.get_pose() or [0.0]*6)
                status = robot.get_status()
                io = list(getattr(status, "io", []) or [])
                estop = (io[4] == 0) if len(io) > 4 else False
                sock.emit("pose_update", {
                    "joints": joints,
                    "xyz": xyz,
                    "status": str(status) if status else "ok",
                    "estop": estop,
                    "error": False,
                })
            except Exception as e:
                now = time.time()
                if now - _last_telem_err_time >= _TELEM_ERR_INTERVAL:
                    print(f"[telemetry] {e}")
                    _last_telem_err_time = now
                    try:
                        sock.emit("pose_update", {
                            "joints": [0.0]*6,
                            "xyz": [0.0]*6,
                            "status": "error",
                            "error": True,
                        })
                    except Exception:
                        pass
            time.sleep(0.02)  # 50 Hz

if __name__ == "__main__":
    args = parse_args()
    simulate = not args.real
    app, sock = create_app(simulate=simulate)

    sock.start_background_task(telemetry_loop, app, sock)

    mode = "SIMULATOR" if simulate else "REAL HARDWARE"
    print(f"PAROL6 Controller [{mode}] → http://localhost:{args.port}")
    print(f"  on the network: http://<this-host>.local:{args.port}")
    if not args.no_browser:
        try:
            webbrowser.open(f"http://localhost:{args.port}")
        except Exception:
            pass

    # allow_unsafe_werkzeug: we intentionally use the built-in server in
    # threading mode for this LAN-only app (Flask-SocketIO blocks it otherwise).
    sock.run(app, host="0.0.0.0", port=args.port, debug=False,
             allow_unsafe_werkzeug=True)
