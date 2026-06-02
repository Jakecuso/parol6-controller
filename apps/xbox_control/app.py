import time
import threading
from flask import Blueprint, render_template

NAME  = "Remote"
ICON  = "🕹️"
COLOR = "linear-gradient(145deg, #ff7043, #bf360c)"
SLUG  = "remote"

DEADZONE = 0.15
MAX_SPEED = 80.0

AXIS_MAP = [
    (0, "X",   1),   # left stick X  → Cartesian X
    (1, "Y",  -1),   # left stick Y  → Cartesian Y (inverted)
    (3, "Z",  -1),   # right stick Y → Cartesian Z
    (2, "RZ",  1),   # right stick X → rotate Z
]

_gamepad_stop = threading.Event()


def register(app, robot, socketio):
    bp = Blueprint("remote", __name__, template_folder="templates")

    @bp.route("/apps/remote")
    def index():
        return render_template("xbox_control/remote.html")

    app.register_blueprint(bp)

    @socketio.on("remote:start")
    def handle_start():
        global _gamepad_stop
        _gamepad_stop.set()
        _gamepad_stop = threading.Event()
        stop_event = _gamepad_stop

        def _loop():
            try:
                import pygame
                pygame.init()
                pygame.joystick.init()
            except ImportError:
                socketio.emit("remote:state", {"connected": False, "error": "pygame not installed"})
                return

            while not stop_event.is_set():
                try:
                    pygame.event.pump()
                    if pygame.joystick.get_count() == 0:
                        socketio.emit("remote:state", {"connected": False})
                        time.sleep(0.5)
                        continue

                    js = pygame.joystick.Joystick(0)
                    js.init()
                    num_axes = js.get_numaxes()
                    axes = [js.get_axis(i) for i in range(num_axes)]

                    state = {
                        "connected": True,
                        "lx": axes[0] if num_axes > 0 else 0,
                        "ly": axes[1] if num_axes > 1 else 0,
                        "rx": axes[2] if num_axes > 2 else 0,
                        "ry": axes[3] if num_axes > 3 else 0,
                    }
                    socketio.emit("remote:state", state)

                    for axis_idx, cart_axis, sign in AXIS_MAP:
                        if axis_idx < len(axes):
                            val = axes[axis_idx] * sign
                            if abs(val) > DEADZONE:
                                speed = (abs(val) - DEADZONE) / (1.0 - DEADZONE) * MAX_SPEED
                                direction = 1 if val > 0 else -1
                                try:
                                    robot.jog_cartesian(cart_axis, direction * speed)
                                except Exception as e:
                                    print(f"[remote] jog error: {e}")

                except Exception as e:
                    print(f"[remote] loop error: {e}")

                time.sleep(0.02)

            try:
                import pygame
                pygame.quit()
            except Exception:
                pass

        socketio.start_background_task(_loop)

    @socketio.on("remote:stop")
    def handle_stop():
        _gamepad_stop.set()
