"""apps/telemetry/app.py — live readout of robot state."""

from __future__ import annotations

import time

NAME = "Telemetry"


def run(robot):
    print("Telemetry — live robot state. Press Ctrl-C or type 'b' to exit.")
    print("  enter a refresh interval in seconds (default 1.0): ", end="", flush=True)
    try:
        raw = input().strip()
        interval = float(raw) if raw else 1.0
    except (ValueError, EOFError):
        interval = 1.0

    try:
        while True:
            angles = robot.get_angles()
            pose = robot.get_pose()
            status = robot.get_status()

            print("\n--- telemetry ---")
            if angles:
                deg = [f"{a:.1f}" for a in angles]
                print(f"  joints (deg): {', '.join(deg)}")
            if pose:
                fmt = [f"{v:.1f}" for v in pose]
                print(f"  TCP pose:     x={fmt[0]} y={fmt[1]} z={fmt[2]}"
                      f"  rx={fmt[3]} ry={fmt[4]} rz={fmt[5]}")
            if status:
                print(f"  status: {status}")

            time.sleep(interval)
    except KeyboardInterrupt:
        pass
