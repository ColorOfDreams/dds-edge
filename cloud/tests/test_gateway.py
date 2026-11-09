"""Kiểm thử gateway bằng server giả lập cho Traffic-SM ingest và ClickHouse.

Server ingest giả lập tái hiện các quy tắc của `gps.Canonicalize` (traffic-SM, Go) đọc từ mã nguồn.
CHƯA kiểm thử với Traffic-SM chạy thật (cần Docker, Go và dữ liệu OSM).
"""
import csv
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from drivefocus_cloud.gateway import Gateway, ValidationError, serve, to_ingest_payload

_HERE = Path(__file__).resolve()
# traffic-SM nằm cạnh drivefocus/ hoặc cạnh repo dds-edge (khi drivefocus/ nằm trong repo đó)
CSV = next((p / "traffic-SM" / "data" / "gps-fake" / "fake_gps.csv" for p in (_HERE.parents[3], _HERE.parents[4])
            if (p / "traffic-SM" / "data" / "gps-fake" / "fake_gps.csv").exists()),
           _HERE.parents[3] / "traffic-SM" / "data" / "gps-fake" / "fake_gps.csv")
VN = timezone(timedelta(hours=7))


from drivefocus_cloud.mock_ingest import go_canonicalize  # noqa: E402


class Recorder:
    def __init__(self):
        self.posts = []
        self.fail = False


def _server(handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def mock_ingest():
    rec = Recorder()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            rec.posts.append(body)
            rejected = [{"index": i, "error": e} for i, p in enumerate(body) if (e := go_canonicalize(p))]
            data = json.dumps({"accepted": len(body) - len(rejected), "rejected": rejected}).encode()
            self.send_response(202); self.send_header("Content-Length", str(len(data))); self.end_headers()
            self.wfile.write(data)

    srv = _server(H)
    rec.url = f"http://127.0.0.1:{srv.server_address[1]}/v1/ingest"
    yield rec
    srv.shutdown()


@pytest.fixture
def mock_ch():
    rec = Recorder()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if rec.fail:
                self.send_response(500); self.send_header("Content-Length", "0"); self.end_headers(); return
            rec.posts.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body.decode()})
            self.send_response(200); self.send_header("Content-Length", "0"); self.end_headers()

    srv = _server(H)
    rec.url = f"http://127.0.0.1:{srv.server_address[1]}"
    yield rec
    srv.shutdown()


@pytest.fixture
def gw(tmp_path, mock_ingest, mock_ch):
    g = Gateway(mock_ingest.url, tmp_path / "data", ch_url=mock_ch.url, ch_user="traffic", ch_password="traffic")
    srv = serve(g, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    g.url = f"http://127.0.0.1:{srv.server_address[1]}"
    yield g
    srv.shutdown()


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def gps_body(n=10, t0=1793062800.0, device="df-sim-0001", trip="trip-abc", **extra):
    pts = [{"ts": t0 + i, "lat": 10.7759 + i * 1e-4, "lng": 106.7058 + i * 1e-4, "speed_mps": 8.0 + i * 0.1} for i in range(n)]
    return {"device_id": device, "trip_id": trip, "vehicle_type": "car", "points": pts, **extra}


# ------------------------------------------------------------------------ GPS
def test_gps_forwarded_in_format_traffic_sm_accepts(gw, mock_ingest):
    code, resp = post(gw.url + "/v1/gps", gps_body())
    assert code == 202 and resp["accepted"] == 10 and resp["rejected"] == []
    sent = mock_ingest.posts[0]
    assert len(sent) == 10
    assert all(go_canonicalize(p) is None for p in sent)


def test_gps_is_anonymised_driver_id_is_trip_id(gw, mock_ingest):
    post(gw.url + "/v1/gps", gps_body(device="df-SECRET-device", trip="trip-xyz"))
    raw = json.dumps(mock_ingest.posts)
    assert "df-SECRET-device" not in raw and "device_id" not in raw
    assert {p["driver_id"] for p in mock_ingest.posts[0]} == {"trip-xyz"}
    assert gw.owner_of("trip-xyz") == "df-SECRET-device"          # ánh xạ chỉ nằm ở kho hạn chế


def test_bearing_is_computed_from_movement(gw, mock_ingest):
    post(gw.url + "/v1/gps", gps_body())
    sent = mock_ingest.posts[0]
    assert sent[0]["bearing"] == -1                                  # điểm đầu chưa có hướng
    assert 0 <= sent[3]["bearing"] < 90                              # đi về đông bắc


def test_timestamp_truncation_never_produces_60(gw, mock_ingest):
    base = datetime(2026, 11, 9, 14, 5, 59, 960000, tzinfo=VN).timestamp()
    post(gw.url + "/v1/gps", gps_body(n=1, t0=base))
    p = mock_ingest.posts[0][0]
    assert p["t_timestamp"] == "05:59.9" and go_canonicalize(p) is None


def test_invalid_points_are_rejected_but_valid_ones_pass(gw, mock_ingest):
    body = gps_body(n=3)
    body["points"][1]["lat"] = 123.0
    body["points"].append({"ts": 1793062900.0, "lat": "x", "lng": 106.7, "speed_mps": 1.0})
    code, resp = post(gw.url + "/v1/gps", body)
    assert code == 202 and resp["accepted"] == 2 and len(resp["rejected"]) == 2


def test_bad_requests(gw):
    assert post(gw.url + "/v1/gps", {"trip_id": "t"})[0] == 400
    assert post(gw.url + "/v1/gps", {**gps_body(), "vehicle_type": "motorcycle"})[0] == 400   # Traffic-SM chỉ nhận car|bike
    assert post(gw.url + "/v1/gps", {**gps_body(), "points": []})[0] == 400
    assert post(gw.url + "/v1/nope", {})[0] == 404


def test_returns_502_when_traffic_sm_is_down(tmp_path):
    g = Gateway("http://127.0.0.1:9/v1/ingest", tmp_path, http_timeout=0.5)
    code, resp = g.handle_gps(gps_body())
    assert code == 502


@pytest.mark.skipif(not CSV.exists(), reason="không có data/gps-fake/fake_gps.csv của traffic-SM")
def test_conversion_reproduces_traffic_sm_own_formatting():
    """Với cùng một thời điểm, định dạng `time` và `t_timestamp` phải trùng với CSV do chính Traffic-SM sinh."""
    with open(CSV, newline="", encoding="utf-8") as f:
        rows = [r for _, r in zip(range(200), csv.DictReader(f))]
    checked = 0
    for r in rows:
        pl = to_ingest_payload({"ts": float(r["timestamp"]), "lat": float(r["lat"]), "lng": float(r["lng"]),
                                "speed_mps": float(r["speed"])}, "t", r["vehicle_type"], None)
        assert pl["time"] == r["time"], (pl["time"], r["time"])
        assert pl["t_timestamp"] == r["t_timestamp"], (pl["t_timestamp"], r["t_timestamp"])
        assert go_canonicalize(pl) is None
        checked += 1
    assert checked == 200


# ---------------------------------------------------------------------- sự kiện
def event(eid="e1", trip="trip-abc", device="df-sim-0001", **kw):
    e = {"schema": "df.event.v1", "event_id": eid, "trip_id": trip, "device_id": device, "type": "EYES_CLOSED",
         "level": 4, "ts_start": "2026-11-09T14:03:11.200Z", "ts_end": "2026-11-09T14:03:14.700Z",
         "duration_ms": 3500, "distance_m": 48.2, "speed_kmh_avg": 49.6, "speed_kmh_max": 51.0,
         "lat": 10.7769, "lng": 106.7009, "eyes_observable": True, "fw_version": "sim-0.1", "config_version": 2}
    e.update(kw)
    return e


def test_event_stored_without_device_id(gw, mock_ch):
    code, resp = post(gw.url + "/v1/events", event(device="df-SECRET-device"))
    assert code == 202 and resp == {"stored": 1, "duplicate": 0}
    ins = mock_ch.posts[0]
    assert "INSERT" in ins["path"] and "df.events" in ins["path"] and "JSONEachRow" in ins["path"]
    assert ins["auth"].startswith("Basic ")
    assert "device_id" not in ins["body"] and "df-SECRET-device" not in ins["body"]
    line = (gw.dir / "events.jsonl").read_text(encoding="utf-8")
    assert "df-SECRET-device" not in line and '"trip_id": "trip-abc"' in line
    assert gw.owner_of("trip-abc") == "df-SECRET-device"


def test_duplicate_event_is_stored_once(gw, mock_ch):
    post(gw.url + "/v1/events", event())
    code, resp = post(gw.url + "/v1/events", event())
    assert resp == {"stored": 0, "duplicate": 1}
    assert len(mock_ch.posts) == 1


def test_clickhouse_failure_returns_502_and_retry_succeeds(gw, mock_ch):
    mock_ch.fail = True
    assert post(gw.url + "/v1/events", event())[0] == 502
    mock_ch.fail = False
    code, resp = post(gw.url + "/v1/events", event())           # thiết bị gửi lại
    assert code == 202 and resp["stored"] == 1


@pytest.mark.parametrize("patch", [{"level": 0}, {"level": 5}, {"type": "NOPE"}, {"schema": "x"},
                                   {"ts_start": "hôm qua"}, {"duration_ms": -1}])
def test_invalid_events_rejected(gw, patch):
    assert post(gw.url + "/v1/events", event(**patch))[0] == 400


# --------------------------------------------- thiết bị -> gateway bằng Uplink thật
def test_edge_uplink_end_to_end(gw, mock_ingest, mock_ch, tmp_path):
    pytest.importorskip("drivefocus")
    from drivefocus.types import MotionObs
    from drivefocus.uplink import Uplink

    up = Uplink(gw.url, "df-sim-0001", "trip-up", outbox=tmp_path / "outbox.jsonl", batch_s=0.1)
    for i in range(5):
        up.push_gps(MotionObs(t=i, speed_kmh=36.0, lat=10.77 + i * 1e-4, lng=106.70), 1793062800.0 + i)
    up.push_event({k: v for k, v in event(trip="ignored").items() if k not in ("device_id", "trip_id")})
    up.close()
    assert up.failed == 0 and up.sent["gps"] >= 1 and up.sent["events"] == 1
    assert mock_ingest.posts and mock_ingest.posts[0][0]["driver_id"] == "trip-up"
    assert len(mock_ch.posts) == 1


def test_uplink_queues_to_outbox_when_gateway_down(tmp_path):
    pytest.importorskip("drivefocus")
    from drivefocus.uplink import Uplink

    up = Uplink("http://127.0.0.1:9", "dev", "trip", outbox=tmp_path / "outbox.jsonl", timeout_s=0.3)
    up.push_event({"schema": "df.event.v1", "event_id": "x", "type": "PHONE", "level": 2})
    up.close()
    assert up.failed == 1
    assert (tmp_path / "outbox.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_rejected_indices_refer_to_original_positions(gw):
    """Điểm gửi lên không theo thứ tự thời gian: chỉ số bị từ chối vẫn là vị trí gốc."""
    body = gps_body(n=3)
    body["points"] = [body["points"][2], {"ts": 1793062900.0, "lat": 999.0, "lng": 106.7, "speed_mps": 1.0},
                      body["points"][0], "không phải object", body["points"][1]]
    code, resp = post(gw.url + "/v1/gps", body)
    assert code == 202 and resp["accepted"] == 3
    assert sorted(r["index"] for r in resp["rejected"]) == [1, 3]
