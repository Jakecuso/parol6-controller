"""
run.py — start here.

Boots the shared Robot connection, then opens the home screen.

Default is the SIMULATOR so you can never accidentally move a real arm just by
running this. To drive the real arm on the Pi:

    python run.py --real --no-manage --port 5001

...after you've started the controller against the serial port yourself, e.g.

    parol6-server --serial=/dev/ttyUSB0 --log-level=INFO
"""

from __future__ import annotations

import argparse

from core.robot import Robot
from ui.launcher import home_screen


def parse_args():
    p = argparse.ArgumentParser(description="PAROL6 mini-app launcher")
    p.add_argument("--host", default="127.0.0.1", help="controller UDP host")
    p.add_argument("--port", type=int, default=5001, help="controller UDP port")
    p.add_argument(
        "--real",
        action="store_true",
        help="connect to the REAL arm (default is the safe simulator)",
    )
    p.add_argument(
        "--no-manage",
        action="store_true",
        help="do NOT start/stop the controller ourselves (connect to one "
        "that's already running — normal on the Pi)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    simulate = not args.real
    manage = not args.no_manage

    print(f"connecting (mode={'REAL' if args.real else 'SIM'}, "
          f"manage_controller={manage}) ...")

    with Robot(
        host=args.host,
        port=args.port,
        simulate=simulate,
        manage_controller=manage,
    ) as robot:
        print("connected. ping:", robot.ping())
        home_screen(robot)


if __name__ == "__main__":
    main()
