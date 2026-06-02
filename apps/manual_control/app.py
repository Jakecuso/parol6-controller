"""
apps/manual_control/app.py — App 1: "normal control".

A simple keyboard jog menu. This is a STARTER STUB: the structure and menu are
here, but the actual jog calls go through robot.jog_joint / robot.jog_cartesian,
which still need to be wired to the installed PAROL6 API (see core/robot.py).

The contract the launcher needs:
    NAME : str
    run(robot)
"""

from __future__ import annotations

NAME = "Manual Control"


def run(robot):
    print("Manual Control — basic jog menu")
    print("  type a joint number 1-6 then +/- to jog, e.g. '1+'")
    print("  's' = stop,  'p' = print pose,  'b' = back to home screen")

    while True:
        cmd = input("  manual> ").strip().lower()

        if cmd in ("b", "back", "q"):
            return

        if cmd == "s":
            robot.stop()
            print("  stopped")
            continue

        if cmd == "p":
            try:
                print("  pose:", robot.get_pose())
            except Exception as e:  # noqa: BLE001
                print("  could not read pose:", e)
            continue

        # crude parse: "<joint><sign>", e.g. "3+" or "5-"
        if len(cmd) == 2 and cmd[0] in "123456" and cmd[1] in "+-":
            joint = int(cmd[0])
            speed = 20.0 if cmd[1] == "+" else -20.0  # percent
            try:
                robot.jog_joint(joint, speed)
                print(f"  jogging J{joint} at {speed}%  (press 's' to stop)")
            except NotImplementedError:
                print("  jog_joint() isn't wired to the API yet — see core/robot.py")
            continue

        print("  didn't understand that. examples: '2+', '4-', 's', 'p', 'b'")
