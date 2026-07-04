#!/usr/bin/env python3
"""Direct gripper test — bypasses the web app.

Connects to the already-running controller (the parol6 systemd service starts it
on UDP 127.0.0.1:5001), selects the MSG gripper tool, and commands a few
open/close moves with verbose output. This isolates "can the parol6 API move the
gripper at all" from anything in the web UI.

Run on the Pi:
    source .venv/bin/activate
    python scripts/test_gripper.py
"""
import time
import sys

from parol6 import RobotClient

HOST, PORT = "127.0.0.1", 5001
TOOL = "MSG"


def main():
    print(f"connecting to controller at {HOST}:{PORT} ...")
    c = RobotClient(host=HOST, port=PORT)
    try:
        c.wait_ready(timeout=10)
    except Exception as e:
        print(f"!! could not reach controller: {e}")
        print("   Is the parol6 service running?  systemctl status parol6")
        sys.exit(1)
    print("connected.")

    try:
        print(f"select_tool({TOOL}) ->", c.select_tool(TOOL))
    except Exception as e:
        print(f"!! select_tool failed: {e}")
        sys.exit(2)

    # try to read gripper/tool status if available
    try:
        st = c.status()
        print("status:", st)
    except Exception as e:
        print("status read failed (non-fatal):", e)

    moves = [
        ("CLOSE", 1.0),
        ("OPEN",  0.0),
        ("CLOSE", 1.0),
        ("OPEN",  0.0),
    ]
    for label, pos in moves:
        print(f"\n>>> {label}  tool_action({TOOL!r}, 'move', [{pos}, 0.5, 500])")
        try:
            rc = c.tool_action(TOOL, "move", [pos, 0.5, 500], wait=True, timeout=8)
            print(f"    returned: {rc}")
        except Exception as e:
            print(f"    ERROR: {e!r}")
        time.sleep(1.0)

    c.close()
    print("\ndone. Did the jaws move?")


if __name__ == "__main__":
    main()
