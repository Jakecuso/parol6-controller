#!/usr/bin/env bash
# scripts/setup_pi.sh — one-time setup on the Raspberry Pi (deploy target).
#
# Same idea as the Mac script: venv + PAROL6 API. The API has prebuilt wheels
# for Linux aarch64 and the Pi 5 is its primary development platform, so this
# should be smooth. The difference vs the Mac is that here you'll connect to the
# REAL arm over USB serial.
#
# Usage:   bash scripts/setup_pi.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Python version:"
python3 --version   # want 3.10 or 3.11

echo "Creating virtual environment in .venv ..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip

if [ ! -d external/PAROL6-python-API ]; then
  mkdir -p external
  git clone https://github.com/PCrnjak/PAROL6-python-API external/PAROL6-python-API
fi
pip install ./external/PAROL6-python-API
pip install -r requirements.txt

cat <<'EOF'

Done. To drive the REAL arm:

  1. Plug the PAROL6 control board into the Pi over USB.
  2. Find the serial port (often /dev/ttyUSB0 or /dev/ttyACM0):
       ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
     You may need to be in the 'dialout' group:
       sudo usermod -aG dialout $USER     # then log out/in
  3. Start the controller against that port (in one terminal):
       source .venv/bin/activate
       parol6-server --serial=/dev/ttyUSB0 --log-level=INFO
     (add --auto-home if you want it to home on startup)
  4. In another terminal, run the launcher in REAL mode, connecting to the
     controller you just started:
       source .venv/bin/activate
       python run.py --real --no-manage

Safety: keep the E-Stop reachable, and only run on a trusted local network
(the controller has no authentication).
EOF
