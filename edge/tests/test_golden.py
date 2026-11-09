"""Golden trace: cùng chuỗi đặc trưng vào thì cùng chuỗi sự kiện ra.

Bản Python tham chiếu và bản C++ trên K230 đều phải tái tạo đúng tệp expected này.
Cập nhật có chủ đích bằng: UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""
import json
import os
from pathlib import Path

from drivefocus.replay import canonical_events, read_trace, run_trace, write_trace
from drivefocus.types import FrameObs, MotionObs

from helpers import EAR_CLOSED, EAR_OPEN, FPS, quick_cfg

GOLDEN = Path(__file__).parent / "golden"

# (giây, tốc độ km/h, đặc trưng thay đổi)
TIMELINE = [
    (12.0, 50.0, {}),                                              # vào MOVING, hiệu chỉnh
    (0.25, 50.0, {"ear": EAR_CLOSED}),                             # chớp mắt: không cảnh báo
    (5.0, 50.0, {}),
    (3.5, 50.0, {"ear": EAR_CLOSED}),                              # nhắm mắt 3,5 s: mức 4
    (4.0, 50.0, {}),
    (6.5, 50.0, {"yaw": 50.0}),                                    # nhìn lệch 6,5 s: mức 4 (ngân sách cạn)
    (6.0, 50.0, {}),
    (4.0, 50.0, {"hand_ear": 0.3, "hand_mouth": 1.4, "hand_eye": 1.2, "hands_visible": True}),  # điện thoại
    (6.0, 50.0, {}),
    (6.0, 0.0, {}),                                                # dừng xe, qua thời gian giữ MOVING (5 s)
    (4.0, 0.0, {"ear": EAR_CLOSED}),                               # đang dừng đèn đỏ: không cảnh báo
    (3.0, 0.0, {}),
]


def build_frames():
    t = 0.0
    for secs, speed, kw in TIMELINE:
        for _ in range(int(round(secs * FPS))):
            d = dict(face=True, ear=EAR_OPEN, eyes_observable=True, mar=0.05, yaw=0.0, pitch=0.0, roll=0.0)
            d.update(kw)
            yield FrameObs(t=t, **d), MotionObs(t, speed_kmh=speed)
            t += 1 / FPS


def test_golden_scenario(tmp_path):
    trace = tmp_path / "trace.jsonl"
    write_trace(trace, build_frames())
    result = run_trace(read_trace(trace), quick_cfg())          # đi qua định dạng JSONL thật
    got = canonical_events(result["events"])
    expected_file = GOLDEN / "basic_expected.json"
    if os.environ.get("UPDATE_GOLDEN") or not expected_file.exists():
        GOLDEN.mkdir(exist_ok=True)
        expected_file.write_text(json.dumps(got, indent=2), encoding="utf-8")
        (GOLDEN / "basic_trace.jsonl").write_text(trace.read_text(encoding="utf-8"), encoding="utf-8")
    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    assert got == expected


def test_golden_scenario_semantics():
    """Kiểm ý nghĩa, không chỉ so với tệp: đúng loại, đúng mức, không báo khi dừng xe."""
    result = run_trace(build_frames(), quick_cfg())
    ev = {(e["type"], e["level"]) for e in result["events"]}
    assert ("EYES_CLOSED", 4) in ev
    assert ("LOOK_AWAY", 4) in ev
    assert any(t == "PHONE" for t, _ in ev)
    last = result["events"][-1]
    assert last["ts_start"] < "2026-01-01T00:00:53"                  # không có sự kiện trong đoạn dừng xe
    eyes = [e for e in result["events"] if e["type"] == "EYES_CLOSED"]
    assert len(eyes) == 1                                           # chớp mắt 0,25 s không thành sự kiện
