#!/usr/bin/env python3
"""Direct UART gripper test — bypasses the web app and the arm.

Talks straight to the gripper over its UART (core/gripper_serial.py) and commands
a few open/close moves with verbose output. Use this to confirm the gripper moves
before/without the web UI.

Run on the Pi (with the USB-UART adapter plugged into the gripper):
    source .venv/bin/activate
    python scripts/test_gripper.py
    # or pin the port:
    PAROL6_GRIPPER_PORT=/dev/ttyUSB0 python scripts/test_gripper.py
"""
import time

from core.gripper_serial import GripperSerial


def main():
    g = GripperSerial()
    print("info:", g.info() or "(no reply — check wiring/port/baud)")
    for label, val in (("CLOSE", 255), ("OPEN", 0), ("CLOSE", 255), ("OPEN", 0)):
        print(f"\n>>> {label}  (#Grippos {val})")
        try:
            print("   ->", g.set_position(val))
        except Exception as e:
            print("   ERROR:", e)
        time.sleep(1.5)
    g.close()
    print("\ndone. Did the jaws move?")


if __name__ == "__main__":
    main()
