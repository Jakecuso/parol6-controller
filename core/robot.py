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

    # ---- lifecycle -------------------------------------------------------

    def connect(self):
        from parol6 import Robot as _RobotDef, RobotClient

        if self.manage_controller:
            # Robot.start() blocks until the controller subprocess is ready.
            self._robot_def = _RobotDef(host=self.host, port=self.port)
            self._robot_def.start()

        self._client = RobotClient(host=self.host, port=self.port)
        # wait_ready is a no-op if start() already confirmed readiness, but
        # it's cheap insurance when connecting to an externally-managed server.
        self._client.wait_ready(timeout=10)
        self._client.simulator(self.simulate)
        return self

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
        """Halt all motion immediately."""
        return self.client.halt()

    def disable(self):
        """Alias for stop — parol6 0.2.7 has no separate disable command."""
        return self.client.halt()

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
        duration  : seconds to run the jog pulse (default 0.2 s)
        frame     : coordinate frame, default 'WRF' (world reference frame)
        """
        return self.client.jog_l(frame, axis.upper(), speed_pct / 100.0, duration)

    def move_joints(self, angles_deg: list, speed: float = 0.3, wait: bool = True):
        """Move to absolute joint angles (degrees, list of 6).

        speed: fraction 0.0–1.0 of max joint speed.
        """
        return self.client.move_j(angles_deg, speed=speed, wait=wait)
