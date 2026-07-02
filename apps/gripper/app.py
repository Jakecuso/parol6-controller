"""Gripper mini-app — open/close the MSG gripper and set jaw position.

All hardware access goes through core/robot.py (robot.gripper_*). Moves run in a
background task so the SocketIO handler never blocks while the jaws travel.
"""
from flask import Blueprint, render_template

NAME  = "Gripper"
ICON  = "🤏"
COLOR = "linear-gradient(145deg, #26a69a, #00695c)"
SLUG  = "gripper"


def register(app, robot, socketio):
    bp = Blueprint("gripper", __name__, template_folder="templates")

    @bp.route("/apps/gripper")
    def index():
        return render_template("gripper/gripper.html")

    app.register_blueprint(bp)

    def _run(fn, label):
        """Run a gripper command off the SocketIO thread; surface errors."""
        def _task():
            try:
                rc = fn()
                if rc == -1:
                    socketio.emit("robot:error",
                                  {"msg": f"Gripper {label}: arm not connected"})
            except Exception as e:
                print(f"[gripper] {label} error: {e}")
                socketio.emit("robot:error", {"msg": f"Gripper {label} error: {e}"})
        socketio.start_background_task(_task)

    @socketio.on("gripper:open")
    def _open():
        _run(robot.gripper_open, "open")

    @socketio.on("gripper:close")
    def _close():
        _run(robot.gripper_close, "close")

    @socketio.on("gripper:set")
    def _set(data):
        pct = float((data or {}).get("position", 0))
        pos = max(0.0, min(1.0, pct / 100.0))
        _run(lambda: robot.gripper_move(pos), f"set {pct:.0f}%")

    @socketio.on("gripper:calibrate")
    def _cal():
        _run(robot.gripper_calibrate, "calibrate")
