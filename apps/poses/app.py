"""apps/poses/app.py — save and replay named joint-angle poses."""

from __future__ import annotations

import json
import os

NAME = "Poses"

POSES_FILE = os.path.join(os.path.dirname(__file__), "../../data/poses.json")


def _load() -> dict:
    try:
        with open(POSES_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(poses: dict):
    os.makedirs(os.path.dirname(POSES_FILE), exist_ok=True)
    with open(POSES_FILE, "w") as f:
        json.dump(poses, f, indent=2)


def run(robot):
    poses = _load()
    print("Poses — save and replay named positions")
    print("  's <name>' = save current pose,  'g <name>' = go to pose")
    print("  'l' = list poses,  'b' = back")

    while True:
        cmd = input("  poses> ").strip()
        if not cmd:
            continue
        parts = cmd.split(None, 1)
        verb = parts[0].lower()

        if verb in ("b", "back", "q"):
            return

        if verb == "l":
            if not poses:
                print("  (no saved poses)")
            else:
                for name, angles in poses.items():
                    print(f"  {name}: {angles}")
            continue

        if verb == "s" and len(parts) == 2:
            name = parts[1].strip()
            angles = robot.get_angles()
            if angles is None:
                print("  could not read angles from robot")
                continue
            poses[name] = list(angles)
            _save(poses)
            print(f"  saved '{name}'")
            continue

        if verb == "g" and len(parts) == 2:
            name = parts[1].strip()
            if name not in poses:
                print(f"  unknown pose '{name}'")
                continue
            print(f"  moving to '{name}' ...")
            robot.move_joints(poses[name], speed=0.3, wait=True)
            print("  done")
            continue

        print("  examples: 's home', 'g home', 'l', 'b'")
