"""
apps/xbox_control/app.py — App 2: Bluetooth Xbox controller teleop.

Reads an Xbox controller (paired over Bluetooth, so the OS sees it as a normal
gamepad) and maps the sticks to robot jog commands.

This is a STARTER STUB. It shows the recommended shape:
  - open the gamepad
  - loop: read stick axes -> map to jog speeds -> send to robot
  - use streaming mode for smooth continuous jogging

Two pieces still need finishing:
  1. The robot jog calls (robot.jog_cartesian) must be wired to the real API.
  2. A gamepad library must be installed. `pygame` is the simplest cross-platform
     choice and works on both macOS and Raspberry Pi. It's listed (commented)
     in requirements.txt — uncomment it when you start this app.

Pairing the controller is an OS-level step (Bluetooth settings on the Mac, or
bluetoothctl on the Pi); once paired it just shows up as a joystick.
"""

from __future__ import annotations

NAME = "Xbox Control"

# Tuning constants — tweak freely.
DEADZONE = 0.12          # ignore tiny stick noise near center
MAX_SPEED_PCT = 30.0     # stick fully pushed -> this jog speed (percent)


def _apply_deadzone(value: float) -> float:
    return 0.0 if abs(value) < DEADZONE else value


def run(robot):
    try:
        import pygame  # noqa: F401
    except ImportError:
        print("  This app needs pygame. Install it (and uncomment it in")
        print("  requirements.txt):   pip install pygame")
        return

    import pygame

    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("  No gamepad found. Pair your Xbox controller over Bluetooth")
        print("  first, then try again.")
        pygame.quit()
        return

    pad = pygame.joystick.Joystick(0)
    pad.init()
    print(f"  using controller: {pad.get_name()}")
    print("  left stick = X/Y,  right stick = Z / rotate.  Ctrl-C to exit.")

    try:
        while True:
            pygame.event.pump()

            # Typical Xbox axis layout (may vary by OS/driver — verify):
            #   axis 0 = left stick X,  axis 1 = left stick Y
            #   axis 3 = right stick X, axis 4 = right stick Y
            lx = _apply_deadzone(pad.get_axis(0))
            ly = _apply_deadzone(pad.get_axis(1))
            ry = _apply_deadzone(pad.get_axis(4))

            if lx or ly or ry:
                robot.jog_cartesian("x", lx * MAX_SPEED_PCT)
                robot.jog_cartesian("y", -ly * MAX_SPEED_PCT)  # invert: up = +Y
                robot.jog_cartesian("z", -ry * MAX_SPEED_PCT)

            pygame.time.wait(20)  # ~50 Hz update
    finally:
        robot.stop()
        pygame.quit()
