#!/usr/bin/env bash
# scripts/setup_pi.sh — one-command setup on a Raspberry Pi (deploy target).
#
# Makes the controller fully plug-and-play:
#   • swap (so a low-RAM Pi doesn't freeze installing/running heavy native libs)
#   • Python venv + PAROL6 API + dependencies
#   • serial port access (dialout group)
#   • mDNS so you can reach it at http://<hostname>.local:5050
#   • a systemd service so it auto-starts on boot and auto-restarts on crash
#
# After this runs, you can power the Pi off, plug everything back in, and the
# controller comes up on its own — connected to the arm and ready.
#
# Usage:
#   bash scripts/setup_pi.sh            # normal setup (safe to re-run)
#   bash scripts/setup_pi.sh --clean    # wipe .venv and rebuild from scratch
#                                        (use this if a previous install was
#                                         interrupted / left things corrupted)
set -euo pipefail

# ── args ─────────────────────────────────────────────────────────────────────
CLEAN=0
for a in "$@"; do
  case "$a" in
    --clean) CLEAN=1 ;;
    *) echo "Unknown option: $a"; exit 1 ;;
  esac
done

# ── paths / identity ─────────────────────────────────────────────────────────
APPDIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="$(whoami)"
PORT="${PAROL6_PORT:-5050}"
# Want ≥2GB swap on low-RAM Pis; native robotics libs (pinokin/pinocchio,
# robotics-toolbox) are memory-hungry to install AND to run.
SWAP_MB=2048
cd "$APPDIR"

echo "──────────────────────────────────────────────"
echo " PAROL6 Controller — Pi setup"
echo "   dir:   $APPDIR"
echo "   user:  $RUN_USER"
echo "   port:  $PORT"
echo "   clean: $CLEAN"
echo "──────────────────────────────────────────────"

# ── preflight: platform compatibility ────────────────────────────────────────
# The PAROL6 API depends on `pinokin` (pinocchio-based kinematics), which only
# ships prebuilt wheels for 64-bit ARM with glibc >= 2.39 and Python 3.11–3.14.
# Raspberry Pi OS *Bookworm* has glibc 2.36 — too old. You need *Trixie* (Debian
# 13, glibc 2.41, Python 3.13). Catch this now with a clear message instead of a
# cryptic "is not a supported wheel on this platform" failure mid-install.
echo "[preflight] Checking platform compatibility…"
ver_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]; }

ARCH="$(uname -m)"
if [ "$ARCH" != "aarch64" ]; then
  echo "  ✗ Architecture is '$ARCH', but only 64-bit ARM (aarch64) is supported."
  echo "    Flash the 64-bit Raspberry Pi OS (not the 32-bit image)."
  exit 1
fi

# NOTE: `... | head -1` can SIGPIPE the upstream command; under `set -o pipefail`
# that would silently kill the script. The trailing `|| true` swallows it.
GLIBC="$(ldd --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -n1)" || true
NEED_GLIBC="2.39"
if [ -n "$GLIBC" ] && ! ver_ge "$GLIBC" "$NEED_GLIBC"; then
  echo "  ✗ System glibc is $GLIBC, but pinokin's wheels need >= $NEED_GLIBC."
  echo "    Raspberry Pi OS Bookworm (glibc 2.36) is too old for this."
  echo "    FIX: flash the latest Raspberry Pi OS — Trixie / Debian 13, 64-bit —"
  echo "         which has glibc 2.41 and Python 3.13, then re-run this script."
  exit 1
fi

PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo '?')"
case "$PYV" in
  3.11|3.12|3.13|3.14) : ;;
  *) echo "  ⚠ Python $PYV found; pinokin ships wheels for 3.11–3.14 only — install may fail." ;;
esac
echo "  ✓ aarch64 · glibc ${GLIBC:-unknown} · Python $PYV"

# ── 1. system packages ───────────────────────────────────────────────────────
echo "[1/7] Installing system packages (git, python venv, avahi)…"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3-venv python3-dev avahi-daemon dphys-swapfile

# ── 2. swap (prevents OOM freezes on 2-4GB Pis) ──────────────────────────────
echo "[2/7] Ensuring at least ${SWAP_MB}MB of swap…"
CUR_SWAP_KB="$(awk '/SwapTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0)"
CUR_SWAP_MB=$(( CUR_SWAP_KB / 1024 ))
if [ "$CUR_SWAP_MB" -lt "$SWAP_MB" ]; then
  echo "      current swap ${CUR_SWAP_MB}MB → setting ${SWAP_MB}MB"
  sudo dphys-swapfile swapoff || true
  # CONF_SWAPMAXSIZE must allow our target, or dphys caps it.
  if grep -q '^CONF_SWAPSIZE=' /etc/dphys-swapfile; then
    sudo sed -i "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=${SWAP_MB}/" /etc/dphys-swapfile
  else
    echo "CONF_SWAPSIZE=${SWAP_MB}" | sudo tee -a /etc/dphys-swapfile >/dev/null
  fi
  if grep -q '^CONF_SWAPMAXSIZE=' /etc/dphys-swapfile; then
    sudo sed -i "s/^CONF_SWAPMAXSIZE=.*/CONF_SWAPMAXSIZE=${SWAP_MB}/" /etc/dphys-swapfile
  else
    echo "CONF_SWAPMAXSIZE=${SWAP_MB}" | sudo tee -a /etc/dphys-swapfile >/dev/null
  fi
  sudo dphys-swapfile setup
  sudo dphys-swapfile swapon
else
  echo "      already ${CUR_SWAP_MB}MB — leaving it."
fi

# ── 3. python venv ───────────────────────────────────────────────────────────
if [ "$CLEAN" = "1" ]; then
  echo "[3/7] --clean: removing existing .venv and cloned API…"
  rm -rf .venv external/PAROL6-python-API
fi
echo "[3/7] Creating virtual environment…"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip -q

# Keep memory pressure down on a small Pi: don't cache wheels, build serially.
export MAKEFLAGS="-j1"
export MAX_JOBS=1
PIP_OPTS=(--no-cache-dir -q)

# ── 4. PAROL6 API + deps ─────────────────────────────────────────────────────
echo "[4/7] Installing the PAROL6 Python API (this is the slow part)…"
if [ ! -d external/PAROL6-python-API ]; then
  mkdir -p external
  git clone --depth 1 https://github.com/PCrnjak/PAROL6-python-API external/PAROL6-python-API
fi
pip install "${PIP_OPTS[@]}" ./external/PAROL6-python-API
pip install "${PIP_OPTS[@]}" -r requirements.txt

# Sanity-check the native kinematics module loads (this is what failed before).
echo "      verifying parol6 / pinokin import…"
if ! python -c "import parol6" 2>/dev/null; then
  echo "      ⚠ parol6 failed to import. Re-run with --clean, and make sure swap"
  echo "        is active (free -h). See output above for the real error."
  exit 1
fi

# ── 5. serial access ─────────────────────────────────────────────────────────
echo "[5/7] Granting serial port access (dialout group)…"
sudo usermod -aG dialout "$RUN_USER" || true

# ── 6. systemd service ───────────────────────────────────────────────────────
echo "[6/7] Installing systemd service…"
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

# ── 7. done ──────────────────────────────────────────────────────────────────
echo "[7/7] Done."
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
       free -h                           # check RAM + swap

 NOTE: you were just added to the 'dialout' group for serial
 access — log out and back in (or reboot) once so it takes effect.

 Plug the PAROL6 control board into USB and it auto-connects.
 LAN only — never expose this to the internet (there's no login).
──────────────────────────────────────────────────────────────
EOF
