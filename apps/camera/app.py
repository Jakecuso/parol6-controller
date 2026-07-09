"""Camera mini-app — live MJPEG feed from a USB webcam on the Pi.

A single background thread (real OS thread; the app runs SocketIO in "threading"
mode) grabs frames from /dev/video0 via OpenCV and keeps only the newest JPEG.
The /apps/camera/stream route serves them as multipart/x-mixed-replace so a plain
<img> shows the live feed. If no camera is present, the stream returns 503 and
the template shows a "No camera" placeholder — nothing crashes.

OpenCV is imported lazily inside the capture loop so this module still loads (and
the app still appears) on machines without opencv-python-headless installed.
"""
import time
import threading
from flask import Blueprint, render_template, Response

NAME  = "Camera"
ICON  = "📷"
COLOR = "linear-gradient(145deg, #7e57c2, #4527a0)"
SLUG  = "camera"

WIDTH, HEIGHT, FPS = 640, 480, 15
DEVICE = 0             # /dev/video0
IDLE_STOP_SEC = 5.0    # release the webcam this long after the last viewer leaves


class _Camera:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None        # latest JPEG bytes
        self._thread = None
        self._running = False
        self._last_view = 0.0

    @property
    def running(self) -> bool:
        return self._running

    def _capture_loop(self):
        try:
            import cv2
        except Exception as e:
            print(f"[camera] OpenCV not available: {e}")
            self._running = False
            return

        cap = cv2.VideoCapture(DEVICE)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, FPS)
        if not cap.isOpened():
            print(f"[camera] could not open device {DEVICE}")
            cap.release()
            self._running = False
            return

        print("[camera] capture started")
        interval = 1.0 / FPS
        while self._running:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with self._lock:
                    self._frame = jpg.tobytes()
            if time.time() - self._last_view > IDLE_STOP_SEC:
                break  # no viewers — free the webcam
            time.sleep(interval)

        cap.release()
        with self._lock:
            self._frame = None
        self._running = False
        print("[camera] capture stopped")

    def ensure_started(self):
        self._last_view = time.time()
        if self._running:
            return
        self._running = True
        with self._lock:
            self._frame = None
        self._thread = threading.Thread(target=self._capture_loop,
                                        daemon=True, name="camera")
        self._thread.start()

    def wait_first_frame(self, timeout: float = 2.0) -> bool:
        """True once a frame is available (camera works); False if it can't open."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._frame is not None:
                    return True
            if not self._running:   # capture thread bailed (no cv2 / no device)
                return False
            time.sleep(0.05)
        with self._lock:
            return self._frame is not None

    def get_jpeg(self):
        self._last_view = time.time()
        with self._lock:
            return self._frame


_cam = _Camera()


def register(app, robot, socketio):
    bp = Blueprint("camera", __name__, template_folder="templates")

    @bp.route("/apps/camera")
    def index():
        return render_template("camera/camera.html")

    @bp.route("/apps/camera/stream")
    def stream():
        _cam.ensure_started()
        if not _cam.wait_first_frame(timeout=2.0):
            return Response("no camera", status=503)

        def _gen():
            while True:
                jpg = _cam.get_jpeg()
                if jpg is None:
                    if not _cam.running:
                        break
                    time.sleep(0.05)
                    continue
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                       + jpg + b"\r\n")
                time.sleep(1.0 / FPS)

        return Response(_gen(),
                        mimetype="multipart/x-mixed-replace; boundary=frame")

    app.register_blueprint(bp)
