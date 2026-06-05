import json
import os
import threading
import time
from flask import Blueprint, render_template, request, jsonify

NAME  = "Sequences"
ICON  = "⏺"
COLOR = "linear-gradient(145deg, #ffb300, #e65100)"
SLUG  = "sequences"

SEQ_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sequences")

_recording     = False
_record_frames = []
_record_stop   = threading.Event()
_playback_stop = threading.Event()


def _seq_path(name):
    os.makedirs(SEQ_DIR, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in "-_ ").strip().replace(" ", "_")
    return os.path.join(SEQ_DIR, f"{safe}.json")


def register(app, robot, socketio):
    bp = Blueprint("sequences", __name__, template_folder="templates")

    @bp.route("/apps/sequences")
    def index():
        seqs = []
        if os.path.isdir(SEQ_DIR):
            for fname in sorted(os.listdir(SEQ_DIR)):
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(SEQ_DIR, fname)) as f:
                            data = json.load(f)
                        seqs.append({
                            "name": fname[:-5].replace("_", " "),
                            "frames": len(data),
                            "duration": round(len(data) / 10.0, 1),
                        })
                    except Exception:
                        pass
        return render_template("sequences/sequences.html", sequences=seqs)

    @bp.route("/api/sequences/record/start", methods=["POST"])
    def record_start():
        global _recording, _record_frames, _record_stop
        if _recording:
            return jsonify({"ok": False, "error": "already recording"})
        _recording = True
        _record_frames = []
        _record_stop = threading.Event()
        stop_ev = _record_stop

        def _loop():
            global _recording
            while not stop_ev.is_set():
                try:
                    angles = robot.get_angles()
                    if angles:
                        _record_frames.append(list(angles))
                except Exception as e:
                    print(f"[sequences] record error: {e}")
                time.sleep(0.1)
            _recording = False

        socketio.start_background_task(_loop)
        return jsonify({"ok": True})

    @bp.route("/api/sequences/record/stop", methods=["POST"])
    def record_stop():
        data = request.get_json(silent=True) or {}
        name = data.get("name", f"seq_{int(time.time())}")
        _record_stop.set()
        if _record_frames:
            with open(_seq_path(name), "w") as f:
                json.dump(_record_frames, f)
        return jsonify({"ok": True, "frames": len(_record_frames), "name": name})

    @bp.route("/api/sequences/play", methods=["POST"])
    def play():
        global _playback_stop
        data = request.get_json(silent=True) or {}
        name = data.get("name", "")
        path = _seq_path(name)
        if not os.path.exists(path):
            return jsonify({"ok": False, "error": "not found"})
        with open(path) as f:
            frames = json.load(f)
        _playback_stop = threading.Event()
        stop_ev = _playback_stop

        def _loop():
            for frame in frames:
                if stop_ev.is_set():
                    break
                try:
                    robot.move_joints(frame, speed=0.3, wait=True)
                except Exception as e:
                    print(f"[sequences] playback error: {e}")
                    break

        socketio.start_background_task(_loop)
        return jsonify({"ok": True})

    @bp.route("/api/sequences/stop", methods=["POST"])
    def stop_play():
        _playback_stop.set()
        return jsonify({"ok": True})

    @bp.route("/api/sequences/delete", methods=["POST"])
    def delete():
        data = request.get_json(silent=True) or {}
        name = data.get("name", "")
        path = _seq_path(name)
        if os.path.exists(path):
            os.remove(path)
        return jsonify({"ok": True})

    app.register_blueprint(bp)
