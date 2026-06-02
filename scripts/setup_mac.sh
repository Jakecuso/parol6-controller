#!/usr/bin/env bash
# scripts/setup_mac.sh — one-time setup on your Mac (development machine).
#
# Creates a virtual environment and installs the PAROL6 Python API plus this
# project's deps. You develop here against the SIMULATOR (no hardware needed).
#
# Usage:   bash scripts/setup_mac.sh
set -euo pipefail

# Move to the project root (the parent of this scripts/ dir).
cd "$(dirname "$0")/.."

# PAROL6 API supports Python 3.10 and 3.11. Check you have one of those.
echo "Python version:"
python3 --version

echo "Creating virtual environment in .venv ..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip

# Get the PAROL6 Python API (not on PyPI) and install it. Prebuilt wheels for
# macOS arm64/x86_64 are selected automatically.
if [ ! -d external/PAROL6-python-API ]; then
  mkdir -p external
  git clone https://github.com/PCrnjak/PAROL6-python-API external/PAROL6-python-API
fi
pip install ./external/PAROL6-python-API

# This project's own (light) requirements.
pip install -r requirements.txt

echo
echo "Done. Next:"
echo "  source .venv/bin/activate"
echo "  python run.py            # opens the home screen in SIMULATOR mode"
