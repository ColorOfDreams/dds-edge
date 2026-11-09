"""Lớp giả lập phần cứng (HAL): camera, nguồn tốc độ/GPS, còi.

Trên K230, từng lớp này được thay bằng bản cài đặt dùng MIPI/ISP, UART GNSS, I2C IMU
và PWM/I2S, trong khi tầng thuật toán không đổi.
"""
from __future__ import annotations

import bisect
import csv
import math
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Iterator, Optional

from .types import MotionObs


# ------------------------------------------------------------------- camera
class VideoSource:
    """Webcam (số nguyên) hoặc tệp video. Mốc thời gian t tính bằng giây.

    Webcam dùng đồng hồ thực; tệp video dùng chỉ số khung / fps để chạy lại cho kết quả
    xác định.
    """

    def __init__(self, source: str | int, width: int = 640, height: int = 480):
        import cv2

        self.cv2 = cv2
        self.is_file = isinstance(source, str) and not source.isdigit()
        src = source if self.is_file else int(source)
        self.cap = cv2.VideoCapture(src) if self.is_file else cv2.VideoCapture(src, cv2.CAP_DSHOW if sys.platform == "win32" else 0)
        if not self.cap.isOpened() and not self.is_file:
            self.cap = cv2.VideoCapture(src)           # thử backend mặc định
        if not self.cap.isOpened():
            raise RuntimeError(f"không mở được nguồn video: {source!r}")
        if not self.is_file:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._t0 = time.monotonic()
        self._n = 0

    def frames(self) -> Iterator[tuple[float, "object"]]:
        while True:
            ok, frame = self.cap.read()
            if not ok:
                return
            t = (self._n / self.fps) if self.is_file else (time.monotonic() - self._t0)
            self._n += 1
            yield t, frame

    def close(self) -> None:
        self.cap.release()


# -------------------------------------------------------------- tốc độ / GPS
class ManualSpeed:
    """Tốc độ do người dùng điều khiển bằng phím (giả lập xe chạy/dừng)."""

    def __init__(self, kmh: float = 50.0):
        self.kmh = kmh

    def adjust(self, delta: float) -> None:
        self.kmh = max(0.0, min(160.0, self.kmh + delta))

    def toggle_stop(self, run_speed: float = 50.0) -> None:
        self.kmh = 0.0 if self.kmh > 0 else run_speed

    def at(self, t: float) -> MotionObs:
        return MotionObs(t=t, speed_kmh=self.kmh)


class RouteSource:
    """Phát lại tuyến GPS từ CSV. Hỗ trợ định dạng của Traffic-SM (`fake_gps.csv`) và CSV tối giản
    có cột `t,lat,lng,speed_kmh`."""

    def __init__(self, ts: list[float], speeds_kmh: list[float], lats: list[float], lngs: list[float], loop: bool = True):
        if len(ts) < 2:
            raise ValueError("tuyến cần ít nhất 2 điểm")
        self.ts, self.speeds, self.lats, self.lngs, self.loop = ts, speeds_kmh, lats, lngs, loop
        self.duration = ts[-1] - ts[0]

    @classmethod
    def from_csv(cls, path: str | Path, driver_id: Optional[str] = None, loop: bool = True) -> "RouteSource":
        ts: list[float] = []
        sp: list[float] = []
        la: list[float] = []
        ln: list[float] = []
        with open(path, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            fields = set(rd.fieldnames or [])
            traffic = {"driver_id", "timestamp", "speed", "lat", "lng"} <= fields
            for row in rd:
                if traffic:
                    if driver_id is not None and row["driver_id"] != str(driver_id):
                        continue
                    ts.append(float(row["timestamp"]))
                    sp.append(float(row["speed"]) * 3.6)          # m/s -> km/h
                else:
                    ts.append(float(row["t"]))
                    sp.append(float(row["speed_kmh"]))
                la.append(float(row["lat"]))
                ln.append(float(row["lng"]))
        order = sorted(range(len(ts)), key=ts.__getitem__)
        t0 = ts[order[0]]
        return cls([ts[i] - t0 for i in order], [sp[i] for i in order], [la[i] for i in order],
                   [ln[i] for i in order], loop)

    def at(self, t: float) -> MotionObs:
        tt = t % self.duration if self.loop and self.duration > 0 else min(t, self.duration)
        i = bisect.bisect_right(self.ts, tt)
        i0, i1 = max(0, i - 1), min(len(self.ts) - 1, i)
        span = self.ts[i1] - self.ts[i0]
        a = 0.0 if span <= 0 else (tt - self.ts[i0]) / span
        speed = self.speeds[i0] + a * (self.speeds[i1] - self.speeds[i0])
        return MotionObs(t=t, speed_kmh=speed, lat=self.lats[i0] + a * (self.lats[i1] - self.lats[i0]),
                         lng=self.lngs[i0] + a * (self.lngs[i1] - self.lngs[i0]))


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ----------------------------------------------------------------- còi / loa
# (tần số Hz, thời lượng ms, số lần, nghỉ ms) theo mức 1..4
BEEP_PATTERNS = {
    1: [(800, 120)],
    2: [(1000, 150), (1000, 150)],
    3: [(1400, 200), (1400, 200), (1400, 200)],
    4: [(2000, 250), (1500, 250), (2000, 250), (1500, 250)],
}
LEVEL_TEXT = {
    0: "",
    1: "Nhac nhe: hay tap trung",
    2: "CANH BAO: hay tap trung lai xe",
    3: "NGUY HIEM: tap trung ngay",
    4: "BAO DONG KHAN CAP",
}


class SoundActuator:
    """Còi mô phỏng. Windows dùng winsound.Beep; nơi khác in chuông terminal. Không chặn luồng chính."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._q: "queue.Queue[int]" = queue.Queue()
        self._level = 0
        self._stop = False
        try:
            import winsound  # type: ignore[import-not-found]
            self._winsound = winsound
        except ImportError:
            self._winsound = None
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def set_level(self, level: int) -> None:
        """Gọi mỗi khung; chỉ phát khi mức đổi hoặc (mức 3/4) lặp lại theo chu kỳ."""
        if level != self._level:
            self._level = level
            if level > 0 and self.enabled:
                self._q.put(level)
        elif level >= 3 and self.enabled and self._q.empty() and time.monotonic() - getattr(self, "_last", 0) > (1.2 if level == 3 else 0.6):
            self._q.put(level)

    def _worker(self) -> None:
        while not self._stop:
            try:
                level = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            self._last = time.monotonic()
            for freq, ms in BEEP_PATTERNS[level]:
                if self._winsound:
                    self._winsound.Beep(freq, ms)
                else:
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                    time.sleep(ms / 1000)
                time.sleep(0.04)

    def close(self) -> None:
        self._stop = True
