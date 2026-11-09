"""Đường lên DF-Cloud: gom GPS theo lô, gửi sự kiện, hàng đợi khi mất mạng.

Thiết bị không bao giờ chờ mạng: mọi lệnh gọi ở đây không chặn, lỗi mạng chỉ làm dữ liệu
nằm lại hàng đợi (và ghi ra tệp outbox để gửi bù lần sau).
"""
from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from .types import MotionObs


class Uplink:
    def __init__(self, base_url: str, device_id: str, trip_id: str, vehicle_type: str = "car",
                 outbox: Optional[Path] = None, batch_s: float = 5.0, timeout_s: float = 3.0):
        self.base = base_url.rstrip("/")
        self.device_id, self.trip_id, self.vehicle_type = device_id, trip_id, vehicle_type
        self.outbox = outbox
        self.batch_s, self.timeout = batch_s, timeout_s
        self._q: "queue.Queue[tuple[str, dict[str, Any]]]" = queue.Queue(maxsize=10000)
        self._gps: list[dict[str, Any]] = []
        self._last_flush = time.monotonic()
        self._stop = False
        self.sent = {"gps": 0, "events": 0}
        self.failed = 0
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # ---- gọi từ luồng chính, không chặn
    def push_gps(self, m: MotionObs, unix_ts: float) -> None:
        if m.lat is None or m.lng is None or m.speed_kmh is None:
            return
        self._gps.append({"ts": unix_ts, "lat": m.lat, "lng": m.lng, "speed_mps": m.speed_kmh / 3.6})
        if time.monotonic() - self._last_flush >= self.batch_s:
            self.flush_gps()

    def flush_gps(self) -> None:
        if self._gps:
            body = {"device_id": self.device_id, "trip_id": self.trip_id,
                    "vehicle_type": self.vehicle_type, "points": self._gps}
            self._gps = []
            self._enqueue("/v1/gps", body)
        self._last_flush = time.monotonic()

    def push_event(self, event: dict[str, Any]) -> None:
        body = dict(event)
        body["device_id"] = self.device_id
        body["trip_id"] = self.trip_id
        self._enqueue("/v1/events", body)

    def _enqueue(self, path: str, body: dict[str, Any]) -> None:
        try:
            self._q.put_nowait((path, body))
        except queue.Full:
            self._to_outbox(path, body)

    # ---- luồng nền
    def _post(self, path: str, body: dict[str, Any]) -> bool:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            return False

    def _to_outbox(self, path: str, body: dict[str, Any]) -> None:
        if self.outbox:
            self.outbox.parent.mkdir(parents=True, exist_ok=True)
            with open(self.outbox, "a", encoding="utf-8") as f:
                f.write(json.dumps({"path": path, "body": body}) + "\n")

    def resend_outbox(self) -> int:
        """Gửi bù những gì đã ghi ra outbox ở phiên trước. Trả về số bản ghi gửi được."""
        if not self.outbox or not self.outbox.exists():
            return 0
        lines = self.outbox.read_text(encoding="utf-8").splitlines()
        left, ok = [], 0
        for line in lines:
            item = json.loads(line)
            if self._post(item["path"], item["body"]):
                ok += 1
            else:
                left.append(line)
        self.outbox.write_text("\n".join(left) + ("\n" if left else ""), encoding="utf-8")
        return ok

    def _worker(self) -> None:
        while not self._stop or not self._q.empty():
            try:
                path, body = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            if self._post(path, body):
                self.sent["gps" if path.endswith("gps") else "events"] += 1
            else:
                self.failed += 1
                self._to_outbox(path, body)

    def close(self) -> None:
        self.flush_gps()
        self._stop = True
        self._thread.join(timeout=self.timeout + 1)
