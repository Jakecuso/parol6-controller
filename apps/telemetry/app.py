from flask import Blueprint, render_template

NAME  = "Telemetry"
ICON  = "📊"
COLOR = "linear-gradient(145deg, #ab47bc, #4a148c)"
SLUG  = "telemetry"


def register(app, robot, socketio):
    bp = Blueprint("telemetry", __name__, template_folder="templates")

    @bp.route("/apps/telemetry")
    def index():
        return render_template("telemetry/telemetry.html")

    app.register_blueprint(bp)
