"""
ui/launcher.py — the "home screen".

Auto-discovers every mini app in apps/ and lets you pick one to run. An app is
any folder under apps/ that contains an app.py exposing:
    NAME : str          (display name on the home screen)
    run(robot)          (the app's entry point; receives the shared Robot)

This is a plain terminal menu for now. Later you can swap this file for a GUI
(Tkinter, a web UI, etc.) without touching the apps or core — that's the whole
point of keeping the launcher separate.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable, List

import apps  # the apps package


@dataclass
class AppEntry:
    name: str
    module_name: str
    run: Callable


def discover_apps() -> List[AppEntry]:
    """Find every apps/<name>/app.py that follows the NAME + run() contract."""
    entries: List[AppEntry] = []
    for mod in pkgutil.iter_modules(apps.__path__):
        if not mod.ispkg:
            continue
        app_module_name = f"apps.{mod.name}.app"
        try:
            module = importlib.import_module(app_module_name)
        except Exception as e:  # noqa: BLE001 - show the user, keep going
            print(f"  [skip] {mod.name}: failed to import ({e})")
            continue
        name = getattr(module, "NAME", None)
        run = getattr(module, "run", None)
        if isinstance(name, str) and callable(run):
            entries.append(AppEntry(name=name, module_name=mod.name, run=run))
        else:
            print(f"  [skip] {mod.name}: missing NAME or run()")
    return sorted(entries, key=lambda e: e.name.lower())


def home_screen(robot):
    """Show the menu loop. `robot` is a connected core.robot.Robot."""
    while True:
        apps_list = discover_apps()
        print("\n" + "=" * 40)
        print("  PAROL6 — Home Screen")
        mode = "SIMULATOR" if getattr(robot, "simulate", True) else "REAL ARM"
        print(f"  mode: {mode}")
        print("=" * 40)
        if not apps_list:
            print("  (no apps found in apps/)")
        for i, entry in enumerate(apps_list, start=1):
            print(f"  {i}. {entry.name}")
        print("  q. quit")
        print("-" * 40)

        choice = input("  pick an app: ").strip().lower()
        if choice in ("q", "quit", "exit"):
            print("  bye!")
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(apps_list)):
            print("  invalid choice")
            continue

        entry = apps_list[int(choice) - 1]
        print(f"\n  → launching: {entry.name}\n")
        try:
            entry.run(robot)
        except KeyboardInterrupt:
            print(f"\n  (left {entry.name})")
        except NotImplementedError as e:
            print(f"  {entry.name} isn't finished yet: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  {entry.name} crashed: {e}")
        finally:
            # safety: make sure the arm isn't left moving after an app exits
            try:
                robot.stop()
            except Exception:
                pass
