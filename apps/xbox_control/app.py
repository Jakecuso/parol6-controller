import json
import os
import time
import threading
from pathlib import Path
from flask import Blueprint, render_template, jsonify, request

NAME  = "Remote"
ICON  = "🕹️"
COLOR = "linear-gradient(145deg, #ff7043, #bf360c)"
SLUG  = "remote"

DEADZONE  = 0.15

# Left stick  → X/Y plane  |  Right stick → RX/RY rotation  |  LB/RB → Z up/down
AXIS_MAP = [
    (0, "X",   1),   # left  X
    (1, "Y",  -1),   # left  Y (stick down = negative)
    (2, "RX",  1),   # right X
    (3, "RY", -1),   # right Y
]
BTN_LB = 4
BTN_RB = 5

BUTTON_NAMES = {
    "btn_0": "A",     "btn_1": "B",     "btn_2": "X",     "btn_3": "Y",
    "btn_4": "LB",    "btn_5": "RB",    "btn_6": "Back",  "btn_7": "Start",
    "btn_8": "L3",    "btn_9": "R3",
    "hat_0_1": "D-Pad ↑", "hat_0_-1": "D-Pad ↓",
    "hat_-1_0": "D-Pad ←", "hat_1_0": "D-Pad →",
}

ACTIONS = {
    "none":       "— None —",
    "stop":       "Emergency Stop",
    "home":       "Go Home",
    "enable":     "Enable Motors",
    "speed_up":   "Speed +10%",
    "speed_down": "Speed −10%",
    "save_pose":  "Save Current Pose",
}

BINDINGS_PATH = Path(__file__).parent.parent.parent / "config" / "button_bindings.json"

_gamepad_stop = threading.Event()
_jog_speed    = 50.0  # separate speed for the gamepad loop


def _load_bindings():
    try:
        return json.loads(BINDINGS_PATH.read_text())
    except Exception:
        return {}


def _save_bindings(b):
    BINDINGS_PATH.parent.mkdir(exist_ok=True)
    BINDINGS_PATH.write_text(json.dumps(b, indent=2))


def _execute_action(action, robot, socketio):
    global _jog_speed
    if not action or action == "none":
        return
    try:
        if action == "stop":
            robot.stop()
            socketio.emit("settings:resume_ack", {"ok": False, "msg": "Halted by gamepad"})
        elif action == "home":
            threading.Thread(target=robot.home, daemon=True).start()
            socketio.emit("remote:feedback", {"msg": "Going home…"})
        elif action == "enable":
            robot.resume()
            socketio.emit("remote:feedback", {"msg": "Motors enabled"})
        elif action == "speed_up":
            _jog_speed = min(100.0, _jog_speed + 10.0)
            socketio.emit("remote:speed", {"speed": _jog_speed})
        elif action == "speed_down":
            _jog_speed = max(5.0, _jog_speed - 10.0)
            socketio.emit("remote:speed", {"speed": _jog_speed})
        elif action == "save_pose":
            socketio.emit("remote:feedback", {"msg": "Pose saved"})
    except Exception as e:
        print(f"[remote] action error ({action}): {e}")


def register(app, robot, socketio):
    bp = Blueprint("remote", __name__, template_folder="templates")

    @bp.route("/apps/remote")
    def index():
        return render_template(
            "xbox_control/remote.html",
            button_names=BUTTON_NAMES,
            actions=ACTIONS,
            bindings=_load_bindings(),
            jog_speed=_jog_speed,
        )

    @bp.route("/apps/remote/bindings", methods=["GET"])
    def get_bindings():
        return jsonify(_load_bindings())

    @bp.route("/apps/remote/bindings", methods=["POST"])
    def post_bindings():
        _save_bindings(request.get_json(force=True))
        return jsonify({"ok": True})

    app.register_blueprint(bp)

    @socketio.on("remote:start")
    def handle_start():
        global _gamepad_stop
        _gamepad_stop.set()
        _gamepad_stop = threading.Event()
        stop_event = _gamepad_stop

        def _loop():
            global _jog_speed
            # Headless SDL — no display needed, prevents crash on macOS background thread
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

            try:
                import pygame
                pygame.display.init()
                pygame.joystick.init()
            except Exception as e:
                socketio.emit("remote:state", {"connected": False, "error": str(e)})
                return

            js        = None
            prev_count   = -1
            prev_btns    = {}
            prev_hat     = (0, 0)
            bindings     = _load_bindings()

            while not stop_event.is_set():
                try:
                    pygame.event.pump()
                    count = pygame.joystick.get_count()

                    # joystick connect / disconnect
                    if count != prev_count:
                        if js is not None:
                            try: js.quit()
                            except Exception: pass
                            js = None
                        prev_count = count
                        if count > 0:
                            try:
                                js = pygame.joystick.Joystick(0)
                                js.init()
                                bindings = _load_bindings()
                            except Exception as e:
                                print(f"[remote] joystick init: {e}")
                                js = None

                    if js is None:
                        socketio.emit("remote:state", {"connected": False})
                        time.sleep(0.5)
                        continue

                    # read inputs
                    na    = js.get_numaxes()
                    axes  = [js.get_axis(i) for i in range(na)]
                    nb    = js.get_numbuttons()
                    btns  = {i: bool(js.get_button(i)) for i in range(nb)}
                    hat   = js.get_hat(0) if js.get_numhats() > 0 else (0, 0)
                    lt    = axes[4] if na > 4 else -1.0
                    rt    = axes[5] if na > 5 else -1.0

                    socketio.emit("remote:state", {
                        "connected": True,
                        "lx": axes[0] if na > 0 else 0,
                        "ly": axes[1] if na > 1 else 0,
                        "rx": axes[2] if na > 2 else 0,
                        "ry": axes[3] if na > 3 else 0,
                        "lt": lt, "rt": rt,
                        "buttons": {str(k): v for k, v in btns.items()},
                        "hat": list(hat),
                        "speed": _jog_speed,
                    })

                    # axis jog
                    for ax_idx, cart_ax, sign in AXIS_MAP:
                        if ax_idx < len(axes):
                            val = axes[ax_idx] * sign
                            if abs(val) > DEADZONE:
                                spd = (abs(val) - DEADZONE) / (1.0 - DEADZONE) * _jog_speed
                                robot.jog_cartesian(cart_ax, (1 if val > 0 else -1) * spd)

                    # LB/RB → Z down / up (held)
                    if btns.get(BTN_LB, False):
                        robot.jog_cartesian("Z", -_jog_speed)
                    elif btns.get(BTN_RB, False):
                        robot.jog_cartesian("Z", _jog_speed)

                    # button bindings — rising edge
                    for bi, pressed in btns.items():
                        if pressed and not prev_btns.get(bi, False):
                            _execute_action(bindings.get(f"btn_{bi}", "none"), robot, socketio)

                    # hat bindings — rising edge
                    if hat != (0, 0) and hat != prev_hat:
                        hat_key = f"hat_{hat[0]}_{hat[1]}"
                        _execute_action(bindings.get(hat_key, "none"), robot, socketio)

                    prev_btns = btns
                    prev_hat  = hat

                except Exception as e:
                    print(f"[remote] loop: {e}")
                    time.sleep(0.1)

                time.sleep(0.02)

            # clean up only the subsystems we started
            try:
                pygame.joystick.quit()
                pygame.display.quit()
            except Exception:
                pass

        socketio.start_background_task(_loop)

    @socketio.on("remote:stop")
    def handle_stop():
        _gamepad_stop.set()

    @socketio.on("remote:set_speed")
    def handle_set_speed(data):
        global _jog_speed
        _jog_speed = max(5.0, min(100.0, float(data.get("speed", 50))))
