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
]

def create_app(simulate: bool = True):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "parol6-dev"

    socketio.init_app(app, async_mode="eventlet", cors_allowed_origins="*")

    from core.robot import Robot
    robot = Robot(simulate=simulate)
    app.robot = robot

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
