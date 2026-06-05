#!/usr/bin/env bash
# scripts/update.sh — pull the latest code and restart the controller.
#
# This is the command-line equivalent of the in-app "Update" button. Run it on
# the Pi over SSH:
#
#   cd ~/parol6-controller && ./scripts/update.sh
#
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Pulling latest…"
git pull --ff-only

echo "Updating dependencies…"
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if systemctl list-units --type=service 2>/dev/null | grep -q parol6; then
  echo "Restarting service…"
  sudo systemctl restart parol6
  echo "Done. → http://$(hostname).local:${PAROL6_PORT:-5050}"
else
  echo "Done. (No systemd service found — start it with: python run.py)"
fi
