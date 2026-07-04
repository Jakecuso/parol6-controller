"""Gripper mini-app — open/close the MSG gripper and set jaw position.

Talks to the gripper DIRECTLY over UART (core/gripper_serial.py), independent of
the arm's CAN bus. Commands run in a background task so the SocketIO handler
never blocks on serial I/O. Errors (e.g. no adapter plugged in) surface as a
toast.
"""
from flask import Blueprint, render_template

from core.gripper_serial import GripperSerial

NAME  = "Gripper"
ICON  = "🤏"
COLOR = "linear-gradient(145deg, #26a69a, #00695c)"
SLUG  = "gripper"

_grip = GripperSerial()


def register(app, robot, socketio):
    bp = Blueprint("gripper", __name__, template_folder="templates")

    @bp.route("/apps/gripper")
    def index():
        return render_template("gripper/gripper.html")

    app.register_blueprint(bp)

    def _run(fn, label):
        """Run a gripper serial command off the SocketIO thread; surface errors."""
        print(f"[gripper] command: {label}")

        def _task():
            try:
                fn()
            except Exception as e:
                print(f"[gripper] {label} error: {e}")
                socketio.emit("robot:error", {"msg": f"Gripper {label}: {e}"})
        socketio.start_background_task(_task)

    @socketio.on("gripper:open")
    def _open():
        _run(_grip.open_jaws, "open")

    @socketio.on("gripper:close")
    def _close():
        _run(_grip.close_jaws, "close")

    @socketio.on("gripper:set")
    def _set(data):
        pct = max(0.0, min(100.0, float((data or {}).get("position", 0))))
        value = round(pct / 100.0 * 255)   # 0% -> 0 (open), 100% -> 255 (closed)
        _run(lambda: _grip.set_position(value), f"set {pct:.0f}% ({value})")

    @socketio.on("gripper:calibrate")
    def _cal():
        _run(_grip.calibrate, "calibrate")
