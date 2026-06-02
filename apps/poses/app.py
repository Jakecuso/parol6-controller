import json
import os
import time
from flask import Blueprint, render_template, request, jsonify

NAME  = "Poses"
ICON  = "📍"
COLOR = "linear-gradient(145deg, #26c6da, #006064)"
SLUG  = "poses"

POSES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "poses.json")


def _load():
    if os.path.exists(POSES_FILE):
        try:
            with open(POSES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save(poses):
    os.makedirs(os.path.dirname(POSES_FILE), exist_ok=True)
    with open(POSES_FILE, "w") as f:
        json.dump(poses, f, indent=2)


def register(app, robot, socketio):
    bp = Blueprint("poses", __name__, template_folder="templates")

    @bp.route("/apps/poses")
    def index():
        return render_template("poses/poses.html", poses=_load())

    @bp.route("/api/poses/save", methods=["POST"])
    def save():
        data = request.get_json(silent=True) or {}
        name = data.get("name", f"pose_{int(time.time())}")
        try:
            joints = list(robot.get_angles() or [])
            xyz    = list(robot.get_pose()   or [])
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
        if not joints:
            return jsonify({"ok": False, "error": "could not read joint angles"})
        poses = _load()
        poses.append({
            "name":      name,
            "timestamp": int(time.time()),
            "joints":    joints,
            "xyz":       xyz,
        })
        _save(poses)
        return jsonify({"ok": True, "joints": joints, "xyz": xyz})

    @bp.route("/api/poses/goto", methods=["POST"])
    def goto():
        data = request.get_json(silent=True) or {}
        name = data.get("name", "")
        poses = _load()
        match = next((p for p in poses if p["name"] == name), None)
        if not match:
            return jsonify({"ok": False, "error": "not found"})
        try:
            robot.move_joints(match["joints"])
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
        return jsonify({"ok": True})

    @bp.route("/api/poses/delete", methods=["POST"])
    def delete():
        data = request.get_json(silent=True) or {}
        name = data.get("name", "")
        poses = [p for p in _load() if p["name"] != name]
        _save(poses)
        return jsonify({"ok": True})

    app.register_blueprint(bp)
