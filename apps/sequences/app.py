"""apps/sequences/app.py — record and play back a sequence of poses."""

from __future__ import annotations

import json
import os
import time

NAME = "Sequences"

SEQ_FILE = os.path.join(os.path.dirname(__file__), "../../data/sequences.json")


def _load() -> dict:
    try:
        with open(SEQ_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(seqs: dict):
    os.makedirs(os.path.dirname(SEQ_FILE), exist_ok=True)
    with open(SEQ_FILE, "w") as f:
        json.dump(seqs, f, indent=2)


def run(robot):
    seqs = _load()
    recording: list | None = None
    rec_name: str | None = None

    print("Sequences — record and replay multi-step motion sequences")
    print("  'rec <name>' = start recording,  'stop' = finish recording")
    print("  'mark' = capture current joint angles as a waypoint")
    print("  'play <name>' = replay,  'l' = list,  'b' = back")

    while True:
        cmd = input("  seq> ").strip()
        if not cmd:
            continue
        parts = cmd.split(None, 1)
        verb = parts[0].lower()

        if verb in ("b", "back", "q"):
            return

        if verb == "l":
            if not seqs:
                print("  (no saved sequences)")
            else:
                for name, steps in seqs.items():
                    print(f"  {name}: {len(steps)} waypoints")
            continue

        if verb == "rec" and len(parts) == 2:
            rec_name = parts[1].strip()
            recording = []
            print(f"  recording '{rec_name}' — type 'mark' to capture waypoints, 'stop' when done")
            continue

        if verb == "mark":
            if recording is None:
                print("  start a recording first: 'rec <name>'")
                continue
            angles = robot.get_angles()
            if angles is None:
                print("  could not read angles")
                continue
            recording.append(list(angles))
            print(f"  waypoint {len(recording)} captured")
            continue

        if verb == "stop":
            if recording is None or rec_name is None:
                print("  not recording")
                continue
            seqs[rec_name] = recording
            _save(seqs)
            print(f"  saved '{rec_name}' with {len(recording)} waypoints")
            recording = None
            rec_name = None
            continue

        if verb == "play" and len(parts) == 2:
            name = parts[1].strip()
            if name not in seqs:
                print(f"  unknown sequence '{name}'")
                continue
            steps = seqs[name]
            print(f"  playing '{name}' ({len(steps)} waypoints) ...")
            for i, angles in enumerate(steps, 1):
                print(f"  step {i}/{len(steps)}")
                robot.move_joints(angles, speed=0.3, wait=True)
                time.sleep(0.1)
            print("  done")
            continue

        print("  examples: 'rec wave', 'mark', 'stop', 'play wave', 'l', 'b'")
