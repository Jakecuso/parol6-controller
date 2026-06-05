import time
import threading
from flask import Blueprint, render_template

NAME  = "Manual"
ICON  = "🎮"
COLOR = "linear-gradient(145deg, #2196f3, #0d47a1)"
SLUG  = "manual"

JOINT_NAMES  = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Tool"]
JOINT_LIMITS = [
    (-123.046875, 123.046875),
    (-145.0088,   -3.375),
    (107.866,     287.8675),
    (-105.46975,  105.46975),
    (-90.0,       90.0),
    (0.0,         360.0),
]
HOME_ANGLES = [90.0, -90.0, 180.0, 0.0, 0.0, 180.0]

_jog_stop = threading.Event()
_jog_thread = None


def register(app, robot, socketio):
    bp = Blueprint("manual", __name__, template_folder="templates")

    @bp.route("/apps/manual")
    def index():
        return render_template("manual_control/manual.html", limits=JOINT_LIMITS)

    app.register_blueprint(bp)

    @socketio.on("manual:jog_start")
    def handle_jog_start(data):
        global _jog_thread, _jog_stop
        _jog_stop.set()
        _jog_stop = threading.Event()
        stop_event = _jog_stop

        jog_type   = data.get("type", "joint")
        joint_idx  = data.get("joint", 0)       # 0-indexed from browser
        direction  = data.get("direction", 1)
        axis       = data.get("axis", "X")
        axes_combo = data.get("axes")            # dict {"X":1,"Y":-1} for multi-axis cart
        speed_pct  = float(data.get("speed", 25))

        def _loop():
            while not stop_event.is_set():
                try:
                    if jog_type == "joint":
                        rc = robot.jog_joint(joint_idx + 1, direction * speed_pct)
                    elif axes_combo:
                        # Normalize diagonal speed so combined magnitude equals single-axis
                        n = len(axes_combo)
                        norm = (1.0 / (n ** 0.5)) if n > 1 else 1.0
                        axes_speeds = {ax: d * speed_pct * norm for ax, d in axes_combo.items()}
                        rc = robot.jog_cartesian_multi(axes_speeds)
                    else:
                        rc = robot.jog_cartesian(axis, direction * speed_pct)
                    if rc == -1:
                        socketio.emit("robot:error", {
                            "msg": "Controller disabled — go to Settings → Enable"
                        })
                        break
                except Exception as e:
                    print(f"[manual] jog error: {e}")
                    socketio.emit("robot:error", {"msg": f"Jog error: {e}"})
                    break
                time.sleep(0.15)

        _jog_thread = socketio.start_background_task(_loop)

    @socketio.on("manual:jog_stop")
    def handle_jog_stop():
        _jog_stop.set()
