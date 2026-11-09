"""DF-Cloud device-gateway (bản demo, chỉ dùng thư viện chuẩn).

Việc của gateway:
1. Nhận GPS của thiết bị, ẩn danh hóa (driver_id = trip_id, bỏ device_id) rồi chuyển tiếp sang
   `POST /v1/ingest` của Traffic-SM đúng định dạng nó yêu cầu.
2. Nhận sự kiện cảnh báo, loại trùng theo event_id, bỏ device_id, ghi vào ClickHouse (bảng
   df.events) và tệp JSONL. Ánh xạ trip_id -> device_id nằm riêng trong SQLite (vùng hạn chế).

Chưa có xác thực/mã hóa: đó là việc của giai đoạn P6 (docs/hld/07-bao-mat-va-rieng-tu.md).
Chạy:  python -m drivefocus_cloud.gateway --port 8099 --ingest-url http://localhost:8080/v1/ingest
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import math
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

VN_TZ = timezone(timedelta(hours=7))   # Traffic-SM đọc trường `time` theo Asia/Ho_Chi_Minh
EVENT_TYPES = {"EYES_CLOSED", "PERCLOS_HIGH", "YAWN", "HEAD_NOD", "LOOK_AWAY", "PHONE", "BEHAVIOR_OTHER",
               "NO_FACE", "CAMERA_OBSTRUCTED", "PAUSE_PRESSED", "DEVICE_TAMPER"}
MAX_POINTS = 5000            # bằng giới hạn lô của /v1/ingest
MAX_BODY = 8 << 20


class ValidationError(ValueError):
    pass


def _finite(v: Any, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValidationError(f"{name} phải là số hữu hạn")
    return float(v)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def to_ingest_payload(point: dict[str, Any], trip_id: str, vehicle_type: str,
                      prev: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Một điểm GPS của thiết bị -> bản ghi theo gps.RequestPayload của Traffic-SM."""
    ts = _finite(point.get("ts"), "ts")
    lat = _finite(point.get("lat"), "lat")
    lng = _finite(point.get("lng"), "lng")
    speed = max(0.0, _finite(point.get("speed_mps"), "speed_mps"))
    if ts <= 0:
        raise ValidationError("ts phải dương")
    if not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise ValidationError("lat/lng ngoài phạm vi")

    local = datetime.fromtimestamp(ts, tz=VN_TZ)
    bearing = point.get("bearing")
    if bearing is not None:
        bearing = _finite(bearing, "bearing")
    if bearing is None:
        bearing = -1.0
        if prev and speed >= 0.5 and haversine_m(prev["lat"], prev["lng"], lat, lng) >= 1.0:
            bearing = round(bearing_deg(prev["lat"], prev["lng"], lat, lng), 2)
    dt = point.get("time_delta")
    if dt is not None:
        dt = _finite(dt, "time_delta")
    else:
        dt = max(0.0, ts - prev["ts"]) if prev else 1.0
    return {
        "driver_id": trip_id,                                           # ẩn danh: mã chuyến, không phải thiết bị
        # cắt (không làm tròn) về phần mười giây để 59.96 không thành "60.0"
        "t_timestamp": f"{local.minute:02d}:{local.second:02d}.{local.microsecond // 100000}",
        "lat": lat, "lng": lng,
        "bearing": bearing,
        "bearing_acc": _finite(point.get("bearing_acc", 10.0), "bearing_acc"),
        "horizontal_acc": _finite(point.get("horizontal_acc", 5.0), "horizontal_acc"),
        "speed": round(speed, 3),
        "speed_acc": _finite(point.get("speed_acc", 0.5), "speed_acc"),
        "time_delta": dt,
        "vertical_acc": _finite(point.get("vertical_acc", 5.0), "vertical_acc"),
        "status": "IN TRIP",
        "vehicle_type": vehicle_type,
        "time": f"{local.month}/{local.day}/{local.year} {local.hour}:{local.minute:02d}",
        "timestamp": ts,
        "altitude": _finite(point.get("altitude", 0.0), "altitude"),
    }


def validate_event(ev: dict[str, Any]) -> None:
    for key in ("schema", "event_id", "trip_id", "device_id", "type", "level", "ts_start", "ts_end", "duration_ms"):
        if key not in ev:
            raise ValidationError(f"thiếu trường {key}")
    if ev["schema"] != "df.event.v1":
        raise ValidationError("schema không hỗ trợ")
    if ev["type"] not in EVENT_TYPES:
        raise ValidationError(f"type không hợp lệ: {ev['type']}")
    if not isinstance(ev["level"], int) or not 1 <= ev["level"] <= 4:
        raise ValidationError("level phải từ 1 đến 4")
    if not isinstance(ev["duration_ms"], int) or ev["duration_ms"] < 0:
        raise ValidationError("duration_ms không hợp lệ")
    for key in ("event_id", "trip_id", "device_id"):
        if not isinstance(ev[key], str) or not ev[key]:
            raise ValidationError(f"{key} phải là chuỗi không rỗng")
    for key in ("ts_start", "ts_end"):
        try:
            datetime.fromisoformat(str(ev[key]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError(f"{key} không phải ISO 8601") from exc


def anonymise_event(ev: dict[str, Any]) -> dict[str, Any]:
    """Hàng đưa vào kho sự kiện: không có device_id."""
    row = {k: v for k, v in ev.items() if k != "device_id"}
    if isinstance(row.get("context_used"), dict):
        row["context_used"] = json.dumps(row["context_used"], ensure_ascii=False)
    row["eyes_observable"] = bool(row.get("eyes_observable", True))
    return row


class Gateway:
    def __init__(self, ingest_url: str, data_dir: str | Path, ch_url: Optional[str] = None,
                 ch_user: str = "default", ch_password: str = "", ch_table: str = "df.events",
                 http_timeout: float = 5.0):
        self.ingest_url, self.ch_url = ingest_url, ch_url
        self.ch_user, self.ch_password, self.ch_table = ch_user, ch_password, ch_table
        self.timeout = http_timeout
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last: dict[str, dict[str, Any]] = {}      # điểm cuối của mỗi chuyến, để tính hướng
        self._db = sqlite3.connect(self.dir / "restricted.sqlite", check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS trip_owner (trip_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, "
                         "first_seen REAL NOT NULL)")
        self._db.execute("CREATE TABLE IF NOT EXISTS events_seen (event_id TEXT PRIMARY KEY)")
        self._db.commit()
        self.counters = {"gps_in": 0, "gps_forwarded": 0, "gps_rejected": 0, "events_in": 0, "events_stored": 0,
                         "events_duplicate": 0}

    # ----------------------------------------------------------------- GPS
    def handle_gps(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        device_id, trip_id = body.get("device_id"), body.get("trip_id")
        if not isinstance(device_id, str) or not device_id or not isinstance(trip_id, str) or not trip_id:
            raise ValidationError("device_id và trip_id là bắt buộc")
        vehicle_type = body.get("vehicle_type", "car")
        if vehicle_type not in ("car", "bike"):
            raise ValidationError('vehicle_type phải là "car" hoặc "bike"')
        points = body.get("points")
        if not isinstance(points, list) or not points:
            raise ValidationError("points phải là mảng không rỗng")
        if len(points) > MAX_POINTS:
            return 413, {"error": f"tối đa {MAX_POINTS} điểm mỗi lô"}
        self._remember_trip(trip_id, device_id)

        payloads, rejected = [], []
        with self._lock:
            prev = self._last.get(trip_id)
            def _ts_key(q: dict[str, Any]) -> float:
                v = q.get("ts")
                return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else 0.0

            # chỉ số trong "rejected" luôn là vị trí trong mảng thiết bị gửi lên, không phải sau khi sắp xếp
            indexed = []
            for i, q in enumerate(points):
                if isinstance(q, dict):
                    indexed.append((i, q))
                else:
                    rejected.append({"index": i, "error": "điểm phải là object"})
            fwd_index: list[int] = []
            for i, p in sorted(indexed, key=lambda iq: _ts_key(iq[1])):
                try:
                    pl = to_ingest_payload(p, trip_id, vehicle_type, prev)
                except ValidationError as exc:
                    rejected.append({"index": i, "error": str(exc)})
                    continue
                payloads.append(pl)
                fwd_index.append(i)
                prev = {"lat": pl["lat"], "lng": pl["lng"], "ts": pl["timestamp"]}
            if prev:
                self._last[trip_id] = prev
            if len(self._last) > 10000:
                self._last.pop(next(iter(self._last)))
        self.counters["gps_in"] += len(points)
        self.counters["gps_rejected"] += len(rejected)
        if not payloads:
            return 400, {"accepted": 0, "rejected": rejected}
        try:
            resp = self._post_json(self.ingest_url, payloads)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            return 502, {"error": f"không chuyển tiếp được tới Traffic-SM: {exc}"}
        self.counters["gps_forwarded"] += resp.get("accepted", 0)
        ingest_rejected = []
        for r in resp.get("rejected") or []:
            j = r.get("index")
            # Traffic-SM đánh số theo mảng đã chuyển tiếp: đổi về vị trí gốc của thiết bị
            orig = fwd_index[j] if isinstance(j, int) and 0 <= j < len(fwd_index) else j
            ingest_rejected.append({"index": orig, "error": r.get("error"), "source": "traffic-sm"})
        self.counters["gps_rejected"] += len(ingest_rejected)
        rejected.sort(key=lambda r: r["index"] if isinstance(r["index"], int) else -1)
        return 202, {"accepted": resp.get("accepted", 0), "rejected": rejected + ingest_rejected}

    # -------------------------------------------------------------- sự kiện
    def handle_events(self, body: Any) -> tuple[int, dict[str, Any]]:
        events = body if isinstance(body, list) else [body]
        stored = dup = 0
        for ev in events:
            if not isinstance(ev, dict):
                raise ValidationError("sự kiện phải là object")
            validate_event(ev)
            self.counters["events_in"] += 1
            self._remember_trip(ev["trip_id"], ev["device_id"])
            if self._seen(ev["event_id"]):
                dup += 1
                self.counters["events_duplicate"] += 1
                continue
            row = anonymise_event(ev)
            if self.ch_url:
                self._insert_clickhouse(row)           # lỗi thì ném ra => 502, thiết bị gửi lại
            with open(self.dir / "events.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            self._mark_seen(ev["event_id"])
            stored += 1
            self.counters["events_stored"] += 1
        return 202, {"stored": stored, "duplicate": dup}

    # ------------------------------------------------------------- nội bộ
    def _remember_trip(self, trip_id: str, device_id: str) -> None:
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO trip_owner VALUES (?, ?, ?)", (trip_id, device_id, time.time()))
            self._db.commit()

    def _seen(self, event_id: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM events_seen WHERE event_id=?", (event_id,)).fetchone() is not None

    def _mark_seen(self, event_id: str) -> None:
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO events_seen VALUES (?)", (event_id,))
            self._db.commit()

    def owner_of(self, trip_id: str) -> Optional[str]:
        with self._lock:
            r = self._db.execute("SELECT device_id FROM trip_owner WHERE trip_id=?", (trip_id,)).fetchone()
        return r[0] if r else None

    def _post_json(self, url: str, body: Any) -> dict[str, Any]:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            text = resp.read().decode("utf-8") or "{}"
            return json.loads(text)

    def _insert_clickhouse(self, row: dict[str, Any]) -> None:
        query = f"INSERT INTO {self.ch_table} FORMAT JSONEachRow"
        url = f"{self.ch_url.rstrip('/')}/?" + urllib.parse.urlencode(
            {"query": query, "date_time_input_format": "best_effort"})
        req = urllib.request.Request(url, data=(json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"),
                                     method="POST")
        token = base64.b64encode(f"{self.ch_user}:{self.ch_password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req, timeout=self.timeout):
            pass


def make_handler(gw: Gateway):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # yên lặng
            pass

        def _send(self, code: int, obj: dict[str, Any]) -> None:
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"status": "ok", **gw.counters})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BODY:
                    return self._send(413 if length > MAX_BODY else 400, {"error": "kích thước thân yêu cầu không hợp lệ"})
                try:
                    body = json.loads(self.rfile.read(length))
                except json.JSONDecodeError as exc:
                    return self._send(400, {"error": f"JSON lỗi: {exc}"})
                if self.path == "/v1/gps":
                    if not isinstance(body, dict):
                        raise ValidationError("thân phải là object")
                    code, obj = gw.handle_gps(body)
                elif self.path == "/v1/events":
                    code, obj = gw.handle_events(body)
                else:
                    return self._send(404, {"error": "not found"})
                self._send(code, obj)
            except ValidationError as exc:
                self._send(400, {"error": str(exc)})
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                self._send(502, {"error": f"phụ thuộc phía sau lỗi: {exc}"})

    return Handler


def serve(gw: Gateway, host: str = "127.0.0.1", port: int = 8099) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(gw))
    return server


def main(argv: Optional[list[str]] = None) -> None:
    import os
    env = os.environ.get
    ap = argparse.ArgumentParser(description="DriveFocus device-gateway (demo). Mọi tham số có thể đặt bằng biến môi trường (dùng trong Docker).")
    ap.add_argument("--host", default=env("GATEWAY_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(env("GATEWAY_PORT", "8099")))
    ap.add_argument("--ingest-url", default=env("INGEST_URL", "http://localhost:8080/v1/ingest"))
    ap.add_argument("--clickhouse-url", default=env("CLICKHOUSE_URL") or None,
                    help="ví dụ http://localhost:8123 ; bỏ trống thì chỉ ghi JSONL")
    ap.add_argument("--clickhouse-user", default=env("CLICKHOUSE_USER", "traffic"))
    ap.add_argument("--clickhouse-password", default=env("CLICKHOUSE_PASSWORD", "traffic"))
    ap.add_argument("--data-dir", default=env("DATA_DIR", "gateway-data"))
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = ap.parse_args(argv)
    gw = Gateway(args.ingest_url, args.data_dir, args.clickhouse_url, args.clickhouse_user, args.clickhouse_password)
    server = serve(gw, args.host, args.port)
    print(f"device-gateway lắng nghe {args.host}:{args.port}  ingest={args.ingest_url}  clickhouse={args.clickhouse_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
