#!/usr/bin/env bash
# scripts/setup_pi.sh — one-command setup on a Raspberry Pi (deploy target).
#
# Makes the controller fully plug-and-play:
#   • Python venv + PAROL6 API + dependencies
#   • serial port access (dialout group)
#   • mDNS so you can reach it at http://<hostname>.local:5050
#   • a systemd service so it auto-starts on boot and auto-restarts on crash
#
# After this runs, you can power the Pi off, plug everything back in, and the
# controller comes up on its own — connected to the arm and ready.
#
# Usage:   bash scripts/setup_pi.sh
set -euo pipefail

# ── paths / identity ─────────────────────────────────────────────────────────
APPDIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="$(whoami)"
PORT="${PAROL6_PORT:-5050}"
cd "$APPDIR"

echo "──────────────────────────────────────────────"
echo " PAROL6 Controller — Pi setup"
echo "   dir:  $APPDIR"
echo "   user: $RUN_USER"
echo "   port: $PORT"
echo "──────────────────────────────────────────────"

# ── 1. system packages ───────────────────────────────────────────────────────
echo "[1/6] Installing system packages (git, python venv, avahi)…"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3-venv python3-dev avahi-daemon

# ── 2. python venv + deps ────────────────────────────────────────────────────
echo "[2/6] Creating virtual environment…"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip -q

echo "[3/6] Installing the PAROL6 Python API…"
if [ ! -d external/PAROL6-python-API ]; then
  mkdir -p external
  git clone --depth 1 https://github.com/PCrnjak/PAROL6-python-API external/PAROL6-python-API
fi
pip install -q ./external/PAROL6-python-API
pip install -q -r requirements.txt

# ── 3. serial access ─────────────────────────────────────────────────────────
echo "[4/6] Granting serial port access (dialout group)…"
sudo usermod -aG dialout "$RUN_USER" || true

# ── 4. systemd service ───────────────────────────────────────────────────────
echo "[5/6] Installing systemd service…"
SERVICE_PATH="/etc/systemd/system/parol6.service"
sudo tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=PAROL6 Web Controller
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APPDIR
ExecStart=$APPDIR/.venv/bin/python run.py
Restart=always
RestartSec=5
Environment=PAROL6_SIMULATE=0
Environment=PAROL6_PORT=$PORT
Environment=PAROL6_NO_BROWSER=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable parol6
sudo systemctl restart parol6

# ── 5. done ──────────────────────────────────────────────────────────────────
echo "[6/6] Done."
HOSTNAME_LOCAL="$(hostname).local"
cat <<EOF

──────────────────────────────────────────────────────────────
 PAROL6 Controller is now running and will start on every boot.

   Open it from any device on your network:
       http://$HOSTNAME_LOCAL:$PORT

   Handy commands:
       sudo systemctl status parol6      # is it running?
       sudo systemctl restart parol6     # restart it
       journalctl -u parol6 -f           # live logs

 NOTE: you were just added to the 'dialout' group for serial
 access — log out and back in (or reboot) once so it takes effect.

 Plug the PAROL6 control board into USB and it auto-connects.
 LAN only — never expose this to the internet (there's no login).
──────────────────────────────────────────────────────────────
EOF
