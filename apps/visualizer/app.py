from pathlib import Path
from flask import Blueprint, render_template, send_from_directory

NAME  = "3D View"
ICON  = "🦾"
COLOR = "linear-gradient(145deg, #1a237e, #283593)"
SLUG  = "visualizer"

import parol6 as _p6
MESH_DIR = Path(_p6.__file__).parent / "urdf_model" / "meshes"


def register(app, robot, socketio):
    bp = Blueprint("visualizer", __name__, template_folder="templates")

    @bp.route("/apps/visualizer")
    def index():
        return render_template("visualizer/visualizer.html")

    @bp.route("/apps/visualizer/mesh/<path:filename>")
    def serve_mesh(filename):
        if not filename.lower().endswith(".stl"):
            return "Not found", 404
        return send_from_directory(MESH_DIR, filename)

    app.register_blueprint(bp)
