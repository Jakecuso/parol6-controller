import argparse
import time
import webbrowser

from server import create_app, socketio

def parse_args():
    p = argparse.ArgumentParser(description="PAROL6 Web Controller")
    p.add_argument("--real", action="store_true", help="Connect to real hardware")
    p.add_argument("--port", type=int, default=5050)
    return p.parse_args()

def telemetry_loop(app, sock):
    """Background greenlet: push pose_update at ~50 Hz."""
    robot = app.robot
    with app.app_context():
        while True:
            try:
                joints = list(robot.get_angles() or [0.0]*6)
                xyz = list(robot.get_pose() or [0.0]*6)
                status = robot.get_status()
                sock.emit("pose_update", {
                    "joints": joints,
                    "xyz": xyz,
                    "status": str(status) if status else "ok",
                    "error": False,
                }, broadcast=True)
            except Exception as e:
                print(f"[telemetry] error: {e}")
                try:
                    sock.emit("pose_update", {
                        "joints": [0.0]*6,
                        "xyz": [0.0]*6,
                        "status": "error",
                        "error": True,
                    }, broadcast=True)
                except Exception:
                    pass
            time.sleep(0.02)  # 50 Hz

if __name__ == "__main__":
    args = parse_args()
    simulate = not args.real
    app, sock = create_app(simulate=simulate)

    sock.start_background_task(telemetry_loop, app, sock)

    url = f"http://localhost:{args.port}"
    print(f"PAROL6 Controller → {url}")
    webbrowser.open(url)

    sock.run(app, host="0.0.0.0", port=args.port, debug=False)
