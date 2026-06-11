# server.py
import importlib
from flask import Flask, render_template
from flask_socketio import SocketIO

socketio = SocketIO()

APP_DIRS = [
    "manual_control",
    "xbox_control",
    "telemetry",
    "sequences",
    "poses",
    "visualizer",
    "kiosk",
    "settings",
]

def create_app(simulate: bool = True):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "parol6-dev"

    socketio.init_app(app, async_mode="threading", cors_allowed_origins="*")

    from core.robot import Robot
    robot = Robot(simulate=simulate)
    app.robot = robot

    if simulate:
        # Simulator connects instantly — no hardware to wait on.
        robot.connect()
    else:
        # Real hardware: bring the web UI up immediately and connect to the arm
        # in the background, retrying until the USB board is ready. This is what
        # makes power-on plug-and-play — the arm may enumerate seconds after the
        # Pi finishes booting. connect_async() also resume()s, so the arm comes
        # up live ("straight to hardware").
        def _announce(_r):
            socketio.emit("settings:status", {
                "ok": True, "msg": "Connected (real hardware)",
                "enabled": _r.is_enabled(),
            })
        robot.connect_async(on_connect=_announce)

    # Discover and register Blueprint apps
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

    @socketio.on("stop")
    def on_stop():
        robot.stop()
        socketio.emit("settings:resume_ack", {"ok": False, "msg": "Halted — tap Enable to resume"})

    @socketio.on("home")
    def on_home():
        robot.home()

    @app.route("/")
    def home():
        return render_template("home.html", apps=app.config["APPS"])

    @app.errorhandler(404)
    def not_found(e):
        return "Not found", 404

    return app, socketio
