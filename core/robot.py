"""
core/robot.py — the single place where this project talks to the PAROL6 arm.

Every mini app receives a `Robot` instance and calls its methods. Apps must
never import `parol6` directly or open their own connection. That keeps one
safe, consistent connection layer for the whole project.

Two modes:
  - simulate=True  (default): spins up a managed controller and turns the
    software simulator on. No hardware, no serial port. Use this on the Mac.
  - simulate=False: connects to a controller you started yourself against the
    real USB serial port (on the Pi). See scripts/setup_pi.sh.

API notes (verified against installed parol6 0.2.7 / waldoctl):
  - manage_controller=True: uses parol6.Robot(host, port).start() to spin up
    the controller subprocess, then connect a RobotClient to it.
  - RobotClient methods: ping(), angles(), pose(frame), status(), halt(),
    home(wait, timeout), simulator(enabled), wait_ready(timeout),
    jog_j(joint_0idx, speed_frac, duration), jog_l(frame, axis, speed_frac, duration),
    move_j(angles_deg, speed=0-1), select_tool(name), close().
  - Joints are 0-indexed in the parol6 API; our public API uses 1-indexed.
  - Speeds are fractions 0.0–1.0 in the parol6 API; our public API uses percent.
"""

from __future__ import annotations

import threading
import time


def find_serial_port() -> str | None:
    """Auto-detect the PAROL6 control board's USB serial port.

    Returns the first plausible device (Pi: /dev/ttyACM* or /dev/ttyUSB*;
    macOS: /dev/tty.usbserial-* / /dev/tty.usbmodem*), or None if nothing
    USB-serial-looking is plugged in.
    """
    try:
        from serial.tools import list_ports
    except Exception:
        return None

    keys = ("ttyacm", "ttyusb", "usbserial", "usbmodem")
    for p in list_ports.comports():
        dev = p.device or ""
        if any(k in dev.lower() for k in keys):
            return dev
    return None


class Robot:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5001,
        simulate: bool = True,
        manage_controller: bool = True,
    ):
        self.host = host
        self.port = port
        self.simulate = simulate
        self.manage_controller = manage_controller

        self._client = None    # parol6.RobotClient (sync)
        self._robot_def = None  # parol6.Robot (server lifecycle manager)
        self._connecting = False  # guards connect_async against double-starts

    @property
    def connected(self) -> bool:
        return self._client is not None

    # ---- lifecycle -------------------------------------------------------

    def connect(self, com_port: str | None = None):
        from parol6 import Robot as _RobotDef, RobotClient

        # Real hardware with no explicit port → try to auto-detect the USB board.
        if not self.simulate and com_port is None:
            com_port = find_serial_port()
            if com_port:
                print(f"[robot] auto-detected serial port: {com_port}")

        if self.manage_controller:
            self._robot_def = _RobotDef(host=self.host, port=self.port)
            try:
                self._robot_def.start(com_port=com_port)
            except RuntimeError as e:
                if "already running" in str(e).lower():
                    print(f"[robot] attaching to existing controller at {self.host}:{self.port}")
                else:
                    raise

        self._client = RobotClient(host=self.host, port=self.port)
        self._client.wait_ready(timeout=10)
        self._client.simulator(self.simulate)
        return self

    def connect_async(self, com_port: str | None = None, retry_delay: float = 4.0,
                      on_connect=None):
        """Connect in a background thread, retrying forever until it succeeds.

        Used at boot on the Pi: when the Pi and the arm power up together, the
        control board's USB port may take several seconds to enumerate. Rather
        than crash (and lean on systemd to restart us), we bring the web server
        up immediately and keep retrying the hardware connection until it lands.
        `on_connect(robot)` is called once, after the first successful connect.
        """
        if self._connecting or self.connected:
            return

        self._connecting = True

        def _worker():
            attempt = 0
            while not self.connected:
                attempt += 1
                try:
                    self.connect(com_port=com_port)
                    try:
                        self.resume()  # straight to live: enable motors on boot
                    except Exception:
                        pass
                    print(f"[robot] connected on attempt {attempt}")
                    if on_connect:
                        try:
                            on_connect(self)
                        except Exception as e:
                            print(f"[robot] on_connect callback error: {e}")
                    break
                except Exception as e:
                    if attempt == 1 or attempt % 5 == 0:
                        print(f"[robot] connect attempt {attempt} failed ({e}); "
                              f"retrying every {retry_delay:.0f}s…")
                    # tear down any half-built state before the next try
                    try:
                        self.close()
                    except Exception:
                        pass
                    time.sleep(retry_delay)
            self._connecting = False

        threading.Thread(target=_worker, daemon=True, name="robot-connect").start()

    def reconfigure(self, simulate: bool, com_port: str | None = None):
        """Disconnect, apply new settings, reconnect. Called from Settings app."""
        self.close()
        self.simulate = simulate
        self.connect(com_port=com_port)
        try:
            self.resume()
        except Exception:
            pass  # E-stop may be pressed; jog path will surface the error

    def close(self):
        try:
            if self._client is not None:
                try:
                    self._client.halt()
                except Exception:
                    pass
                self._client.close()
        finally:
            self._client = None
            if self._robot_def is not None:
                try:
                    self._robot_def.stop()
                except Exception:
                    pass
                self._robot_def = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    # ---- escape hatch ----------------------------------------------------

    @property
    def client(self):
        """Raw parol6 RobotClient. Use wrapper methods instead where possible."""
        if self._client is None:
            raise RuntimeError("Robot not connected. Call connect() first.")
        return self._client

    # ---- status / info ---------------------------------------------------

    def ping(self):
        return self.client.ping()

    def get_pose(self, frame: str = "WRF"):
        """Return TCP pose as [x, y, z, rx, ry, rz] in mm / degrees."""
        return self.client.pose(frame)

    def get_angles(self):
        """Return joint angles in degrees (list of 6)."""
        return self.client.angles()

    def get_status(self):
        return self.client.status()

    # ---- control ---------------------------------------------------------

    def stop(self):
        """Halt all motion immediately (also disables controller)."""
        return self.client.halt()

    def disable(self):
        """Alias for stop."""
        return self.client.halt()

    def resume(self):
        """Re-enable controller after halt(). Must call before motion works again."""
        return self.client.resume()

    def is_enabled(self) -> bool:
        """Return True if controller is in enabled (driveable) state."""
        try:
            # status() has no .enabled field; use E-stop io[4]: 1=not pressed, 0=pressed
            s = self.client.status()
            io = getattr(s, "io", None)
            if io and len(io) > 4:
                return bool(io[4])
            return True
        except Exception:
            return False

    def set_tool(self, name: str):
        """e.g. 'NONE' or 'PNEUMATIC'. See parol6 tool registry."""
        return self.client.select_tool(name)

    # ---- motion ----------------------------------------------------------

    def home(self, wait: bool = True, timeout: float = 60.0):
        """Move all joints to the home position."""
        return self.client.home(wait=wait, timeout=timeout)

    def jog_joint(self, joint: int, speed_pct: float, duration: float = 0.2):
        """Jog a single joint.

        joint     : 1-indexed (1–6)
        speed_pct : velocity as a percentage; negative reverses direction
        duration  : seconds to run the jog pulse (default 0.2 s)
        """
        return self.client.jog_j(joint - 1, speed_pct / 100.0, duration)

    def jog_cartesian(self, axis: str, speed_pct: float, duration: float = 0.2,
                      frame: str = "WRF"):
        """Jog in Cartesian space along one axis.

        axis      : one of X Y Z RX RY RZ (case-insensitive)
        speed_pct : velocity as a percentage; negative reverses direction
        """
        return self.client.jog_l(frame, axis.upper(), speed_pct / 100.0, duration)

    def jog_cartesian_multi(self, axes_speeds: dict, duration: float = 0.2,
                            frame: str = "WRF"):
        """Jog multiple Cartesian axes simultaneously.

        axes_speeds : {"X": 50, "Y": -50} — keys are axis names, values are
                      signed speed percent (negative = reverse direction).
        """
        axes = list(axes_speeds.keys())
        speeds = [axes_speeds[ax] / 100.0 for ax in axes]
        return self.client.jog_l(frame, axes=axes, speeds_list=speeds, duration=duration)

    def move_joints(self, angles_deg: list, speed: float = 0.3, wait: bool = True):
        """Move to absolute joint angles (degrees, list of 6).

        speed: fraction 0.0–1.0 of max joint speed.
        """
        return self.client.move_j(angles_deg, speed=speed, wait=wait)
