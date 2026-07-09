"""core/gripper_serial.py — direct UART control of the MSG gripper.

The MSG gripper is a STEPFOC in gripper mode. Instead of routing through the
arm's CAN bus / controller, we talk to it directly over its own UART at 256000
baud (the same link used for #Gripcal during setup). This keeps the gripper
completely independent of the arm.

STEPFOC gripper commands (already-calibrated, gripper mode on):
    #Grippos <0-255>   target position — 0 = fully OPEN, 255 = fully CLOSED
                       (auto-enters GOTO mode and executes; no #Close needed)
    #Gripvel <0-255>   jaw speed
    #Gripcur <mA>      grip current / force (150-1000; <150 unstable)

Port selection (a USB-UART adapter from the Pi to the gripper's UART header):
    1. env PAROL6_GRIPPER_PORT if set (e.g. /dev/ttyUSB0) — recommended
    2. else auto-detect a USB-UART adapter (FTDI/CH340/CP210x), preferring
       /dev/ttyUSB* so it does NOT grab the arm controller's native-USB port.
"""
from __future__ import annotations

import os
import time
import threading

BAUD = 256000

# defaults applied once on first connect so #Grippos actually produces motion
DEFAULT_SPEED   = int(os.environ.get("PAROL6_GRIPPER_SPEED", "150"))   # 0-255
DEFAULT_CURRENT = int(os.environ.get("PAROL6_GRIPPER_CURRENT", "400"))  # mA

_UART_HINTS = ("ftdi", "ft232", "ch340", "ch910", "cp210", "silicon labs",
               "usb-serial", "usb serial", "wch")


class GripperSerial:
    def __init__(self, port: str | None = None, baud: int = BAUD):
        self._port = port or os.environ.get("PAROL6_GRIPPER_PORT")
        self._baud = baud
        self._ser = None
        self._inited = False
        self._lock = threading.Lock()
        self._status = {
            "connected": False, "port": None, "configured_port": self._port,
            "last_cmd": None, "last_resp": None, "error": None,
        }

    def status(self) -> dict:
        """Snapshot for the UI: connection state, port, last command/response."""
        s = dict(self._status)
        try:
            s["available_ports"] = self._list_ports()
        except Exception:
            s["available_ports"] = []
        return s

    def _list_ports(self):
        try:
            from serial.tools import list_ports
        except Exception:
            return []
        out = []
        for p in list_ports.comports():
            out.append({"device": p.device,
                        "desc": (p.description or "").strip(),
                        "id": (getattr(p, "product", None) or
                               getattr(p, "manufacturer", None) or "")})
        return out

    # ---- port / connection ----------------------------------------------

    def _find_port(self):
        if self._port:
            return self._port
        try:
            from serial.tools import list_ports
        except Exception:
            return None
        cands = []
        for p in list_ports.comports():
            dev = (p.device or "")
            desc = f"{p.description} {p.manufacturer} {p.product}".lower()
            if any(h in desc for h in _UART_HINTS) or "ttyusb" in dev.lower():
                cands.append(dev)
        # prefer ttyUSB* (FTDI/CH340 adapters) over ttyACM* (native USB = arm board)
        cands.sort(key=lambda d: (0 if "ttyusb" in d.lower() else 1, d))
        return cands[0] if cands else None

    def _connect(self):
        if self._ser is not None:
            return self._ser
        import serial
        port = self._find_port()
        if not port:
            raise RuntimeError(
                "no gripper serial port found — plug the USB-UART adapter into "
                "the Pi and/or set PAROL6_GRIPPER_PORT")
        self._ser = serial.Serial(port, self._baud, timeout=0.3)
        print(f"[gripper-uart] connected {port} @ {self._baud}")
        self._inited = False
        self._status.update(connected=True, port=port, error=None)
        return self._ser

    def _send_raw(self, ser, cmd: str) -> str:
        ser.reset_input_buffer()
        ser.write((cmd + "\n").encode())
        ser.flush()
        time.sleep(0.05)
        resp = ser.read(ser.in_waiting or 0).decode(errors="replace").strip()
        print(f"[gripper-uart] {cmd} -> {resp!r}")
        self._status.update(last_cmd=cmd, last_resp=resp, error=None)
        return resp

    def _send(self, cmd: str) -> str:
        with self._lock:
            try:
                ser = self._connect()
                if not self._inited:
                    # apply sane speed/current once so moves actually happen
                    self._send_raw(ser, f"#Gripvel {DEFAULT_SPEED}")
                    self._send_raw(ser, f"#Gripcur {DEFAULT_CURRENT}")
                    self._inited = True
                return self._send_raw(ser, cmd)
            except Exception as e:
                # drop the connection so the next call reconnects cleanly
                if self._ser is not None:
                    try:
                        self._ser.close()
                    except Exception:
                        pass
                self._ser = None
                self._inited = False
                self._status.update(connected=False, error=str(e))
                raise

    # ---- public API ------------------------------------------------------

    def set_position(self, value: int) -> str:
        """0 = fully open, 255 = fully closed."""
        return self._send(f"#Grippos {max(0, min(255, int(value)))}")

    def open_jaws(self) -> str:
        return self.set_position(0)

    def close_jaws(self) -> str:
        return self.set_position(255)

    def set_speed(self, value: int) -> str:
        return self._send(f"#Gripvel {max(0, min(255, int(value)))}")

    def set_current(self, ma: int) -> str:
        return self._send(f"#Gripcur {max(0, min(1000, int(ma)))}")

    def calibrate(self) -> str:
        return self._send("#Gripcal")

    def info(self) -> str:
        return self._send("#Info")

    def close(self):
        with self._lock:
            if self._ser is not None:
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
                self._inited = False
