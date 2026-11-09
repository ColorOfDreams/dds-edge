"""Server ingest GIẢ LẬP thay cho Traffic-SM khi chưa chạy Docker.

Tái hiện các quy tắc kiểm tra của `gps.Canonicalize` (traffic-SM/services/location-service/internal/gps/canonical.go)
và giao diện `POST /v1/ingest`: nhận một bản ghi hoặc mảng, trả 202 {"accepted", "rejected"}.
Đây KHÔNG phải Traffic-SM: nó chỉ chứng minh payload của gateway đúng định dạng. Khi có Docker, trỏ
gateway vào `http://localhost:8080/v1/ingest` của Traffic-SM thật.

    python -m drivefocus_cloud.mock_ingest --port 18080
"""
from __future__ import annotations

import argparse
import json
import sys
import math
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional


def go_canonicalize(p: dict) -> str | None:
    """Trả None nếu hợp lệ, ngược lại là thông báo lỗi (theo gps.Canonicalize)."""
    if not str(p.get("driver_id", "")).strip():
        return "driver_id is required"
    if not str(p.get("t_timestamp", "")).strip():
        return "t_timestamp is required"
    if not str(p.get("time", "")).strip():
        return "time is required"
    if str(p.get("status", "")).strip().upper() not in ("IN TRIP", "ONLINE", "OFFLINE"):
        return "status invalid"
    if str(p.get("vehicle_type", "")).strip().lower() not in ("car", "bike"):
        return "vehicle_type must be car or bike"
    for k in ("lat", "lng", "bearing", "bearing_acc", "horizontal_acc", "speed", "speed_acc", "time_delta",
              "vertical_acc", "timestamp", "altitude"):
        v = p.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            return f"{k} is required"
    if not -90 <= p["lat"] <= 90 or not -180 <= p["lng"] <= 180:
        return "lat/lng out of range"
    if p["bearing"] != -1 and not 0 <= p["bearing"] < 360:
        return "bearing must be -1 or from 0 up to but not including 360"
    for k in ("bearing_acc", "horizontal_acc", "speed", "speed_acc", "time_delta", "vertical_acc"):
        if p[k] < 0:
            return f"{k} must not be negative"
    if p["timestamp"] <= 0:
        return "timestamp must be positive"
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2})", p["time"])
    if not m:
        return "time invalid"
    mo, d, y, hh, mm = map(int, m.groups())
    try:
        datetime(y, mo, d, hh, mm)
    except ValueError:
        return "time invalid"
    parts = p["t_timestamp"].split(":")
    if len(parts) != 2:
        return "t_timestamp must use MM:SS.s format"
    try:
        minute, sec = int(parts[0]), float(parts[1])
    except ValueError:
        return "t_timestamp invalid"
    if not 0 <= minute < 60 or minute != mm:
        return "t_timestamp minute does not match time minute"
    if not 0 <= sec < 60:
        return "t_timestamp invalid seconds"
    return None


def make_handler(store: list, stats: dict):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            if self.path != "/v1/ingest":
                self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            items = body if isinstance(body, list) else [body]
            rejected = []
            for i, p in enumerate(items):
                err = go_canonicalize(p)
                if err:
                    rejected.append({"index": i, "error": err})
                else:
                    store.append(p)
            stats["accepted"] += len(items) - len(rejected)
            stats["rejected"] += len(rejected)
            data = json.dumps({"accepted": len(items) - len(rejected), "rejected": rejected}).encode()
            self.send_response(202); self.send_header("Content-Length", str(len(data))); self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            data = json.dumps({"status": "mock", **stats, "drivers": sorted({p["driver_id"] for p in store})}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers()
            self.wfile.write(data)

    return H


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Mock Traffic-SM ingest")
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 khi chạy trong container")
    ap.add_argument("--port", type=int, default=18080)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = ap.parse_args(argv)
    store: list = []
    stats = {"accepted": 0, "rejected": 0}
    srv = ThreadingHTTPServer((args.host, args.port), make_handler(store, stats))
    print(f"mock ingest tại http://{args.host}:{args.port}/v1/ingest  (GET / để xem thống kê)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
