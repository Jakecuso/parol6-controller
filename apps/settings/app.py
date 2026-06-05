import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Blueprint, render_template, jsonify

NAME  = "Settings"
ICON  = "⚙️"
COLOR = "linear-gradient(145deg, #546e7a, #263238)"
SLUG  = "settings"

_reconfig_lock = threading.Lock()
_update_lock = threading.Lock()

# repo root: apps/settings/app.py → parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd, cwd=REPO_ROOT, timeout=180):
    """Run a command, return (ok, combined_output)."""
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out.strip()
    except Exception as e:
        return False, str(e)


def _under_systemd() -> bool:
    # systemd sets INVOCATION_ID for every service it starts.
    return bool(os.environ.get("INVOCATION_ID"))


def _list_ports():
    try:
        from serial.tools import list_ports
        ports = [p.device for p in list_ports.comports()]
        # put USB/serial-looking ports first
        usb = [p for p in ports if "usb" in p.lower() or "serial" in p.lower() or "modem" in p.lower()]
        other = [p for p in ports if p not in usb]
        return usb + other
    except Exception:
        return []


def register(app, robot, socketio):
    bp = Blueprint("settings", __name__, template_folder="templates")

    @bp.route("/apps/settings")
    def index():
        ports = _list_ports()
        return render_template(
            "settings/settings.html",
            ports=ports,
            simulate=robot.simulate,
            connected=robot._client is not None,
        )

    @bp.route("/apps/settings/ports")
    def list_serial_ports():
        return jsonify({"ports": _list_ports()})

    @bp.route("/apps/settings/version")
    def version():
        ok, out = _run(["git", "log", "-1", "--pretty=%h  %s  (%cr)"])
        return jsonify({"version": out if ok else "unknown"})

    app.register_blueprint(bp)

    @socketio.on("settings:connect")
    def handle_connect(data):
        simulate = bool(data.get("simulate", True))
        com_port = data.get("com_port") or None

        if not simulate and not com_port:
            socketio.emit("settings:status", {"ok": False, "msg": "Select a COM port for real hardware"})
            return

        socketio.emit("settings:status", {"ok": None, "msg": "Connecting…"})

        def _do():
            with _reconfig_lock:
                try:
                    robot.reconfigure(simulate=simulate, com_port=com_port)
                    mode = "simulator" if simulate else com_port
                    enabled = robot.is_enabled()
                    socketio.emit("settings:status", {
                        "ok": True,
                        "msg": f"Connected ({mode})",
                        "enabled": enabled,
                    })
                except Exception as e:
                    socketio.emit("settings:status", {"ok": False, "msg": str(e), "enabled": False})

        threading.Thread(target=_do, daemon=True).start()

    @socketio.on("settings:resume")
    def handle_resume():
        try:
            robot.resume()
            socketio.emit("settings:resume_ack", {"ok": True, "msg": "Controller enabled — ready to move"})
        except Exception as e:
            socketio.emit("settings:resume_ack", {"ok": False, "msg": str(e)})

    @socketio.on("settings:update")
    def handle_update():
        """Pull the latest code from GitHub and restart.

        Safety: halt the arm first so it can't be moving during the restart.
        After a successful pull + dependency install we exit the process; under
        systemd (Restart=always) that brings the new code straight back up. On a
        dev machine (no systemd) we stop and ask the user to restart manually.
        """
        if not _update_lock.acquire(blocking=False):
            socketio.emit("settings:update_status", {"stage": "busy", "msg": "Update already running"})
            return

        def emit(stage, msg, ok=None):
            socketio.emit("settings:update_status", {"stage": stage, "msg": msg, "ok": ok})

        def _do():
            try:
                # 1) Stop the arm — never update while it's live/moving.
                try:
                    robot.stop()
                    emit("halt", "Arm halted")
                except Exception:
                    emit("halt", "Arm not connected (skipping halt)")

                # 2) Pull
                emit("pull", "Pulling latest from GitHub…")
                ok, out = _run(["git", "pull", "--ff-only"])
                if not ok:
                    emit("done", f"git pull failed:\n{out}", ok=False)
                    return
                if "Already up to date" in out:
                    emit("uptodate", "Already up to date — nothing to install.", ok=True)
                    return
                emit("pull", out.splitlines()[-1] if out else "Pulled.")

                # 3) Dependencies (in case requirements.txt changed)
                emit("deps", "Updating dependencies…")
                ok, out = _run([sys.executable, "-m", "pip", "install", "-q",
                                "-r", "requirements.txt"], timeout=600)
                if not ok:
                    emit("done", f"pip install failed:\n{out[-400:]}", ok=False)
                    return

                # 4) Restart
                if _under_systemd():
                    emit("restart", "Updated. Restarting — this page will reconnect…", ok=True)

                    def _exit():
                        time.sleep(1.5)
                        os._exit(0)  # systemd Restart=always brings us back up
                    threading.Thread(target=_exit, daemon=True).start()
                else:
                    emit("restart",
                         "Updated. Restart the server manually to load new code "
                         "(no systemd detected).", ok=True)
            finally:
                _update_lock.release()

        threading.Thread(target=_do, daemon=True).start()
