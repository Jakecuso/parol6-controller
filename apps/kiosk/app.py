"""
apps/kiosk/app.py — touch-panel UI for a local screen on the Pi.

Designed for a small touchscreen wired to the Pi: big touch targets, three
sections — WiFi, Bluetooth, and a live Robot animation. WiFi uses NetworkManager
(`nmcli`, the default on Raspberry Pi OS Trixie) and Bluetooth uses `bluetoothctl`.

Everything degrades gracefully when those tools aren't present (e.g. testing in a
browser on a Mac) — the endpoints report `available: false` and the UI explains
that control only works on the Pi. So this whole app is testable off-Pi.
"""
import re
import shutil
import subprocess
from flask import Blueprint, render_template, jsonify, request

NAME  = "Touch Panel"
ICON  = "📟"
COLOR = "linear-gradient(145deg, #00897b, #004d40)"
SLUG  = "kiosk"

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


def _run(args, timeout=15):
    """Run a command (no shell — injection-safe). Returns (ok, stdout+stderr)."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return False, str(e)


def _unescape_nmcli(s: str) -> str:
    # nmcli -t escapes literal ':' and '\' in fields as '\:' and '\\'
    return s.replace("\\:", ":").replace("\\\\", "\\")


def _split_nmcli(line: str):
    # split on unescaped ':' separators
    out, cur, i = [], "", 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            cur += line[i:i + 2]
            i += 2
            continue
        if c == ":":
            out.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    out.append(cur)
    return [_unescape_nmcli(x) for x in out]


# ── WiFi (NetworkManager / nmcli) ────────────────────────────────────────────

def wifi_status():
    if not _have("nmcli"):
        return {"available": False}
    ssid = ""
    ok, out = _run(["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"])
    if ok:
        for line in out.splitlines():
            parts = _split_nmcli(line)
            if parts and parts[0] == "yes":
                ssid = parts[1] if len(parts) > 1 else ""
                break
    _, ip_out = _run(["hostname", "-I"])
    ip = ip_out.split()[0] if ip_out.split() else ""
    return {"available": True, "ssid": ssid, "ip": ip}


def wifi_scan():
    if not _have("nmcli"):
        return {"available": False, "networks": []}
    _run(["nmcli", "device", "wifi", "rescan"], timeout=20)
    ok, out = _run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                    "device", "wifi", "list"], timeout=20)
    seen = {}
    if ok:
        for line in out.splitlines():
            f = _split_nmcli(line)
            if len(f) < 4:
                continue
            in_use = f[0].strip() == "*"
            ssid = f[1].strip()
            if not ssid:
                continue
            try:
                signal = int(f[2])
            except ValueError:
                signal = 0
            security = f[3].strip()
            prev = seen.get(ssid)
            if prev is None or signal > prev["signal"]:
                seen[ssid] = {"ssid": ssid, "signal": signal,
                              "secure": security not in ("", "--"),
                              "active": in_use}
    nets = sorted(seen.values(), key=lambda n: (-n["active"], -n["signal"]))
    return {"available": True, "networks": nets}


def wifi_connect(ssid: str, password: str):
    if not _have("nmcli"):
        return False, "nmcli not available (this only works on the Pi)"
    if not ssid:
        return False, "No network selected"
    args = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    return _run(args, timeout=45)


# ── Bluetooth (bluetoothctl) ─────────────────────────────────────────────────

def bt_scan():
    if not _have("bluetoothctl"):
        return {"available": False, "devices": []}
    _run(["bluetoothctl", "power", "on"], timeout=8)
    # discover for a few seconds, then list what we found / know
    _run(["bluetoothctl", "--timeout", "8", "scan", "on"], timeout=12)
    ok, out = _run(["bluetoothctl", "devices"], timeout=8)
    _, paired_out = _run(["bluetoothctl", "devices", "Paired"], timeout=8)
    paired_macs = {l.split()[1] for l in paired_out.splitlines()
                   if l.startswith("Device") and len(l.split()) > 1}
    devices = []
    if ok:
        for line in out.splitlines():
            parts = line.split(" ", 2)
            if len(parts) >= 3 and parts[0] == "Device":
                mac, name = parts[1], parts[2]
                if not _MAC_RE.match(mac):
                    continue
                # skip nameless entries that are just the MAC repeated
                devices.append({"mac": mac, "name": name,
                                "paired": mac in paired_macs})
    devices.sort(key=lambda d: (not d["paired"], d["name"].lower()))
    return {"available": True, "devices": devices}


def bt_pair(mac: str):
    if not _have("bluetoothctl"):
        return False, "bluetoothctl not available (this only works on the Pi)"
    if not _MAC_RE.match(mac or ""):
        return False, "Invalid device address"
    _run(["bluetoothctl", "power", "on"], timeout=8)
    _run(["bluetoothctl", "--timeout", "5", "scan", "on"], timeout=9)
    msgs = []
    for verb in ("pair", "trust", "connect"):
        ok, out = _run(["bluetoothctl", verb, mac], timeout=25)
        msgs.append(f"{verb}: {'ok' if ok else out.splitlines()[-1] if out else 'failed'}")
    # success if it ends up connected
    ok, info = _run(["bluetoothctl", "info", mac], timeout=8)
    connected = "Connected: yes" in info
    return connected, " · ".join(msgs)


# ── Blueprint ────────────────────────────────────────────────────────────────

def register(app, robot, socketio):
    bp = Blueprint("kiosk", __name__, template_folder="templates")

    @bp.route("/apps/kiosk")
    def index():
        return render_template("kiosk/kiosk.html")

    @bp.route("/apps/kiosk/wifi/status")
    def r_wifi_status():
        return jsonify(wifi_status())

    @bp.route("/apps/kiosk/wifi/scan")
    def r_wifi_scan():
        return jsonify(wifi_scan())

    @bp.route("/apps/kiosk/wifi/connect", methods=["POST"])
    def r_wifi_connect():
        data = request.get_json(force=True, silent=True) or {}
        ok, msg = wifi_connect(data.get("ssid", ""), data.get("password", ""))
        return jsonify({"ok": ok, "msg": msg})

    @bp.route("/apps/kiosk/bt/scan")
    def r_bt_scan():
        return jsonify(bt_scan())

    @bp.route("/apps/kiosk/bt/pair", methods=["POST"])
    def r_bt_pair():
        data = request.get_json(force=True, silent=True) or {}
        ok, msg = bt_pair(data.get("mac", ""))
        return jsonify({"ok": ok, "msg": msg})

    app.register_blueprint(bp)
